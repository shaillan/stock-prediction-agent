"""
Agent 状态定义 - LangGraph State Schema
"""
from typing import TypedDict, List, Dict, Optional, Annotated, Any
from langgraph.graph.message import add_messages
import pandas as pd


class AgentState(TypedDict, total=False):
    """贯穿所有 LangGraph 节点的共享状态"""

    # ========== 输入参数（由 UI 设置） ==========
    stock_code: str  # 股票代码，如 "600519"
    stock_name: str  # 股票名称
    start_date: str  # 起始日期 "YYYY-MM-DD"
    end_date: str  # 结束日期 "YYYY-MM-DD"

    # ========== 数据采集输出 ==========
    kline_data: Optional[Any]  # pd.DataFrame: K线历史数据
    realtime_quote: Optional[Dict]  # 实时行情
    financial_data: Optional[Dict]  # 财务指标
    news_data: Optional[List[Dict]]  # 新闻列表
    market_index: Optional[Dict]  # 大盘指数

    # ========== 技术分析输出 ==========
    technical_indicators: Optional[Dict]  # 技术指标快照 (最新值)
    technical_analysis_result: Optional[str]  # LLM 技术分析中文文本

    # ========== 新闻情绪输出 ==========
    news_sentiment_result: Optional[str]  # LLM 新闻情绪分析中文文本

    # ========== 综合预测输出 ==========
    prediction: Optional[Dict]  # 预测结果 JSON

    # ========== 报告输出 ==========
    final_report: Optional[str]  # 最终中文 Markdown 报告

    # ========== 控制状态 ==========
    status: str  # "idle" | "collecting" | "analyzing" | "predicting" | "done" | "error"
    errors: List[str]  # 累积的非致命错误
    messages: Annotated[list, add_messages]  # LangGraph 消息历史

    # ========== LLM 配置（从 UI 传入） ==========
    llm_model: str
    llm_api_key: str
    llm_base_url: str
