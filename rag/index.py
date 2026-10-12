# -*- coding: utf-8 -*-
"""
第2步 建索引：文本切块 → embedding → 存向量库

为什么要切块：
  LLM 的上下文装不下 11 万字年报；而且检索时我们希望"精准命中那一段"，
  而不是把整篇都塞进去。切成几百字的小块，检索命中率最高。
"""
import os
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

# 国内访问 HuggingFace 需走镜像（官方源被墙）。仅在首次下载模型时用到。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import chromadb
from sentence_transformers import SentenceTransformer

# bge 系列模型本地加载；已下载过则走本地缓存，不再联网。
_MODEL_NAME = "BAAI/bge-small-zh-v1.5"

# 默认集合名。流水线按股票分集合时传入 announcements_{code}，
# CLI 不传则用这个默认值，保持原有用法不变。
DEFAULT_COLLECTION = "cninfo_announcements"


def _local_snapshot(model_name: str) -> Optional[str]:
    """
    在 HuggingFace 缓存里找已下载的模型快照目录。

    为什么要这样做：huggingface_hub 在 **import 时**就把 endpoint 固化成官方地址，
    如果它在我们的 os.environ.setdefault 之前被别的库（如 langchain 栈）导入，
    设镜像就失效了，于是每次都去连被墙的 huggingface.co、超时重试 5 次。
    直接给 SentenceTransformer 一个本地目录路径，就完全不触发网络请求。
    """
    cache_root = os.path.expanduser("~/.cache/huggingface/hub")
    snapshots = os.path.join(cache_root, "models--" + model_name.replace("/", "--"), "snapshots")
    if not os.path.isdir(snapshots):
        return None
    for name in os.listdir(snapshots):
        path = os.path.join(snapshots, name)
        if os.path.isfile(os.path.join(path, "config.json")):  # 文件齐全才算可用
            return path
    return None


@lru_cache(maxsize=4)
def load_embedding_model(model_name: str = _MODEL_NAME) -> SentenceTransformer:
    """
    加载 embedding 模型。优先用本地快照（零网络），没有才联网下载。

    加了 lru_cache：同一进程内只加载一次。否则每检索一个问题都重新加载模型，
    既慢又会反复触发上面的网络检查（service 层一次要检索 6 个问题）。
    """
    local = _local_snapshot(model_name)
    return SentenceTransformer(local or model_name)


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> List[str]:
    """
    把长文本切成固定大小的块，块之间保留 overlap 的重叠，
    避免一句话被拦腰截断在块边界上。
    """
    text = text.replace("　", " ").strip()
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def _embed(texts: List[str], model: SentenceTransformer) -> List[List[float]]:
    """编码成 512 维向量，并归一化（内积=余弦相似度）"""
    return model.encode(texts, normalize_embeddings=True).tolist()


def build_index(
    announcements: List[Dict],
    persist_dir: str,
    collection_name: str = DEFAULT_COLLECTION,
    model: SentenceTransformer = None,
) -> Tuple[int, int]:
    """
    把所有公告切块、编码、存入 chromadb 持久化向量库。

    返回 (公告数, 切块数)。
    """
    model = model or load_embedding_model()

    # PersistentClient = 数据落到磁盘，重启不丢
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},  # 用余弦距离衡量向量相似度
    )

    from .fetch import _fmt_date

    n_docs = 0
    for ann in announcements:
        chunks = chunk_text(ann["text"])
        if not chunks:
            continue
        embeddings = _embed(chunks, model)
        collection.add(
            ids=[f"{ann['title']}-{i}" for i in range(len(chunks))],
            documents=chunks,
            embeddings=embeddings,
            metadatas=[{
                "title": ann["title"],
                "date": _fmt_date(ann.get("date")),  # 兼容缓存里的原始时间戳
                "url": ann["url"],
            } for _ in chunks],
        )
        n_docs += 1

    return n_docs, collection.count()


def load_collection(persist_dir: str, collection_name: str = DEFAULT_COLLECTION):
    """只读加载已有向量库"""
    return chromadb.PersistentClient(path=persist_dir).get_collection(collection_name)


def collection_exists(persist_dir: str, collection_name: str) -> bool:
    """该集合是否已建好且有内容（避免重复下载 PDF / 重复编码）"""
    try:
        col = load_collection(persist_dir, collection_name)
        return col.count() > 0
    except Exception:
        return False
