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
from typing import Dict, List, NamedTuple

from .index import DEFAULT_COLLECTION, load_collection, load_embedding_model
from .lexical import BM25, expand_query, parse_date_hint, rrf_scores

# bge v1.5 建议：查询句前面加这个指令，检索效果更好
_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

# 融合前每路各取多少条候选。取少了 BM25 捞到的长尾进不了融合，取多了白算。
_POOL = 50


class Corpus(NamedTuple):
    """一次加载、反复复用的全库视图"""
    ids: List[str]
    docs: List[str]
    metas: List[dict]
    id2idx: Dict[str, int]
    bm25: BM25                 # 正文关键词
    title_bm25: BM25           # 标题关键词（一份公告一条，不按块重复）
    doc_of_chunk: List[int]    # 每个块属于哪个标题
    chunks_by_doc: Dict[int, List[int]]  # 标题 → 它名下所有块的下标


@lru_cache(maxsize=8)
def _load_corpus(persist_dir: str, collection_name: str) -> Corpus:
    """
    读全库文档并建好 BM25 索引，缓存起来。

    为什么要缓存：流水线一次要跑 6 个固定问题，BM25 建索引（含 jieba 分词）
    每问一次重建 6 次是纯浪费。集合内容变了要调 clear_corpus_cache()。

    这里额外建一份"标题 BM25"：标题只在 metadata 里，正文往往一次都不出现
    （例如《重大事项公告》的正文不会再说"重大事项"），不给它单独建索引，
    这类问题就永远捞不上来。
    """
    col = load_collection(persist_dir, collection_name)
    data = col.get(include=["documents", "metadatas"])
    ids, docs, metas = data["ids"], data["documents"], data["metadatas"]
    id2idx = {doc_id: i for i, doc_id in enumerate(ids)}

    title_to_idx: Dict[str, int] = {}
    title_texts: List[str] = []
    doc_of_chunk: List[int] = []
    chunks_by_doc: Dict[int, List[int]] = {}
    for ci, meta in enumerate(metas):
        title = (meta or {}).get("title", "")
        ti = title_to_idx.get(title)
        if ti is None:
            ti = len(title_texts)
            title_to_idx[title] = ti
            title_texts.append(title)
        doc_of_chunk.append(ti)
        chunks_by_doc.setdefault(ti, []).append(ci)

    return Corpus(
        ids=ids,
        docs=docs,
        metas=metas,
        id2idx=id2idx,
        bm25=BM25(docs),
        title_bm25=BM25(title_texts),
        doc_of_chunk=doc_of_chunk,
        chunks_by_doc=chunks_by_doc,
    )


def clear_corpus_cache() -> None:
    """重建索引后必须调用，否则 BM25 还缓存着旧语料"""
    _load_corpus.cache_clear()


# 以下三个权重都以"RRF 第 1 名的分数 1/k"为单位：
# 标题满分 ≈ 额外赢下一路检索的第 1 名，日期命中 ≈ 半路。
_RRF_K = 60
_TITLE_BOOST = 0.6
_DATE_BOOST = 0.5
_TITLE_MIN_RATIO = 0.5  # 标题得分不到最高分一半的，不算命中


def _diversify(ranked: List[int], titles: List[str], top_k: int) -> List[int]:
    """给同一份公告设名额上限：先每篇 1 块，再放宽到 2 块，最后兜底填满。

    为什么需要：一份 19 块的公告可以把 top-3 全部占满（实测《法律意见书》
    就干过），别的公告再相关也露不出脸。
    最后一轮用 top_k 兜底，是防止整个库只有一两份公告时返回不足 k 条。
    """
    max_per_title = max(2, top_k // 5)
    picked: List[int] = []
    counts: Dict[str, int] = {}
    for limit in (1, max_per_title, top_k):
        for idx in ranked:
            if idx in picked:
                continue
            title = titles[idx]
            if counts.get(title, 0) >= limit:
                continue
            picked.append(idx)
            counts[title] = counts.get(title, 0) + 1
            if len(picked) >= top_k:
                return picked
    return picked


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

    混合模式下比单纯 RRF 多做了三件事（都不需要重建索引）：
      1. 同义词扩展，只作用于关键词/标题两路，向量仍用原句；
      2. 标题单独建 BM25：正文里不出现、标题里才有的词（"重大事项"）也能命中；
      3. 问题里提到"7月"这类日期时，给当月公告软加权（不做硬过滤）。
    最后按"每份公告最多占几个名额"做一次多样性重排。
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

    vec_titles = [(m or {}).get("title", "") for m in vec_metas]

    if not hybrid:
        order = _diversify(list(range(len(vec_ids))), vec_titles, top_k)
        return [
            {
                "text": vec_docs[i],
                "title": vec_titles[i],
                "date": (vec_metas[i] or {}).get("date", ""),
                "distance": vec_dists[i],  # 越小越相似
                "bm25": None,
            }
            for i in order
        ]

    corpus = _load_corpus(persist_dir, collection_name)
    lex_query = expand_query(question)
    lex_scores = corpus.bm25.score(lex_query)
    lex_top = sorted(range(len(corpus.docs)), key=lambda i: -lex_scores[i])[:pool]

    dist_by_idx = {corpus.id2idx[i]: d for i, d in zip(vec_ids, vec_dists) if i in corpus.id2idx}

    scores = rrf_scores(
        [[corpus.id2idx[i] for i in vec_ids if i in corpus.id2idx], lex_top],
        k=_RRF_K,
    )
    unit = 1.0 / _RRF_K

    # 标题这一路：只给标题得分接近最高分的文档加分，
    # 否则"股东""公告"这种通用词会把半库都抬上来。
    title_scores = corpus.title_bm25.score(lex_query)
    top_title = max(title_scores) if title_scores else 0.0
    if top_title > 0:
        for ti, score in enumerate(title_scores):
            if score <= 0 or score < _TITLE_MIN_RATIO * top_title:
                continue
            bonus = _TITLE_BOOST * (score / top_title) * unit
            for ci in corpus.chunks_by_doc.get(ti, ()):
                scores[ci] = scores.get(ci, 0.0) + bonus

    # 日期这一路：软加权。硬过滤会误杀"一季度"（公告 4 月才发）。
    year, month = parse_date_hint(question)
    if month or year:
        for ci in list(scores):
            date = (corpus.metas[ci] or {}).get("date", "")
            if not date:
                continue
            if month and date[5:7] != month:
                continue
            if year and date[:4] != year:
                continue
            scores[ci] += _DATE_BOOST * unit

    ranked = sorted(scores, key=lambda i: -scores[i])
    titles = [(m or {}).get("title", "") for m in corpus.metas]
    picked = _diversify(ranked, titles, top_k)

    return [
        {
            "text": corpus.docs[i],
            "title": titles[i],
            "date": (corpus.metas[i] or {}).get("date", ""),
            "distance": dist_by_idx.get(i, float("nan")),  # 纯关键词捞上来的可能没向量距离
            "bm25": lex_scores[i],
        }
        for i in picked
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
