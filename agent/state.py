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


# ===================== 子 Agent 的输入 / 输出契约 =====================
#
# 每个子 Agent 都是一个编译过的子图，挂在主图上。子图的「状态」是整个
# AgentState，但它的**回传**只包含 output schema 里声明的键。这两件事必须
# 说清楚，否则并行时会踩两个坑：
#
# 1) 回传了不属于自己的键：
#    技术分析和新闻情绪并行执行，两边都把传入的 kline_data 原样回传，
#    主图会直接报
#        InvalidUpdateError: At key 'kline_data':
#        Can receive only one value per step.
#    声明 output 后各回传各的，不再撞车。
#
# 2) 回传了累积的 errors：
#    子图的 errors 通道带 add reducer，会把主图传进来的错误也累进去。
#    如果再把整份回传给主图，主图的 add reducer 会再加一次 —— 错误翻倍。
#    所以 input schema 里**不包含 errors**：子图从空列表开始，只回传自己新增的。


class DataAgentInput(TypedDict, total=False):
    stock_code: str
    stock_name: str
    start_date: str
    end_date: str


class DataAgentOutput(TypedDict, total=False):
    stock_name: str
    kline_data: Optional[Any]
    realtime_quote: Optional[Dict]
    financial_data: Optional[Dict]
    news_data: Optional[List[Dict]]
    market_index: Optional[Dict]
    status: Annotated[str, _keep_last]
    errors: Annotated[List[str], add]


class TechAgentInput(TypedDict, total=False):
    stock_code: str
    stock_name: str
    kline_data: Optional[Any]
    llm_model: str
    llm_api_key: str
    llm_base_url: str


class TechAgentOutput(TypedDict, total=False):
    technical_indicators: Optional[Dict]
    technical_analysis_result: Optional[str]
    _indicator_text: Optional[str]
    errors: Annotated[List[str], add]


class SentimentAgentInput(TypedDict, total=False):
    news_data: Optional[List[Dict]]
    llm_model: str
    llm_api_key: str
    llm_base_url: str


class SentimentAgentOutput(TypedDict, total=False):
    news_sentiment_result: Optional[str]
    errors: Annotated[List[str], add]


class PredictionAgentInput(TypedDict, total=False):
    stock_code: str
    stock_name: str
    technical_analysis_result: Optional[str]
    news_sentiment_result: Optional[str]
    financial_data: Optional[Dict]
    realtime_quote: Optional[Dict]
    market_index: Optional[Dict]
    llm_model: str
    llm_api_key: str
    llm_base_url: str


class PredictionAgentOutput(TypedDict, total=False):
    prediction: Optional[Dict]
    final_report: Optional[str]
    status: Annotated[str, _keep_last]
    errors: Annotated[List[str], add]
