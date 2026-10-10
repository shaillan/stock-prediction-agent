"""
规则信号 —— 用纯技术指标产生趋势判断，不调用 LLM

独立成模块，是为了让"信号来源"可替换：后续可以换成别的规则、
或者接上 LLM / 多空 agent，引擎和评估指标都不用动。

约定：信号必须是 看涨 / 看跌 / 震荡 三者之一。
"""
import pandas as pd

BULL = "看涨"
BEAR = "看跌"
NEUTRAL = "震荡"

ALL_CLASSES = (BULL, BEAR, NEUTRAL)


def trend_signal(row) -> str:
    """
    趋势跟随规则：收盘价与 MA20 的相对位置 + MACD 金叉/死叉

    两者同向才给方向，否则视为震荡（避免单指标噪声）。

    Args:
        row: 含 close / ma20 / macd_dif / macd_dea 的一行指标数据

    Returns:
        "看涨" | "看跌" | "震荡"
    """
    close = row.get("close")
    ma20 = row.get("ma20")
    dif = row.get("macd_dif")
    dea = row.get("macd_dea")

    # 指标 warmup 期或缺失数据 → 不给方向
    for value in (close, ma20, dif, dea):
        if value is None or pd.isna(value):
            return NEUTRAL

    if close > ma20 and dif > dea:
        return BULL
    if close < ma20 and dif < dea:
        return BEAR
    return NEUTRAL
