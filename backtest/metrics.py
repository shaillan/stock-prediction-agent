"""
回测评估指标

单看命中率没有意义，必须和朴素基线比 —— A股本身有漂移，"永远猜涨"
或"永远猜震荡"也能拿到不低的分数。真正要看的指标是 skill（净胜率）。
"""
import math

import numpy as np
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


def _as_pct(value: float, signed: bool = False) -> str:
    """小数 → 百分比。顺手把 -0.000001 这种「负零」显示成 0"""
    if pd.isna(value):
        return "—"
    value = 0.0 if abs(value) < 5e-5 else value
    return f"{value:+.2%}" if signed else f"{value:.2%}"


def _pct_table(df: pd.DataFrame, cols) -> str:
    """
    把比例列换成百分比字符串再排版——0.3922 对小白不友好，39.22% 才好读。

    同样不用 pandas 的 to_string：中文占两格宽，它对不齐。
    """
    if df.empty:
        return "（没有样本）"

    show = df.copy()
    for c in cols:
        if c in show.columns:
            show[c] = show[c].map(_as_pct)

    headers = [str(show.index.name or "")] + [str(c) for c in show.columns]
    rows = [
        [str(idx)] + [str(v) for v in row]
        for idx, row in zip(show.index, show.values)
    ]
    widths = [
        max([_display_width(h)] + [_display_width(r[i]) for r in rows])
        for i, h in enumerate(headers)
    ]

    lines = [" ".join(_pad(h, widths[i], left=(i == 0)) for i, h in enumerate(headers))]
    lines += [
        " ".join(_pad(v, widths[i], left=(i == 0)) for i, v in enumerate(r))
        for r in rows
    ]
    return "\n".join(lines)


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
        f"  信号命中率          {hr:.2%}   （猜对的比例）",
        f"  最佳基线            {best_base_val:.2%}   （{best_base_name}能拿到的比例）",
        f"  净胜率              {sk:+.2%}   （命中率 − 基线；> 0 才算真有本事）",
        "",
    ]

    if sk <= 0:
        lines.append("  ⚠️  净胜率 ≤ 0：这个信号还不如「不管行情、永远猜同一个方向」。")
        lines.append("      这不是失败，是结论：技术指标规则撑不起 1-5 日的预测。")
        lines.append("      注意：本口径对「敢给方向」的信号有先天惩罚，别单看这一栏 ——")
        lines.append("      排行榜里的「口径 B · 纯方向」才是评判方向能力的公平尺子。")
    else:
        lines.append(f"  ✅ 净胜率 > 0：信号比基线好 {sk:.2%}，但需扩大样本/换时间段再确认。")
    lines.append("")

    lines.append("【基线：永远只猜同一个方向能拿多少分】")
    for name, val in base.items():
        lines.append(f"  {name.replace('always_', '永远猜'):<10} {val:.2%}")
    lines.append("")

    lines.append("【实际结果分布】(震荡占比越高，三分类口径越容易把信号的分压低)")
    for name, val in outcome_distribution(df).items():
        lines.append(f"  {name:<8} {val:.2%}")
    lines.append("")

    lines.append("【按信号分组】")
    lines.append(_pct_table(
        signal_breakdown(df),
        ("命中率", "平均未来收益", "实际看涨占比", "实际看跌占比"),
    ))
    lines.append("")

    lines.append("【按股票】")
    lines.append(_pct_table(per_stock(df), ("命中率", "平均未来收益")))
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
        "【核心结论】(只看「信号敢开口」的样本，这是公平口径)",
        f"  给出方向时的命中率  {hr:.2%}",
        f"  最佳基线            {best_val:.2%}   (永远猜{best_name})",
        f"  净胜率              {sk:+.2%}   （命中率 − 基线）",
        "",
    ]

    if sk <= 0:
        lines.append("  ⚠️  净胜率 ≤ 0：即使去掉震荡死角、只算敢开口的时候，")
        lines.append("      依然不如「无脑一直猜同一个方向」。")
        lines.append("      这就排除了「是三分类判定不公平」这个解释。")
    else:
        lines.append(f"  ✅ 净胜率 > 0：信号比基线好 {sk:.2%}。")
    lines.append("")

    lines.append("【基线】(同一批样本上，永远只猜一个方向)")
    lines.append(f"  永远猜看涨         {base[BULL]:.2%}")
    lines.append(f"  永远猜看跌         {base[BEAR]:.2%}")
    lines.append("")

    lines.append("【按信号分组】")
    lines.append(_pct_table(by_signal, ("命中率", "平均未来收益")))
    lines.append("")

    lines.append("【按股票】")
    lines.append(_pct_table(per_stock(committed), ("命中率", "平均未来收益")))
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
    "理论上限": float("nan"),
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


