# -*- coding: utf-8 -*-
"""Agent 模式核心：harness 运行时的薄壳

真正的循环已经迁到 harness/runtime.py（工具注册 / 预算守卫 / 轨迹落盘都在那层）。
这里只保留对外入口与兼容别名，让 CLI、UI、测试的 import 路径不用改：
- `run_agent_mode`   非流式，阻塞跑完返回 dict
- `stream_agent_mode` 流式，返回事件生成器
- `_dispatch`        旧版工具分发（测试在用），内部走 harness.registry.execute
"""
from typing import Dict, List, Optional

from harness.runtime import (  # noqa: F401 —— 兼容旧 import 路径
    DEFAULT_MAX_STEPS,
    SYSTEM_PROMPT,
    _aggregate,
    _as_text,
    _summarize_result,
    iter_agent_events,
)


def _dispatch(name: str, args: dict, impls: Dict[str, object]) -> str:
    """执行一个工具，永远返回字符串（报错文本也回喂模型）"""
    from harness.registry import execute

    text, _meta = execute(name, args, impls)
    return text


def _iter_agent_events(*args, **kwargs):
    """旧名字保留：README 和外部脚本可能直接引用它"""
    return iter_agent_events(*args, **kwargs)


def run_agent_mode(
    question: str,
    stock_code: str = "",
    max_steps: int = DEFAULT_MAX_STEPS,
    llm=None,
    tool_impls: Optional[Dict[str, object]] = None,
    history: Optional[List[dict]] = None,
    budget=None,
    tracer=None,
) -> dict:
    """ReAct 主循环（非流式）：CLI 与测试用这个。

    Returns:
        answer / trajectory / steps_used / stopped("answered"|"cap"|"budget")
        以及 usage、budget_reason、run_id、trace_path（没传 tracer 时后两项为空）
    """
    final = {"answer": "", "trajectory": [], "steps_used": 0, "stopped": "answered"}
    for ev in iter_agent_events(
        question=question,
        stock_code=stock_code,
        max_steps=max_steps,
        llm=llm,
        tool_impls=tool_impls,
        history=history,
        stream=False,
        budget=budget,
        tracer=tracer,
    ):
        if ev["type"] == "done":
            final = {
                "answer": ev["answer"],
                "trajectory": ev["trajectory"],
                "steps_used": ev["steps_used"],
                "stopped": ev["stopped"],
                "usage": ev.get("usage") or {},
                "budget_reason": ev.get("budget_reason"),
                "run_id": getattr(tracer, "run_id", None),
                "trace_path": tracer.rel_path() if tracer is not None else "",
            }
    return final


def stream_agent_mode(
    question: str,
    stock_code: str = "",
    max_steps: int = DEFAULT_MAX_STEPS,
    llm=None,
    tool_impls: Optional[Dict[str, object]] = None,
    history: Optional[List[dict]] = None,
    budget=None,
    tracer=None,
):
    """流式版 ReAct：返回事件生成器，交给 UI 逐条渲染。

    事件类型见 harness/runtime.iter_agent_events 的 docstring。
    """
    return iter_agent_events(
        question=question,
        stock_code=stock_code,
        max_steps=max_steps,
        llm=llm,
        tool_impls=tool_impls,
        history=history,
        stream=True,
        budget=budget,
        tracer=tracer,
    )
