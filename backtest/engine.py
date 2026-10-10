"""
回测引擎 —— walk-forward：每个时点产生信号，对照未来 N 日的实际涨跌

时点正确性（重要）：
- K线取后复权(hfq)。前复权价格会随新数据重新锚定，同一历史日期的价格
  在不同时间跑出来不一样，回测结果不可复现。
- 技术指标是因果计算（rolling / ewm 只用当前及之前的数据），所以第 t 行的
  指标值只包含 t 及之前的信息，不存在前视偏差。
- 未来收益用 t+horizon 的收盘价，与信号严格分离。

两种标签口径（--label）：
- threshold: 涨超 +阈值才算"看涨"、跌超 -阈值才算"看跌"，中间算"震荡"。
             符合"1-5个交易日趋势"的直觉，但中间死角会让"永远猜震荡"
             这类基线虚高。
- direction: 纯方向二分类，涨就是看涨、跌就是看跌，没有死角。
             更公平，但要求信号敢站队（震荡信号会被排除，见 metrics）。
"""
from typing import Optional

import pandas as pd
from loguru import logger

from data.akhare_client import AKShareClient
from data.cache_manager import CacheManager
from data.technical_indicators import TechnicalIndicatorCalculator

from .signals import BULL, BEAR, NEUTRAL, SIGNAL_FUNCS, trend_signal

# 指标预热：MA60 需要 60 根 K 线，留足余量后再开始打分
WARMUP_ROWS = 60

# 需要分段评估时，向前多取一段数据用于预热指标，避免吃掉区间开头的样本
WARMUP_BUFFER_DAYS = 250


def classify_forward_return(
    fwd_return: float,
    threshold: float = 0.02,
    mode: str = "threshold",
) -> str:
    """
    把未来收益判定成实际走势类别

    mode="threshold": > +threshold → 看涨; < -threshold → 看跌; 其余 → 震荡
    mode="direction": > 0 → 看涨; < 0 → 看跌; 恰好 0 → 震荡(极罕见)
    """
    if mode == "direction":
        if fwd_return > 0:
            return BULL
        if fwd_return < 0:
            return BEAR
        return NEUTRAL

    if fwd_return > threshold:
        return BULL
    if fwd_return < -threshold:
        return BEAR
    return NEUTRAL


def load_indicators(
    code: str,
    start_date: str,
    end_date: str,
    adjust: str = "hfq",
) -> pd.DataFrame:
    """取 K 线并算出完整历史指标表（每行对应一个交易日）"""
    client = AKShareClient(cache_manager=CacheManager())
    raw = client.get_stock_kline(code, "daily", start_date, end_date, adjust=adjust)

    df = raw.copy()
    # K线源返回的 date 是字符串且不保证排序，这里统一处理
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    calculator = TechnicalIndicatorCalculator(df)
    calculator.calc_all()

    indicators = calculator.get_latest_values(n_rows=len(df))
    return indicators.reset_index(drop=True)