def relabel(df: pd.DataFrame, mode: str, threshold: float = 0.02) -> pd.DataFrame:
    """
    按指定口径重新打一遍标签（行数不变）。

    为什么需要：scan_signals 只会按一种口径算 actual/correct，但排行榜要同时
    展示两种口径。用 fwd_return 重新判定一次，就能在同一批数据上得到两套
    互相可比的结果，不用把回测跑两遍。
    """
    out = df.copy()
    if out.empty:
        return out
    fwd = out["fwd_return"]
    if mode == "direction":
        out["actual"] = np.where(fwd > 0, BULL, np.where(fwd < 0, BEAR, NEUTRAL))
    else:
        out["actual"] = np.where(
            fwd > threshold, BULL,
            np.where(fwd < -threshold, BEAR, NEUTRAL),
        )
    out["correct"] = out["signal"] == out["actual"]
    return out


def threshold_row(df: pd.DataFrame, threshold: float) -> dict:
    """
    三分类口径的成绩单，多一列「理论上限」。

    为什么必须有「理论上限」：三分类把「涨跌不到 ±阈值」也算成一类（震荡），
    而 A 股一大半时间都在震荡。一个信号越是敢给方向，它撞上震荡的次数就越多，
    命中率就越低 —— 这是口径的数学结果，不是信号的本事。

    上限的算法：假设这个信号「开口时次次都对、闭嘴时刚好都撞上震荡」——
    它能对上的非震荡样本最多是 min(站队率, 实际非震荡占比)，
    再加上 min(闭嘴率, 实际震荡占比) 个震荡样本。连这个上限都低于基线，
    说明这一行的负分是口径给的，换谁来都赢不了，不能当成「信号很差」的证据。
    """
    d = relabel(df, "threshold", threshold)
    if d.empty:
        return dict(_EMPTY_ROW)

    hit = float(d["correct"].mean())
    actual = d["actual"]
    base = float(max((actual == c).mean() for c in CLASS_ORDER))
    commit = float((d["signal"] != NEUTRAL).mean())
    p_neutral = float((actual == NEUTRAL).mean())

    ceiling_hit = min(commit, 1.0 - p_neutral) + min(1.0 - commit, p_neutral)

    row = {
        "样本数": len(d),
        "命中率": hit,
        "最佳基线": base,
        "净胜率": hit - base,
        "理论上限": ceiling_hit - base,
        "站队率": commit,
    }
    return _with_significance(row, hit, len(d))


def direction_row(df: pd.DataFrame) -> dict:
    """
    纯方向口径的成绩单：只在「信号敢给方向」的样本上算命中率，基线也换到
    同一批样本上。这是评判方向判断有没有本事的公平口径。

    为什么排除震荡信号：对交易来说「含糊其辞」等于没给信号。把「不表态」
    算进分母，会让一个从不开口的信号也拿到不低的命中率。
    """
    d = relabel(df, "direction")
    if d.empty:
        return dict(_EMPTY_ROW)

    d = d[(d["signal"] != NEUTRAL) & (d["actual"] != NEUTRAL)]
    if d.empty:
        return dict(_EMPTY_ROW)

    hit = float(d["correct"].mean())
    bull = float((d["actual"] == BULL).mean())
    bear = float((d["actual"] == BEAR).mean())
    base = max(bull, bear)

    row = {
        "样本数": len(d),
        "命中率": hit,
        "最佳基线": base,
        "净胜率": hit - base,
        "站队率": float((df["signal"] != NEUTRAL).mean()),
    }
    return _with_significance(row, hit, len(d))


