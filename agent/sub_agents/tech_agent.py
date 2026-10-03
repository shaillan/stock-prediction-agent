"""
子 Agent: 技术分析
步骤1: 纯代码计算 7 类技术指标
步骤2: LLM 解读分析
"""
from typing import Dict, Any
from loguru import logger

from langgraph.graph import StateGraph, END

from ..state import AgentState
from ..prompts.system_prompts import build_technical_prompt
from data.technical_indicators import TechnicalIndicatorCalculator
from utils.llm_factory import create_chat_model


def _calc_indicators(state: AgentState) -> Dict[str, Any]:
    """纯代码：计算 7 类技术指标"""
    logger.info("📊 [TechAgent] 计算技术指标...")

    kline_data = state.get("kline_data")
    if kline_data is None or (hasattr(kline_data, "empty") and kline_data.empty):
        return {
            "errors": state.get("errors", []) + ["缺少K线数据，无法进行技术分析"],
            "technical_analysis_result": "## 技术分析\n\n⚠️ 由于缺少K线数据，无法进行技术分析。",
        }

    try:
        calculator = TechnicalIndicatorCalculator(kline_data)
        calculator.calc_all()
        snapshot = calculator.get_latest_snapshot()
        indicator_text = calculator.get_indicator_text_table(n_rows=15)

        logger.info(f"  ✅ 指标计算完成, close={snapshot.get('close')}")

        return {
            "technical_indicators": snapshot,
            "_indicator_text": indicator_text,  # 内部传递，给下一个节点用
        }
    except Exception as e:
        logger.error(f"  ❌ 指标计算失败: {e}")
        return {
            "errors": state.get("errors", []) + [f"技术指标计算失败: {str(e)}"],
        }


def _llm_analyze(state: AgentState) -> Dict[str, Any]:
    """LLM：解读技术指标"""
    logger.info("📊 [TechAgent] LLM 解读...")

    # 如果上一步已经失败，跳过
    if state.get("technical_analysis_result"):
        return {}

    try:
        snapshot = state.get("technical_indicators", {})
        indicator_text = state.get("_indicator_text", "")
        if not indicator_text:
            # 兜底：重新从指标生成
            indicator_text = str(snapshot)

        prompt = build_technical_prompt(
            state.get("stock_name", ""),
            state.get("stock_code", ""),
            indicator_text,
            snapshot,
        )

        llm = create_chat_model(
            model=state.get("llm_model"),
            api_key=state.get("llm_api_key"),
            base_url=state.get("llm_base_url"),
            temperature=0.1,
        )

        response = llm.invoke(prompt)
        analysis_text = response.content if hasattr(response, "content") else str(response)

        logger.info("  ✅ LLM 技术解读完成")
        return {"technical_analysis_result": analysis_text}

    except Exception as e:
        logger.error(f"  ❌ LLM 技术解读失败: {e}")
        return {
            "errors": state.get("errors", []) + [f"技术分析失败: {str(e)}"],
            "technical_analysis_result": f"## 技术分析\n\n❌ 分析过程出错: {str(e)}",
        }


def build_tech_agent() -> StateGraph:
    """构建技术分析子 Agent（2 步流水线：计算 → LLM 解读）"""
    workflow = StateGraph(AgentState)
    workflow.add_node("calc", _calc_indicators)
    workflow.add_node("analyze", _llm_analyze)
    workflow.set_entry_point("calc")
    workflow.add_edge("calc", "analyze")
    workflow.add_edge("analyze", END)
    return workflow.compile()
