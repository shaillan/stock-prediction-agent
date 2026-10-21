"""
子 Agent: 综合预测 + 报告生成
步骤1: LLM 综合所有分析 → 结构化 JSON 预测
步骤2: LLM 生成最终 Markdown 报告
"""
import json
import re
from functools import partial
from typing import Dict, Any
from loguru import logger

from langgraph.graph import StateGraph, END

from ..state import AgentState, PredictionAgentInput, PredictionAgentOutput
from ..prompts.system_prompts import build_prediction_prompt, build_report_prompt
from utils.llm_factory import create_chat_model

# ===== 数据缺口（gap）机制 =====
# 降级不再是一段写死的「无舆情」文案：每路数据都有健康标记（sentiment_ok /
# announcement_ok）或可直接判空（market_index / financial_data），预测节点先
# 盘点缺口，再按缺口逐项处理。分两类：
#
# - 信号级（*_ok is False）：那一路产出是垃圾或缺失，必须换占位说明、报告标注，
#   且置信度被代码强制封顶（不指望 LLM 自觉下调）。
# - 数据级（输入为空）：对应 prompt 段落是空的，要明说「缺了」，防止 LLM 把
#   「没提供」当成「没有风险」，或把「检索失败」说成「无重大事项」。
#
# 主图的条件边只认信号级缺口（见 agent/graph.py 的 _route_after_join）；
# 数据级缺口不换分支，在两个分支里都走同一套标注。

_DEGRADED_CONFIDENCE_CAP = 0.6  # 信号级缺口存在时，置信度不允许高于此值

_SIGNAL_GAP_PLACEHOLDERS = {
    "sentiment": (
        "（本次新闻情绪分析失败，无可用舆情数据。）\n"
        "请仅基于技术面、公告与基本面做出判断；"
        "在 reasoning_summary 中明确注明「本次分析未包含最新舆情数据」，不要臆造新闻或市场情绪。"
    ),
    "announcement": (
        "（本次公告检索失败，无可用公告动态。）\n"
        "不要据此推断「公司近期无重大事项」——检索失败不等于没有公告；"
        "请在 reasoning_summary 中注明「本次分析未包含公告数据」。"
    ),
}

_REPORT_GAP_LINES = {
    "sentiment": "新闻情绪分析失败，报告未包含最新舆情数据",
    "announcement": "公告检索失败，报告未包含公告动态",
    "market": "大盘指数缺失，报告未包含市场环境参考",
    "financials": "财务数据缺失，报告未包含基本面参考",
}


def _collect_gaps(state: AgentState) -> list:
    """盘点本次缺失的数据路，返回稳定的缺口键列表（顺序即标注顺序）"""
    gaps = []
    if state.get("sentiment_ok") is False:
        gaps.append("sentiment")
    if state.get("announcement_ok") is False:
        gaps.append("announcement")
    if not state.get("market_index"):
        gaps.append("market")
    if not state.get("financial_data"):
        gaps.append("financials")
    return gaps


def _gap_note(gaps: list) -> str:
    """把缺口列表写成 prompt 里的「数据缺口说明」段"""
    if not gaps:
        return ""
    lines = "\n".join(f"- {_REPORT_GAP_LINES[g]}" for g in gaps)
    return (
        "以下数据本次缺失。请勿臆造其内容，也不要把「未提供」解读为「没有风险」"
        "或「无重大事项」：\n" + lines
    )


