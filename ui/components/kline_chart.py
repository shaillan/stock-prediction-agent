"""
K线图组件 - Plotly 交互式 K 线图 + 技术指标叠加
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional, Dict


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
            font=dict(size=20, color="gray"),
        )
        fig.update_layout(title=f"{stock_name}（{stock_code}）- 无数据")
        return fig

    # 确保数据类型正确
    df = kline_data.copy()
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])

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
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="K线",
            increasing_line_color="#e53e3e",
            decreasing_line_color="#38a169",
            showlegend=True,
        ),
        row=1, col=1,
    )

    # 叠加均线
    ma_colors = {"ma5": "#FF9800", "ma10": "#2196F3", "ma20": "#9C27B0", "ma60": "#4CAF50"}
    if indicators:
        for ma_name, color in ma_colors.items():
            if ma_name in indicators:
                ma_series = indicators[ma_name]
                if hasattr(ma_series, "values"):
                    ma_series = ma_series.values
                fig.add_trace(
                    go.Scatter(
                        x=df["date"],
                        y=ma_series,
                        name=ma_name.upper(),
                        line=dict(width=1.2, color=color),
                        showlegend=True,
                    ),
                    row=1, col=1,
                )

    # 叠加布林带
    if indicators and "boll_upper" in indicators and "boll_lower" in indicators:
        boll_upper = indicators["boll_upper"]
        boll_lower = indicators["boll_lower"]
        if hasattr(boll_upper, "values"):
            boll_upper = boll_upper.values
        if hasattr(boll_lower, "values"):
            boll_lower = boll_lower.values

        # 布林带上轨
        fig.add_trace(
            go.Scatter(
                x=df["date"], y=boll_upper,
                name="布林上轨",
                line=dict(width=0.8, color="gray", dash="dash"),
                showlegend=True,
            ),
            row=1, col=1,
        )
        # 布林带下轨（填充区域）
        fig.add_trace(
            go.Scatter(
                x=df["date"], y=boll_lower,
                name="布林下轨",
                line=dict(width=0.8, color="gray", dash="dash"),
                fill="tonexty",
                fillcolor="rgba(128, 128, 128, 0.1)",
                showlegend=True,
            ),
            row=1, col=1,
        )

    # ===== Row 2: 成交量 =====
    colors = ["#e53e3e" if close >= open_ else "#38a169"
              for close, open_ in zip(df["close"], df["open"])]
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=df["volume"],
            name="成交量",
            marker_color=colors,
            showlegend=False,
        ),
        row=2, col=1,
    )

    # 成交量均线
    if indicators and "vol_ma5" in indicators:
        vol_ma = indicators["vol_ma5"]
        if hasattr(vol_ma, "values"):
            vol_ma = vol_ma.values
        fig.add_trace(
            go.Scatter(
                x=df["date"], y=vol_ma,
                name="VOL MA5",
                line=dict(width=1, color="#FF9800"),
                showlegend=False,
            ),
            row=2, col=1,
        )

    # ===== Row 3: MACD =====
    if indicators:
        # DIF 线
        if "macd_dif" in indicators:
            dif = indicators["macd_dif"]
            if hasattr(dif, "values"):
                dif = dif.values
            fig.add_trace(
                go.Scatter(
                    x=df["date"], y=dif,
                    name="DIF", line=dict(width=1.2, color="#2196F3"),
                ),
                row=3, col=1,
            )
        # DEA 线
        if "macd_dea" in indicators:
            dea = indicators["macd_dea"]
            if hasattr(dea, "values"):
                dea = dea.values
            fig.add_trace(
                go.Scatter(
                    x=df["date"], y=dea,
                    name="DEA", line=dict(width=1.2, color="#FF9800"),
                ),
                row=3, col=1,
            )
        # MACD 柱状图
        if "macd_hist" in indicators:
            hist = indicators["macd_hist"]
            if hasattr(hist, "values"):
                hist = hist.values
            hist_colors = ["#e53e3e" if h >= 0 else "#38a169" for h in hist]
            fig.add_trace(
                go.Bar(
                    x=df["date"], y=hist,
                    name="MACD柱",
                    marker_color=hist_colors,
                ),
                row=3, col=1,
            )

        # 零轴参考线
        fig.add_hline(y=0, line_dash="solid", line_color="gray",
                      line_width=0.5, row=3, col=1)

    # ===== Row 4: RSI =====
    if indicators:
        rsi_colors = {"rsi6": "#e53e3e", "rsi14": "#2196F3", "rsi24": "#9C27B0"}
        for rsi_name, color in rsi_colors.items():
            if rsi_name in indicators:
                rsi = indicators[rsi_name]
                if hasattr(rsi, "values"):
                    rsi = rsi.values
                fig.add_trace(
                    go.Scatter(
                        x=df["date"], y=rsi,
                        name=rsi_name.upper(),
                        line=dict(width=1.2, color=color),
                    ),
                    row=4, col=1,
                )

        # RSI 参考线 (30 和 70)
        fig.add_hline(y=70, line_dash="dash", line_color="red",
                      line_width=0.8, row=4, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green",
                      line_width=0.8, row=4, col=1)
        fig.add_hline(y=50, line_dash="dot", line_color="gray",
                      line_width=0.5, row=4, col=1)

    # ===== 布局设置 =====
    fig.update_layout(
        height=900,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=40, b=0),
        template="plotly_white",
    )

    # Y轴标签
    fig.update_yaxes(title_text="价格", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)
    fig.update_yaxes(title_text="RSI", row=4, col=1)
    fig.update_xaxes(title_text="日期", row=4, col=1)

    return fig
