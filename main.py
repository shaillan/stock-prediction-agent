"""
📈 股票智能预测 Agent - Streamlit 主入口
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
from ui.components.sidebar import render_sidebar
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
def main():
    # 页面标题
    st.markdown(
        '<div class="main-header">📈 股票智能预测 Agent</div>',
        unsafe_allow_html=True,
    )
    st.caption("基于 LangGraph + LLM 多源分析 | 技术面 + 消息面 + 基本面 | 仅供参考")

    # 渲染侧边栏并获取配置
    config = render_sidebar()

    # ===== 主内容区 =====
    # 如果没有分析结果，显示欢迎信息
    if not st.session_state.analysis_done:
        st.info(
            """
        ### 👋 欢迎使用股票智能预测 Agent！

        **使用步骤：**
        1. 在左侧选择或输入 A 股股票代码
        2. 选择分析周期
        3. 配置 LLM 模型和 API Key
        4. 点击 **"🚀 开始分析"** 按钮

        **分析流程：**
        📡 数据采集 → 📊 技术分析 → 📰 新闻情绪 → 🧠 综合预测 → 📝 报告生成

        **支持的分析维度：**
        - 🔍 技术指标解读（MA / MACD / RSI / KDJ / 布林带）
        - 📰 新闻情绪分析（利好 / 利空 / 强度评估）
        - 💰 基本面概览（PE / PB / ROE 等关键指标）
        - 🎯 短期趋势预测（1-5天方向 + 置信度 + 目标价位）
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

        # 创建进度显示
        progress_placeholder = st.empty()
        status_placeholder = st.empty()

        with progress_placeholder.container():
            render_progress(status="idle")

        # 使用 Status 上下文管理器
        with st.status("🤖 AI Agent 分析中...", expanded=True) as status_box:

            # ----- 阶段1: 数据采集 -----
            st.write("📡 正在获取行情数据...")
            st.session_state.progress_status = "collecting"
            render_progress(status="collecting")

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

            # ----- 阶段2-5: Agent 流水线 -----
            st.write("---")

            # 运行 Agent
            st.session_state.progress_status = "analyzing"
            render_progress(status="analyzing")

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
                )

                st.session_state.agent_state = agent_state
                st.session_state.analysis_done = True
                st.session_state.progress_status = "done"
                st.session_state.progress_errors = agent_state.get("errors", [])

                status_box.update(label="✅ 分析完成!", state="complete")

            except Exception as e:
                logger.exception("Agent 运行异常")
                st.error(f"❌ Agent 运行失败: {e}")
                st.session_state.analysis_running = False
                st.session_state.progress_status = "error"
                status_box.update(label="❌ 分析失败", state="error")
                return

        st.session_state.analysis_running = False

        # 最终进度
        render_progress(
            status="done",
            errors=st.session_state.progress_errors,
        )

    # ===== 显示分析结果 =====
    if st.session_state.analysis_done and st.session_state.agent_state:
        agent_state = st.session_state.agent_state

        st.markdown("---")

        # K线图
        st.markdown("## 📊 K线图与技术指标")
        tech_indicators = agent_state.get("technical_indicators")

        kline_data = st.session_state.kline_df
        if kline_data is not None and not kline_data.empty:
            fig = render_kline_chart(
                kline_data=kline_data,
                indicators=tech_indicators,
                stock_name=agent_state.get("stock_name", ""),
                stock_code=config["stock_code"],
            )
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
        )


# ===== 底部信息 =====
def render_footer():
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align:center; color:#a0aec0; font-size:0.8rem; padding:1rem;">
            <p>📈 股票智能预测 Agent | Powered by LangGraph + LLM</p>
            <p>⚠️ 本工具仅供学习研究使用，AI 预测不构成投资建议。股市有风险，投资需谨慎。</p>
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
