"""
📈 股票智能预测工作流 - Streamlit 主入口
基于 LangGraph + LLM 多源分析 A 股走势
"""
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
from loguru import logger

from config import settings
from ui.styles import apply_custom_css
from ui.components.sidebar import (
    render_llm_config, render_mode_selector, render_sidebar,
)
from ui.components.kline_chart import render_kline_chart
from ui.components.prediction_panel import render_prediction_panel
from ui.components.analysis_reasoning import render_analysis_details
from ui.components.progress_display import render_progress, AgentProgressContext
from agent.graph import run_agent


# ===== 页面配置 =====
st.set_page_config(
    page_title=settings.page_title,
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 应用自定义样式
apply_custom_css()


# ===== 初始化 Session State =====
def init_session_state():
    """初始化 Streamlit session state"""
    defaults = {
        "agent_state": None,
        "analysis_done": False,
        "analysis_running": False,
        "kline_df": None,
        "technical_indicators": None,
        "progress_status": "idle",
        "progress_errors": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# ===== 主页面 =====
def _render_topbar(config: dict) -> None:
    """页面标题区（视觉稿 .term-topbar）"""
    name = config.get("stock_name") or ""
    code = config.get("stock_code") or ""
    st.markdown(
        f"""
        <div class="term-topbar">
          <div>
            <h1>个股深度分析</h1>
            <p class="sub">{name} {code} · {config.get("start_date", "")}
             至 {config.get("end_date", "")}</p>
          </div>
          <span class="term-badge">技术面 · 消息面 · 基本面</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpi_row(indicators: dict) -> None:
    """关键指标四联卡：只描述当前状态，不暗示方向"""
    if not indicators:
        return
    close = indicators.get("close")
    ma20 = indicators.get("ma20")
    rsi = indicators.get("rsi14")
    # 快照里的 key 是 macd_dif / macd_dea / macd_hist，没有单独的 "macd"
    macd = indicators.get("macd_dif")
    vol_ratio = indicators.get("volume_ratio")

    def _num(v, digits=2, suffix=""):
        # 负号统一用 U+2212，和行情条的 .delta 一致
        return (f"{v:,.{digits}f}{suffix}".replace("-", "−")
                if isinstance(v, (int, float)) else "—")

    gap = ""
    gap_cls = ""
    if isinstance(close, (int, float)) and isinstance(ma20, (int, float)) and ma20:
        pct = (close / ma20 - 1) * 100
        gap = f"{pct:+.2f}%".replace("-", "−")
        gap_cls = "up" if pct > 0 else "down"

    has_macd = isinstance(macd, (int, float))
    macd_above = has_macd and macd > 0
    macd_note = f"{'▲' if macd_above else '▼'} {'零轴上方' if macd_above else '零轴下方'}" if has_macd else ""
    macd_cls = ("up" if macd_above else "down") if has_macd else ""

    rsi_note = "中性区间（30–70）"
    if isinstance(rsi, (int, float)):
        if rsi > 70:
            rsi_note = "偏高（>70 超买）"
        elif rsi < 30:
            rsi_note = "偏低（<30 超卖）"

    tiles = [
        ("RSI（14 日）", _num(rsi), "", rsi_note, ""),
        ("MACD", _num(macd, 3), "", macd_note, macd_cls),
        ("距 20 日均线", gap or "—", "", f"MA20 = {_num(ma20)}", gap_cls),
        ("量比", _num(vol_ratio), "", "当日成交活跃度", ""),
    ]
    # 涨跌色只上在"有方向的数字"上（现值/涨跌幅），注释行保持中性灰——
    # 给 "MA20 = 1,294.63" 这种参照值染色，会被读成"MA20 在涨"
    html = "".join(
        f'<div class="kpi"><div class="kpi-label">{lab}</div>'
        f'<div class="kpi-value {cls}">{val}{suf}</div>'
        f'<div class="kpi-note">{note}</div></div>'
        for lab, val, suf, note, cls in tiles
    )
    st.markdown(f'<div class="kpi-row">{html}</div>', unsafe_allow_html=True)
    st.write("")


def main():
    # ===== 功能模式 =====
    mode = render_mode_selector()
    if mode == "briefing":
        llm_cfg = render_llm_config()
        from ui.components.briefing import render_briefing_page
        render_briefing_page(llm_cfg)
        return
    if mode == "agent":
        llm_cfg = render_llm_config()
        from ui.components.agent_chat import render_agent_page
        render_agent_page(llm_cfg)
        return

    # 渲染侧边栏并获取配置
    config = render_sidebar()
    _render_topbar(config)

    # ===== 主内容区 =====
    # 如果没有分析结果，显示欢迎信息
    if not st.session_state.analysis_done:
        with st.container(border=True):
            st.markdown('<p class="section-label">开始</p>', unsafe_allow_html=True)
            st.markdown(
                """
在左侧选股、配好模型后，点 **「🚀 开始分析」**。程序会依次完成：

1. **数据采集** — 行情、财务、新闻、公告
2. **三路并行** — 技术指标解读 / 新闻情绪 / 公告全文检索（RAG）
3. **综合预测** — 给方向与置信度，并**明确标出缺了哪一路信号**
4. **报告生成** — 汇总成可读的报告

> 整个流程约 30 秒–2 分钟。AI 预测不构成投资建议。
                """
            )

    # ===== 点击分析按钮 =====
    if config["run_clicked"]:
        # 验证输入
        if not config["stock_code"]:
            st.error("❌ 请输入股票代码")
            return

        if not config["llm_api_key"]:
            st.error("❌ 请在侧边栏配置 LLM API Key")
            return

        st.session_state.analysis_running = True
        st.session_state.analysis_done = False
        st.session_state.progress_status = "idle"

        # 步骤条只占一个占位符：每个阶段原地替换。
        # 直接调 render_progress 的话，每次都会在下面**追加**一组新的步骤点，
        # 分析跑完页面上会摞起四五排一模一样的进度条。
        progress_placeholder = st.empty()

        def _progress(status: str) -> None:
            st.session_state.progress_status = status
            with progress_placeholder.container():
                render_progress(status=status)

        _progress("idle")

        # 使用 Status 上下文管理器
        with st.status("🤖 分析中...", expanded=True) as status_box:

            # ----- 阶段1: 数据采集 -----
            st.write("📡 正在获取行情数据...")
            _progress("collecting")

            try:
                from data.akhare_client import AKShareClient
                from data.cache_manager import CacheManager
                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
                from tenacity import RetryError

                cache = CacheManager()
                client = AKShareClient(cache_manager=cache)

                # 获取K线（带超时保护）
                executor = ThreadPoolExecutor(max_workers=1)
                try:
                    kline_future = executor.submit(
                        client.get_stock_kline,
                        config["stock_code"], "daily",
                        config["start_date"], config["end_date"]
                    )
                    kline_df = kline_future.result(timeout=25)
                except FutureTimeout:
                    st.error("❌ 获取K线数据超时（25秒），AKShare 数据源可能暂时不可用，请稍后重试")
                    st.info("💡 提示：可尝试切换网络环境或在非交易时段重试")
                    st.session_state.analysis_running = False
                    return
                except RetryError as e:
                    st.error(f"❌ 无法连接数据源（重试均失败）\n\n> 错误详情：{e.last_attempt.exception() if hasattr(e, 'last_attempt') else e}")
                    st.session_state.analysis_running = False
                    return
                finally:
                    executor.shutdown(wait=False)  # 不等待可能卡死的线程

                st.session_state.kline_df = kline_df

                if kline_df is not None and not kline_df.empty:
                    st.write(f"✅ K线数据获取成功（{len(kline_df)} 条）")
                else:
                    st.error(f"❌ 未获取到 {config['stock_code']} 的K线数据")
                    st.session_state.analysis_running = False
                    return

                # 从K线直接提取实时行情（无需额外调接口）
                quote = client.get_realtime_quote(config["stock_code"], kline_df=kline_df)
                if quote:
                    config["stock_name"] = quote.get("name", config["stock_name"])
                    st.write(f"✅ 最新价: {quote.get('price')} (涨跌: {quote.get('change_pct', 0):+.2f}%)")

            except Exception as e:
                st.error(f"❌ 数据获取失败: {e}")
                logger.exception("数据获取异常")
                st.session_state.analysis_running = False
                return

            # ----- 阶段2-5: LLM 工作流 -----
            st.write("---")

            # 运行工作流
            _progress("analyzing")

            try:
                from agent.prefetch import set_pre_fetched, clear as clear_prefetch
                clear_prefetch()
                set_pre_fetched(
                    kline_df=kline_df,
                    quote=quote,
                    stock_name=config.get("stock_name", ""),
                )
                agent_state = run_agent(
                    stock_code=config["stock_code"],
                    start_date=config["start_date"],
                    end_date=config["end_date"],
                    llm_model=config["llm_model"],
                    llm_api_key=config["llm_api_key"],
                    llm_base_url=config["llm_base_url"],
                    stock_name=config.get("stock_name", ""),
                    rag_enabled=config.get("rag_enabled", True),
                )

                st.session_state.agent_state = agent_state
                st.session_state.analysis_done = True
                st.session_state.progress_status = "done"
                st.session_state.progress_errors = agent_state.get("errors", [])

                status_box.update(label="✅ 分析完成!", state="complete")

            except Exception as e:
                logger.exception("工作流运行异常")
                st.error(f"❌ 工作流运行失败: {e}")
                st.session_state.analysis_running = False
                st.session_state.progress_status = "error"
                status_box.update(label="❌ 分析失败", state="error")
                return

        st.session_state.analysis_running = False

        # 立刻重跑一遍：这一趟的"开始"引导卡、状态框、进度条都是分析过程中画的，
        # 不清掉的话它们会一直挂在结果页上方，直到用户碰下一个控件才消失。
        st.rerun()

    # ===== 显示分析结果 =====
    if st.session_state.analysis_done and st.session_state.agent_state:
        agent_state = st.session_state.agent_state

        st.write("")
        _render_kpi_row(agent_state.get("technical_indicators"))

        # K线图
        st.markdown("## K 线与技术指标")

        kline_data = st.session_state.kline_df
        if kline_data is not None and not kline_data.empty:
            # 图表要的是全年指标序列；state 里只存了最新快照（标量，够 LLM 用、不够画图，
            # 直接传会让每条指标线只剩 1 个点）。对图上这份K线现算一遍：与横轴天然对齐。
            try:
                from data.technical_indicators import TechnicalIndicatorCalculator
                indicator_series = TechnicalIndicatorCalculator(kline_data).calc_all()
            except Exception as e:
                st.warning(f"技术指标序列计算失败，图中只显示K线：{e}")
                indicator_series = None
            fig = render_kline_chart(
                kline_data=kline_data,
                indicators=indicator_series,
                stock_name=agent_state.get("stock_name", ""),
                stock_code=config["stock_code"],
            )
            # 放进卡片里，图的透明底就落在 --surface-1 上（配色是按这个底色校验的）
            with st.container(border=True):
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("暂无K线数据可显示")

        st.markdown("---")

        # 预测面板
        prediction = agent_state.get("prediction")
        render_prediction_panel(prediction)

        st.markdown("---")

        # 分析详情（标签页）
        render_analysis_details(
            technical_result=agent_state.get("technical_analysis_result"),
            sentiment_result=agent_state.get("news_sentiment_result"),
            financial_data=agent_state.get("financial_data"),
            final_report=agent_state.get("final_report"),
            realtime_quote=agent_state.get("realtime_quote"),
            announcement_context=agent_state.get("announcement_context"),
            rag_enabled=config.get("rag_enabled", True),
            # 公告检索失败时节点会静默降级（只塞一条 error 不抛异常），
            # 这里把那条 error 挑出来，让 tab 里能看见，而不是悄无声息地少一路信号
            rag_error=next(
                (e for e in (agent_state.get("errors") or []) if "公告检索" in e),
                None,
            ),
        )


# ===== 底部信息 =====
def render_footer():
    st.markdown(
        """
        <div style="text-align:center; color:#8a94a6; font-size:0.75rem;
                    padding:1rem; border-top:1px solid #232a36;">
            <p>股票智能预测工作流 · LangGraph + LLM</p>
            <p>本工具仅供学习研究使用，AI 预测不构成投资建议。股市有风险，投资需谨慎。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    try:
        main()
        render_footer()
    except Exception as e:
        logger.exception("应用异常")
        st.error(f"应用运行出错: {e}")
        st.info("请检查配置后刷新页面重试。")
