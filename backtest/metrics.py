"""
回测评估指标

单看命中率没有意义，必须和朴素基线比 —— A股本身有漂移，"永远猜涨"
或"永远猜震荡"也能拿到不低的分数。真正要看的指标是 skill（净胜率）。
"""
import pandas as pd

from .signals import ALL_CLASSES, BULL, BEAR, NEUTRAL

CLASS_ORDER = (BULL, BEAR, NEUTRAL)


def hit_rate(df: pd.DataFrame) -> float:
    """整体命中率：信号 vs 实际完全一致的比例"""
    if df.empty:
        return 0.0
    return float(df["correct"].mean())


def baselines(df: pd.DataFrame) -> pd.Series:
    """
    朴素基线：无论什么情况都猜同一个方向，能拿到的命中率

    "永远猜震荡"这条通常会很高，因为 ±threshold 的区间覆盖了大多数
    5 日波动 —— 这正是 threshold 口径下判断信号有没有价值的参照物。
    """
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series({f"always_{c}": float((df["actual"] == c).mean()) for c in ALL_CLASSES})


def skill(df: pd.DataFrame) -> float:
    """净胜率 = 命中率 − 最佳朴素基线。<= 0 表示信号没有信息量"""
    if df.empty:
        return 0.0
    base = baselines(df)
    return hit_rate(df) - float(base.max())


def per_stock(df: pd.DataFrame) -> pd.DataFrame:
    """每只股票的命中率"""
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby("code").agg(
        样本数=("correct", "size"),
        命中率=("correct", "mean"),
        平均未来收益=("fwd_return", "mean"),
    )
    grouped["命中率"] = grouped["命中率"].round(4)
    grouped["平均未来收益"] = grouped["平均未来收益"].round(4)
    return grouped.sort_values("命中率", ascending=False)