def scorecard_row(df: pd.DataFrame, mode: str, threshold: float) -> dict:
    """兼容旧调用：按 mode 返回对应口径的成绩单"""
    return direction_row(df) if mode == "direction" else threshold_row(df, threshold)


def _display_width(text: str) -> int:
    """按「显示宽度」算长度：中文/全角占两格，否则列会错位"""
    import unicodedata

    return sum(
        2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        for ch in str(text)
    )


def _pad(text: str, width: int, left: bool = False) -> str:
    gap = " " * max(width - _display_width(text), 0)
    return text + gap if left else gap + text


def _fmt_rows(rows: list, cols: list) -> str:
    """
    把一组成绩单排成表格。

    不用 pandas 的 to_string：它按「字符个数」补空格，中文一个字符占两格，
    结果数字永远对不到表头下面。这里按显示宽度自己补，才对得齐。
    """
    if not rows:
        return "（没有样本）"

    table = pd.DataFrame(rows).sort_values("t值", ascending=False, na_position="last")
    fmt = {
        "样本数": lambda v: f"{v:.0f}",
        "命中率": _as_pct,
        "最佳基线": _as_pct,
        "净胜率": lambda v: _as_pct(v, signed=True),
        "理论上限": lambda v: _as_pct(v, signed=True),
        "站队率": lambda v: _as_pct(v, signed=False),
        "t值": lambda v: f"{v:+.2f}",
    }

    body = [
        [fmt.get(c, str)(row[c]) if pd.notna(row[c]) else "—" for c in cols]
        for _, row in table.iterrows()
    ]
    widths = [
        max([_display_width(c)] + [_display_width(r[i]) for r in body])
        for i, c in enumerate(cols)
    ]
    lefts = [c == "信号" for c in cols]

    lines = [" ".join(_pad(c, widths[i], lefts[i]) for i, c in enumerate(cols))]
    lines += [
        " ".join(_pad(v, widths[i], lefts[i]) for i, v in enumerate(r))
        for r in body
    ]
    return "\n".join(lines)


