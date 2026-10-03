"""
Agent 状态定义 - LangGraph State Schema
有 Annotated reducer 的字段才能在并行分支中安全合并
"""
from typing import TypedDict, List, Dict, Optional, Annotated, Any
from operator import add
from langgraph.graph.message import add_messages


def _keep_first(a, b):
    """reducer: 保留第一个非空值（用于不可变配置字段）"""
    return a if a else b


def _keep_last(a, b):
    """reducer: 最后写入的生效（用于 status）"""
    return b


class AgentState(TypedDict, total=False):
    """贯穿所有 LangGraph 节点的共享状态"""

    # ========== 输入参数（由 UI 设置，运行中不变） ==========
    stock_code: Annotated[str, _keep_first]
    stock_name: Annotated[str, _keep_first]
    start_date: Annotated[str, _keep_first]
    end_date: Annotated[str, _keep_first]

    # ========== 数据采集输出 ==========
    kline_data: Optional[Any]  # pd.DataFrame，仅在 data_agent 中写入
    realtime_quote: Optional[Dict]
    financial_data: Optional[Dict]
    news_data: Optional[List[Dict]]
    market_index: Optional[Dict]

    # ========== 技术分析输出 ==========
    technical_indicators: Optional[Dict]
    technical_analysis_result: Optional[str]
    _indicator_text: Optional[str]  # 技术指标文本（内部传递）

    # ========== 新闻情绪输出 ==========
    news_sentiment_result: Optional[str]

    # ========== 综合预测输出 ==========
    prediction: Optional[Dict]

    # ========== 报告输出 ==========
    final_report: Optional[str]

    # ========== 控制状态 ==========
    status: Annotated[str, _keep_last]
    errors: Annotated[List[str], add]  # 并行时自动拼接
    messages: Annotated[list, add_messages]

    # ========== LLM 配置 ==========
    llm_model: Annotated[str, _keep_first]
    llm_api_key: Annotated[str, _keep_first]
    llm_base_url: Annotated[str, _keep_first]
