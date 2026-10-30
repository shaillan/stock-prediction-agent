# -*- coding: utf-8 -*-
"""图表配色与深色布局 —— 全项目 Plotly 图共用

色值和 ui/styles.py 的 CSS token 一一对应，改色两处一起改。
涨跌两色色盲区分度只有 ΔE 6.5，所以任何用它们的地方都必须再带一层非颜色编码
（K 线用空心/实心，文字用 ▲▼ 和正负号）。
"""
# 涨跌
UP = "#e66767"
DOWN = "#199e70"
# 表面与文字
SURFACE = "#11151c"
INK_1 = "#e8edf5"
INK_2 = "#a7b1c2"
INK_3 = "#8a94a6"
GRID = "#1b212b"
AXIS = "#232a36"
REF = "#3a4354"
# 分类色：四个一组已跑过配色校验（深色面 #11151c 上全部通过）
C_BLUE, C_ORANGE, C_VIOLET, C_MAGENTA = "#3987e5", "#d95926", "#9085e9", "#d55181"
# 中性线（股价、示意线）
C_NEUTRAL = "#7c879b"


def apply_dark(fig, height: int = None, legend=None):
    """把一张 Plotly 图改成深色底、发丝网格、透明背景。

    只设默认值：图上已经显式指定的颜色（比如标注文字）不会被覆盖。
    legend 传 None 表示不干预——单序列的图就不会冒出 "trace 0" 这种图例。
    """
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=INK_2, size=11),
        colorway=[C_BLUE, C_ORANGE, C_VIOLET, C_MAGENTA],
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right",
                    x=1, traceorder="normal", bgcolor="rgba(0,0,0,0)",
                    font=dict(size=11, color=INK_3)),
        hoverlabel=dict(bgcolor="#161b24", bordercolor=AXIS,
                        font=dict(size=11, color=INK_1)),
    )
    if legend is not None:
        fig.update_layout(showlegend=legend)
    if height:
        fig.update_layout(height=height)
    fig.update_xaxes(showgrid=True, gridcolor=GRID, linecolor=AXIS,
                     zeroline=False, tickfont=dict(color=INK_3))
    fig.update_yaxes(showgrid=True, gridcolor=GRID, linecolor=AXIS,
                     zeroline=False, tickfont=dict(color=INK_3))
    # 标题默认弱化；标注文字保留自己的颜色
    if fig.layout.title and fig.layout.title.text:
        fig.update_layout(title=dict(font=dict(size=13, color=INK_2)))
    return fig
