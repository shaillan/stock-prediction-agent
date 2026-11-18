# -*- coding: utf-8 -*-
"""模型适配：把不同厂商的消息差异收敛成两件事——文本和 token 用量

LangChain 的 usage 字段在不同 provider 上位置不一样：
- 新版标准：message.usage_metadata = {input_tokens, output_tokens, total_tokens}
- OpenAI 兼容：message.response_metadata["token_usage"]
- 流式：只有最后一个 chunk 可能带用量
这里统一成 {prompt_tokens, completion_tokens, total_tokens}，拿不到就返回空 dict
（宁可显示「未知」，也不编一个数字）。
"""
import time
from typing import Any, Optional

from loguru import logger


def _num(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def extract_usage(message: Any) -> dict:
    """从 AIMessage / AIMessageChunk 提取 token 用量；没有就返回 {}"""
    if message is None:
        return {}

    um = getattr(message, "usage_metadata", None) or {}
    if isinstance(um, dict) and um:
        prompt = _num(um.get("input_tokens"))
        completion = _num(um.get("output_tokens"))
        if prompt or completion:
            return {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": _num(um.get("total_tokens")) or prompt + completion,
            }

    rm = getattr(message, "response_metadata", None) or {}
    if isinstance(rm, dict):
        raw = rm.get("token_usage") or rm.get("usage") or {}
        if isinstance(raw, dict) and raw:
            prompt = _num(raw.get("prompt_tokens") or raw.get("input_tokens"))
            completion = _num(raw.get("completion_tokens") or raw.get("output_tokens"))
            if prompt or completion:
                return {
                    "prompt_tokens": prompt,
                    "completion_tokens": completion,
                    "total_tokens": _num(raw.get("total_tokens")) or prompt + completion,
                }
    return {}


def invoke_with_retry(model, messages, retries: int = 2, base_delay: float = 0.8):
    """非流式调用 + 指数退避。只包 invoke；流式的重试在 runtime 里按轮处理。"""
    last: Optional[BaseException] = None
    for attempt in range(retries + 1):
        try:
            return model.invoke(messages)
        except Exception as exc:  # noqa: BLE001 —— 交给调用方决定是否放弃
            last = exc
            if attempt < retries:
                logger.warning(f"[harness] LLM 调用失败，第 {attempt + 1} 次重试：{exc}")
                time.sleep(base_delay * (2 ** attempt))
    raise last
