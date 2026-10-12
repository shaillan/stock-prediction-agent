# -*- coding: utf-8 -*-
"""
检索质量诊断

要回答的问题：这次检索到底有没有"找对东西"？

为什么不能看相似度距离的绝对值：
  bge 这类句向量模型有"各向异性"——所有句向量都挤在空间里的一个窄锥中，
  于是任意两段文本的余弦距离天然就偏高、天然就接近。再加上同一家公司的
  公告全是中文正式公文，用词高度重合，基线相似度更高。
  所以"0.45 算不算相关"没有通用答案。

看什么才有意义：**gap = 全库距离中位数 − top1 距离**
  也就是"最好的那条比'随便抽一条'好多少"。
  gap 大 → 检索真的把信号挑出来了；gap 小 → 排在前面的和随机抽的差不多。

经验档位（针对本项目的中文公告语料，实测得出）：
  gap > 0.20  检索有效
  gap 0.15~0.20  勉强，可能漏掉真信号
  gap < 0.15  基本是碰运气，等于没检索
"""
from typing import Dict, List, Optional

from .index import DEFAULT_COLLECTION, load_collection, load_embedding_model
from .lexical import rrf_fuse
from .query import _QUERY_PREFIX, _load_corpus


def diagnose(
    question: str,
    persist_dir: str,
    top_k: int = 10,
    model=None,
    collection_name: str = DEFAULT_COLLECTION,
) -> Dict:
    """
    对整个集合算距离分布，判断这次检索有没有分辨力。

    不是只查 top_k —— 而是把全部块的距离都算出来，才能知道
    "最好的那条"在"全库分布"里到底处于什么位置。

    同时给出关键词那一路的冠军和融合后的排名，方便判断
    "是向量没找到，还是关键词救了它"。
    """
    model = model or load_embedding_model()
    q_vec = model.encode([_QUERY_PREFIX + question], normalize_embeddings=True).tolist()

    col = load_collection(persist_dir, collection_name)
    total = col.count()
    if total == 0:
        return {"question": question, "total": 0, "error": "集合为空"}

    res = col.query(
        query_embeddings=q_vec,
        n_results=total,  # 全部算出来，才有分布可比
        include=["documents", "metadatas", "distances"],
    )

    ids = res["ids"][0]
    dists = res["distances"][0]
    metas = res["metadatas"][0]
    doclist = res["documents"][0]

    # 向量排名（query 返回的顺序就是按距离升序）
    vec_rank = {doc_id: r for r, doc_id in enumerate(ids)}
    values = sorted(dists)

    median = values[len(values) // 2]
    top1 = values[0]
    gap = median - top1

    if gap > 0.20:
        verdict = "有效"
    elif gap > 0.15:
        verdict = "勉强"
    else:
        verdict = "失效"

    band = 0.03  # top1 附近多挤
    near = sum(1 for v in values if v <= top1 + band)

    # ---- 关键词这一路 + 融合 ----
    c_ids, c_docs, c_metas, id2idx, bm25 = _load_corpus(persist_dir, collection_name)
    lex_scores = bm25.score(question)
    lex_ranked = sorted(range(len(c_docs)), key=lambda i: -lex_scores[i])

    lex_ranking_ids = [c_ids[i] for i in lex_ranked]
    vec_ranking_ids = list(ids)
    fused_ids = rrf_fuse([vec_ranking_ids, lex_ranking_ids])[:top_k]

    dist_by_id = dict(zip(ids, dists))
    meta_by_id = {c_ids[i]: (c_metas[i] or {}) for i in range(len(c_ids))}
    doc_by_id = dict(zip(c_ids, c_docs))

    lex_rank_by_id = {c_ids[i]: r for r, i in enumerate(lex_ranked)}

    return {
        "question": question,
        "total": total,
        "top1_distance": top1,
        "median_distance": median,
        "max_distance": values[-1],
        "gap": gap,
        "verdict": verdict,
        "near_top1_count": near,
        "vector_top1": (metas[0] or {}).get("title", ""),
        "lexical_top1": c_metas[lex_ranked[0]].get("title", ""),
        "lexical_top1_terms": bm25.explain(question, lex_ranked[0]),
        "hits": [
            {
                "distance": dist_by_id.get(doc_id),
                "bm25": lex_scores[id2idx[doc_id]],
                "vec_rank": vec_rank.get(doc_id),
                "lex_rank": lex_rank_by_id.get(doc_id),
                "title": meta_by_id.get(doc_id, {}).get("title", ""),
                "date": meta_by_id.get(doc_id, {}).get("date", ""),
                "text": doc_by_id.get(doc_id, ""),
            }
            for doc_id in fused_ids
        ],
    }


def render(report: Dict) -> str:
    """把 diagnose() 的结果渲染成给人看的文本"""
    if report.get("error"):
        return f"{report['question']}：{report['error']}"

    lines: List[str] = []
    n = report["total"]
    lines.append(f"问题：{report['question']}")
    lines.append(f"集合共 {n} 块")

    lines.append("")
    lines.append("  【向量这一路】")
    lines.append(f"    top-1 距离 = {report['top1_distance']:.3f}   中位 = {report['median_distance']:.3f}"
                 f"   最差 = {report['max_distance']:.3f}")
    lines.append(
        f"    gap = {report['gap']:.3f}  ->  {report['verdict']}"
        f"   (gap = 中位数 - top1，越大说明向量越能挑出信号)"
    )
    lines.append(f"    距离在 top-1 附近 {0.03} 内挤了 {report['near_top1_count']}/{n} 块"
                 f" ({report['near_top1_count'] / n * 100:.1f}%)")
    lines.append(f"    冠军：《{report['vector_top1'][:44]}》")

    lines.append("")
    lines.append("  【关键词这一路】")
    lines.append(f"    冠军：《{report['lexical_top1'][:44]}》")
    terms = "、".join(f"{t}({s:.2f})" for t, s in report["lexical_top1_terms"])
    lines.append(f"    靠这些词得分：{terms}")

    lines.append("")
    lines.append("  【融合后 top-k】（RRF 把两路排名合并）")
    lines.append(f"    {'文档':<40} {'向量排名':>8} {'词排名':>7} {'向量距离':>8} {'BM25':>7}")
    for i, h in enumerate(report["hits"], 1):
        d = h["distance"]
        d_str = f"{d:.3f}" if d is not None and d == d else "  —  "
        lines.append(
            f"  [{i:>2}] {h['title'][:38]:<40} {h['vec_rank']:>8} {h['lex_rank']:>7} "
            f"{d_str:>8} {h['bm25']:>7.2f}"
        )
    return "\n".join(lines)
