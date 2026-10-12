# -*- coding: utf-8 -*-
"""
第3步 检索 + 第4步 生成

检索：**混合检索**（向量 + 关键词），两路结果用 RRF 融合。
生成：把这些片段 + 问题 拼进 prompt，让 LLM 据实回答。

为什么不是纯向量——实测：
  问"大股东有没有减持或增持？"，答案文档《关于回购股份实施结果暨股份变动的公告》
  里写着"控股股东…累计增持1,274,234股…未减持"，纯向量检索却**连 top-10 都进不去**；
  top-10 被《股东会通知》《独董声明》占满（只含"股东"二字，主题相关但答非所问）。

  向量匹配的是**主题**，关键词（BM25）匹配的是**词**。两者互补：
  向量懂"意思相近"，BM25 懂"减持/增持这种精确词确实出现了"。
  加上关键词这一路后，同一问题该文档从"榜上无名"升到**第 1 名**。

详见 rag/lexical.py 与 rag/TUTORIAL.md。
"""
from functools import lru_cache
from typing import List, Tuple

from .index import DEFAULT_COLLECTION, load_collection, load_embedding_model
from .lexical import BM25, rrf_fuse

# bge v1.5 建议：查询句前面加这个指令，检索效果更好
_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

# 融合前每路各取多少条候选。取少了 BM25 捞到的长尾进不了融合，取多了白算。
_POOL = 50


@lru_cache(maxsize=8)
def _load_corpus(persist_dir: str, collection_name: str) -> Tuple:
    """
    读全库文档并建好 BM25 索引，缓存起来。

    为什么要缓存：流水线一次要跑 6 个固定问题，BM25 建索引（含 jieba 分词）
    每问一次重建 6 次是纯浪费。集合内容变了要调 clear_corpus_cache()。
    """
    col = load_collection(persist_dir, collection_name)
    data = col.get(include=["documents", "metadatas"])
    ids, docs, metas = data["ids"], data["documents"], data["metadatas"]
    id2idx = {doc_id: i for i, doc_id in enumerate(ids)}
    return ids, docs, metas, id2idx, BM25(docs)


def clear_corpus_cache() -> None:
    """重建索引后必须调用，否则 BM25 还缓存着旧语料"""
    _load_corpus.cache_clear()


def retrieve(
    question: str,
    persist_dir: str,
    top_k: int = 4,
    model=None,
    collection_name: str = DEFAULT_COLLECTION,
    hybrid: bool = True,
) -> List[dict]:
    """
    返回最相关的 top_k 个片段，附标题、日期、相似度距离、（混合检索时的）BM25 得分。

    hybrid=True 走"向量 + 关键词"融合；False 则退回纯向量（用来做对照）。
    """
    collection = load_collection(persist_dir, collection_name)
    total = collection.count()
    if total == 0:
        return []

    model = model or load_embedding_model()
    q_vec = model.encode([_QUERY_PREFIX + question], normalize_embeddings=True).tolist()

    pool = min(max(_POOL, top_k), total)
    res = collection.query(
        query_embeddings=q_vec,
        n_results=pool,
        include=["documents", "metadatas", "distances"],
    )
    vec_ids = res["ids"][0]
    vec_dists = res["distances"][0]
    vec_docs = res["documents"][0]
    vec_metas = res["metadatas"][0]

    vec_hits = [
        {
            "text": vec_docs[i],
            "title": (vec_metas[i] or {}).get("title", ""),
            "date": (vec_metas[i] or {}).get("date", ""),
            "distance": vec_dists[i],  # 越小越相似
            "bm25": None,
        }
        for i in range(len(vec_ids))
    ]

    if not hybrid:
        return vec_hits[:top_k]

    # ---- 关键词这一路 ----
    ids, docs, metas, id2idx, bm25 = _load_corpus(persist_dir, collection_name)
    lex_scores = bm25.score(question)
    lex_top = sorted(range(len(docs)), key=lambda i: -lex_scores[i])[:pool]

    dist_by_idx = {id2idx[i]: d for i, d in zip(vec_ids, vec_dists) if i in id2idx}

    # RRF 融合两路排名
    fused = rrf_fuse([[id2idx[i] for i in vec_ids if i in id2idx], lex_top])[:top_k]

    return [
        {
            "text": docs[i],
            "title": (metas[i] or {}).get("title", ""),
            "date": (metas[i] or {}).get("date", ""),
            "distance": dist_by_idx.get(i, float("nan")),  # 纯关键词捞上来的可能没向量距离
            "bm25": lex_scores[i],
        }
        for i in fused
    ]


def answer(question: str, persist_dir: str, top_k: int = 4, llm=None,
           collection_name: str = DEFAULT_COLLECTION, hybrid: bool = True) -> str:
    """检索 + 生成，返回最终回答文本"""
    hits = retrieve(question, persist_dir, top_k=top_k, collection_name=collection_name,
                    hybrid=hybrid)

    # 拼检索到的片段
    context_parts = []
    for i, h in enumerate(hits, 1):
        context_parts.append(f"[片段{i}] 《{h['title']}》({h['date']})\n{h['text']}")
    context = "\n\n".join(context_parts)

    prompt = (
        "你是股票研究助手。请只根据下面这些公告原文回答用户问题。\n"
        "如果原文里没有答案，就明确说「公告中未提及」，不要编造。\n\n"
        f"{context}\n\n"
        f"用户问题：{question}\n"
        "回答（如果引用数字，请注明出自哪份公告）："
    )

    # 复用项目现有的 LLM 工厂（DeepSeek，读 .env 的 key）
    if llm is None:
        from utils.llm_factory import create_chat_model
        llm = create_chat_model(temperature=0.0)

    response = llm.invoke(prompt)
    text = response.content if hasattr(response, "content") else str(response)

    # 附带展示"命中了哪些片段"，让人能核查
    def _desc(h):
        parts = []
        d = h.get("distance")
        if d is not None and d == d:  # 非 NaN
            parts.append(f"向量距离={d:.3f}")
        b = h.get("bm25")
        if b:
            parts.append(f"关键词得分={b:.2f}")
        return "、".join(parts) or "—"

    sources = "\n".join(
        f"  - 《{h['title']}》({h['date']}) {_desc(h)}"
        for h in hits
    )
    return f"{text}\n\n---\n【依据片段】\n{sources}"
