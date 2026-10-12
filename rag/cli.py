# -*- coding: utf-8 -*-
"""
命令行入口

建索引：python -m rag.cli index --code 600519 --start 2026-01-01 --end 2026-10-11
问问题：python -m rag.cli ask "贵州茅台2025年度每股现金分红是多少？"
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


def cmd_index(args):
    from .fetch import fetch_announcements
    from .index import build_index

    cache_file = os.path.join(CACHE_DIR, f"ann_{args.code}.json")
    logger.info(f"拉取 {args.code} 的公告（{args.start} ~ {args.end}）...")
    anns = fetch_announcements(args.code, args.start, args.end, limit=args.limit, cache_file=cache_file)
    logger.info(f"抽到 {len(anns)} 篇公告，开始切块+编码...")

    n_docs, n_chunks = build_index(anns, PERSIST_DIR)
    logger.info(f"✅ 索引完成：{n_docs} 篇公告 → {n_chunks} 个块，存于 {PERSIST_DIR}")


def cmd_ask(args):
    from .query import answer
    print(answer(args.question, PERSIST_DIR, top_k=args.top_k))


def main():
    p = argparse.ArgumentParser(description="公告全文 RAG")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("index", help="拉公告并建索引")
    pi.add_argument("--code", default="600519")
    pi.add_argument("--start", default="2026-01-01")
    pi.add_argument("--end", default="2026-10-11")
    pi.add_argument("--limit", type=int, default=30)
    pi.set_defaults(func=cmd_index)

    pa = sub.add_parser("ask", help="问答")
    pa.add_argument("question")
    pa.add_argument("--top_k", type=int, default=4)
    pa.set_defaults(func=cmd_ask)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
