# -*- coding: utf-8 -*-
"""
Agent 模式的工具集：把现有数据层包装成 LLM 可调用的函数

设计要点：
- 工具返回**给模型读的紧凑文本**，不是给程序读的 dict：数字带单位与口径，
  失败时如实说失败（绝不让模型拿到编造的内容）
- 每个工具有两层：`_xxx_impl` 纯实现（注册进 TOOL_IMPLS，测试可直接调/可替换），
  `@tool` 包装版（TOOL_SPECS，bind_tools 给 LLM 看的 schema 从签名和 docstring 推断）
- 重依赖全部延迟导入：不装 chromadb / 没下 embedding 模型时，只有对应工具会失败，
  其它工具照常可用
"""
from datetime import date, timedelta

from langchain_core.tools import tool
from loguru import logger


def _query_market_impl(stock_code: str, days: int = 30) -> str:
    """行情 + 技术指标快照（给模型读的紧凑摘要）"""
    from data.akhare_client import AKShareClient
    from data.technical_indicators import TechnicalIndicatorCalculator

    days = max(5, min(int(days), 250))
    end = date.today()
    client = AKShareClient()
    df = client.get_stock_kline(stock_code, "daily",
                                (end - timedelta(days=int(days * 1.6) + 80)).strftime("%Y%m%d"),
                                end.strftime("%Y%m%d"))
    calc = TechnicalIndicatorCalculator(df)
    calc.calc_all()
    snap = calc.get_latest_snapshot()

    def _pct(n):
        if len(df) <= n:
            return None
        base = float(df["close"].iloc[-1 - n])
        return (float(df["close"].iloc[-1]) / base - 1) * 100 if base else None

    chg5, chg20 = _pct(5), _pct(20)
    lines = [
        f"股票 {stock_code} 截至 {str(snap.get('date'))[:10]}：最新收盘 {snap.get('close')} 元",
        f"近5日涨跌 {chg5:+.1f}%，近20日涨跌 {chg20:+.1f}%" if chg5 is not None and chg20 is not None else "",
        f"MA5={snap.get('ma5')}，MA20={snap.get('ma20')}，MA60={snap.get('ma60')}"
        f"（价格站在均线上方=偏强，下方=偏弱）",
        f"RSI14={snap.get('rsi14')}（>70 超买，<30 超卖）；量比={snap.get('volume_ratio')}",
        "数据来源：AKShare（东方财富，失败自动切新浪）",
    ]
    return "\n".join(ln for ln in lines if ln)


def _get_financials_impl(stock_code: str) -> str:
    """财务指标（东财主接口，失败自动切新浪备用）"""
    from data.akhare_client import AKShareClient

    data = AKShareClient().get_financial_indicators(stock_code)
    if not data:
        return "未获取到财务数据（接口正常但该股票没有数据）"
    label = {
        "pe": "PE市盈率", "pb": "PB市净率", "ps": "PS市销率", "roe": "ROE净资产收益率%",
        "roa": "ROA总资产收益率%", "gross_margin": "毛利率%", "net_margin": "净利率%",
        "revenue_growth": "营收增长率%", "profit_growth": "净利润增长率%",
        "debt_ratio": "资产负债率%", "total_market_value": "总市值", "circulating_market_value": "流通市值",
    }
    parts = [f"{label.get(k, k)}={v}" for k, v in data.items() if v is not None]
    return f"股票 {stock_code} 财务指标：\n" + "；".join(parts)


def _get_news_impl(stock_code: str, limit: int = 8) -> str:
    """近期个股新闻标题（标题+来源+日期，正文太长不塞给模型）"""
    from config import settings
    from data.akhare_client import AKShareClient

    news = AKShareClient().get_stock_news(stock_code, min(limit, settings.max_news_items))
    if not news:
        return "近期没有查到相关新闻"
    lines = [f"{i + 1}. [{n.get('datetime', '')[:10]}][{n.get('source', '')}] {n.get('title', '')}"
             for i, n in enumerate(news[:limit])]
    return f"股票 {stock_code} 近期新闻 {len(lines)} 条：\n" + "\n".join(lines)


def _search_announcements_impl(stock_code: str, question: str) -> str:
    """自由提问式公告检索（向量+关键词混合），这是 Agent 模式相对工作流最大的增强：
    工作流只能问 6 个预设研究问题，这里模型可以想问什么问什么"""
    from rag.service import PERSIST_DIR
    from rag.query import retrieve

    hits = retrieve(question, PERSIST_DIR, top_k=3,
                    collection_name=f"announcements_{stock_code}")
    if not hits:
        return ("没有检索到相关公告。可能：该股票还没建过公告索引"
                "（先在主工作流里跑一次带公告检索的分析）、或近期确实没有相关公告。")
    lines = [f"{i + 1}. 《{h['title']}》{h['date']}\n   {h['text'][:220]}"
             for i, h in enumerate(hits)]
    return f"「{question}」的公告检索结果（按相关度排序）：\n" + "\n".join(lines)


def _get_track_record_impl(stock_code: str) -> str:
    """历史预测战绩：这个工具判断过的预测到底准不准"""
    from utils.track_record import load_records, summarize

    recs = [r for r in load_records() if r.get("stock_code") == stock_code]
    if not recs:
        return f"{stock_code} 还没有存档的预测记录。"
    s = summarize(recs)
    lines = [f"{stock_code} 预测战绩：存档 {s['total']} 条，已复盘 {s['reviewed']} 条"]
    if s["hit_rate"] is not None:
        lines.append(f"方向命中率 {s['hit_rate'] * 100:.0f}%（{s['direction_hits']}/{s['reviewed']}）"
                     f"，平均置信度 {s['avg_confidence'] * 100:.0f}%")
    if s["pending"]:
        lines.append(f"{s['pending']} 条还在预测期内未复盘")
    return "\n".join(lines)


# ---- @tool 包装版：bind_tools 的 schema 从签名 + docstring 推断 ----

@tool
def query_market(stock_code: str, days: int = 30) -> str:
    """查询一只A股的最新行情与技术指标：收盘价、近5/20日涨跌、均线、RSI、量比。"""
    return _query_market_impl(stock_code, days)


@tool
def get_financials(stock_code: str) -> str:
    """查询一只A股的财务指标：PE、PB、ROE、毛利率、营收增速等。"""
    return _get_financials_impl(stock_code)


@tool
def get_news(stock_code: str, limit: int = 8) -> str:
    """查询一只A股的近期新闻标题列表（含来源与日期）。"""
    return _get_news_impl(stock_code, limit)


@tool
def search_announcements(stock_code: str, question: str) -> str:
    """用自然语言问题检索该公司的公告原文片段（巨潮资讯）。可问任何内容，如
    "大股东最近有没有减持"、"最近的回购进展如何"。"""
    return _search_announcements_impl(stock_code, question)


@tool
def get_track_record(stock_code: str) -> str:
    """查询本工具对这只股票历史预测的战绩（命中率、平均置信度），用于评估结论可信度。"""
    return _get_track_record_impl(stock_code)


TOOL_SPECS = [query_market, get_financials, get_news, search_announcements, get_track_record]
TOOL_IMPLS = {
    "query_market": _query_market_impl,
    "get_financials": _get_financials_impl,
    "get_news": _get_news_impl,
    "search_announcements": _search_announcements_impl,
    "get_track_record": _get_track_record_impl,
}
