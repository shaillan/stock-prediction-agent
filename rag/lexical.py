# -*- coding: utf-8 -*-
"""
关键词检索（BM25 over jieba 分词）

为什么需要它——实测结论：
  问"大股东有没有减持或增持？"，答案《关于回购股份实施结果暨股份变动的公告》里
  白纸黑字写着"控股股东…累计增持1,274,234股…未减持"，却连 top-10 都进不去。
  top-10 反而被《股东会通知》《独立董事候选人声明》占满——它们只含"股东"二字，
  主题相关但答非所问。

  说明稠密向量匹配的是**主题**，不是**答案**。关键词检索恰好相反：按词命中，
  并用 IDF 让"增持/减持"这种罕见词权重远高于"股东"这种常见词。

为什么必须真正分词，不能用字符二元组：
  二元组会把"减持或增持"切成 {减持, 持或, 或增, 增持}——
  "持或""或增"是跨词边界的垃圾，可它们的 df/idf 和答案词"减持""增持"**完全一样**
  （语料小，出现 1 次就是 df=1）。统计量分不出来，垃圾词就会把答案顶掉。
  jieba 分词后"减持""增持"是词，"或""有没有"是虚词进停用词表，垃圾从根上消失。

BM25 相比"数几个词命中"多做了两件事，正是它的价值：
  1. 词频饱和：同一个词出现 50 次不等于 50 倍相关（用 k1 压住）
  2. 长度归一化：长文档天生覆盖更多词，要按长度惩罚（用 b 压住）
"""
import math
from typing import Dict, List, Sequence, Tuple

import jieba

jieba.setLogLevel(60)  # 关掉 jieba 首次加载词典的日志

_K1 = 1.5   # BM25 词频饱和：越大越看重重复出现
_B = 0.75   # BM25 长度归一化：0=不惩罚长文，1=完全按长度平摊

# 停用词：虚词、提问用语。留着它们只会给"碰巧含这些字"的无关文档加分。
# 只收明确无语义的词——宁可少收，误删会丢召回。
STOPWORDS = {
    "的", "了", "和", "与", "或", "及", "是", "在", "有", "无", "不", "也", "都", "就",
    "还", "被", "把", "对", "为", "于", "之", "其", "该", "本", "这", "那", "哪",
    "什么", "多少", "哪些", "哪个", "是否", "请问", "没有", "有没有",
    "近期", "最近", "目前", "已经", "正在", "并", "而", "则", "以", "从", "到", "向",
    "给", "让", "使", "得", "地", "着", "过", "们", "个", "些", "等", "被",
}


def _is_content(token: str) -> bool:
    """是否是值得用来匹配的词：非停用词、非单字、含中英文数字"""
    t = token.strip()
    if not t or t in STOPWORDS:
        return False
    if len(t) < 2:
        return False  # 单字（大/高/股）区分度太低
    return any(ch.isalnum() or "一" <= ch <= "鿿" for ch in t)


def tokenize(text: str) -> List[str]:
    """分词并过滤，保留重复（BM25 需要词频）"""
    return [t for t in jieba.cut(text or "") if _is_content(t)]


class BM25:
    """
    jieba 分词 BM25。创建时喂全部文档建索引，之后可反复查询。

    语料不动时只需建一次，查询很便宜。
    """

    def __init__(self, documents: Sequence[str]):
        self.n_docs = len(documents)
        self.doc_tf: List[Dict[str, int]] = []
        self.doc_len: List[int] = []
        self.df: Dict[str, int] = {}

        for doc in documents:
            tokens = tokenize(doc)
            tf: Dict[str, int] = {}
            for tk in tokens:
                tf[tk] = tf.get(tk, 0) + 1
            self.doc_tf.append(tf)
            self.doc_len.append(len(tokens))
            for tk in tf:
                self.df[tk] = self.df.get(tk, 0) + 1

        self.avgdl = (sum(self.doc_len) / self.n_docs) if self.n_docs else 0.0
        # IDF 预先算好（标准 BM25 平滑形式，恒为正）
        self.idf: Dict[str, float] = {
            tk: math.log(1 + (self.n_docs - n + 0.5) / (n + 0.5))
            for tk, n in self.df.items()
        }

    def score(self, query: str) -> List[float]:
        """返回每个文档的 BM25 得分（越大越相关）"""
        q_terms = set(tokenize(query))
        out: List[float] = []
        for i in range(self.n_docs):
            tf = self.doc_tf[i]
            denom_len = _K1 * (1 - _B + _B * self.doc_len[i] / self.avgdl) if self.avgdl else _K1
            s = 0.0
            for t in q_terms:
                f = tf.get(t)
                if not f:
                    continue
                s += self.idf.get(t, 0.0) * f * (_K1 + 1) / (f + denom_len)
            out.append(s)
        return out

    def explain(self, query: str, doc_index: int, top_terms: int = 5) -> List[Tuple[str, float]]:
        """某文档靠哪些词得分——用来解释检索结果、排查误解"""
        tf = self.doc_tf[doc_index]
        denom_len = _K1 * (1 - _B + _B * self.doc_len[doc_index] / self.avgdl) if self.avgdl else _K1
        hits = []
        for t in set(tokenize(query)):
            f = tf.get(t)
            if not f:
                continue
            hits.append((t, self.idf.get(t, 0.0) * f * (_K1 + 1) / (f + denom_len)))
        hits.sort(key=lambda x: -x[1])
        return hits[:top_terms]


def rrf_fuse(rankings: Sequence[List[int]], k: int = 60) -> List[int]:
    """
    倒数排名融合（Reciprocal Rank Fusion）——把多路检索结果合成一路。

    输入：几组"下标按相关性从高到低排好"的列表；输出：融合后的顺序。

    为什么不用"两种分数加权相加"：向量距离和 BM25 得分的量纲完全不同，
    直接相加要调一个说不清道理的权重。RRF 只看"排第几"，不需要归一化、
    不用调参，是工业界混合检索的默认做法（k=60 是原论文推荐值）。
    """
    fused: Dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank)
    return sorted(fused, key=lambda i: -fused[i])
