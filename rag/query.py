# -*- coding: utf-8 -*-
"""
第3步 检索 + 第4步 生成

检索：把用户问题也编码成向量，在向量库里找"距离最近"的几个片段。
生成：把这些片段 + 问题 拼进 prompt，让 LLM 据实回答。
"""
from typing import List

from .index import DEFAULT_COLLECTION, load_collection, load_embedding_model

# bge v1.5 建议：查询句前面加这个指令，检索效果更好
_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


def retrieve(
    question: str,
    persist_dir: str,
    top_k: int = 4,
    model=None,
    collection_name: str = DEFAULT_COLLECTION,
) -> List[dict]:
    """返回最相关的 top_k 个片段，附标题、日期、相似度"""
    model = model or load_embedding_model()
    q_vec = model.encode([_QUERY_PREFIX + question], normalize_embeddings=True).tolist()

    collection = load_collection(persist_dir, collection_name)
    res = collection.query(
        query_embeddings=q_vec,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for i in range(len(res["documents"][0])):
        meta = res["metadatas"][0][i]
        hits.append({
            "text": res["documents"][0][i],
            "title": meta.get("title", ""),
            "date": meta.get("date", ""),
            "distance": res["distances"][0][i],  # 越小越相似
        })
    return hits


def answer(question: str, persist_dir: str, top_k: int = 4, llm=None,
           collection_name: str = DEFAULT_COLLECTION) -> str:
    """检索 + 生成，返回最终回答文本"""
    hits = retrieve(question, persist_dir, top_k=top_k, collection_name=collection_name)

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
    sources = "\n".join(
        f"  - 《{h['title']}》({h['date']}) 相似度距离={h['distance']:.3f}"
        for h in hits
    )
    return f"{text}\n\n---\n【依据片段】\n{sources}"
