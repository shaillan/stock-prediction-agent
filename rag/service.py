# -*- coding: utf-8 -*-
"""
RAG 服务层 —— 给预测流水线用的一站式入口

预测流程里没有"用户提问"，RAG 却需要一个 query。
解法：用一组固定的研究问题（减持/回购/业绩预告/重大合同/分红/风险）
对每只股票检索公告片段，拼成一段"公告动态"文本，喂给预测和报告。

对外只有一个函数：build_stock_context(code) -> str
"""
import os
from typing import List, Optional

from loguru import logger

from .fetch import fetch_announcements
from .index import build_index, collection_exists
from .query import retrieve

# 缓存/向量库根目录（cache/ 已 gitignore）
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache", "rag")
PERSIST_DIR = os.path.join(CACHE_DIR, "chroma")

# 固定研究问题：覆盖短期股价最相关的公告类型
DEFAULT_QUESTIONS = [
    "大股东、董监高近期有没有减持或增持股份？",
    "公司近期有没有回购股份的计划或实施结果？",
    "有没有业绩预告、业绩快报或业绩修正公告？",
    "有没有重大合同、中标、对外投资或收购事项？",
    "利润分配或现金分红方案是什么？",
    "有没有诉讼、仲裁、行政处罚或重大风险提示？",
]

_MAX_CHUNKS = 8       # 最终最多保留多少个片段，防止 prompt 过长
_SNIPPET_LEN = 350    # 每段摘要截断长度
_MAX_PER_TITLE = 2    # 同一份公告最多贡献几段，避免它把 8 个名额占满


def build_stock_context(
    code: str,
    end_date: Optional[str] = None,
    questions: Optional[List[str]] = None,
    top_k: int = 3,
    lookback_days: int = 180,
    rebuild: bool = False,
    skip_regular_reports: bool = True,
) -> str:
    """
    返回该股票的"公告动态"文本（markdown）。任何失败都返回 ""，绝不抛异常。

    流程：确保向量库已建 → 对每个固定问题检索 → 去重截断 → 拼成文本

    建索引时丢弃两类噪音文书（`build_index` 的默认口径）：
      定期报告——半年报/年报/季报，占向量库一半以上的块却只贡献数字碎片
      独董模板文书——候选人/提名人声明、述职报告，通篇套话只为"股东"二字而命中
    """
    from datetime import date, timedelta

    end_date = end_date or date.today().strftime("%Y-%m-%d")
    start_date = (date.fromisoformat(end_date) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    collection_name = f"announcements_{code}"

    # ---- 1. 确保索引存在（首次会下 PDF 建索引，之后秒级）----
    # collection_exists 会校验建库口径，口径不符（老版本含定期报告/独董文书）则自动重建
    if rebuild or not collection_exists(
        PERSIST_DIR, collection_name,
        skip_regular_reports=skip_regular_reports, drop_director_docs=True,
    ):
        cache_file = os.path.join(CACHE_DIR, f"ann_{code}.json")
        logger.info(f"📢 [AnnouncementAgent] 建公告索引 {code}（首次较慢）...")
        anns = fetch_announcements(code, start_date, end_date, cache_file=cache_file)
        if not anns:
            logger.info(f"  {code} 近期无公告，跳过")
            return ""
        n_docs, n_chunks = build_index(
            anns, PERSIST_DIR, collection_name=collection_name,
            skip_regular_reports=skip_regular_reports, drop_director_docs=True,
        )
        logger.info(f"  ✅ 索引完成：{n_docs} 篇 → {n_chunks} 块")
        # 语料变了，BM25 缓存作废（否则会拿旧语料的关键词排名去融合）
        from .query import clear_corpus_cache
        clear_corpus_cache()

    # ---- 2. 对每个固定问题检索 ----
    questions = questions or DEFAULT_QUESTIONS
    seen = set()          # 按片段文本去重（不同问题可能命中同一段）
    per_title = {}        # 每份公告已贡献几段，防止单一公告刷屏
    collected = []        # [(标题, 日期, 摘要)]
    for q in questions:
        if len(collected) >= _MAX_CHUNKS:
            break
        try:
            hits = retrieve(q, PERSIST_DIR, top_k=top_k, collection_name=collection_name)
        except Exception as e:
            logger.warning(f"  检索失败（{q[:12]}...）：{type(e).__name__}")
            continue
        for h in hits:
            text = (h.get("text") or "").strip()
            key = text[:80]
            title = h.get("title", "")
            if not text or key in seen:
                continue
            if per_title.get(title, 0) >= _MAX_PER_TITLE:
                continue  # 这份公告已经出过够了，把名额让给别的信号
            seen.add(key)
            per_title[title] = per_title.get(title, 0) + 1
            collected.append((title, h.get("date", ""), text[:_SNIPPET_LEN].replace("\n", " ")))
            if len(collected) >= _MAX_CHUNKS:
                break

    if not collected:
        return ""

    # ---- 3. 拼成 markdown ----
    lines = ["## 公告动态（检索自巨潮资讯公告全文）"]
    for title, dt, snippet in collected:
        lines.append(f"- **《{title}》**（{dt}）：{snippet}…")
    logger.info(f"  📢 [AnnouncementAgent] 命中 {len(collected)} 条公告片段")
    return "\n".join(lines)