def _predict(state: AgentState, degraded: bool = False) -> Dict[str, Any]:
    """综合预测：LLM 整合所有分析 → JSON"""
    gaps = _collect_gaps(state)
    logger.info(f"🧠 [PredictionAgent] 综合预测{'（降级，缺口: ' + ', '.join(gaps) + '）' if degraded else ''}...")

    try:
        sentiment_analysis = state.get("news_sentiment_result", "暂无语义分析")
        if "sentiment" in gaps:
            sentiment_analysis = _SIGNAL_GAP_PLACEHOLDERS["sentiment"]

        announcement_context = state.get("announcement_context", "") or ""
        if "announcement" in gaps:
            announcement_context = _SIGNAL_GAP_PLACEHOLDERS["announcement"]

        prompt = build_prediction_prompt(
            stock_name=state.get("stock_name", ""),
            stock_code=state.get("stock_code", ""),
            technical_analysis=state.get("technical_analysis_result", "暂无技术分析"),
            sentiment_analysis=sentiment_analysis,
            financial_data=state.get("financial_data", {}),
            realtime_quote=state.get("realtime_quote", {}),
            market_index=state.get("market_index", {}),
            announcement_context=announcement_context,
            data_gap_note=_gap_note(gaps),
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

        # 信号级缺口时置信度封顶：报告可以说得委婉，数字必须由代码兜住
        if degraded and prediction["confidence"] > _DEGRADED_CONFIDENCE_CAP:
            prediction["confidence"] = _DEGRADED_CONFIDENCE_CAP
            prediction.setdefault("risk_warnings", []).append(
                f"本次存在数据缺口（{', '.join(gaps)}），置信度已被强制下调"
            )
            logger.info(f"  ⚠️ 存在信号级缺口，置信度封顶 {_DEGRADED_CONFIDENCE_CAP}")

        logger.info(f"  ✅ 综合预测: trend={prediction.get('trend')}, confidence={prediction.get('confidence')}")
        return {"prediction": prediction}

    except Exception as e:
        logger.error(f"  ❌ 综合预测失败: {e}")
        return {
            # 只返回本次新增的错误：errors 带 add reducer，会自动与已有列表拼接
            "errors": [f"综合预测失败: {str(e)}"],
            "prediction": _get_default_prediction(),
        }


def _generate_report(state: AgentState, degraded: bool = False) -> Dict[str, Any]:
    """报告生成：LLM 整合所有内容 → Markdown"""
    gaps = _collect_gaps(state)
    logger.info(f"📝 [PredictionAgent] 生成报告{'（降级，缺口: ' + ', '.join(gaps) + '）' if degraded else ''}...")

    try:
        sentiment_analysis = state.get("news_sentiment_result", "暂缺")
        if "sentiment" in gaps:
            sentiment_analysis = _SIGNAL_GAP_PLACEHOLDERS["sentiment"]

        announcement_context = state.get("announcement_context", "") or ""
        if "announcement" in gaps:
            announcement_context = _SIGNAL_GAP_PLACEHOLDERS["announcement"]

        prompt = build_report_prompt(
            stock_name=state.get("stock_name", ""),
            stock_code=state.get("stock_code", ""),
            technical_analysis=state.get("technical_analysis_result", "暂缺"),
            sentiment_analysis=sentiment_analysis,
            financial_data=state.get("financial_data", {}),
            prediction=state.get("prediction", {}),
            announcement_context=announcement_context,
            data_gap_note=_gap_note(gaps),
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

        # 缺口必须在报告最显眼处说清"缺了什么"，而不是让读者自己发现。
        # 信号级缺口（降级分支）一定至少缺一路；数据级缺口在正常分支也会出现
        if gaps:
            gap_lines = "\n".join(f"> - {_REPORT_GAP_LINES[g]}" for g in gaps)
            header_parts[1:1] = [
                f"> ⚠️ **数据缺口提示**：本次分析缺失以下数据，相关结论的置信度应相应下调：\n{gap_lines}",
                "",
            ]

        if quote:
            change_pct = quote.get("change_pct", 0)
            # 中国市场约定：红涨绿跌（与欧美相反）
            emoji = "🔴" if change_pct > 0 else ("🟢" if change_pct < 0 else "⚪")
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
            "errors": [f"报告生成失败: {str(e)}"],
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
    gaps = _collect_gaps(state)
    if gaps:
        parts.append("## ⚠️ 数据缺口")
        parts.extend(f"- {_REPORT_GAP_LINES[g]}" for g in gaps)
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
        "> **⚠️ 免责声明**：本报告由 LLM 工作流自动生成，仅供参考，不构成任何投资建议。",
        "> 股市有风险，投资需谨慎。",
    ])
    return "\n\n".join(parts)


def build_prediction_agent(degraded: bool = False) -> StateGraph:
    """构建综合预测 + 报告子 Agent

    degraded=True 是主图降级分支用的实例（存在信号级缺口）：除了按 state 里的
    缺口逐项换占位说明、标注报告外，还把置信度强制封顶。缺口具体是哪几路
    不看这个参数，看 sentiment_ok / announcement_ok / market_index /
    financial_data（见 _collect_gaps）。主图用条件边决定实例化哪一版（见 agent/graph.py）。
    """
    workflow = StateGraph(AgentState, input=PredictionAgentInput, output=PredictionAgentOutput)
    workflow.add_node("predict", partial(_predict, degraded=degraded))
    workflow.add_node("report", partial(_generate_report, degraded=degraded))
    workflow.set_entry_point("predict")
    workflow.add_edge("predict", "report")
    workflow.add_edge("report", END)
    return workflow.compile()
