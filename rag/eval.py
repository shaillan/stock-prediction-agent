# -*- coding: utf-8 -*-
"""检索评测：用标注集算召回率 / 准确率 / MRR

用法:
    python -m rag.eval                                  # 默认跑 rag/gold_600519.jsonl
    python -m rag.eval --suite rag/gold_600519.jsonl
    python -m rag.eval --top-k 3 --no-hybrid            # 对照：纯向量 vs 混合
    python -m rag.eval --case 回购 --limit 3            # 只跑子集
    python -m rag.eval --min-recall 0.8                 # 低于阈值时退出码 1

标注集一行一条（JSONL）:
    {"id": "dividend-1",
     "question": "今年每股分红是多少，方案调整过吗？",
     "stock_code": "600519",
     "gold_docs": [{"title": "贵州茅台2025年年度权益分派实施公告", "date": "2026-06-22"}],
     "note": "为什么这个问题该命中这份公告"}

口径说明（重要）:
- 评测单位是「公告」，不是「块」。检索返回的是块，同一份公告可能占多个块，
  计算前按标题去重。
- Recall@k = 命中的 gold 公告数 / 该问题全部 gold 公告数（分母是问题需要的全部）
- Precision@k = 命中的 gold 公告数 / 前 k 块里去重后的公告数（不是除以 k：
  同一份公告占 3 个块时，按 k 算会凭空扣分）
- MRR = 第一个 gold 公告出现在第几块，取倒数后平均
- 只算检索，不调 LLM、不算生成质量
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.query import retrieve
from rag.service import PERSIST_DIR

DEFAULT_SUITE = Path(__file__).parent / "gold_600519.jsonl"
REPORT_DIR = Path("runs/evals")


def normalize_title(title: str) -> str:
    """统一标题格式：去高亮标签、书名号、全角空格，压缩空白"""
    text = (title or "").replace("<em>", "").replace("</em>", "")
    text = text.replace("《", "").replace("》", "").replace("　", " ")
    return " ".join(text.split())


def load_suite(path) -> List[dict]:
    """读 JSONL；空行和 # 注释跳过，坏行带行号报错"""
    cases: List[dict] = []
    with Path(path).open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno} JSON 解析失败：{exc}") from exc
            if not case.get("question") or not case.get("gold_docs"):
                raise ValueError(f"{path}:{lineno} 缺少 question 或 gold_docs")
            case.setdefault("id", f"case-{lineno}")
            cases.append(case)
    return cases


def _collection_for(case: dict, override: Optional[str]) -> str:
    if override:
        return override
    if case.get("collection"):
        return case["collection"]
    code = case.get("stock_code")
    if not code:
        raise ValueError(f"用例 {case.get('id')} 没有 stock_code，也没在命令行指定 --collection")
    return f"announcements_{code}"


def evaluate_case(case: dict, hits: List[dict], k: int) -> dict:
    """对一条用例算 Recall@k / Precision@k / Hit@k / RR（文档级）"""
    gold: List[str] = []
    for item in case.get("gold_docs") or []:
        raw = item.get("title") if isinstance(item, dict) else item
        title = normalize_title(raw)
        if title and title not in gold:
            gold.append(title)
    gold_set = set(gold)

    top = (hits or [])[:k]
    ranked: List[str] = []
    for hit in top:
        title = normalize_title(hit.get("title"))
        if title and title not in ranked:
            ranked.append(title)

    matched = [t for t in ranked if t in gold_set]
    missed = [t for t in gold if t not in ranked]

    rr = 0.0
    for rank, hit in enumerate(top, 1):
        if normalize_title(hit.get("title")) in gold_set:
            rr = 1.0 / rank
            break

    return {
        "id": case.get("id"),
        "question": case.get("question"),
        "gold": gold,
        "matched": matched,
        "missed": missed,
        "top_titles": ranked,
        "recall": len(matched) / len(gold) if gold else 0.0,
        "precision": len(matched) / len(ranked) if ranked else 0.0,
        "hit": 1.0 if matched else 0.0,
        "rr": rr,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="公告检索评测（召回率 / 准确率）")
    parser.add_argument("--suite", default=str(DEFAULT_SUITE), help="标注集 JSONL")
    parser.add_argument("--collection", default=None,
                        help="集合名；不传则按用例的 stock_code 生成 announcements_{code}")
    parser.add_argument("--top-k", type=int, default=3, help="取前 k 块（默认 3）")
    parser.add_argument("--no-hybrid", action="store_true",
                        help="退回纯向量检索，用来和混合检索对照")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条")
    parser.add_argument("--case", default="", help="按 id 子串过滤")
    parser.add_argument("--out", default="", help="报告路径；默认 runs/evals/rag_<时间戳>.json")
    parser.add_argument("--min-recall", type=float, default=0.0,
                        help="macro Recall 低于该值时退出码 1（默认不设阈值）")
    return parser.parse_args(argv)