def signal_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    按信号分组看：给出某个信号时，实际走势如何

    命中率低但"平均未来收益"方向正确，说明信号有方向性但幅度不够
    （被 threshold 判成了震荡）—— 这类信息对调参很有用。
    """
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby("signal").agg(
        样本数=("correct", "size"),
        命中率=("correct", "mean"),
        平均未来收益=("fwd_return", "mean"),
        实际看涨占比=("actual", lambda s: float((s == BULL).mean())),
        实际看跌占比=("actual", lambda s: float((s == BEAR).mean())),
    )
    for col in ("命中率", "平均未来收益", "实际看涨占比", "实际看跌占比"):
        grouped[col] = grouped[col].round(4)
    return grouped.reindex([c for c in CLASS_ORDER if c in grouped.index])


def outcome_distribution(df: pd.DataFrame) -> pd.Series:
    """实际结果的类别分布"""
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(
        {c: float((df["actual"] == c).mean()) for c in CLASS_ORDER}
    ).round(4)


def summarize(df: pd.DataFrame, horizon: int, threshold: float) -> str:
    """threshold 口径：三分类，含死角。把指标拼成一份可读报告"""
    if df.empty:
        return "⚠️ 没有回测样本，请检查日期区间与股票代码"

    hr = hit_rate(df)
    base = baselines(df)
    sk = skill(df)
    best_base_name = base.idxmax().replace("always_", "永远猜")
    best_base_val = float(base.max())

    lines = [
        "=" * 62,
        f"回测报告[threshold]  样本数={len(df)}  股票数={df['code'].nunique()}  "
        f"持有期={horizon}个交易日  阈值=±{threshold:.1%}",
        f"时间区间  {df['date'].min():%Y-%m-%d} ~ {df['date'].max():%Y-%m-%d}",
        "=" * 62,
        "",
        "【核心结论】",
        f"  信号命中率          {hr:.4f}",
        f"  最佳朴素基线        {best_base_val:.4f}  ({best_base_name})",
        f"  净胜率 skill        {sk:+.4f}",
        "",
    ]

    if sk <= 0:
        lines.append("  ⚠️  净胜率 <= 0：该信号并不优于「什么都不想直接猜一个方向」。")
        lines.append("      这本身就是有价值的结论 —— 说明技术指标规则不足以支撑预测。")
    else:
        lines.append(f"  ✅ 净胜率 > 0：信号比朴素基线好 {sk:.2%}，但需扩大样本再确认。")
    lines.append("")

    lines.append("【朴素基线】")
    for name, val in base.items():
        lines.append(f"  {name.replace('always_', '永远猜'):<12} {val:.4f}")
    lines.append("")

    lines.append("【实际结果分布】(阈值低于此分布过于集中时，命中率会被基线带高)")
    for name, val in outcome_distribution(df).items():
        lines.append(f"  {name:<8} {val:.4f}")
    lines.append("")

    lines.append("【按信号分组】")
    lines.append(signal_breakdown(df).to_string())
    lines.append("")

    lines.append("【按股票】")
    lines.append(per_stock(df).to_string())
    lines.append("")

    return "\n".join(lines)


def summarize_direction(df: pd.DataFrame, horizon: int) -> str:
    """
    direction 口径：纯方向二分类，无死角

    只在"信号敢给方向"的样本上评估（震荡信号排除）——因为对交易来说，
    含糊其辞等于没给信号。基线也在同一个子集上算，才公平。
    """
    if df.empty:
        return "⚠️ 没有回测样本，请检查日期区间与股票代码"

    total = len(df)
    committed = df[df["signal"] != NEUTRAL].copy()
    excluded = total - len(committed)

    if committed.empty:
        return (
            f"⚠️ {total} 个样本中，信号从未给出方向（全是震荡），无法评估。\n"
            "   请检查信号规则或扩大数据范围。"
        )

    committed = committed[committed["actual"] != NEUTRAL]  # 极罕见：恰好 0 收益
    hr = float(committed["correct"].mean())

    base = pd.Series({
        BULL: float((committed["actual"] == BULL).mean()),
        BEAR: float((committed["actual"] == BEAR).mean()),
    })
    best_name = base.idxmax()
    best_val = float(base.max())
    sk = hr - best_val

    by_signal = committed.groupby("signal").agg(
        样本数=("correct", "size"),
        命中率=("correct", "mean"),
        平均未来收益=("fwd_return", "mean"),
    ).round(4)

    lines = [
        "=" * 62,
        f"回测报告[direction]  股票数={df['code'].nunique()}  持有期={horizon}个交易日",
        f"时间区间  {df['date'].min():%Y-%m-%d} ~ {df['date'].max():%Y-%m-%d}",
        "=" * 62,
        "",
        f"总样本 {total}，其中信号给出方向的 {len(committed)} 个，"
        f"排除震荡 {excluded} 个（{excluded / total:.1%}）",
        "",
        "【核心结论】(只看「敢站队」的样本)",
        f"  给出方向时的命中率  {hr:.4f}",
        f"  最佳朴素基线        {best_val:.4f}  (永远猜{best_name})",
        f"  净胜率 skill        {sk:+.4f}",
        "",
    ]

    if sk <= 0:
        lines.append("  ⚠️  净胜率 <= 0：即使去掉了死角、只算敢站队的时候，")
        lines.append("      依然不优于「无脑一直猜同一个方向」。")
        lines.append("      这排除了「是阈值判定不公平」这个解释。")
    else:
        lines.append(f"  ✅ 净胜率 > 0：信号比朴素基线好 {sk:.2%}。")
    lines.append("")

    lines.append("【朴素基线】(同一子集上)")
    lines.append(f"  永远猜看涨         {base[BULL]:.4f}")
    lines.append(f"  永远猜看跌         {base[BEAR]:.4f}")
    lines.append("")

    lines.append("【按信号分组】")
    lines.append(by_signal.to_string())
    lines.append("")

    lines.append("【按股票】")
    lines.append(per_stock(committed).to_string())
    lines.append("")

    return "\n".join(lines)


def summarize_by_mode(df: pd.DataFrame, horizon: int, threshold: float, mode: str) -> str:
    if mode == "direction":
        return summarize_direction(df, horizon)
    return summarize(df, horizon, threshold)
