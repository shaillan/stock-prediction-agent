"""
节点4: 综合预测
LLM 综合技术面+消息面+基本面，输出结构化预测JSON
"""
import json
import re
from typing import Dict, Any
from loguru import logger

from ..state import AgentState
from ..prompts.system_prompts import build_prediction_prompt
from utils.llm_factory import create_chat_model


def comprehensive_prediction_node(state: AgentState) -> Dict[str, Any]:
    """综合预测节点 - 合成所有分析，输出 JSON 预测"""
    logger.info("🧠 开始综合预测...")

    result = {
        "status": "predicting",
        "errors": state.get("errors", []),
    }

    try:
        # 1. 构建综合 Prompt
        prompt = build_prediction_prompt(
            stock_name=state.get("stock_name", ""),
            stock_code=state.get("stock_code", ""),
            technical_analysis=state.get("technical_analysis_result", "暂无技术分析"),
            sentiment_analysis=state.get("news_sentiment_result", "暂无语义分析"),
            financial_data=state.get("financial_data", {}),
            realtime_quote=state.get("realtime_quote", {}),
            market_index=state.get("market_index", {}),
        )

        # 2. 调用 LLM（低温度确保一致输出）
        llm = create_chat_model(
            model=state.get("llm_model"),
            api_key=state.get("llm_api_key"),
            base_url=state.get("llm_base_url"),
            temperature=0.1,
        )

        response = llm.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        # 3. 解析 JSON
        prediction = _parse_prediction_json(response_text)

        # 4. 校验和补全
        prediction = _validate_and_fix_prediction(prediction)

        result["prediction"] = prediction

        logger.info(f"  ✅ 综合预测完成: trend={prediction.get('trend')}, confidence={prediction.get('confidence')}")

    except Exception as e:
        error_msg = f"综合预测失败: {str(e)}"
        logger.error(f"  ❌ {error_msg}")
        result["errors"].append(error_msg)
        result["prediction"] = _get_default_prediction()

    return result


def _parse_prediction_json(text: str) -> Dict:
    """从 LLM 响应中提取 JSON（处理 markdown 代码块等格式）"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个 { ... } 块
    brace_match = re.search(r'\{[\s\S]*\}', text)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("无法从 LLM 响应中解析 JSON，使用默认值")
    return _get_default_prediction()


def _validate_and_fix_prediction(prediction: Dict) -> Dict:
    """校验预测结果并修复缺失字段"""
    valid_trends = ["看涨", "看跌", "震荡"]
    if prediction.get("trend") not in valid_trends:
        prediction["trend"] = "震荡"

    confidence = prediction.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except (ValueError, TypeError):
        confidence = 0.5
    prediction["confidence"] = max(0.0, min(1.0, confidence))

    if not prediction.get("key_factors"):
        prediction["key_factors"] = ["技术指标信号不明", "市场信息不足"]
    if not prediction.get("risk_warnings"):
        prediction["risk_warnings"] = ["市场不确定性风险", "AI 预测仅供参考"]
    if not prediction.get("period"):
        prediction["period"] = "1-5个交易日"
    if not prediction.get("price_targets"):
        prediction["price_targets"] = {}
    if not prediction.get("reasoning_summary"):
        prediction["reasoning_summary"] = "分析过程出现异常，使用默认预测结果"

    return prediction


def _get_default_prediction() -> Dict:
    """默认预测结果（兜底用）"""
    return {
        "trend": "震荡",
        "confidence": 0.3,
        "period": "1-5个交易日",
        "key_factors": ["数据不足，无法做出准确判断"],
        "risk_warnings": ["AI 预测仅供参考，不构成投资建议", "请结合更多信息自行判断"],
        "price_targets": {},
        "reasoning_summary": "由于分析过程中出现问题，此预测为默认兜底结果，不具备参考价值。",
    }