def select_cases(cases: List[dict], case_filter: str = "", limit: int = 0) -> List[dict]:
    if case_filter:
        cases = [c for c in cases if case_filter in str(c.get("id", ""))]
    if limit and limit > 0:
        cases = cases[:limit]
    return cases


def run_case(case: dict, args) -> dict:
    collection = _collection_for(case, args.collection)
    hits = retrieve(
        case["question"], PERSIST_DIR,
        top_k=args.top_k, collection_name=collection,
        hybrid=not args.no_hybrid,
    )
    result = evaluate_case(case, hits, args.top_k)
    result["collection"] = collection
    result["hits"] = [
        {"title": h.get("title"), "date": h.get("date"),
         "distance": h.get("distance"), "bm25": h.get("bm25"),
         "text": (h.get("text") or "")[:200]}
        for h in hits
    ]
    return result


def summarize(results: List[dict]) -> dict:
    valid = [r for r in results if not r.get("error")]
    n = len(valid)
    gold_total = sum(len(r["gold"]) for r in valid)
    gold_matched = sum(len(r["matched"]) for r in valid)
    return {
        "questions": n,
        "errors": len(results) - n,
        "recall": sum(r["recall"] for r in valid) / n if n else 0.0,
        "precision": sum(r["precision"] for r in valid) / n if n else 0.0,
        "hit": sum(r["hit"] for r in valid) / n if n else 0.0,
        "mrr": sum(r["rr"] for r in valid) / n if n else 0.0,
        "micro_recall": gold_matched / gold_total if gold_total else 0.0,
        "gold_total": gold_total,
        "gold_matched": gold_matched,
    }


def render_case(result: dict) -> List[str]:
    if result.get("error"):
        return [f"❌ [{result.get('id')}] 运行失败：{result['error']}"]
    icon = "✅" if not result["missed"] else ("🟡" if result["matched"] else "❌")
    lines = [
        f"{icon} [{result['id']}] Recall {result['recall']:.2f} · "
        f"P {result['precision']:.2f} · RR {result['rr']:.2f}  {result['question']}"
    ]
    if result["missed"]:
        for title in result["missed"]:
            lines.append(f"     ✗ 缺：《{title}》")
        top = "、".join(f"《{t}》" for t in result["top_titles"]) or "（无结果）"
        lines.append(f"       实际 top：{top}")
    return lines


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # Windows GBK 控制台防 emoji 崩
        except Exception:  # noqa: BLE001
            pass

    args = parse_args(argv)
    cases = select_cases(load_suite(args.suite), args.case, args.limit)
    if not cases:
        print(f"⚠️ 没有匹配的用例：{args.suite}")
        return 1

    from rag.index import EmbeddingModelMissing, ensure_embedding_model, load_collection

    try:
        ensure_embedding_model()
    except EmbeddingModelMissing as exc:
        print(f"⚠️ {exc}")
        return 2

    collections = sorted({_collection_for(c, args.collection) for c in cases})
    for name in collections:
        try:
            count = load_collection(PERSIST_DIR, name).count()
        except Exception:  # noqa: BLE001
            print(f"⚠️ 集合 {name} 不存在。先建库："
                  f"python -m rag.cli index --code 600519 --start 2026-01-01 --end 2026-10-11")
            return 2
        if count == 0:
            print(f"⚠️ 集合 {name} 是空的，请先重建")
            return 2

    hybrid = not args.no_hybrid
    print(f"\n🧪 检索评测：{len(cases)} 条（top_k={args.top_k}，"
          f"hybrid={hybrid}，集合 {', '.join(collections)}）\n")

    results: List[dict] = []
    for case in cases:
        try:
            result = run_case(case, args)
        except Exception as exc:  # noqa: BLE001 —— 一条失败不拖垮整批
            result = {"id": case.get("id"), "question": case.get("question"),
                      "error": f"{type(exc).__name__}: {exc}"}
        results.append(result)
        for line in render_case(result):
            print(line)

    summary = summarize(results)
    k = args.top_k
    print("\n" + "=" * 60)
    print(f"Recall@{k}    = {summary['recall']:.2f}（macro） / "
          f"{summary['micro_recall']:.2f}（micro：{summary['gold_matched']}/{summary['gold_total']}）")
    print(f"Precision@{k} = {summary['precision']:.2f} · Hit@{k} = {summary['hit']:.2f} · "
          f"MRR = {summary['mrr']:.2f}")
    if summary["errors"]:
        print(f"⚠️ 有 {summary['errors']} 条运行失败，已排除在汇总外")

    report_dir = Path(args.out).parent if args.out else REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(args.out) if args.out else REPORT_DIR / f"rag_{stamp}.json"
    report_path.write_text(json.dumps({
        "suite": str(args.suite),
        "collections": collections,
        "top_k": args.top_k,
        "hybrid": hybrid,
        "summary": summary,
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告：{report_path}")

    if args.min_recall and summary["recall"] < args.min_recall:
        print(f"⚠️ macro Recall {summary['recall']:.2f} 低于阈值 {args.min_recall:.2f}")
        return 1
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
