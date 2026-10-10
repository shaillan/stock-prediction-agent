"""
规则信号 —— 用纯技术指标产生趋势判断，不调用 LLM

独立成模块，是为了让"信号来源"可替换：后续可以换成别的规则、
或者接上 LLM / 多空 agent，引擎和评估指标都不用动。

约定：信号函数签名 (row) -> str，返回值必须是 看涨 / 看跌 / 震荡 三者之一。
所有信号只用「当前及之前」的指标值 —— 指标本身是因果计算的（rolling / ewm
不涉及未来数据），所以按行回放不会引入前视偏差。

信号故意分成思路相反的两类，放在一起对照：

    顺势：趋势跟随、均线排列、MACD、KDJ、放量突破
    逆势：RSI、布林带、威廉指标的超买超卖反转

如果两类**都**不赚钱，那就不是"方向做反了"或"参数没调对"，
而是这批技术指标本身没有 1-5 个交易日的方向性。
"""
import pandas as pd

BULL = "看涨"
BEAR = "看跌"
NEUTRAL = "震荡"

ALL_CLASSES = (BULL, BEAR, NEUTRAL)


def _ok(*values) -> bool:
    """所有值都非空且非 NaN 才算有效（指标预热期会返回 NaN）"""
    for v in values:
        if v is None or pd.isna(v):
            return False
    return True


# ===================== 顺势 =====================

def trend_signal(row) -> str:
    """
    趋势跟随：收盘价与 MA20 的相对位置 + MACD 金叉/死叉

    两者同向才给方向，否则视为震荡（避免单指标噪声）。
    """
    close, ma20 = row.get("close"), row.get("ma20")
    dif, dea = row.get("macd_dif"), row.get("macd_dea")
    if not _ok(close, ma20, dif, dea):
        return NEUTRAL

    if close > ma20 and dif > dea:
        return BULL
    if close < ma20 and dif < dea:
        return BEAR
    return NEUTRAL


def ma_cross_signal(row) -> str:
    """均线多头/空头排列：close / ma5 / ma20 三线同向"""
    close, ma5, ma20 = row.get("close"), row.get("ma5"), row.get("ma20")
    if not _ok(close, ma5, ma20):
        return NEUTRAL

    if close > ma5 > ma20:
        return BULL
    if close < ma5 < ma20:
        return BEAR
    return NEUTRAL


def macd_only_signal(row) -> str:
    """只看 MACD 单指标 —— 用来对照「单指标」和「多指标组合」有没有差别"""
    dif, dea = row.get("macd_dif"), row.get("macd_dea")
    if not _ok(dif, dea):
        return NEUTRAL

    if dif > dea:
        return BULL
    if dif < dea:
        return BEAR
    return NEUTRAL


def kdj_cross_signal(row) -> str:
    """KDJ 金叉/死叉，但避开超买(>80)超卖(<20)区不追"""
    k, d = row.get("kdj_k"), row.get("kdj_d")
    if not _ok(k, d):
        return NEUTRAL

    if k > d and k < 80:
        return BULL
    if k < d and k > 20:
        return BEAR
    return NEUTRAL


def volume_breakout_signal(row) -> str:
    """放量突破：站上/跌破 MA20 且量比 > 1.5 才给方向（量能确认）"""
    close, ma20 = row.get("close"), row.get("ma20")
    vr = row.get("volume_ratio")
    if not _ok(close, ma20, vr):
        return NEUTRAL

    if vr <= 1.5:
        return NEUTRAL
    if close > ma20:
        return BULL
    if close < ma20:
        return BEAR
    return NEUTRAL


# ===================== 逆势 =====================

def rsi_reversal_signal(row) -> str:
    """RSI 超卖反弹 / 超买回落 —— 与趋势跟随的思路正相反"""
    rsi = row.get("rsi14")
    if not _ok(rsi):
        return NEUTRAL

    if rsi < 30:
        return BULL
    if rsi > 70:
        return BEAR
    return NEUTRAL


def boll_reversal_signal(row) -> str:
    """跌破布林下轨看反弹、突破上轨看回落"""
    close = row.get("close")
    upper, lower = row.get("boll_upper"), row.get("boll_lower")
    if not _ok(close, upper, lower):
        return NEUTRAL

    if close < lower:
        return BULL
    if close > upper:
        return BEAR
    return NEUTRAL


def wr_reversal_signal(row) -> str:
    """
    威廉指标反转

    注意本项目的 wr = (N日最高 − 收盘) / (N日最高 − N日最低) × 100，
    所以数值越大 = 收盘越靠近区间底部（超卖）→ 看涨。
    """
    wr = row.get("wr")
    if not _ok(wr):
        return NEUTRAL

    if wr > 80:
        return BULL
    if wr < 20:
        return BEAR
    return NEUTRAL


# ===================== 注册表 =====================

# (键, 中文标签, 函数) —— 列表顺序就是排行榜里的默认展示顺序
SIGNAL_REGISTRY = [
    ("trend",           "趋势跟随(MA20+MACD)", trend_signal),
    ("ma_cross",        "均线多头排列",        ma_cross_signal),
    ("macd_only",       "MACD单指标",          macd_only_signal),
    ("kdj_cross",       "KDJ金叉死叉",         kdj_cross_signal),
    ("volume_breakout", "放量突破MA20",        volume_breakout_signal),
    ("rsi_reversal",    "RSI超买超卖反转",     rsi_reversal_signal),
    ("boll_reversal",   "布林带触带反转",      boll_reversal_signal),
    ("wr_reversal",     "威廉指标反转",        wr_reversal_signal),
]

SIGNAL_LABELS = {k: label for k, label, _ in SIGNAL_REGISTRY}
SIGNAL_FUNCS = {k: fn for k, _, fn in SIGNAL_REGISTRY}
ALL_SIGNAL_NAMES = [k for k, _, _ in SIGNAL_REGISTRY]

DEFAULT_SIGNAL = "trend"


def signal_label(name: str) -> str:
    return SIGNAL_LABELS[name]


def resolve_signals(spec: str) -> list:
    """
    解析 --signals 参数 → 信号名列表

        ""                    → 默认信号（trend）
        "all"                 → 全部
        "trend,rsi_reversal"  → 指定的几个
    """
    spec = (spec or "").strip()
    if not spec:
        return [DEFAULT_SIGNAL]
    if spec.lower() == "all":
        return list(ALL_SIGNAL_NAMES)

    names = [s.strip() for s in spec.split(",") if s.strip()]
    unknown = [n for n in names if n not in SIGNAL_FUNCS]
    if unknown:
        raise ValueError(
            f"未知信号: {', '.join(unknown)}\n"
            f"可用信号: {', '.join(ALL_SIGNAL_NAMES)}（或 all）"
        )
    return names
