"""
子 Agent: 综合预测 + 报告生成
步骤1: LLM 综合所有分析 → 结构化 JSON 预测
步骤2: LLM 生成最终 Markdown 报告
"""
import json
import re
from typing import Dict, Any
from loguru import logger

from langgraph.graph import StateGraph, END

from ..state import AgentState
from ..prompts.system_prompts import build_prediction_prompt, build_report_prompt
from utils.llm_factory import create_chat_model


def _predict(state: AgentState) -> Dict[str, Any]:
    """综合预测：LLM 整合所有分析 → JSON"""
    logger.info("🧠 [PredictionAgent] 综合预测...")

    try:
        prompt = build_prediction_prompt(
            stock_name=state.get("stock_name", ""),
            stock_code=state.get("stock_code", ""),
            technical_analysis=state.get("technical_analysis_result", "暂无技术分析"),
            sentiment_analysis=state.get("news_sentiment_result", "暂无语义分析"),
            financial_data=state.get("financial_data", {}),
            realtime_quote=state.get("realtime_quote", {}),
            market_index=state.get("market_index", {}),
        )

        llm = create_chat_model(
            model=state.get("llm_model"),
            api_key=state.get("llm_api_key"),
            base_url=state.get("llm_base_url"),
            temperature=0.1,
        )

        response = llm.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        prediction = _parse_prediction_json(response_text)
        prediction = _validate_and_fix_prediction(prediction)

        logger.info(f"  ✅ 综合预测: trend={prediction.get('trend')}, confidence={prediction.get('confidence')}")
        return {"prediction": prediction}

    except Exception as e:
        logger.error(f"  ❌ 综合预测失败: {e}")
        return {
            "errors": state.get("errors", []) + [f"综合预测失败: {str(e)}"],
            "prediction": _get_default_prediction(),
        }


def _generate_report(state: AgentState) -> Dict[str, Any]:
    """报告生成：LLM 整合所有内容 → Markdown"""
    logger.info("📝 [PredictionAgent] 生成报告...")

    try:
        prompt = build_report_prompt(
            stock_name=state.get("stock_name", ""),
            stock_code=state.get("stock_code", ""),
            technical_analysis=state.get("technical_analysis_result", "暂缺"),
            sentiment_analysis=state.get("news_sentiment_result", "暂缺"),
            financial_data=state.get("financial_data", {}),
            prediction=state.get("prediction", {}),
        )

        llm = create_chat_model(
            model=state.get("llm_model"),
            api_key=state.get("llm_api_key"),
            base_url=state.get("llm_base_url"),
            temperature=0.5,
        )

        response = llm.invoke(prompt)
        report_text = response.content if hasattr(response, "content") else str(response)

        # 构建报告头部
        quote = state.get("realtime_quote", {})
        prediction = state.get("prediction", {})
        from datetime import datetime

        header_parts = [
            f"# 📈 {state.get('stock_name', '')}（{state.get('stock_code', '')}）智能分析报告",
            "",
            f"**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**分析方法**：AI 多源综合分析（LangGraph + LLM）",
        ]

        if quote:
            change_pct = quote.get("change_pct", 0)
            emoji = "🔴" if change_pct < 0 else ("🟢" if change_pct > 0 else "⚪")
            header_parts.extend([
                "",
                f"| 最新价 | 涨跌幅 | 预测趋势 | 置信度 |",
                f"|--------|--------|----------|--------|",
                f"| {quote.get('price', 'N/A')} | {emoji} {change_pct:+.2f}% | "
                f"{prediction.get('trend', '待定')} | "
                f"{prediction.get('confidence', 0) * 100:.0f}% |",
            ])

        full_report = "\n".join(header_parts) + "\n\n---\n\n" + report_text

        logger.info("  ✅ 报告生成完成")
        return {"final_report": full_report, "status": "done"}

    except Exception as e:
        logger.error(f"  ❌ 报告生成失败: {e}")
        return {
            "errors": state.get("errors", []) + [f"报告生成失败: {str(e)}"],
            "final_report": _build_fallback_report(state),
            "status": "done",
        }


# ===== JSON 解析（从 comprehensive_prediction.py 搬过来） =====

def _parse_prediction_json(text: str) -> Dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    brace_match = re.search(r'\{[\s\S]*\}', text)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    logger.warning("无法解析 JSON，使用默认值")
    return _get_default_prediction()


def _validate_and_fix_prediction(prediction: Dict) -> Dict:
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
    return {
        "trend": "震荡",
        "confidence": 0.3,
        "period": "1-5个交易日",
        "key_factors": ["数据不足，无法做出准确判断"],
        "risk_warnings": ["AI 预测仅供参考，不构成投资建议", "请结合更多信息自行判断"],
        "price_targets": {},
        "reasoning_summary": "由于分析过程中出现问题，此预测为默认兜底结果，不具备参考价值。",
    }


def _build_fallback_report(state: AgentState) -> str:
    stock_name = state.get("stock_name", "未知")
    stock_code = state.get("stock_code", "未知")
    prediction = state.get("prediction", {})
    errors = state.get("errors", [])

    parts = [
        f"# 📈 {stock_name}（{stock_code}）分析报告",
        "",
        "> ⚠️ 分析过程出现错误，以下为部分可用内容。",
        "",
    ]
    if prediction:
        parts.extend([
            "## 预测摘要",
            f"- 趋势：{prediction.get('trend', 'N/A')}",
            f"- 置信度：{prediction.get('confidence', 0) * 100:.0f}%",
            f"- 关键因素：{', '.join(prediction.get('key_factors', []))}",
        ])
    if state.get("technical_analysis_result"):
        parts.append(state["technical_analysis_result"])
    if state.get("news_sentiment_result"):
        parts.append(state["news_sentiment_result"])
    if errors:
        parts.append("\n## ⚠️ 错误信息\n")
        for e in errors:
            parts.append(f"- {e}")
    parts.extend([
        "",
        "---",
        "> **⚠️ 免责声明**：本报告由 AI 智能体自动生成，仅供参考，不构成任何投资建议。",
        "> 股市有风险，投资需谨慎。",
    ])
    return "\n\n".join(parts)


def build_prediction_agent() -> StateGraph:
    """构建综合预测 + 报告子 Agent"""
    workflow = StateGraph(AgentState)
    workflow.add_node("predict", _predict)
    workflow.add_node("report", _generate_report)
    workflow.set_entry_point("predict")
    workflow.add_edge("predict", "report")
    workflow.add_edge("report", END)
    return workflow.compile()
