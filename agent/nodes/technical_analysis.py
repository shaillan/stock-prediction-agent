"""
节点2: 技术分析
计算技术指标 + LLM 解读分析
"""
from typing import Dict, Any
from loguru import logger

from ..state import AgentState
from ..prompts.system_prompts import build_technical_prompt
from data.technical_indicators import TechnicalIndicatorCalculator
from utils.llm_factory import create_chat_model


def technical_analysis_node(state: AgentState) -> Dict[str, Any]:
    """技术分析节点 - 计算指标 + LLM 解读"""
    logger.info("📊 开始技术分析...")

    result = {
        "status": "analyzing",
        "errors": state.get("errors", []),
    }

    kline_data = state.get("kline_data")

    if kline_data is None or (hasattr(kline_data, "empty") and kline_data.empty):
        result["errors"].append("缺少K线数据，无法进行技术分析")
        result["technical_analysis_result"] = "## 技术分析\n\n⚠️ 由于缺少K线数据，无法进行技术分析。"
        return result

    try:
        # 1. 计算所有技术指标
        calculator = TechnicalIndicatorCalculator(kline_data)
        calculator.calc_all()

        # 获取指标快照和明细
        snapshot = calculator.get_latest_snapshot()
        indicator_text = calculator.get_indicator_text_table(n_rows=15)

        logger.info(f"  技术指标计算完成，最新快照: close={snapshot.get('close')}")

        # 2. 构建 Prompt 并调用 LLM
        stock_name = state.get("stock_name", "")
        stock_code = state.get("stock_code", "")

        prompt = build_technical_prompt(stock_name, stock_code, indicator_text, snapshot)

        # 3. 调用 LLM
        llm = create_chat_model(
            model=state.get("llm_model"),
            api_key=state.get("llm_api_key"),
            base_url=state.get("llm_base_url"),
            temperature=0.1,
        )

        response = llm.invoke(prompt)
        analysis_text = response.content if hasattr(response, "content") else str(response)

        result["technical_indicators"] = snapshot
        result["technical_analysis_result"] = analysis_text

        logger.info("  ✅ 技术分析完成")

    except Exception as e:
        error_msg = f"技术分析失败: {str(e)}"
        logger.error(f"  ❌ {error_msg}")
        result["errors"].append(error_msg)
        result["technical_analysis_result"] = f"## 技术分析\n\n❌ 分析过程出错: {str(e)}"

    return result
