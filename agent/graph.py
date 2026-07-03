"""
LangGraph StateGraph 构建 - Agent 工作流编排
5节点线性流水线 + 错误处理 + Checkpoint
"""
from typing import Dict, Any
from loguru import logger

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import AgentState
from .nodes import (
    data_collection_node,
    technical_analysis_node,
    news_sentiment_node,
    comprehensive_prediction_node,
    report_generation_node,
)


def build_graph() -> StateGraph:
    """
    构建 LangGraph 工作流

    流水线:
    [START] → [数据采集] → [技术分析] → [新闻情绪] → [综合预测] → [报告生成] → [END]

    每步有错误处理，不会因单步失败而中断全流程
    """
    workflow = StateGraph(AgentState)

    # ========== 添加节点 ==========
    workflow.add_node("data_collection", data_collection_node)
    workflow.add_node("technical_analysis", technical_analysis_node)
    workflow.add_node("news_sentiment", news_sentiment_node)
    workflow.add_node("comprehensive_prediction", comprehensive_prediction_node)
    workflow.add_node("report_generation", report_generation_node)

    # ========== 添加边（线性流水线） ==========
    workflow.set_entry_point("data_collection")
    workflow.add_edge("data_collection", "technical_analysis")
    workflow.add_edge("technical_analysis", "news_sentiment")
    workflow.add_edge("news_sentiment", "comprehensive_prediction")
    workflow.add_edge("comprehensive_prediction", "report_generation")
    workflow.add_edge("report_generation", END)

    # ========== 编译（带内存检查点，支持重试） ==========
    memory = MemorySaver()
    compiled = workflow.compile(checkpointer=memory)

    logger.info("✅ LangGraph 工作流构建完成（5节点线性流水线）")
    return compiled


def run_agent(
    stock_code: str,
    start_date: str = "",
    end_date: str = "",
    llm_model: str = "",
    llm_api_key: str = "",
    llm_base_url: str = "",
) -> AgentState:
    """
    运行 Agent 预测流水线

    Args:
        stock_code: 股票代码
        start_date: 起始日期
        end_date: 结束日期
        llm_model: LLM 模型名
        llm_api_key: API Key
        llm_base_url: API Base URL（可选）

    Returns:
        最终的 AgentState（包含所有分析结果和预测）
    """
    from config import settings
    from datetime import date, timedelta

    # 默认日期范围
    if not end_date:
        end_date = date.today().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (date.today() - timedelta(days=settings.default_lookback_days)).strftime("%Y-%m-%d")

    # 初始状态
    initial_state: AgentState = {
        "stock_code": stock_code,
        "stock_name": "",
        "start_date": start_date,
        "end_date": end_date,
        "status": "idle",
        "errors": [],
        "messages": [],
        "llm_model": llm_model or settings.llm_model,
        "llm_api_key": llm_api_key or settings.llm_api_key,
        "llm_base_url": llm_base_url or settings.llm_base_url,
    }

    logger.info(f"🚀 启动 Agent: stock={stock_code}, range={start_date}~{end_date}")
    logger.info(f"   LLM: {initial_state['llm_model']}")

    graph = build_graph()

    # 配置线程ID用于 checkpoint
    config = {"configurable": {"thread_id": f"stock_{stock_code}_{start_date}"}}

    try:
        final_state = graph.invoke(initial_state, config)
        logger.info(f"🏁 Agent 运行完成: status={final_state.get('status')}, errors={len(final_state.get('errors', []))}")
        return final_state
    except Exception as e:
        logger.error(f"❌ Agent 运行异常: {e}")
        initial_state["status"] = "error"
        initial_state["errors"] = [str(e)]
        return initial_state
