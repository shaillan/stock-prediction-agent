# -*- coding: utf-8 -*-
"""
预测战绩跟踪 —— 把每次分析的预测存档，到期后自动复盘「对不对」

为什么要有这个模块：
backtest/ 已经证明规则信号没有稳健预测力；LLM 的综合预测是否更好，没人知道
——因为预测说完就扔了。把每次预测存下来、到期和实际走势对照，才能回答观察型
用户最关心的问题：「这个工具可信吗」。

设计要点：
- 存档挂在 run_agent 末尾，写失败只记日志，绝不影响分析主流程
- 同一股票同一天重跑 → 覆盖旧记录（复盘统计不被同日重跑稀释）
- 复盘判据是「预测期结束时的方向」，不是赚多少钱；阈值集中成常量可调
- 震荡不是「不及格」：预测震荡且期内涨跌幅在 ±3% 以内，算方向命中
"""
import json
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

# ===== 判定阈值（集中放这里，README 有解释）=====
_DIRECTION_DEADBAND_PCT = 0.5  # 看涨/看跌的死区：|涨跌幅| 低于它视为「方向没走出来」，算未命中
_SIDEWAYS_BAND_PCT = 3.0       # 「震荡」判定带：期内涨跌幅在 ±3% 以内算命中
_REVIEW_MAX_AGE_DAYS = 60      # 超过这么多天仍拿不到足够K线（如长期停牌）→ 记为复盘失败，不再重试


def _records_path() -> Path:
    """存档路径：相对路径按项目根解析（utils/ 的上一级）"""
    from config import settings
    p = Path(settings.records_file)
    root = Path(__file__).resolve().parent.parent
    return p if p.is_absolute() else root / p


def _parse_horizon_days(period) -> int:
    """『1-5个交易日』→ 5。取上限：按最保守（最长）的等待期复盘"""
    nums = re.findall(r"\d+", str(period or ""))
    return max(int(n) for n in nums) if nums else 5


def _judge_direction(trend: str, change_pct: float) -> Optional[bool]:
    """方向判定。返回 None = 趋势字段异常，无法判定"""
    if trend == "看涨":
        return change_pct > _DIRECTION_DEADBAND_PCT
    if trend == "看跌":
        return change_pct < -_DIRECTION_DEADBAND_PCT
    if trend == "震荡":
        return abs(change_pct) <= _SIDEWAYS_BAND_PCT
    return None


def save_prediction(final_state: dict, records_file=None) -> Optional[dict]:
    """从主图最终状态提取预测存档。同股同日覆盖。返回写入的记录

    返回 None = 状态里没有可存的预测（trend 缺失）。

    records_file: 存档路径（测试用，默认走配置）
    """
    prediction = final_state.get("prediction") or {}
    if not prediction.get("trend"):
        return None

    from agent.sub_agents.prediction_agent import _collect_gaps
    quote = final_state.get("realtime_quote") or {}
    record = {
        "id": uuid.uuid4().hex[:12],
        "stock_code": final_state.get("stock_code", ""),
        "stock_name": final_state.get("stock_name", ""),
        "prediction_date": (final_state.get("end_date") or datetime.now().strftime("%Y-%m-%d"))[:10],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "trend": prediction.get("trend"),
        "confidence": round(float(prediction.get("confidence", 0)), 3),
        "period_text": prediction.get("period", ""),
        "horizon_days": _parse_horizon_days(prediction.get("period")),
        "price_at_prediction": quote.get("price"),
        "target_high": (prediction.get("price_targets") or {}).get("target_high"),
        "gaps": _collect_gaps(final_state),
        "llm_model": final_state.get("llm_model", ""),
        "reasoning_summary": (prediction.get("reasoning_summary") or "")[:300],
        "outcome": None,
    }

    path = Path(records_file) if records_file else _records_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    records = _load(path)
    # 同股同日只留最新一条：复盘统计不该被同日重跑稀释
    records = [r for r in records
               if not (r.get("stock_code") == record["stock_code"]
                       and r.get("prediction_date") == record["prediction_date"])]
    records.append(record)
    _write(path, records)
    return record


def _load(path: Path) -> List[dict]:
    """读 JSONL；坏行跳过（手工编辑/写一半损坏都不能让整个文件读不出来）"""
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning(f"战绩文件有坏行，已跳过: {line[:80]}")
    return records


