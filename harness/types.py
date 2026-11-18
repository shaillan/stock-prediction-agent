# -*- coding: utf-8 -*-
"""Harness 的数据结构：工具规格、运行记录、事件契约

事件契约（runtime 只 yield 这四种，UI / CLI / 评测都按它消费）：
    {"type": "tool_start", "name", "args", "step"}
    {"type": "tool_end",   "name", "summary", "step", "elapsed_ms", "cached", "retries"}
    {"type": "token",      "text"}                      # 仅 stream=True
    {"type": "done", "answer", "trajectory", "steps_used", "stopped", "usage"}
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class ToolSpec:
    """一个可被模型调用的工具。

    timeout_s / retries / cache_ttl_s 是 harness 相对「裸函数」新增的三件事：
    超时防止 AKShare 卡死整轮，重试覆盖偶发网络抖动，缓存压掉同轮重复查询。
    """
    name: str
    description: str
    impl: Callable[..., Any]
    schema: Dict[str, Any] = field(default_factory=dict)
    timeout_s: float = 20.0
    retries: int = 0
    cache_ttl_s: float = 0.0
    tags: List[str] = field(default_factory=list)


@dataclass
class RunRecord:
    """一次 Agent 运行的完整档案，落盘到 runs/<日期>/<run_id>.jsonl 的末尾摘要"""
    run_id: str
    question: str
    stock_code: str = ""
    model: str = ""
    steps_used: int = 0
    stopped: str = "answered"
    tools: List[str] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    wall_s: float = 0.0
    trace_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "question": self.question,
            "stock_code": self.stock_code,
            "model": self.model,
            "steps_used": self.steps_used,
            "stopped": self.stopped,
            "tools": list(self.tools),
            "usage": dict(self.usage),
            "wall_s": round(self.wall_s, 3),
            "trace_path": self.trace_path,
        }
