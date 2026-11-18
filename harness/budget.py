# -*- coding: utf-8 -*-
"""预算守卫：步数 / token / 墙钟 / 成本

为什么不是「让模型自己收敛」：和主流程「置信度由代码封顶 0.6」同一思路——
能写进代码的硬约束就不该指望 prompt。模型可以无视「快没预算了」的提醒，
但改不了 Budget.limit_reason() 的返回值。
"""
import time
from dataclasses import dataclass, field
from typing import Optional


class BudgetExceeded(RuntimeError):
    """调用方显式要求「超了就抛」时使用；运行时默认走降级收尾，不抛"""

    def __init__(self, limit: str, detail: str = ""):
        self.limit = limit
        super().__init__(f"预算超限: {limit}" + (f" — {detail}" if detail else ""))
@dataclass
class Budget:
    max_steps: int = 12
    max_tokens: int = 60000
    max_seconds: float = 180.0
    max_cost_cny: Optional[float] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_cny: Optional[float] = None
    _started: float = field(default=0.0, repr=False)

    def start(self) -> "Budget":
        self._started = time.monotonic()
        return self

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self._started if self._started else 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add_usage(self, usage: Optional[dict], *, price_prompt: float = 0.0,
                  price_completion: float = 0.0) -> None:
        """累加一次 LLM 调用的 token 用量；单价 > 0 时才计算成本。

        单价留空（默认 0）就报「成本未配置」而不是编一个数字——报错的口径
        可以宽，钱的数字不能猜。
        """
        usage = usage or {}
        p = int(usage.get("prompt_tokens") or 0)
        c = int(usage.get("completion_tokens") or 0)
        self.prompt_tokens += p
        self.completion_tokens += c
        if price_prompt > 0 or price_completion > 0:
            spent = (p / 1000) * price_prompt + (c / 1000) * price_completion
            self.cost_cny = round((self.cost_cny or 0.0) + spent, 6)

    def limit_reason(self, steps_used: int = 0) -> Optional[str]:
        """返回触顶的预算名；没触顶返回 None。运行时每轮开头调用一次。"""
        if steps_used >= self.max_steps:
            return "max_steps"
        if self.max_seconds and self.elapsed_s >= self.max_seconds:
            return "max_seconds"
        if self.max_tokens and self.total_tokens >= self.max_tokens:
            return "max_tokens"
        if self.max_cost_cny is not None and (self.cost_cny or 0.0) >= self.max_cost_cny:
            return "max_cost_cny"
        return None

    def summary(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_cny": self.cost_cny,
            "elapsed_s": round(self.elapsed_s, 3),
        }


def from_settings(max_steps: int = 12, *, max_tokens: int = None,
                  max_seconds: float = None) -> Budget:
    """按 config.py 的默认值造一个预算；显式参数优先，便于 CLI 覆盖"""
    from config import settings

    return Budget(
        max_steps=max_steps,
        max_tokens=max_tokens if max_tokens is not None else settings.harness_max_tokens,
        max_seconds=max_seconds if max_seconds is not None else settings.harness_max_seconds,
    ).start()
