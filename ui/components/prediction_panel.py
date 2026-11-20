"""
预测结果面板组件 - 展示 AI 预测的核心结论

配色一律走 ui/styles.py 的 token，不在组件里写死色值：
深色页面上任何浅色内联背景都会变成刺眼的白块。
"""
import streamlit as st
from typing import Dict, Optional

# 趋势 → (emoji, 样式类, 中文标签)
_TREND = {
    "看涨": ("📈", "up", "bullish"),
    "看跌": ("📉", "down", "bearish"),
    "震荡": ("📊", "warn", "neutral"),
}


def _esc(text) -> str:
    return (str(text)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_prediction_panel(prediction: Optional[Dict]) -> None:
    """渲染预测结果卡片

    Args:
        prediction: 预测结果 Dict {trend, confidence, period, key_factors,
                    risk_warnings, price_targets, reasoning_summary}
    """
    if not prediction:
        st.info("等待分析完成...")
        return

    st.markdown(
        '<div class="section-label"><span class="n">01</span>AI 综合预测</div>',
        unsafe_allow_html=True,
    )

    trend = prediction.get("trend", "震荡")
    confidence = prediction.get("confidence", 0.5) or 0
    period = prediction.get("period", "1-5个交易日")

    emoji, trend_cls, hero_cls = _TREND.get(trend, ("📊", "warn", "neutral"))
    conf_pct = max(0.0, min(1.0, float(confidence))) * 100

    # ===== 主卡：趋势 + 置信度环 =====
    st.markdown(
        f"""
        <div class="pred-hero {hero_cls}">
          <div class="pred-left">
            <div class="pred-kicker">短期趋势判断</div>
            <div class="pred-trend {trend_cls}">
              <span class="ico">{emoji}</span><span>{_esc(trend)}</span>
            </div>
            <div class="pred-meta">
              <span class="chip accent">预测周期 · {_esc(period)}</span>
              <span class="chip">多源信号综合</span>
              <span class="chip">技术面 · 消息面 · 基本面</span>
            </div>
          </div>
          <div class="conf-ring" style="--p:{conf_pct:.0f}">
            <div class="conf-inner">
              <b>{conf_pct:.0f}%</b>
              <span>置信度</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    # ===== 关键因素 + 风险提示 =====
    col_left, col_right = st.columns(2, gap="medium")

    with col_left:
        with st.container(border=True):
            st.markdown(
                '<div class="card-head"><span class="card-title">关键因素</span>'
                '<span class="card-hint">支撑本次判断</span></div>',
                unsafe_allow_html=True,
            )
            factors = prediction.get("key_factors") or []
            if factors:
                # 这里不能加 ✅：关键因素里一半是偏空的（"财务数据缺失"、"个股逆势
                # 下跌"），给每条都挂个绿勾等于把利空标成了利好
                items = "".join(
                    f'<li><span class="b"></span><span>{_esc(f)}</span></li>'
                    for f in factors
                )
                st.markdown(f'<ul class="factor-list">{items}</ul>',
                            unsafe_allow_html=True)
            else:
                st.caption("暂无")

    with col_right:
        with st.container(border=True):
            st.markdown(
                '<div class="card-head"><span class="card-title">风险提示</span>'
                '<span class="card-hint warn">需留意</span></div>',
                unsafe_allow_html=True,
            )
            warnings = prediction.get("risk_warnings") or []
            if warnings:
                items = "".join(
                    f'<li><span class="b"></span><span>{_esc(w)}</span></li>'
                    for w in warnings
                )
                st.markdown(f'<ul class="factor-list risk">{items}</ul>',
                            unsafe_allow_html=True)
            else:
                st.caption("暂无")

    # ===== 目标价位：支撑位 → 现价 → 压力位，一张横向区间条 =====
    price_targets = prediction.get("price_targets") or {}
    support = price_targets.get("support") or 0
    current = price_targets.get("current") or 0
    resistance = price_targets.get("resistance") or 0
    target = price_targets.get("target_high") or price_targets.get("target") or 0

    if support and resistance and current and resistance > support:
        st.write("")
        with st.container(border=True):
            st.markdown(
                '<div class="card-head"><span class="card-title">目标价位</span>'
                '<span class="card-hint">支撑 / 现价 / 压力</span></div>',
                unsafe_allow_html=True,
            )
            pct = min(max((current - support) / (resistance - support), 0.0), 1.0) * 100
            st.markdown(
                f'<div class="range-wrap">'
                f'<div class="range-bar">'
                f'<span class="range-mark" style="left:{pct:.1f}%">现价 ¥{current:,.2f}</span>'
                f'</div>'
                f'<div class="range-ends">'
                f'<span>支撑 ¥{support:,.2f}</span>'
                f'<span>压力 ¥{resistance:,.2f}</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            cols = st.columns(4 if target else 3, gap="small")
            cols[0].metric("🛡️ 支撑位", f"¥{support:,.2f}")
            cols[1].metric("📍 当前价", f"¥{current:,.2f}")
            cols[2].metric("🧱 压力位", f"¥{resistance:,.2f}")
            if target:
                cols[3].metric("🎯 目标价", f"¥{target:,.2f}")

    # ===== 综合分析摘要 =====
    summary = prediction.get("reasoning_summary", "")
    if summary:
        st.write("")
        with st.container(border=True):
            st.markdown(
                '<div class="card-head"><span class="card-title">分析摘要</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(f'<div class="prose">{_esc(summary)}</div>',
                        unsafe_allow_html=True)
