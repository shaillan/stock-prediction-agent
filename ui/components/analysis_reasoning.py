"""
分析详情展开面板组件 - 展示技术分析、新闻情绪、公告检索、基本面等详细内容
"""
import streamlit as st
from typing import Dict, Optional


def render_analysis_details(
    technical_result: Optional[str] = None,
    sentiment_result: Optional[str] = None,
    financial_data: Optional[Dict] = None,
    final_report: Optional[str] = None,
    realtime_quote: Optional[Dict] = None,
    announcement_context: Optional[str] = None,
    rag_enabled: bool = True,
    rag_error: Optional[str] = None,
) -> None:
    """渲染分析详情展开面板

    Args:
        technical_result: 技术分析文本 (Markdown)
        sentiment_result: 新闻情绪分析文本 (Markdown)
        financial_data: 财务指标 Dict
        final_report: 最终完整报告 (Markdown)
        realtime_quote: 实时行情 Dict
        announcement_context: RAG 检索到的"公告动态"原文，空串/None = 没命中
        rag_enabled: 侧边栏的公告检索开关，用来区分"没开"和"没命中"
        rag_error: 公告检索的报错（若有），用来暴露流水线的静默降级
    """
    st.markdown("## 📋 详细分析")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 技术分析",
        "📰 新闻情绪",
        "📢 公告",
        "💰 基本面",
        "📝 完整报告",
    ])

    # ===== Tab 1: 技术分析 =====
    with tab1:
        if technical_result:
            st.markdown(technical_result)
        else:
            st.info("暂无技术分析数据")

    # ===== Tab 2: 新闻情绪 =====
    with tab2:
        if sentiment_result:
            st.markdown(sentiment_result)
        else:
            st.info("暂无新闻情绪分析数据")

    # ===== Tab 3: 公告检索（RAG）=====
    with tab3:
        _render_announcements(announcement_context, rag_enabled, rag_error)

    # ===== Tab 4: 基本面 =====
    with tab4:
        if financial_data:
            # 表格展示
            col1, col2 = st.columns(2)

            metrics = [
                ("市盈率 (PE)", financial_data.get("pe")),
                ("市净率 (PB)", financial_data.get("pb")),
                ("市销率 (PS)", financial_data.get("ps")),
                ("ROE", financial_data.get("roe")),
                ("ROA", financial_data.get("roa")),
                ("毛利率", financial_data.get("gross_margin")),
                ("净利率", financial_data.get("net_margin")),
                ("营收增长率", financial_data.get("revenue_growth")),
                ("利润增长率", financial_data.get("profit_growth")),
                ("资产负债率", financial_data.get("debt_ratio")),
                ("总市值(亿)", financial_data.get("total_market_value")),
                ("流通市值(亿)", financial_data.get("circulating_market_value")),
            ]

            for i, (label, value) in enumerate(metrics):
                col = col1 if i % 2 == 0 else col2
                with col:
                    if value is not None:
                        formatted = f"{float(value):.2f}" if isinstance(value, (int, float)) else str(value)
                        st.metric(label, formatted)
                    else:
                        st.metric(label, "N/A")
        else:
            st.info("暂无基本面数据")

        # 实时行情
        if realtime_quote:
            st.markdown("---")
            st.markdown("### 📡 实时行情")
            q = realtime_quote
            cols = st.columns(4)
            cols[0].metric("最新价", f"¥{q.get('price', 'N/A')}")
            change_pct = q.get('change_pct', 0)
            # delta_color="inverse" 让涨显示红色、跌显示绿色（中式约定，Streamlit 默认是反的）
            cols[1].metric("涨跌幅", f"{change_pct:+.2f}%",
                          delta=f"{change_pct:+.2f}%" if change_pct else None,
                          delta_color="inverse")
            cols[2].metric("成交量", f"{q.get('volume', 0):,.0f}")
            cols[3].metric("换手率", f"{q.get('turnover', 'N/A')}%")

    # ===== Tab 5: 完整报告 =====
    with tab5:
        if final_report:
            st.markdown(final_report)
        else:
            st.info("暂无完整报告")

    # 免责声明
    st.markdown("""
    <div class="disclaimer">
        <strong>⚠️ 免责声明</strong><br>
        本报告由 AI 智能体自动生成，所有分析和预测均基于历史数据和公开信息的统计分析，<strong>仅供参考，不构成任何投资建议</strong>。
        股市有风险，投资需谨慎。投资者应当独立做出投资决策，并自行承担投资风险。
        AI 预测具有不确定性，过往表现不代表未来收益。
    </div>
    """, unsafe_allow_html=True)


def _render_announcements(
    announcement_context: Optional[str],
    rag_enabled: bool,
    rag_error: Optional[str],
) -> None:
    """渲染"公告"tab。

    显示的就是 rag.service.build_stock_context 的返回值**原文**——和塞进预测
    prompt 的那段字符完全一致（agent/prompts/system_prompts.py），便于核对
    检索是否真的生效。

    三种"空"要分开提示：检索关闭 / 检索报错 / 确实没命中。
    流水线对公告检索是静默降级的（失败不中断分析，只是少一路信号），
    不在这里区分的话，RAG 挂掉时界面上一点痕迹都没有。
    """
    if announcement_context:
        n = sum(1 for ln in announcement_context.splitlines() if ln.startswith("- **《"))
        st.caption(f"命中 {n} 条公告片段 · 以下即流水线实际喂给预测模型的原文")
        st.markdown(announcement_context)
        st.markdown("---")
        st.caption(
            '想看每条命中的距离 / 关键词得分 / gap：'
            '`python -m rag.cli diagnose "问题" --code 600519`（详见 rag/TUTORIAL.md）'
        )
        return

    if not rag_enabled:
        st.info("公告全文检索（RAG）已在左侧边栏关闭，本次分析未使用公告信号。")
        return

    if rag_error:
        st.error("公告检索失败，本次预测未包含公告信号。")
        st.caption(f"错误详情：{rag_error}")
        st.caption("流水线对公告检索是静默降级的——失败不会中断分析，只是少一路信号。")
        return

    st.info(
        "本次没有命中公告片段。可能是这只股票在该时间窗内没有公告，"
        "也可能是公告没命中固定的 6 个研究问题（减持/回购/业绩预告/合同/分红/风险）。"
    )
