"""
预测结果面板组件 - 展示 AI 预测的核心结论

配色一律走 ui/styles.py 的 token，不在组件里写死色值：
深色页面上任何浅色内联背景都会变成刺眼的白块。
"""
import streamlit as st
from typing import Dict, Optional

# 趋势 → (emoji, 样式类)。涨红跌绿沿用 A 股约定，且都配了 emoji 做第二编码
_TREND = {
    "看涨": ("📈", "up"),
    "看跌": ("📉", "down"),
    "震荡": ("📊", "warn"),
}


def _card(label: str, value: str, cls: str = "", size: str = "") -> str:
    style = f' style="font-size:{size}"' if size else ""
    return (
        f'<div class="metric-card">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value {cls}"{style}>{value}</div></div>'
    )
def render_prediction_panel(prediction: Optional[Dict]) -> None:
    """渲染预测结果卡片

    Args:
        prediction: 预测结果 Dict {trend, confidence, period, key_factors,
                    risk_warnings, price_targets, reasoning_summary}
    """
    if not prediction:
        st.info("等待分析完成...")
        return

    st.markdown("## 🎯 AI 综合预测")

    trend = prediction.get("trend", "震荡")
    confidence = prediction.get("confidence", 0.5)
    period = prediction.get("period", "1-5个交易日")

    emoji, trend_cls = _TREND.get(trend, ("📊", "warn"))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(_card("短期趋势", f"{emoji} {trend}", trend_cls),
                    unsafe_allow_html=True)
    with col2:
        conf_pct = confidence * 100
        # 置信度是"模型有多确定"，不是涨跌方向，所以不用红绿
        conf_cls = "warn" if conf_pct >= 70 else ""
        st.markdown(_card("置信度", f"{conf_pct:.0f}%", conf_cls),
                    unsafe_allow_html=True)
    with col3:
        st.markdown(_card("预测周期", period, "", "1.05rem"),
                    unsafe_allow_html=True)

    st.markdown("---")

    # 关键因素 + 风险提示
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### 关键因素")
        for factor in prediction.get("key_factors", []):
            # 这里不能加 ✅：关键因素里一半是偏空的（"财务数据缺失"、"个股逆势
            # 下跌"），给每条都挂个绿勾等于把利空标成了利好
            st.markdown(f"- {factor}")
        if not prediction.get("key_factors"):
            st.caption("暂无")

    with col_right:
        st.markdown("### 风险提示")
        for warning in prediction.get("risk_warnings", []):
            st.markdown(f"- ⚠️ {warning}")
        if not prediction.get("risk_warnings"):
            st.caption("暂无")

    # 价格目标：支撑位 → 现价 → 压力位，一张横向区间条
    price_targets = prediction.get("price_targets") or {}
    support = price_targets.get("support") or 0
    current = price_targets.get("current") or 0
    resistance = price_targets.get("resistance") or 0
    target = price_targets.get("target_high") or price_targets.get("target") or 0

    if support and resistance and current and resistance > support:
        st.markdown("---")
        st.markdown("### 目标价位")

        pct = min(max((current - support) / (resistance - support), 0.0), 1.0) * 100
        st.markdown(
            f'<div class="range-bar">'
            f'<span class="range-mark" style="left:{pct:.1f}%">现价 ¥{current:,.2f}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        cols = st.columns(4)
        cols[0].metric("🛡️ 支撑位", f"¥{support:,.2f}")
        cols[1].metric("📍 当前价", f"¥{current:,.2f}")
        cols[2].metric("🧱 压力位", f"¥{resistance:,.2f}")
        if target:
            cols[3].metric("🎯 目标价", f"¥{target:,.2f}")

    # 综合分析摘要
    summary = prediction.get("reasoning_summary", "")
    if summary:
        st.markdown("---")
        st.markdown("### 分析摘要")
        st.info(summary)
