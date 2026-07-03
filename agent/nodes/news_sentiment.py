"""
节点3: 新闻情绪分析
LLM 分析新闻/公告的情绪和影响
"""
from typing import Dict, Any
from loguru import logger

from ..state import AgentState
from ..prompts.system_prompts import build_sentiment_prompt
from utils.llm_factory import create_chat_model


def news_sentiment_node(state: AgentState) -> Dict[str, Any]:
    """新闻情绪分析节点 - LLM 解读新闻情绪"""
    logger.info("📰 开始新闻情绪分析...")

    result = {
        "status": "analyzing",
        "errors": state.get("errors", []),
    }

    news_data = state.get("news_data", [])

    # 如果无新闻，跳过
    if not news_data:
        logger.info("  暂无相关新闻，跳过新闻情绪分析")
        result["news_sentiment_result"] = "## 新闻情绪分析\n\n📭 该股票近期暂无相关新闻报道。"
        return result

    try:
        # 1. 构建 Prompt
        prompt = build_sentiment_prompt(news_data)

        # 2. 调用 LLM
        llm = create_chat_model(
            model=state.get("llm_model"),
            api_key=state.get("llm_api_key"),
            base_url=state.get("llm_base_url"),
            temperature=0.6,
        )

        response = llm.invoke(prompt)
        analysis_text = response.content if hasattr(response, "content") else str(response)

        result["news_sentiment_result"] = analysis_text

        logger.info("  ✅ 新闻情绪分析完成")

    except Exception as e:
        error_msg = f"新闻情绪分析失败: {str(e)}"
        logger.error(f"  ❌ {error_msg}")
        result["errors"].append(error_msg)
        result["news_sentiment_result"] = f"## 新闻情绪分析\n\n❌ 分析过程出错: {str(e)}"

    return result
