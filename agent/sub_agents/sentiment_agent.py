"""
子 Agent: 新闻情绪分析
LLM 分析新闻/公告的情绪——利好/利空/中性，打星评分
"""
from typing import Dict, Any
from loguru import logger

from langgraph.graph import StateGraph, END

from ..state import AgentState
from ..prompts.system_prompts import build_sentiment_prompt
from utils.llm_factory import create_chat_model


def _analyze_sentiment(state: AgentState) -> Dict[str, Any]:
    """LLM 新闻情绪分析"""
    logger.info("📰 [SentimentAgent] 分析新闻情绪...")

    news_data = state.get("news_data", [])

    if not news_data:
        logger.info("  暂无新闻，跳过")
        return {
            "news_sentiment_result": "## 新闻情绪分析\n\n📭 该股票近期暂无相关新闻报道。",
        }

    try:
        prompt = build_sentiment_prompt(news_data)

        llm = create_chat_model(
            model=state.get("llm_model"),
            api_key=state.get("llm_api_key"),
            base_url=state.get("llm_base_url"),
            temperature=0.6,
        )

        response = llm.invoke(prompt)
        analysis_text = response.content if hasattr(response, "content") else str(response)

        logger.info("  ✅ 新闻情绪分析完成")
        return {"news_sentiment_result": analysis_text}

    except Exception as e:
        logger.error(f"  ❌ 新闻情绪分析失败: {e}")
        return {
            "errors": state.get("errors", []) + [f"新闻情绪分析失败: {str(e)}"],
            "news_sentiment_result": f"## 新闻情绪分析\n\n❌ 分析过程出错: {str(e)}",
        }


def build_sentiment_agent() -> StateGraph:
    """构建新闻情绪子 Agent"""
    workflow = StateGraph(AgentState)
    workflow.add_node("analyze", _analyze_sentiment)
    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", END)
    return workflow.compile()
