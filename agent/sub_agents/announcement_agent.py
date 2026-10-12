# -*- coding: utf-8 -*-
"""
公告检索节点（RAG）

与技术分析 / 新闻情绪并行运行，产出 announcement_context 供综合预测使用。

注意：这里是一个**普通函数节点**，不是子图。因为它只有一步（建索引→检索→
拼文本），没有多步 LLM 调用；用纯函数节点能避开子图状态映射的坑
（见 agent/state.py 底部的契约说明）。
"""
from typing import Any, Dict

from loguru import logger

from ..state import AgentState


def analyze_announcements(state: AgentState) -> Dict[str, Any]:
    """检索该股票的公告全文，拼成"公告动态"文本"""
    if not state.get("rag_enabled", True):
        logger.info("📢 [AnnouncementAgent] 公告检索已关闭，跳过")
        return {"announcement_context": ""}

    code = state.get("stock_code", "")
    end_date = state.get("end_date", "")
    if not code:
        return {"announcement_context": ""}

    logger.info(f"📢 [AnnouncementAgent] 检索公告 {code}...")
    try:
        # 延迟导入：避免没装 chromadb/sentence_transformers 时整个 agent 包导入失败
        from rag.service import build_stock_context

        text = build_stock_context(code, end_date=end_date or None)
        if not text:
            logger.info("  近期无相关公告")
        return {"announcement_context": text}

    except Exception as e:
        logger.error(f"  ❌ 公告检索失败: {e}")
        # 降级：返回空文本 + 一条错误，绝不中断流水线
        return {
            "announcement_context": "",
            "errors": [f"公告检索失败: {str(e)}"],
        }
