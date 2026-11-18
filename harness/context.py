# -*- coding: utf-8 -*-
"""上下文装配：系统提示 + 历史 + 本轮问题，并给历史设一个字符预算

多轮对话最容易无声失控的地方：聊到第五轮，历史 + 工具结果把上下文塞满，
模型开始丢前面的信息、费用也开始飙。这里从最旧的轮次开始丢，
丢到放得下为止——只丢历史，不动系统提示和本轮问题。
"""
from typing import Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger

DEFAULT_MAX_CHARS = 12000


def _content_len(turn: Dict) -> int:
    return len(str(turn.get("content") or ""))


def build_messages(system_prompt: str, history: Optional[List[dict]] = None,
                   question: str = "",
                   max_chars: int = DEFAULT_MAX_CHARS) -> List:
    """把 (系统提示, 历史, 本轮问题) 装配成 LangChain 消息列表。

    历史形如 [{"role": "user"|"assistant", "content": str}]，不含本轮问题。
    """
    turns = [t for t in (history or [])
             if isinstance(t, dict) and t.get("content")]
    system_len = len(system_prompt) + len(question or "")

    def total() -> int:
        return system_len + sum(_content_len(t) for t in turns)

    dropped = 0
    while turns and total() > max_chars:
        turns.pop(0)
        dropped += 1
    if dropped:
        logger.warning(
            f"[harness] 历史超出 {max_chars} 字符预算，丢弃最旧的 {dropped} 条消息")

    messages = [SystemMessage(content=system_prompt)]
    for turn in turns:
        content = str(turn.get("content") or "")
        if turn.get("role") == "user":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=question or ""))
    return messages