def leaderboard(
    results: dict,
    mode: str,
    threshold: float,
    horizon: int,
    title: str = "",
    n_stocks: int = 0,
) -> str:
    """
    把多个信号排成一张榜——**两种口径同时打印**。

    为什么必须同时打：三分类口径对「敢给方向」的信号有先天惩罚（市场一大半
    时间在震荡），单看它会把「口径的结构性赤字」误读成「信号全烂」。
    纯方向口径才是评判方向能力的公平尺子。两栏并排，读者才不会看错。

    mode 参数保留只为兼容旧调用，不再影响输出内容。
    """
    if not results or all(df.empty for df in results.values()):
        return "⚠️ 没有回测样本，请检查日期区间与股票代码"

    t_rows, d_rows = [], []
    for name, df in results.items():
        t_rows.append({"信号": signal_label(name), **threshold_row(df, threshold)})
        d_rows.append({"信号": signal_label(name), **direction_row(df)})

    valid = [r for r in d_rows if pd.notna(r["t值"])]
    best = max(valid, key=lambda r: r["t值"]) if valid else None

    head = f"信号排行榜  持有期={horizon}个交易日"
    if n_stocks:
        head += f"  股票 {n_stocks} 只"
    if title:
        head += f"  {title}"
    bar = "=" * max(len(head) + 10, 86)

    lines = [bar, head, bar, ""]

    # ---------- 口径 A ----------
    lines.append(
        f"【口径 A · 三分类】涨超 +{threshold:.1%} 才算看涨，跌超 -{threshold:.1%} 才算看跌，"
        f"涨跌不到 {threshold:.1%} 的算「震荡」"
    )
    lines.append("")
    lines.append(_fmt_rows(
        t_rows,
        ["信号", "样本数", "命中率", "最佳基线", "净胜率", "理论上限", "站队率", "t值"],
    ))
    lines.append("")
    lines.append("  ⚠️ 这一栏不能直接当结论：市场一大半时间在震荡，谁越少开口，谁越容易拿高分。")
    lines.append("     「理论上限」= 假设信号「开口时次次都对、闭嘴时刚好都撞上震荡」，")
    lines.append("     这个口径下它能拿到的最高分。上限是负数的行，就算能预知未来也赢不了——")
    lines.append("     那几行的负分是口径给的，不是信号差。")
    lines.append("")

    # ---------- 口径 B ----------
    lines.append("【口径 B · 纯方向】涨就算涨、跌就算跌，只在信号敢开口的时候比")
    lines.append("")
    lines.append(_fmt_rows(
        d_rows,
        ["信号", "样本数", "命中率", "最佳基线", "净胜率", "站队率", "t值"],
    ))
    lines.append("")
    lines.append("  ✅ 判断「这信号方向准不准」请看这一栏：没有震荡这个死角，")
    lines.append("     基线也换到同一批样本上，两者才公平。")
    lines.append("")

    # ---------- 读表说明 ----------
    lines.append("【三句话读懂】")
    lines.append("  1. 命中率：信号猜对的比例。")
    lines.append("  2. 最佳基线：不管行情、永远只猜同一个方向（比如永远猜震荡）能拿到的命中率。")
    lines.append("     净胜率 = 命中率 − 最佳基线，> 0 才算真比「无脑猜」强，≤ 0 就是白忙。")
    lines.append("  3. t值：净胜率 ÷ 运气波动的幅度。|t| < 2 时，这点优势很可能只是运气，不能当本事。")
    lines.append("     站队率低的信号，样本少，结论更不稳。")
    lines.append("")

    # ---------- 结论 ----------
    if best is None:
        lines.append("👉 所有信号都没给过方向（全程震荡），无法评估。")
    elif best["t值"] >= 2:
        lines.append(
            f"👉 榜上最像样的是「{best['信号']}」：方向命中率 {best['命中率']:.2%}，"
            f"比「永远猜同一个方向」高 {best['净胜率']:+.2%}，t值 {best['t值']:+.2f}（≥2）。"
        )
        lines.append("   暂时不像运气，但只代表这一段行情 —— 换时间段（--periods）复核之前别当真。")
    elif best["净胜率"] > 0:
        lines.append(
            f"👉 榜上最像样的是「{best['信号']}」：方向命中率 {best['命中率']:.2%}，"
            f"比「永远猜同一个方向」高 {best['净胜率']:+.2%}，但 t值只有 {best['t值']:+.2f}（<2）。"
        )
        lines.append("   这点优势还在运气波动的范围里 —— 榜上有名，不等于有本事。")
    else:
        lines.append("👉 全部信号的净胜率都 ≤ 0：这批技术指标规则没有 1-5 个交易日的方向性。")
        lines.append("   顺势和逆势两类都失败 —— 不是「方向做反了」，也不是「参数没调对」。")

    sig_neg = [r for r in valid if r["t值"] <= -2]
    if sig_neg:
        names = "、".join(r["信号"] for r in sig_neg)
        lines.append("")
        lines.append(f"   另有 {len(sig_neg)} 个信号显著为负（{names}）——但「显著为负」不等于")
        lines.append("   「反着做就能赚」：基线本身就不是 50%，反过来之后同样只是回到硬币。")
    lines.append("")
    return "\n".join(lines)
