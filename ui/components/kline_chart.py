"""
K线图组件 - Plotly 交互式 K 线图 + 技术指标叠加
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional, Dict

from ui.chart_theme import (
    C_BLUE, C_MAGENTA, C_ORANGE, C_VIOLET, DOWN, GRID, INK_2, INK_3,
    REF, UP, apply_dark,
)


def _safe_values(series, fillna=True):
    """将 Series/array 转为 plotly 安全的一维数组，去掉 NaN"""
    import numpy as np
    if series is None:
        return None
    if hasattr(series, "values"):
        arr = series.values
    elif isinstance(series, (list, tuple)):
        arr = np.array(series)
    else:
        arr = np.asarray(series)
    # 转为一维
    arr = np.asarray(arr).ravel()
    if fillna:
        arr = np.where(np.isnan(arr), None, arr)
    return arr


def render_kline_chart(
    kline_data: pd.DataFrame,
    indicators: Optional[Dict] = None,
    stock_name: str = "",
    stock_code: str = "",
) -> go.Figure:
    """
    渲染交互式 K 线图，叠加技术指标

    Args:
        kline_data: K线 DataFrame (date, open, high, low, close, volume)
        indicators: 技术指标 Dict (可选)
        stock_name: 股票名称
        stock_code: 股票代码

    Returns:
        Plotly Figure 对象
    """
    if kline_data is None or kline_data.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="暂无K线数据",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color=INK_3),
        )
        fig.update_layout(
            title=f"{stock_name}（{stock_code}）- 无数据",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=INK_2, size=11),
        )
        return fig

    # 确保数据类型正确
    df = kline_data.copy()
    # 日期标准化
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # 去掉包含 NaN 的行（前几行可能没有完整指标）
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.reset_index(drop=True)

    # 创建子图布局：K线主图 + 成交量 + MACD + RSI
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.45, 0.15, 0.2, 0.2],
        subplot_titles=(
            f"{stock_name}（{stock_code}）K线图",
            "成交量",
            "MACD (12, 26, 9)",
            "RSI (6, 14, 24)",
        ),
    )

    # ===== Row 1: K线图 =====
    fig.add_trace(
        go.Candlestick(
            x=_safe_values(df["date"], fillna=False),
            open=_safe_values(df["open"]),
            high=_safe_values(df["high"]),
            low=_safe_values(df["low"]),
            close=_safe_values(df["close"]),
            name="K线",
            increasing_line_color=UP,
            increasing_fillcolor="rgba(0,0,0,0)",   # 涨：空心
            decreasing_line_color=DOWN,
            decreasing_fillcolor=DOWN,              # 跌：实心
            showlegend=True,
        ),
        row=1, col=1,
    )

    # 叠加均线
    ma_colors = {"ma5": C_BLUE, "ma10": C_ORANGE, "ma20": C_VIOLET, "ma60": C_MAGENTA}
    if indicators:
        for ma_name, color in ma_colors.items():
            if ma_name in indicators:
                ma_series = _safe_values(indicators[ma_name])
                if ma_series is not None:
                    fig.add_trace(
                        go.Scatter(
                            x=_safe_values(df["date"], fillna=False),
                            y=ma_series,
                            name=ma_name.upper(),
                            line=dict(width=1.2, color=color),
                            showlegend=True,
                        ),
                        row=1, col=1,
                    )

    # 叠加布林带
    if indicators and "boll_upper" in indicators and "boll_lower" in indicators:
        boll_upper = _safe_values(indicators["boll_upper"])
        boll_lower = _safe_values(indicators["boll_lower"])
        date_arr = _safe_values(df["date"], fillna=False)

        if boll_upper is not None and boll_lower is not None:
            fig.add_trace(
                go.Scatter(
                    x=date_arr, y=boll_upper,
                    name="布林上轨",
                    line=dict(width=0.8, color="#4a5468"),
                    showlegend=True,
                ),
                row=1, col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=date_arr, y=boll_lower,
                    name="布林下轨",
                    line=dict(width=0.8, color="#4a5468"),
                    fill="tonexty",
                    fillcolor="rgba(74, 84, 104, 0.05)",
                    showlegend=True,
                ),
                row=1, col=1,
            )

    # ===== Row 2: 成交量 =====
    close_arr = _safe_values(df["close"])
    open_arr = _safe_values(df["open"])
    vol_arr = _safe_values(df["volume"])
    colors = [UP if (c is not None and o is not None and c >= o) else DOWN
              for c, o in zip(close_arr, open_arr)]
    fig.add_trace(
        go.Bar(
            x=_safe_values(df["date"], fillna=False),
            y=vol_arr,
            name="成交量",
            marker_color=colors,
            showlegend=False,
        ),
        row=2, col=1,
    )

    # 成交量均线
    if indicators and "vol_ma5" in indicators:
        vol_ma = _safe_values(indicators["vol_ma5"])
        if vol_ma is not None:
            fig.add_trace(
                go.Scatter(
                    x=_safe_values(df["date"], fillna=False), y=vol_ma,
                    name="VOL MA5",
                    line=dict(width=1, color=C_BLUE),
                    showlegend=False,
                ),
                row=2, col=1,
            )

    # ===== Row 3: MACD =====
    if indicators:
        date_arr = _safe_values(df["date"], fillna=False)
        if "macd_dif" in indicators:
            dif = _safe_values(indicators["macd_dif"])
            if dif is not None:
                fig.add_trace(
                    go.Scatter(x=date_arr, y=dif, showlegend=False,
                        name="DIF", line=dict(width=1.2, color=C_BLUE)),
                    row=3, col=1,
                )
        if "macd_dea" in indicators:
            dea = _safe_values(indicators["macd_dea"])
            if dea is not None:
                fig.add_trace(
                    go.Scatter(x=date_arr, y=dea, showlegend=False,
                        name="DEA", line=dict(width=1.2, color=C_ORANGE)),
                    row=3, col=1,
                )
        if "macd_hist" in indicators:
            hist = _safe_values(indicators["macd_hist"])
            if hist is not None:
                hist_colors = [UP if (h is not None and h >= 0) else DOWN for h in hist]
                fig.add_trace(
                    go.Bar(x=date_arr, y=hist, name="MACD柱",
                           marker_color=hist_colors, showlegend=False),
                    row=3, col=1,
                )

        # 零轴参考线
        fig.add_hline(y=0, line_dash="solid", line_color=REF,
                      line_width=0.8, row=3, col=1)

    # ===== Row 4: RSI =====
    if indicators:
        date_arr = _safe_values(df["date"], fillna=False)
        rsi_colors = {"rsi6": C_BLUE, "rsi14": C_ORANGE, "rsi24": C_VIOLET}
        for rsi_name, color in rsi_colors.items():
            if rsi_name in indicators:
                rsi = _safe_values(indicators[rsi_name])
                if rsi is not None:
                    fig.add_trace(
                        go.Scatter(x=date_arr, y=rsi, showlegend=False,
                            name=rsi_name.upper(),
                            line=dict(width=1.2, color=color)),
                        row=4, col=1,
                    )

        # RSI 参考线 (30 和 70)：用同一档发丝实线，不用红绿（红绿在这是涨跌专用）
        for level in (70, 30):
            fig.add_hline(y=level, line_dash="solid", line_color=REF,
                          line_width=0.8, row=4, col=1)
        fig.add_hline(y=50, line_dash="solid", line_color=GRID,
                      line_width=0.8, row=4, col=1)

    # ===== 布局设置（深色，和页面同一套 token）=====
    apply_dark(fig, height=860, legend=True)
    fig.update_layout(
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=44, b=0),
    )
    # 竖直游标：横向扫过时能对齐四张子图
    fig.update_xaxes(showspikes=True, spikecolor=INK_3,
                     spikethickness=1, spikedash="solid")

    # 子图标题：左对齐、弱化成小字。面板名已经在标题里，Y 轴就不再重复写"价格/成交量"
    for ann in fig.layout.annotations:
        ann.font.update(color=INK_3, size=11)
        ann.x, ann.xanchor = 0.0, "left"

    fig.update_yaxes(title_text=None)
    fig.update_yaxes(range=[0, 100], row=4, col=1)

    return fig