def score_indicators(
    code: str,
    indicators: pd.DataFrame,
    signal_fn,
    horizon: int = 5,
    threshold: float = 0.02,
    mode: str = "threshold",
    eval_start: Optional[pd.Timestamp] = None,
    eval_end: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """
    在一张已算好的指标表上逐时点打分，并对照未来收益

    抽成独立函数，是为了让 scan_signals 能「取一次数、算一次指标、
    评估多个信号」—— 否则 N 个信号就要 N 次重复取数。
    """
    n = len(indicators)
    if n <= WARMUP_ROWS + horizon:
        return pd.DataFrame()

    records = []
    for t in range(WARMUP_ROWS, n - horizon):
        row = indicators.iloc[t]
        row_date = row["date"]

        # 分段评估：只保留落在评估窗口内的时点
        if eval_start is not None and row_date < eval_start:
            continue
        if eval_end is not None and row_date > eval_end:
            continue

        signal = signal_fn(row)

        close_now = row["close"]
        close_future = indicators.iloc[t + horizon]["close"]
        if pd.isna(close_now) or pd.isna(close_future) or close_now == 0:
            continue

        fwd_return = float((close_future - close_now) / close_now)
        actual = classify_forward_return(fwd_return, threshold, mode)

        records.append(
            {
                "code": code,
                "date": row_date,
                "close": float(close_now),
                "signal": signal,
                "fwd_return": round(fwd_return, 6),
                "actual": actual,
                "correct": signal == actual,
            }
        )

    return pd.DataFrame(records)


def backtest_stock(
    code: str,
    start_date: str,
    end_date: str,
    horizon: int = 5,
    threshold: float = 0.02,
    mode: str = "threshold",
    eval_start: Optional[pd.Timestamp] = None,
    eval_end: Optional[pd.Timestamp] = None,
    adjust: str = "hfq",
    signal_fn=trend_signal,
) -> pd.DataFrame:
    """
    对单只股票做 walk-forward 回测

    Args:
        start_date / end_date: 取 K 线的范围
        eval_start / eval_end: 只把这些日期内的时点计入结果。
            用于分段评估时先向前多取数据做指标预热，再裁剪评估窗口。
        signal_fn: (row) -> 看涨/看跌/震荡，默认 trend_signal

    Returns:
        DataFrame，每个时点一行：
        date / close / signal / fwd_return / actual / correct
    """
    indicators = load_indicators(code, start_date, end_date, adjust=adjust)
    n = len(indicators)

    if n <= WARMUP_ROWS + horizon:
        logger.warning(f"{code}: 数据不足（{n} 行），跳过")
        return pd.DataFrame()

    df = score_indicators(
        code, indicators, signal_fn,
        horizon=horizon, threshold=threshold, mode=mode,
        eval_start=eval_start, eval_end=eval_end,
    )
    logger.info(f"{code}: 回测完成，{len(df)} 个时点")
    return df


def backtest_universe(
    codes: list,
    start_date: str,
    end_date: str,
    horizon: int = 5,
    threshold: float = 0.02,
    mode: str = "threshold",
    eval_start: Optional[pd.Timestamp] = None,
    eval_end: Optional[pd.Timestamp] = None,
    adjust: str = "hfq",
    signal_fn=trend_signal,
) -> pd.DataFrame:
    """对一组股票跑单个信号的回测，单只失败不影响整体"""
    frames = []
    for code in codes:
        try:
            df = backtest_stock(
                code, start_date, end_date,
                horizon=horizon, threshold=threshold, mode=mode,
                eval_start=eval_start, eval_end=eval_end, adjust=adjust,
                signal_fn=signal_fn,
            )
        except Exception as e:
            logger.error(f"{code}: 回测失败，跳过 —— {e}")
            continue
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def scan_signals(
    codes: list,
    start_date: str,
    end_date: str,
    signal_names: list,
    horizon: int = 5,
    threshold: float = 0.02,
    mode: str = "threshold",
    eval_start: Optional[pd.Timestamp] = None,
    eval_end: Optional[pd.Timestamp] = None,
    adjust: str = "hfq",
) -> dict:
    """
    一次评估多个信号：每只股票的 K 线只取一次、指标只算一遍，
    然后在这同一张表上跑所有信号。

    Args:
        signal_names: backtest.signals 里的信号键名列表

    Returns:
        {信号名: 逐时点明细 DataFrame}，每个 DataFrame 多一列 signal_rule 记录来源
    """
    results = {name: [] for name in signal_names}

    for code in codes:
        try:
            indicators = load_indicators(code, start_date, end_date, adjust=adjust)
        except Exception as e:
            logger.error(f"{code}: 取数/算指标失败，跳过 —— {e}")
            continue

        if len(indicators) <= WARMUP_ROWS + horizon:
            logger.warning(f"{code}: 数据不足（{len(indicators)} 行），跳过")
            continue

        for name in signal_names:
            df = score_indicators(
                code, indicators, SIGNAL_FUNCS[name],
                horizon=horizon, threshold=threshold, mode=mode,
                eval_start=eval_start, eval_end=eval_end,
            )
            if not df.empty:
                df["signal_rule"] = name
                results[name].append(df)

        logger.info(f"{code}: {len(signal_names)} 个信号评估完成")

    return {
        name: (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame())
        for name, frames in results.items()
    }
