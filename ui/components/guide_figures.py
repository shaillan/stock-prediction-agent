# -*- coding: utf-8 -*-
"""
新手科普配图 —— 每个概念一张 Plotly 教学小图

设计要点：
- 全部用**合成数据**（确定性公式，不用随机数/不联网）：每次打开长一样，
  且形状被刻意设计成最能说明该概念的样子（如金叉一定出现在图中间）
- 尺寸紧凑（高 ~280px），去工具栏，和小白「看图识字」的预期一致
- 纯函数模块（不 import streamlit），方便单独测试
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ui.chart_theme import (
    C_BLUE, C_NEUTRAL, C_ORANGE, C_VIOLET, DOWN, INK_3, UP, apply_dark,
)

_W = dict(margin=dict(l=10, r=10, t=30, b=10), height=280)


def _blank(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=dict(text=title, font=dict(size=13)), **_W)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)")
    return fig


def fig_candle() -> go.Figure:
    """K线解剖：一红一绿两根蜡烛，标注四个价格"""
    # 空心/实心要和上面那张真 K 线图一致（涨=空心、跌=实心），
    # 否则科普讲的编码和用户抬头看到的图对不上
    fig = go.Figure(go.Candlestick(
        x=["第 1 天", "第 2 天"],
        open=[100, 110], high=[113, 112], low=[98, 102], close=[110, 104],
        increasing_line_color=UP, increasing_fillcolor="rgba(0,0,0,0)",
        decreasing_line_color=DOWN, decreasing_fillcolor=DOWN,
    ))
    fig.update_layout(title="一根K线 = 开盘/收盘/最高/最低（红涨绿跌）", **_W)
    fig.update_layout(xaxis_rangeslider_visible=False)
    for x, y, text in [("第 1 天", 113, "最高 113（上影线）"),
                       ("第 1 天", 100, "开盘 100（实体下沿）"),
                       ("第 1 天", 110, "收盘 110（实体上沿）"),
                       ("第 2 天", 102, "最低 102（下影线）")]:
        fig.add_annotation(x=x, y=y, text=text, showarrow=True, arrowhead=2,
                           ay=-28 if "高" in text else 28, font=dict(size=11))
    return fig


def fig_ma() -> go.Figure:
    """均线：价格上穿、MA5 在 MA20 上方 = 多头排列"""
    t = np.arange(60)
    price = 100 + t * 0.35 + 3 * np.sin(t / 4)
    df = pd.DataFrame({"close": price})
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    fig = go.Figure()
    fig.add_scatter(y=df["close"], name="股价", line=dict(color=C_NEUTRAL, width=1))
    fig.add_scatter(y=df["ma5"], name="MA5（短期均价）", line=dict(color=C_ORANGE, width=2))
    fig.add_scatter(y=df["ma20"], name="MA20（长期均价）", line=dict(color=C_BLUE, width=2))
    fig.add_annotation(x=48, y=df["ma5"].iloc[48] + 6, text="多头排列：MA5 在 MA20 上方 → 趋势偏强",
                       showarrow=False, font=dict(size=12, color=UP))
    fig.update_layout(title="均线 = 最近 N 天的平均成本（示意走势）", **_W)
    fig.update_yaxes(visible=False)
    return fig


def fig_macd() -> go.Figure:
    """MACD：先跌后涨的走势里出现一次金叉，柱子由绿转红"""
    t = np.arange(60)
    price = np.where(t < 30, 115 - t * 0.5, 100 + (t - 30) * 0.6)
    s = pd.Series(price)
    dif = s.ewm(span=12, adjust=False).mean() - s.ewm(span=26, adjust=False).mean()
    dea = dif.ewm(span=9, adjust=False).mean()
    hist = dif - dea
    cross = int(np.argmax((dif > dea) & (dif.shift(1) <= dea.shift(1))))
    fig = go.Figure()
    fig.add_bar(y=hist, name="柱 = DIF−DEA",
                marker_color=[UP if h >= 0 else DOWN for h in hist], opacity=0.5)
    fig.add_scatter(y=dif, name="DIF（快线）", line=dict(color=C_BLUE, width=2))
    fig.add_scatter(y=dea, name="DEA（慢线）", line=dict(color=C_ORANGE, width=2))
    fig.add_annotation(x=cross, y=float(dea.iloc[cross]), text="金叉：DIF 上穿 DEA → 动能转强",
                       showarrow=True, arrowhead=2, ay=-40, font=dict(size=12, color=UP))
    fig.update_layout(title="MACD = 上涨的「劲儿」在变强还是变弱（先跌后涨的示意）", **_W)
    fig.update_yaxes(visible=False)
    return fig


def fig_rsi() -> go.Figure:
    """RSI：冲上 70 的超买区再回落，跌进 30 的超卖区"""
    t = np.arange(60)
    rsi = 45 + 33 * np.sin(t / 60 * np.pi) * np.sin(t / 9) + 6 * np.sin(t / 2.5)
    fig = go.Figure()
    fig.add_scatter(y=rsi, name="RSI14", line=dict(color=C_VIOLET, width=2))
    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(230,103,103,0.10)", line_width=0)
    fig.add_hrect(y0=0, y1=30, fillcolor="rgba(25,158,112,0.10)", line_width=0)
    fig.add_hline(y=70, line_dash="dash", line_color=UP)
    fig.add_hline(y=30, line_dash="dash", line_color=DOWN)
    peak = int(np.argmax(rsi)); trough = int(np.argmin(rsi))
    fig.add_annotation(x=peak, y=rsi[peak], text="超买（涨太急，留神回调）",
                       showarrow=True, arrowhead=2, ay=-30, font=dict(size=12, color=UP))
    fig.add_annotation(x=trough, y=rsi[trough], text="超卖（跌太狠，可能反弹）",
                       showarrow=True, arrowhead=2, ay=30, font=dict(size=12, color=DOWN))
    fig.update_layout(title="RSI = 市场体温计（70 过热 / 30 过冷）", yaxis_range=[0, 105], **_W)
    fig.update_xaxes(visible=False)
    return fig


def fig_boll() -> go.Figure:
    """布林带：带宽收窄（憋劲）→ 向上突破"""
    t = np.arange(60)
    half = np.where(t < 40, 8 - t * 0.15, 2.0)          # 上下轨距离先收窄再维持
    mid = np.where(t < 40, 100.0, 100.0 + (t - 40) * 0.45)
    price = np.where(t < 40, mid + half * np.sin(t / 2.5) * (1 - t / 90), mid + 3.5 + (t - 40) * 0.3)
    fig = go.Figure()
    fig.add_scatter(y=mid + half, name="上轨", line=dict(color=C_NEUTRAL, width=1, dash="dash"))
    fig.add_scatter(y=mid, name="中轨（20日均价）", line=dict(color=C_NEUTRAL, width=1))
    fig.add_scatter(y=mid - half, name="下轨", line=dict(color=C_NEUTRAL, width=1, dash="dash"),
                    fill="tonexty", fillcolor="rgba(124,135,155,0.10)")
    fig.add_scatter(y=price, name="股价", line=dict(color=C_BLUE, width=2))
    fig.add_annotation(x=30, y=93, text="带宽收窄 = 憋着一股劲", showarrow=False,
                       font=dict(size=12, color=INK_3))
    fig.add_annotation(x=48, y=mid[48] + half[48] + 2, text="突破", showarrow=True,
                       arrowhead=2, ay=-30, font=dict(size=12, color=UP))
    fig.update_layout(title="布林带 = 股价的「正常活动范围」", **_W)
    fig.update_xaxes(visible=False); fig.update_yaxes(visible=False)
    return fig


def fig_support() -> go.Figure:
    """支撑/压力：价格在地板和天花板之间来回"""
    t = np.arange(60)
    price = 102.5 + 7.0 * np.sin(t / 60 * 3 * np.pi) + 1.2 * np.sin(t / 3.1)
    fig = go.Figure()
    fig.add_scatter(y=price, name="股价", line=dict(color=C_BLUE, width=2))
    fig.add_hline(y=110, line_color=UP, line_dash="dash")
    fig.add_hline(y=95, line_color=DOWN, line_dash="dash")
    fig.add_annotation(x=44, y=110.8, text="压力位 110（天花板）", showarrow=False,
                       font=dict(size=12, color=UP))
    fig.add_annotation(x=44, y=94.2, text="支撑位 95（地板）", showarrow=False,
                       font=dict(size=12, color=DOWN))
    fig.update_layout(title="支撑位与压力位 = 地板和天花板（是区域不是精确数字）", **_W)
    fig.update_xaxes(visible=False); fig.update_yaxes(visible=False)
    return fig


def fig_pe_compare() -> go.Figure:
    """PE 行业对比：不同行业差很多，跨行业比较没有意义"""
    names = ["银行", "家电", "白酒", "半导体"]
    vals = [6, 15, 25, 45]
    colors = [DOWN, C_BLUE, C_VIOLET, UP]
    fig = go.Figure(go.Bar(x=names, y=vals, marker_color=colors, text=[f"PE {v}" for v in vals],
                           textposition="outside"))
    fig.update_layout(
        title=dict(text="不同行业的 PE 天差地别（示意值）"
                        "<br><sup>PE 高≠贵：市场可能预期它利润长得快</sup>"),
        margin=dict(l=10, r=10, t=48, b=10), height=280)
    # 留出顶空，不然最高那根柱子的"PE 45"标签会被裁掉
    fig.update_yaxes(visible=False, range=[0, 54])
    return fig


def fig_margin() -> go.Figure:
    """一杯奶茶的账：毛利率 vs 净利率（瀑布图）"""
    fig = go.Figure(go.Waterfall(
        x=["售价", "原料/杯子", "房租人工广告", "最后到手（净利）"],
        measure=["absolute", "relative", "relative", "total"],
        y=[20, -6, -12, 0],
        text=["卖 20 元", "−6 元", "−12 元", "剩 2 元"],
        increasing_marker_color=UP, decreasing_marker_color=DOWN,
        totals_marker_color=C_BLUE,
    ))
    fig.update_layout(title="毛利率/净利率：一杯奶茶的三本账", **_W)
    fig.update_yaxes(visible=False)
    return fig
