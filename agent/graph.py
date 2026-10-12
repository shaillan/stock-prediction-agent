"""
主工作流 —— 编排各分析节点

注意：这是**工作流（workflow），不是 Agent**。判断标准只有一条——「谁决定下一步
做什么」。本图的 7 条边全部硬编码，没有任何 add_conditional_edges；LLM 也没有
bind_tools，即从不自己调工具、从不知道"工具"这个概念，只拿到代码准备好的材料
写一段文字。所以控制流由代码决定，LLM 不参与决策。

（目录仍叫 agent/、类仍叫 AgentState，是历史命名，改动会牵动全项目 import，
故保留；用户可见文案已统一改为"工作流"。）

拓扑结构（静态：5 节点 / 7 边，无条件分支）:
  [数据采集] ─┬─→ 技术分析 ─┬─→ [综合预测 → 报告]
              ├─→ 新闻情绪 ─┤
              └─→ 公告检索 ─┘

技术分析、新闻情绪、公告检索三者互不依赖（分别只读 kline_data / news_data /
stock_code），所以并行执行；三者都完成后综合预测才启动。
"""
from loguru import logger

from langgraph.graph import StateGraph, END

from .state import AgentState
from .sub_agents import (
    build_data_agent,
    build_tech_agent,
    build_sentiment_agent,
    build_prediction_agent,
    analyze_announcements,
)


def build_graph() -> StateGraph:
    """
    构建工作流

    各步骤分工:
    - data_agent:     数据采集（纯代码，不调 LLM）
    - tech_agent:     技术分析（指标计算 + LLM 解读）  ┐
    - sentiment_agent: 新闻情绪（LLM 分析）            ├ 并行，
    - announcement_agent: 公告检索（RAG，纯代码）      ┘ 都只依赖 data_agent
    - prediction_agent: 综合预测（LLM）→ 报告生成（LLM）
    """
    workflow = StateGraph(AgentState)

    # ========== 注册各步骤为节点 ==========
    workflow.add_node("data_collection", build_data_agent())
    workflow.add_node("tech_analysis", build_tech_agent())
    workflow.add_node("sentiment", build_sentiment_agent())
    # 公告检索是普通函数节点（不是子图），见 announcement_agent.py 的说明
    workflow.add_node("announcement", analyze_announcements)
    # 注意：节点名不能和 AgentState 的字段重名（状态里已有 "prediction" 字段），
    # 否则 add_node 会报 ValueError: 'prediction' is already being used as a state key
    workflow.add_node("comprehensive_prediction", build_prediction_agent())

    # ========== 编排依赖 ==========
    workflow.set_entry_point("data_collection")

    # 三条边同时从 data_collection 出发 = 并行执行
    workflow.add_edge("data_collection", "tech_analysis")
    workflow.add_edge("data_collection", "sentiment")
    workflow.add_edge("data_collection", "announcement")

    # 汇合点：LangGraph 默认要等所有上游分支完成，才执行 comprehensive_prediction
    workflow.add_edge("tech_analysis", "comprehensive_prediction")
    workflow.add_edge("sentiment", "comprehensive_prediction")
    workflow.add_edge("announcement", "comprehensive_prediction")

    workflow.add_edge("comprehensive_prediction", END)

    compiled = workflow.compile()
    logger.info("✅ 工作流构建完成（数据 → [技术分析 ∥ 新闻情绪 ∥ 公告检索] → 综合预测）")
    return compiled


def run_agent(
    stock_code: str,
    start_date: str = "",
    end_date: str = "",
    llm_model: str = "",
    llm_api_key: str = "",
    llm_base_url: str = "",
    stock_name: str = "",
    rag_enabled: bool = True,
) -> AgentState:
    """运行 LLM 工作流"""
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
        "rag_enabled": rag_enabled,
        "llm_model": llm_model or settings.llm_model,
        "llm_api_key": llm_api_key or settings.llm_api_key,
        "llm_base_url": llm_base_url or settings.llm_base_url,
    }

    logger.info(f"🚀 启动工作流: stock={stock_code}, range={start_date}~{end_date}")
    logger.info(f"   LLM: {initial_state['llm_model']}")

    graph = build_graph()

    try:
        final_state = graph.invoke(initial_state)
        logger.info(f"🏁 工作流完成: status={final_state.get('status')}, errors={len(final_state.get('errors', []))}")
        return final_state
    except Exception as e:
        logger.error(f"❌ 工作流异常: {e}")
        initial_state["status"] = "error"
        initial_state["errors"] = [str(e)]
        return initial_state
