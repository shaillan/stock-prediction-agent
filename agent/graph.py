"""
主工作流 —— 编排各分析节点

注意：这仍然是**工作流（workflow），不是 Agent**，尽管现在有了 1 条条件边。
判断标准只有一条——「谁决定下一步做什么」。这里的分支条件是代码写死的
`sentiment_ok / announcement_ok is False`，不是 LLM 临场判断；LLM 依旧没有 bind_tools，
只拿到代码准备好的材料写一段文字。所以控制流仍由代码决定。

（加了条件边只是让"出错时的路径"显式化，属于降级设计，不等于把决策权交给模型。）

拓扑结构（7 节点：静态边 8 条 + 1 条条件边，2 个去向）:
  [数据采集] ─┬─→ 技术分析 ─┐
              ├─→ 新闻情绪 ─┼─→ [汇合/路由] ─┬─ 信号齐全 ───→ [综合预测 → 报告]
              └─→ 公告检索 ─┘                └─ 有信号缺口 → [降级预测 → 报告]

技术分析、新闻情绪、公告检索三者互不依赖（分别只读 kline_data / news_data /
stock_code），所以并行执行；三者都完成后才进入汇合节点。
汇合后由 `_route_after_join` 决定走哪条路：新闻情绪或公告检索失败（信号级缺口）
时走降级版——失败那一路在预测 prompt 里换成占位说明、报告头部逐项标注缺口、
置信度由代码强制封顶 0.6。大盘指数、财务这类**数据级**缺口不换分支，两个分支
的预测节点都会按缺口逐项标注（见 prediction_agent._collect_gaps）。
"""
from typing import Any, Dict

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


def _join_branches(state: AgentState) -> Dict[str, Any]:
    """汇合节点：不写任何状态，只负责等三条并行分支全部完成

    为什么不直接把条件边挂在 sentiment 上：那样 comprehensive_prediction 只会
    收到两路输入就被触发，而两个预测节点也会同时被调度。先汇合、再判断，语义才明确。
    """
    return {}


def _route_after_join(state: AgentState) -> str:
    """唯一的条件路由：信号级数据源有没有产出可用结果

    判据是显式 False 才算失败（sentiment_ok / announcement_ok）；
    字段缺失按正常处理，避免历史状态/旧调用被误判成降级。
    数据级缺口（大盘/财务为空）不在这里判断——不需要换分支，预测节点会按缺口逐项标注。
    """
    failed = [
        name for name, ok in (
            ("新闻情绪", state.get("sentiment_ok")),
            ("公告检索", state.get("announcement_ok")),
        ) if ok is False
    ]
    if failed:
        logger.warning(f"⚠️ {'、'.join(failed)}不可用 → 走降级分支（报告将逐项标注缺口，置信度封顶 0.6）")
        return "degraded"
    return "normal"


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

    # 汇合 + 路由：三条并行分支都完成后（同一 superstep 收尾）才执行
    workflow.add_node("degradation_router", _join_branches)

    # 注意：节点名不能和 AgentState 的字段重名（状态里已有 "prediction" 字段），
    # 否则 add_node 会报 ValueError: 'prediction' is already being used as a state key
    workflow.add_node("comprehensive_prediction", build_prediction_agent())
    workflow.add_node(
        "comprehensive_prediction_degraded",
        build_prediction_agent(degraded=True),
    )

    # ========== 编排依赖 ==========
    workflow.set_entry_point("data_collection")

    # 三条边同时从 data_collection 出发 = 并行执行
    workflow.add_edge("data_collection", "tech_analysis")
    workflow.add_edge("data_collection", "sentiment")
    workflow.add_edge("data_collection", "announcement")

    # 三条分支先汇合到同一个节点（LangGraph 按 superstep 推进，等三路都完成）
    workflow.add_edge("tech_analysis", "degradation_router")
    workflow.add_edge("sentiment", "degradation_router")
    workflow.add_edge("announcement", "degradation_router")

    # 第一条（也是目前唯一一条）条件边：由 sentiment_ok 决定走正常版还是降级版
    workflow.add_conditional_edges(
        "degradation_router",
        _route_after_join,
        {
            "normal": "comprehensive_prediction",
            "degraded": "comprehensive_prediction_degraded",
        },
    )

    workflow.add_edge("comprehensive_prediction", END)
    workflow.add_edge("comprehensive_prediction_degraded", END)

    compiled = workflow.compile()
    logger.info(
        "✅ 工作流构建完成（数据 → [技术分析 ∥ 新闻情绪 ∥ 公告检索] → 汇合/路由 → 综合预测）"
    )
    return compiled


def _save_track_record(final_state: dict) -> None:
    """预测存档（战绩跟踪）。失败只记日志——存档绝不能弄挂分析主流程。"""
    try:
        from config import settings
        if not settings.track_records_enabled:
            return
        if final_state.get("status") != "done" or not (final_state.get("prediction") or {}).get("trend"):
            return
        from utils.track_record import save_prediction
        rec = save_prediction(final_state)
        if rec:
            logger.info(f"🏆 预测已存档，到期后可在「战绩」页复盘: {rec['stock_code']} {rec['prediction_date']}")
    except Exception as e:
        logger.warning(f"预测存档失败（不影响分析结果）: {e}")


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
        _save_track_record(final_state)
        return final_state
    except Exception as e:
        logger.error(f"❌ 工作流异常: {e}")
        initial_state["status"] = "error"
        initial_state["errors"] = [str(e)]
        return initial_state
