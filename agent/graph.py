"""
主 Agent —— 编排 4 个子 Agent 的串行流水线

拓扑结构:
  [数据采集] → [技术分析] → [新闻情绪] → [综合预测 → 报告]
"""
from loguru import logger

from langgraph.graph import StateGraph, END

from .state import AgentState
from .sub_agents import (
    build_data_agent,
    build_tech_agent,
    build_sentiment_agent,
    build_prediction_agent,
)


def build_graph() -> StateGraph:
    """
    构建主 Agent 工作流

    子 Agent 分工:
    - data_agent:     数据采集（纯代码，不调 LLM）
    - tech_agent:     技术分析（指标计算 + LLM 解读）
    - sentiment_agent: 新闻情绪（LLM 分析）          ← 与 tech_agent 并行
    - prediction_agent: 综合预测（LLM）→ 报告生成（LLM）
    """
    workflow = StateGraph(AgentState)

    # ========== 注册子 Agent 为节点 ==========
    workflow.add_node("data_collection", build_data_agent())
    workflow.add_node("tech_analysis", build_tech_agent())
    workflow.add_node("sentiment", build_sentiment_agent())
    workflow.add_node("prediction", build_prediction_agent())

    # ========== 编排并行依赖 ==========
    workflow.set_entry_point("data_collection")

    # 串行流水线：数据 → 技术 → 情绪 → 预测
    workflow.add_edge("data_collection", "tech_analysis")
    workflow.add_edge("tech_analysis", "sentiment")
    workflow.add_edge("sentiment", "prediction")

    workflow.add_edge("prediction", END)

    compiled = workflow.compile()
    logger.info("✅ 主 Agent 构建完成（4 子 Agent 串行流水线）")
    return compiled


def run_agent(
    stock_code: str,
    start_date: str = "",
    end_date: str = "",
    llm_model: str = "",
    llm_api_key: str = "",
    llm_base_url: str = "",
    stock_name: str = "",
) -> AgentState:
    """运行 Agent 预测流水线"""
    from config import settings
    from datetime import date, timedelta

    if not end_date:
        end_date = date.today().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (date.today() - timedelta(days=settings.default_lookback_days)).strftime("%Y-%m-%d")

    initial_state: AgentState = {
        "stock_code": stock_code,
        "stock_name": stock_name,
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

    try:
        final_state = graph.invoke(initial_state)
        logger.info(f"🏁 Agent 完成: status={final_state.get('status')}, errors={len(final_state.get('errors', []))}")
        return final_state
    except Exception as e:
        logger.error(f"❌ Agent 异常: {e}")
        initial_state["status"] = "error"
        initial_state["errors"] = [str(e)]
        return initial_state
