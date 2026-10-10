"""
回测入口

用法:
    python -m backtest.run                                  # 全池 30 只，近 3 年
    python -m backtest.run --stocks 600519,000858           # 指定股票
    python -m backtest.run --start 2022-01-01 --end 2024-12-31
    python -m backtest.run --horizon 5 --threshold 0.02
    python -m backtest.run --label direction                # 纯方向口径，无死角
    python -m backtest.run --periods 2019-2021,2022-2024,2024-2026
    python -m backtest.run --output result.csv              # 导出逐时点明细

两种标签口径:
    threshold (默认)  涨超 +阈值才算看涨、跌超 -阈值才算看跌，中间算震荡。
                      贴近"1-5个交易日趋势"的直觉，但死角会让"永远猜震荡"
                      的基线虚高。
    direction         纯方向二分类，涨就是涨、跌就是跌，没有死角。
                      只在信号敢给方向的样本上评估，更公平。

注意: 本回测只使用价格与技术指标，不包含新闻/财务/大盘 —— 后三者的
历史数据接口不可用（只返回最新值），回填会造成前视偏差。
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

# 用绝对导入而非相对导入（from .engine import ...），这样下面两种跑法都成立：
#   python -m backtest.run        （从项目根目录，推荐）
#   python backtest/run.py        （直接跑文件 / IDE 的 Run 按钮）
# 相对导入只在"整个包被一起导入"时可用，直接跑文件会因为找不到父包而报
# ImportError: attempted relative import with no known parent package
from data.stock_registry import StockRegistry
from backtest.engine import WARMUP_BUFFER_DAYS, backtest_universe
from backtest.metrics import summarize_by_mode

DEFAULT_HISTORY_YEARS = 3


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="股票预测信号回测")
    parser.add_argument(
        "--stocks",
        default="",
        help="逗号分隔的股票代码，留空则跑内置 30 只股票池",
    )
    parser.add_argument(
        "--start",
        default="",
        help=f"起始日期 YYYY-MM-DD，默认 {DEFAULT_HISTORY_YEARS} 年前",
    )
    parser.add_argument("--end", default="", help="结束日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--horizon", type=int, default=5, help="持有期（交易日），默认 5")
    parser.add_argument(
        "--threshold", type=float, default=0.02, help="判定涨跌的收益阈值，默认 0.02"
    )
    parser.add_argument(
        "--label",
        choices=("threshold", "direction"),
        default="threshold",
        help="标签口径：threshold(三分类,默认) / direction(纯方向二分类)",
    )
    parser.add_argument(
        "--periods",
        default="",
        help="分段评估，如 2019-2021,2022-2024 或 2020-01-01:2020-12-31。"
             "用于检验结论是否只在某一段行情里成立",
    )
    parser.add_argument("--adjust", default="hfq", help="复权方式，默认 hfq（后复权）")
    parser.add_argument("--output", default="", help="导出逐时点明细的 CSV 路径")
    return parser.parse_args(argv)


def resolve_codes(raw: str) -> list:
    if raw.strip():
        return [c.strip() for c in raw.split(",") if c.strip()]
    return [s["code"] for s in StockRegistry.COMMON_STOCKS]


def parse_periods(raw: str) -> list:
    """'2019-2021,2022-2024' → [('2019-01-01','2021-12-31'), ...]"""
    periods = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            start, end = part.split(":", 1)
        else:
            year_from, year_to = part.split("-", 1)
            start, end = f"{year_from.strip()}-01-01", f"{year_to.strip()}-12-31"
        periods.append((start.strip(), end.strip()))
    return periods


def run_once(codes, start_date, end_date, args, eval_start=None, eval_end=None):
    """跑一次回测并打印报告，返回明细 DataFrame"""
    detail = backtest_universe(
        codes,
        start_date,
        end_date,
        horizon=args.horizon,
        threshold=args.threshold,
        mode=args.label,
        eval_start=eval_start,
        eval_end=eval_end,
        adjust=args.adjust,
    )

    if detail.empty:
        print(f"⚠️ {start_date} ~ {end_date} 没有拿到回测数据，跳过。")
        return detail

    print(summarize_by_mode(detail, horizon=args.horizon, threshold=args.threshold, mode=args.label))
    return detail


def main(argv=None) -> int:
    # Windows 控制台默认 GBK，报表里有 emoji，输出被重定向时会 UnicodeEncodeError
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(errors="replace")
        except Exception:
            pass

    args = parse_args(argv)
    codes = resolve_codes(args.stocks)
    logger.info(f"回测开始: {len(codes)} 只股票, label={args.label}")

    frames = []

    if args.periods:
        periods = parse_periods(args.periods)
        if not periods:
            print("⚠️ --periods 解析为空，请检查格式，例如 2019-2021,2022-2024")
            return 1

        print(f"\n分 {len(periods)} 段评估（每段向前多取 {WARMUP_BUFFER_DAYS} 天预热指标，"
              f"只统计区间内的时点）")
        for period_start, period_end in periods:
            eval_start = pd.Timestamp(period_start)
            eval_end = pd.Timestamp(period_end)
            # 向前多取一段，避免区间开头的 60 天被指标预热吃掉
            fetch_start = (eval_start - pd.Timedelta(days=WARMUP_BUFFER_DAYS)).strftime("%Y-%m-%d")

            print(f"\n\n>>>>>>>>>>>>>>>>>>>>  {period_start} ~ {period_end}  "
                  f"<<<<<<<<<<<<<<<<<<<<\n")
            frames.append(run_once(
                codes, fetch_start, period_end, args,
                eval_start=eval_start, eval_end=eval_end,
            ))
    else:
        end_date = args.end or date.today().strftime("%Y-%m-%d")
        start_date = args.start or (
            date.today() - timedelta(days=365 * DEFAULT_HISTORY_YEARS)
        ).strftime("%Y-%m-%d")
        frames.append(run_once(codes, start_date, end_date, args))

    all_detail = pd.concat([f for f in frames if not f.empty], ignore_index=True) \
        if any(not f.empty for f in frames) else pd.DataFrame()

    if all_detail.empty:
        print("⚠️ 没有拿到任何回测数据。请检查网络 / akshare 是否可用，或换一个日期区间。")
        return 1

    if args.output:
        out = Path(args.output)
        all_detail.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"逐时点明细已导出: {out.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
