"""
节点5: 报告生成
LLM 将所有分析结果整合为一份完整的中文 Markdown 报告
"""
from typing import Dict, Any
from loguru import logger

from ..state import AgentState
from ..prompts.system_prompts import build_report_prompt
from utils.llm_factory import create_chat_model


def report_generation_node(state: AgentState) -> Dict[str, Any]:
    """报告生成节点 - 格式化最终中文报告"""
    logger.info("📝 开始生成分析报告...")

    result = {
        "status": "done",
        "errors": state.get("errors", []),
    }

    try:
        # 1. 构建报告 Prompt
        prompt = build_report_prompt(
            stock_name=state.get("stock_name", ""),
            stock_code=state.get("stock_code", ""),
            technical_analysis=state.get("technical_analysis_result", "暂缺"),
            sentiment_analysis=state.get("news_sentiment_result", "暂缺"),
            financial_data=state.get("financial_data", {}),
            prediction=state.get("prediction", {}),
        )

        # 2. 调用 LLM（稍高温度使报告更自然）
        llm = create_chat_model(
            model=state.get("llm_model"),
            api_key=state.get("llm_api_key"),
            base_url=state.get("llm_base_url"),
            temperature=0.3,
        )

        response = llm.invoke(prompt)
        report_text = response.content if hasattr(response, "content") else str(response)

        # 3. 添加报告头部信息
        stock_name = state.get("stock_name", "")
        stock_code = state.get("stock_code", "")
        quote = state.get("realtime_quote", {})
        prediction = state.get("prediction", {})

        # 构建报告头部
        header_parts = [
            f"# 📈 {stock_name}（{stock_code}）智能分析报告",
            "",
            f"**生成时间**：{_get_current_time()}",
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

        header = "\n".join(header_parts)
        full_report = header + "\n\n---\n\n" + report_text

        result["final_report"] = full_report

        logger.info("  ✅ 报告生成完成")

    except Exception as e:
        error_msg = f"报告生成失败: {str(e)}"
        logger.error(f"  ❌ {error_msg}")
        result["errors"].append(error_msg)
        # 构建一个简单的兜底报告
        result["final_report"] = _build_fallback_report(state)

    return result


def _build_fallback_report(state: AgentState) -> str:
    """构建兜底报告"""
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


def _get_current_time() -> str:
    """获取当前时间字符串"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
