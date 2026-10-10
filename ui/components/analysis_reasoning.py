"""
分析详情展开面板组件 - 展示技术分析、新闻情绪、基本面等详细内容
"""
import streamlit as st
from typing import Dict, Optional


def render_analysis_details(
    technical_result: Optional[str] = None,
    sentiment_result: Optional[str] = None,
    financial_data: Optional[Dict] = None,
    final_report: Optional[str] = None,
    realtime_quote: Optional[Dict] = None,
) -> None:
    """渲染分析详情展开面板

    Args:
        technical_result: 技术分析文本 (Markdown)
        sentiment_result: 新闻情绪分析文本 (Markdown)
        financial_data: 财务指标 Dict
        final_report: 最终完整报告 (Markdown)
        realtime_quote: 实时行情 Dict
    """
    st.markdown("## 📋 详细分析")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 技术分析",
        "📰 新闻情绪",
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

    # ===== Tab 3: 基本面 =====
    with tab3:
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

    # ===== Tab 4: 完整报告 =====
    with tab4:
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
