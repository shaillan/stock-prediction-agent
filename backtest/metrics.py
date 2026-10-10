"""
回测评估指标

单看命中率没有意义，必须和朴素基线比 —— A股本身有漂移，"永远猜涨"
或"永远猜震荡"也能拿到不低的分数。真正要看的指标是 skill（净胜率）。
"""
import math

import pandas as pd

from .signals import ALL_CLASSES, BULL, BEAR, NEUTRAL, signal_label

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


# ===================== 多信号对比 =====================

_EMPTY_ROW = {
    "样本数": 0,
    "命中率": float("nan"),
    "最佳基线": float("nan"),
    "净胜率": float("nan"),
    "标准误": float("nan"),
    "t值": float("nan"),
    "站队率": float("nan"),
}


def _with_significance(row: dict, hit: float, n: int) -> dict:
    """
    补上噪声尺子。

    命中率是用 n 个样本估出来的，本身带随机波动：只要样本有限，就算信号
    毫无信息量，命中率也不会正好等于基线。标准误 SE = sqrt(p(1-p)/n) 就是
    这个波动幅度的估计，t = 净胜率 / SE 表示"净胜率是标准误的几倍"。

    经验判据：|t| < 2 基本就是噪声。仅凭"净胜率 > 0"下结论，
    在 n 只有一两千的时候极容易把噪声当成本事。
    """
    se = math.sqrt(max(hit * (1 - hit), 1e-12) / n) if n > 1 else float("nan")
    row["标准误"] = se
    row["t值"] = row["净胜率"] / se if se and se > 0 else float("nan")
    return row


def scorecard_row(df: pd.DataFrame, mode: str, threshold: float) -> dict:
    """
    单个信号的战果：样本数 / 命中率 / 最佳朴素基线 / 净胜率 / 标准误 / t值 / 站队率

    direction 口径下只在「敢站队」的子集上算 —— 对交易来说含糊其辞等于没给
    信号，基线也必须换到同一子集上，两者才可比。
    """
    if df.empty:
        return dict(_EMPTY_ROW)

    if mode == "direction":
        total = len(df)
        d = df[(df["signal"] != NEUTRAL) & (df["actual"] != NEUTRAL)]
        if d.empty:
            return dict(_EMPTY_ROW)

        hit = float(d["correct"].mean())
        bull = float((d["actual"] == BULL).mean())
        bear = float((d["actual"] == BEAR).mean())
        best_val = max(bull, bear)

        row = {
            "样本数": len(d),
            "命中率": hit,
            "最佳基线": best_val,
            "净胜率": hit - best_val,
            "站队率": len(d) / total,
        }
        return _with_significance(row, hit, len(d))

    hit = float(df["correct"].mean())
    best_val = float(baselines(df).max())

    row = {
        "样本数": len(df),
        "命中率": hit,
        "最佳基线": best_val,
        "净胜率": hit - best_val,
        "站队率": float((df["signal"] != NEUTRAL).mean()),
    }
    return _with_significance(row, hit, len(df))


def leaderboard(
    results: dict,
    mode: str,
    threshold: float,
    horizon: int,
    title: str = "",
) -> str:
    """把多个信号按净胜率排成一张榜"""
    if not results or all(df.empty for df in results.values()):
        return "⚠️ 没有回测样本，请检查日期区间与股票代码"

    rows = []
    for name, df in results.items():
        rows.append({"信号": signal_label(name), **scorecard_row(df, mode, threshold)})

    # 按 t值 排序：它把样本量也考虑进去了，比单看净胜率更靠谱
    table = pd.DataFrame(rows).sort_values("t值", ascending=False, na_position="last")

    body = table.to_string(index=False, float_format=lambda v: f"{v:.4f}")
    bar = "=" * max(len(body.splitlines()[0]), 78)

    head = f"信号排行榜[{mode}]  持有期={horizon}个交易日"
    if title:
        head += f"  {title}"

    lines = [bar, head, bar, "", body, ""]
    lines.append("净胜率 = 命中率 − 最佳朴素基线。> 0 才算比「无脑猜一个方向」强。")
    lines.append("t值 = 净胜率 / 标准误。|t| < 2 基本就是噪声 —— 样本有限时，")
    lines.append("       信号毫无信息量也会碰巧得到正的净胜率。")
    lines.append("站队率 = 信号敢给方向（非震荡）的样本占比；太低说明样本少、结论不稳。")
    lines.append("")

    best = table.iloc[0]
    best_t = best["t值"]
    best_skill = best["净胜率"]

    if pd.notna(best_t) and best_t >= 2:
        lines.append(
            f"👉 榜上最强：{best['信号']}，净胜率 {best_skill:+.4f}，t值 {best_t:+.2f} —— 显著。"
        )
        lines.append("   仍需换时间段/股票池复核，谨防是这一段行情的特例。")
    elif pd.notna(best_skill) and best_skill > 0:
        lines.append(
            f"👉 最好的信号是 {best['信号']}（净胜率 {best_skill:+.4f}），"
            f"但 t值只有 {best_t:+.2f}。"
        )
        lines.append("   样本量不足以把它和噪声区分开 —— 此时「榜上有名」没有意义。")
    else:
        lines.append("👉 所有信号的净胜率都 <= 0：这批技术指标规则没有 1-5 日的方向性。")
        lines.append("   顺势和逆势两类都失败 —— 不是「方向做反了」，也不是「参数没调对」。")
    lines.append("")
    return "\n".join(lines)