def _write(path: Path, records: List[dict]) -> None:
    """先写临时文件再原子替换：写一半崩溃不会损坏已有记录"""
    tmp = path.with_suffix(".jsonl.tmp")
    tmp.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def review_pending(kline_client=None, records_file=None, stock_code: str = "") -> Dict:
    """给所有「到期待复盘」的记录补上实际结果

    到期 = 预测日之后已有 >= horizon_days 根日K（按交易日等，不是自然日）。
    K线拉不到（网络/停牌）就跳过，下次再试；超过 _REVIEW_MAX_AGE_DAYS 还拉不到
    就记为复盘失败，不再无限重试。

    Args:
        kline_client: 提供 get_stock_kline 的对象（默认真实 AKShareClient，测试可注入假客户端）
        records_file: 存档路径（测试用，默认走配置）
        stock_code: 只复盘这只股票；空 = 全部
    Returns:
        {"reviewed": n, "skipped": n, "failed": n}
    """
    path = Path(records_file) if records_file else _records_path()
    records = _load(path)
    if not records:
        return {"reviewed": 0, "skipped": 0, "failed": 0}

    if kline_client is None:
        from data.akhare_client import AKShareClient
        kline_client = AKShareClient()

    today = datetime.now().date()
    stats = {"reviewed": 0, "skipped": 0, "failed": 0}
    klines: Dict[str, Optional[List[dict]]] = {}  # 每只股票只拉一次K线

    for rec in records:
        if rec.get("outcome") is not None:
            continue
        if stock_code and rec.get("stock_code") != stock_code:
            continue
        try:
            pred_date = datetime.strptime(rec["prediction_date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        age_days = (today - pred_date).days
        if age_days < 1:
            stats["skipped"] += 1  # 今天刚预测的，至少等一个交易日后才有「期末」可言
            continue

        code = rec["stock_code"]
        if code not in klines:
            end = (today + timedelta(days=1)).strftime("%Y%m%d")
            start = pred_date.strftime("%Y%m%d")
            try:
                df = kline_client.get_stock_kline(code, "daily", start, end)
                klines[code] = df.to_dict(orient="records") if df is not None and not df.empty else []
            except Exception as e:
                logger.warning(f"复盘拉K线失败 {code}: {e}")
                klines[code] = None

        bars = klines[code]
        if bars is None:
            stats["skipped"] += 1
            continue
        # 只取预测日之后的交易日：预测以当日收盘为基准，涨跌从次日数起
        after = [b for b in bars if str(b.get("date"))[:10] > rec["prediction_date"]]
        if len(after) < rec.get("horizon_days", 5):
            if age_days > _REVIEW_MAX_AGE_DAYS:
                rec["outcome"] = {
                    "error": "超过复盘窗口仍拿不到足够K线（长期停牌或数据缺失）",
                    "reviewed_at": datetime.now().isoformat(timespec="seconds"),
                }
                stats["failed"] += 1
            else:
                stats["skipped"] += 1
            continue

        window = after[: rec["horizon_days"]]
        price_end = float(window[-1]["close"])
        price_start = rec.get("price_at_prediction")
        if price_start is None:
            # 预测时行情缺失没存到价格 → 用预测日收盘价兜底
            same_day = [b for b in bars if str(b.get("date"))[:10] == rec["prediction_date"]]
            price_start = float(same_day[-1]["close"]) if same_day else None
        if not price_start:
            rec["outcome"] = {
                "error": "预测时价格缺失，无法计算涨跌",
                "reviewed_at": datetime.now().isoformat(timespec="seconds"),
            }
            stats["failed"] += 1
            continue

        change_pct = round((price_end / price_start - 1) * 100, 2)
        rec["outcome"] = {
            "price_start": round(price_start, 2),
            "price_end": round(price_end, 2),
            "change_pct": change_pct,
            "direction_hit": _judge_direction(rec.get("trend"), change_pct),
            "target_hit": _judge_target(rec, window),
            "window_end": str(window[-1].get("date"))[:10],
            "reviewed_at": datetime.now().isoformat(timespec="seconds"),
        }
        stats["reviewed"] += 1

    _write(path, records)
    return stats


def _judge_target(rec: dict, window: List[dict]) -> Optional[bool]:
    """目标价达成判定：看涨看期内最高收盘 ≥ target_high；看跌看最低收盘 ≤ target_high"""
    target = rec.get("target_high")
    if target is None or rec.get("trend") not in ("看涨", "看跌"):
        return None
    try:
        target = float(target)
    except (TypeError, ValueError):
        return None
    closes = [float(b["close"]) for b in window]
    if rec["trend"] == "看涨":
        return max(closes) >= target
    return min(closes) <= target


def load_records(records_file=None) -> List[dict]:
    """读取全部存档（UI 战绩页用）"""
    return _load(Path(records_file) if records_file else _records_path())


def summarize(records: Optional[List[dict]] = None, records_file=None) -> Dict:
    """战绩汇总：总数、已复盘、方向命中率、目标价达成数、按置信度分箱的校准表

    置信度校准的含义：如果模型的置信度是可信的，那么「置信度 0.6-0.8」这一箱
    的实际命中率就应该落在 60%-80%。两列差得越远，置信度越不可信。
    """
    if records is None:
        records = _load(Path(records_file) if records_file else _records_path())
    reviewed = [r for r in records if (r.get("outcome") or {}).get("direction_hit") is not None]
    hits = [r for r in reviewed if r["outcome"]["direction_hit"]]

    calibration = []
    for lo, hi in ((0, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)):
        grp = [r for r in reviewed if lo <= r.get("confidence", 0) < hi]
        # 空分组给 "—" 而不是 None：纯 None 的列在 st.dataframe 里会显示成
        # 字面量 "None"，看着像程序出错；命中率也统一写成百分比，和上面的指标一致
        rate = (len([r for r in grp if r["outcome"]["direction_hit"]]) / len(grp)
                if grp else None)
        calibration.append({
            "置信度区间": f"{lo:.1f}~{hi:.1f}",
            "样本数": len(grp),
            "实际命中率": f"{rate * 100:.0f}%" if grp else "—",
        })

    return {
        "total": len(records),
        "reviewed": len(reviewed),
        "pending": len([r for r in records if r.get("outcome") is None]),
        "failed": len([r for r in records if (r.get("outcome") or {}).get("error")]),
        "direction_hits": len(hits),
        "hit_rate": round(len(hits) / len(reviewed), 3) if reviewed else None,
        "target_hits": len([r for r in reviewed if r["outcome"].get("target_hit")]),
        "avg_confidence": round(
            sum(r.get("confidence", 0) for r in reviewed) / len(reviewed), 3
        ) if reviewed else None,
        "calibration": calibration,
    }
