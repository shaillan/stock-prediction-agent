# -*- coding: utf-8 -*-
"""
命令行入口

建索引：  python -m rag.cli index --code 600519 --start 2026-01-01 --end 2026-10-11
问问题：  python -m rag.cli ask "贵州茅台2025年度每股现金分红是多少？"
看检索：  python -m rag.cli retrieve "分红方案是什么？" --code 600519
看全部：  python -m rag.cli collections
看喂给：  python -m rag.cli context --code 600519
"""
import argparse
import os
import sys

# Windows 控制台默认 GBK，中文/emoji 会乱码或崩溃，统一转成 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from loguru import logger

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache", "rag")
PERSIST_DIR = os.path.join(CACHE_DIR, "chroma")


def _resolve_collection(args) -> str:
    """
    决定查哪个集合。流水线按股票分集合存（announcements_600519），
    CLI 的 index 命令存在默认集合里——两者不是同一个，所以必须让用户能指定，
    否则会出现"明明建过索引却查不到"的困惑。
    """
    from .index import DEFAULT_COLLECTION

    if getattr(args, "collection", None):
        return args.collection
    if getattr(args, "code", None):
        return f"announcements_{args.code}"
    return DEFAULT_COLLECTION


def cmd_index(args):
    from .fetch import fetch_announcements
    from .index import build_index

    cache_file = os.path.join(CACHE_DIR, f"ann_{args.code}.json")
    logger.info(f"拉取 {args.code} 的公告（{args.start} ~ {args.end}）...")
    anns = fetch_announcements(args.code, args.start, args.end, limit=args.limit, cache_file=cache_file)
    logger.info(f"抽到 {len(anns)} 篇公告，开始切块+编码...")

    n_docs, n_chunks = build_index(
        anns, PERSIST_DIR, collection_name=_resolve_collection(args),
        skip_regular_reports=not args.keep_reports,
    )
    logger.info(f"✅ 索引完成：{n_docs} 篇公告 → {n_chunks} 个块，存于 {PERSIST_DIR}")


def cmd_ask(args):
    from .query import answer
    print(answer(args.question, PERSIST_DIR, top_k=args.top_k,
                 collection_name=_resolve_collection(args)))


def cmd_retrieve(args):
    """只做检索、不调 LLM —— 用来单独检验检索质量"""
    from .query import retrieve

    col_name = _resolve_collection(args)
    hits = retrieve(args.question, PERSIST_DIR, top_k=args.top_k, collection_name=col_name,
                    hybrid=not args.vector_only)

    print(f"\n查询：{args.question}")
    print(f"集合：{col_name}   模式：{'纯向量' if args.vector_only else '混合检索(向量+关键词)'}\n")
    for i, h in enumerate(hits, 1):
        d = h.get("distance")
        d_str = f"距离={d:.4f}" if d is not None and d == d else "距离=—"
        b = h.get("bm25")
        b_str = f"  关键词={b:.2f}" if b else ""
        print(f"[{i}] {d_str}{b_str}  《{h['title']}》({h['date']})")
        print(f"    {h['text'][:300].replace(chr(10), ' ')}")
        print()


def cmd_collections(args):
    """列出向量库里所有集合及块数——确认某只股票到底建没建索引"""
    import chromadb

    client = chromadb.PersistentClient(path=PERSIST_DIR)
    cols = client.list_collections()
    if not cols:
        print(f"向量库为空：{PERSIST_DIR}")
        return
    print(f"\n向量库：{PERSIST_DIR}\n")
    for col in cols:
        print(f"  {col.name:<28} {col.count():>6} 块")
    print()


def cmd_context(args):
    """打印流水线实际喂给预测 LLM 的那段"公告动态"文本（含检索命中数）"""
    from .service import build_stock_context

    text = build_stock_context(
        args.code, end_date=args.end, rebuild=args.rebuild,
        skip_regular_reports=not args.keep_reports,
    )
    if not text:
        print(f"\n{args.code}：未检索到任何公告片段（可能近期无公告，或索引为空）\n")
        return
    print(f"\n===== {args.code} 的公告动态（{text.count('- **《')} 条）=====\n")
    print(text)
    print()


def cmd_diagnose(args):
    """对一个集合算距离分布，判断这次检索有没有分辨力（见 rag/diagnose.py）"""
    from .diagnose import diagnose, render

    col_name = _resolve_collection(args)
    report = diagnose(args.question, PERSIST_DIR, top_k=args.top_k, collection_name=col_name)
    print(f"\n集合：{col_name}")
    print(render(report))
    print()


def main():
    p = argparse.ArgumentParser(description="公告全文 RAG")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("index", help="拉公告并建索引")
    pi.add_argument("--code", default="600519")
    pi.add_argument("--start", default="2026-01-01")
    pi.add_argument("--end", default="2026-10-11")
    pi.add_argument("--limit", type=int, default=30)
    pi.add_argument("--collection", help="集合名；不传则按 --code 生成 announcements_{code}")
    pi.add_argument("--keep-reports", action="store_true",
                    help="保留半年报/年报/季报（默认丢弃；要查营收等财务数字时才需要）")
    pi.set_defaults(func=cmd_index)

    pa = sub.add_parser("ask", help="检索 + LLM 回答")
    pa.add_argument("question")
    pa.add_argument("--top_k", type=int, default=4)
    pa.add_argument("--code", help="股票代码，查该股流水线建的集合")
    pa.add_argument("--collection", help="直接指定集合名（优先级高于 --code）")
    pa.set_defaults(func=cmd_ask)

    pr = sub.add_parser("retrieve", help="只看检索命中（不调 LLM，不花 token）")
    pr.add_argument("question")
    pr.add_argument("--top_k", type=int, default=5)
    pr.add_argument("--code", help="股票代码")
    pr.add_argument("--collection", help="直接指定集合名")
    pr.add_argument("--vector-only", action="store_true",
                    help="退回纯向量检索，用来和混合检索做对照")
    pr.set_defaults(func=cmd_retrieve)

    pc = sub.add_parser("collections", help="列出所有集合和块数")
    pc.set_defaults(func=cmd_collections)

    px = sub.add_parser("context", help="打印喂给预测 LLM 的公告动态文本")
    px.add_argument("--code", default="600519")
    px.add_argument("--end", help="截止日期 YYYY-MM-DD，默认今天")
    px.add_argument("--rebuild", action="store_true", help="强制重建索引（重新下 PDF）")
    px.add_argument("--keep-reports", action="store_true", help="保留半年报/年报/季报")
    px.set_defaults(func=cmd_context)

    pd = sub.add_parser("diagnose", help="诊断检索有没有分辨力（看 gap）")
    pd.add_argument("question")
    pd.add_argument("--top_k", type=int, default=10)
    pd.add_argument("--code", help="股票代码")
    pd.add_argument("--collection", help="直接指定集合名")
    pd.set_defaults(func=cmd_diagnose)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
