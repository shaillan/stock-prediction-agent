"""
预测结果面板组件 - 展示 AI 预测的核心结论
"""
import streamlit as st
from typing import Dict, Optional


def render_prediction_panel(prediction: Optional[Dict]) -> None:
    """渲染预测结果卡片

    Args:
        prediction: 预测结果 Dict {trend, confidence, period, key_factors, risk_warnings, price_targets, reasoning_summary}
    """
    if not prediction:
        st.info("等待分析完成...")
        return

    st.markdown("## 🎯 AI 综合预测")

    trend = prediction.get("trend", "震荡")
    confidence = prediction.get("confidence", 0.5)
    period = prediction.get("period", "1-5个交易日")

    # ===== 趋势判断 =====
    trend_emoji = {"看涨": "📈", "看跌": "📉", "震荡": "📊"}
    trend_color = {"看涨": "#e53e3e", "看跌": "#38a169", "震荡": "#d69e2e"}
    bg_color = {"看涨": "#fff5f5", "看跌": "#f0fff4", "震荡": "#fffff0"}
    border_color = {"看涨": "#fc8181", "看跌": "#68d391", "震荡": "#f6e05e"}

    emoji = trend_emoji.get(trend, "📊")
    t_color = trend_color.get(trend, "#d69e2e")
    bg = bg_color.get(trend, "#fffff0")
    border = border_color.get(trend, "#f6e05e")

    # 三列指标卡片
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div class="metric-card" style="background:{bg}; border:1px solid {border}">
            <div class="metric-label">短期趋势</div>
            <div class="metric-value" style="color:{t_color}">{emoji} {trend}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        conf_pct = confidence * 100
        conf_color = "#e53e3e" if conf_pct >= 70 else ("#d69e2e" if conf_pct >= 40 else "#718096")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">置信度</div>
            <div class="metric-value" style="color:{conf_color}">{conf_pct:.0f}%</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">预测周期</div>
            <div class="metric-value" style="font-size:1.2rem; color:#4a5568">{period}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 关键因素 + 风险提示
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### 🔑 关键因素")
        for factor in prediction.get("key_factors", []):
            st.markdown(f"- ✅ {factor}")
        if not prediction.get("key_factors"):
            st.caption("暂无")

    with col_right:
        st.markdown("### ⚠️ 风险提示")
        for warning in prediction.get("risk_warnings", []):
            st.markdown(f"- ⚠️ {warning}")
        if not prediction.get("risk_warnings"):
            st.caption("暂无")

    # 价格目标
    price_targets = prediction.get("price_targets", {})
    if price_targets:
        st.markdown("---")
        st.markdown("### 💰 目标价位")

        support = price_targets.get("support", 0)
        current = price_targets.get("current", 0)
        resistance = price_targets.get("resistance", 0)
        target = price_targets.get("target_high", 0) or price_targets.get("target", 0)

        if support and resistance and current:
            # 计算比例用于可视化
            total_range = resistance - support
            if total_range > 0:
                current_pct = (current - support) / total_range * 100

                st.markdown(f"""
                <div style="position:relative; height:40px; background:linear-gradient(to right, #38a169, #e2e8f0, #e53e3e);
                            border-radius:20px; margin:1rem 0;">
                    <div style="position:absolute; left:{current_pct}%; top:-5px;
                                transform:translateX(-50%); font-size:1.2rem;">▼</div>
                </div>
                """, unsafe_allow_html=True)

                cols = st.columns(4)
                cols[0].metric("🛡️ 支撑位", f"¥{support:.2f}")
                cols[1].metric("📍 当前价", f"¥{current:.2f}")
                cols[2].metric("🧱 压力位", f"¥{resistance:.2f}")
                if target:
                    cols[3].metric("🎯 目标价", f"¥{target:.2f}")

    # 综合分析摘要
    summary = prediction.get("reasoning_summary", "")
    if summary:
        st.markdown("---")
        st.markdown("### 📝 分析摘要")
        st.info(summary)
