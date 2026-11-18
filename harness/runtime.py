# -*- coding: utf-8 -*-
"""Harness 运行时：ReAct 循环 + 事件流 + 预算守卫 + 轨迹落盘

这是从 agent_mode/loop.py 迁出来的核心实现，agent_mode.loop 现在只是薄壳。
相比旧版多出三件事，事件类型与顺序完全不变（UI 与测试无感）：
- 每轮开头查预算（墙钟 / token / 成本），触顶就转「降级收尾」而不是硬断
- 工具调用走 registry：带超时、重试、缓存，失败文本口径与旧版一致
- 传了 tracer 就逐事件脱敏落盘，done 事件处自动收尾
"""
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from langchain_core.messages import (
    AIMessage, HumanMessage, SystemMessage, ToolMessage,
)
from loguru import logger

from harness.adapters import extract_usage, invoke_with_retry
from harness.budget import Budget
from harness.context import build_messages

DEFAULT_MAX_STEPS = 12

SYSTEM_PROMPT = """你是一位严谨的 A 股研究助理，回答用户的开放式问题。

规则：
1. 研究对象默认是股票代码 {stock}；工具的 stock_code 参数都填它（除非用户明确问别的股票）
2. 先想清楚回答这个问题需要哪些信息，再调工具；一次可以同时调多个独立工具
3. 信息够用就直接写结论——不要为了调工具而调工具
4. 工具报错最多重试一次，然后改用其它信息，或在结论里如实说明缺什么
5. 结论要写小白能听懂的中文：给数字、给口径（哪个工具查的）、必要时打个比方
6. 最多可用 {max_steps} 轮工具；快用完时优先收尾下结论
7. 这只是分析参考，不构成投资建议——涉及"该不该买"时把这句话带上"""


def _as_text(content) -> str:
    """最终回答统一成纯文本：部分模型会把 content 返回成块列表而非字符串"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            c.get("text", "") if isinstance(c, dict) else str(c) for c in content
        )
    return str(content or "")


def _summarize_result(text: str, limit: int = 160) -> str:
    text = " ".join(str(text).split())
    return text[:limit] + ("…" if len(text) > limit else "")


def _aggregate(tool_chunks: List[dict]) -> List[dict]:
    """把流式分片的工具调用拼回完整调用（args 是分片 JSON 字符串，按 index 拼）"""
    by_index: Dict[int, dict] = {}
    for tc in tool_chunks:
        i = int(tc.get("index", 0) or 0)
        slot = by_index.setdefault(i, {"name": "", "args": "", "id": ""})
        if tc.get("name"):
            slot["name"] += tc["name"]
        if tc.get("args"):
            slot["args"] += tc["args"]
        if tc.get("id"):
            slot["id"] = tc["id"]

    out = []
    for i in sorted(by_index):
        slot = by_index[i]
        try:
            args = json.loads(slot["args"]) if slot["args"] else {}
        except json.JSONDecodeError:
            args = {}  # 参数没拼完整就回退空参，交给工具报「缺参数」
        out.append({"name": slot["name"], "args": args,
                    "id": slot["id"] or f"call_{i}"})
    return out


def _run_tools(started: List[tuple], impls: Optional[Dict]) -> List[tuple]:
    """并行执行本轮所有工具，返回 [(text, meta)]，顺序与调用顺序一致。

    工具内部自己带超时（registry._call_with_timeout），所以这里的 worker
    一定会在 timeout 内返回，外层线程池不会因为一个卡死的请求而挂住。
    """
    from harness.registry import execute

    def _one(item):
        _step, tc = item
        return execute(tc["name"], tc.get("args") or {}, impls)

    with ThreadPoolExecutor(max_workers=max(1, len(started))) as pool:
        return list(pool.map(_one, started))


def iter_agent_events(
    question: str,
    stock_code: str = "",
    max_steps: int = DEFAULT_MAX_STEPS,
    llm=None,
    tool_impls: Optional[Dict[str, object]] = None,
    history: Optional[List[dict]] = None,
    stream: bool = False,
    budget: Optional[Budget] = None,
    tracer=None,
    system_prompt: Optional[str] = None,
    tool_specs=None,
):
    """ReAct 主循环的事件生成器（唯一核心实现）。

    yield 的事件类型见 harness/types.py 顶部的契约。额外保证：
    - 每轮开头检查预算，触顶后 stopped="budget"（与步数到顶的 "cap" 区分）
    - done 事件带 usage（prompt/completion/total/cost/elapsed）
    - 传了 tracer 则逐事件脱敏落盘
    """
    if tool_specs is None or tool_impls is None:
        from agent_mode.tools import TOOL_IMPLS, TOOL_SPECS
        tool_specs = tool_specs if tool_specs is not None else TOOL_SPECS
        tool_impls = tool_impls if tool_impls is not None else TOOL_IMPLS

    budget = budget or Budget(max_steps=max_steps)
    if not budget._started:
        budget.start()

    from config import settings
    price_prompt = settings.harness_price_prompt_cny_per_1k
    price_completion = settings.harness_price_completion_cny_per_1k

    prompt = system_prompt or SYSTEM_PROMPT.format(
        stock=stock_code or "用户提到的股票", max_steps=max_steps)
    messages = build_messages(prompt, history, question)
    bound = llm.bind_tools(tool_specs)

    def emit(ev: dict) -> dict:
        if tracer is not None:
            tracer.emit(ev)
        return ev

    trajectory: List[dict] = []
    steps_used = 0
    budget_hit: Optional[str] = None

    for _ in range(max_steps):
        reason = budget.limit_reason(steps_used)
        if reason:
            budget_hit = reason
            logger.warning(f"[harness] 预算触顶（{reason}），进入降级收尾")
            break

        text_parts: List[str] = []
        tool_chunks: List[dict] = []
        usage: dict = {}

        if not stream:
            resp = invoke_with_retry(bound, messages)
            text_parts.append(_as_text(resp.content))
            calls = resp.tool_calls or []
            ai_msg = resp
            usage = extract_usage(resp)
        else:
            try:
                for chunk in bound.stream(messages):
                    content = getattr(chunk, "content", "") or ""
                    if content:
                        text_parts.append(content)
                        yield emit({"type": "token", "text": content})
                    tool_chunks.extend(getattr(chunk, "tool_call_chunks", None) or [])
                    usage = extract_usage(chunk) or usage
            except Exception as exc:  # noqa: BLE001
                if text_parts:
                    raise
                logger.warning(f"[harness] 流式调用失败，回退非流式：{exc}")
                resp = invoke_with_retry(bound, messages)
                text_parts = [_as_text(resp.content)]
                calls = resp.tool_calls or []
                ai_msg = resp
                usage = extract_usage(resp)
            else:
                calls = _aggregate(tool_chunks)
                if tool_chunks and not any(tc.get("name") for tc in calls) and not text_parts:
                    resp = invoke_with_retry(bound, messages)
                    text_parts = [_as_text(resp.content)]
                    calls = resp.tool_calls or []
                    ai_msg = resp
                    usage = extract_usage(resp)
                else:
                    ai_msg = AIMessage(content="".join(text_parts), tool_calls=calls)

        budget.add_usage(usage, price_prompt=price_prompt,
                         price_completion=price_completion)

        if not calls:
            yield emit({
                "type": "done",
                "answer": "".join(text_parts),
                "trajectory": trajectory,
                "steps_used": steps_used,
                "stopped": "answered",
                "usage": budget.summary(),
            })
            return

        messages.append(ai_msg)
        started = []
        for tc in calls:
            steps_used += 1
            started.append((steps_used, tc))
            yield emit({
                "type": "tool_start",
                "name": tc["name"],
                "args": tc.get("args") or {},
                "step": steps_used,
            })

        results = _run_tools(started, tool_impls)
        for (step, tc), (text, meta) in zip(started, results):
            messages.append(ToolMessage(content=text, tool_call_id=tc["id"]))
            summary = _summarize_result(text)
            trajectory.append({
                "step": step,
                "tool": tc["name"],
                "args": tc.get("args") or {},
                "summary": summary,
            })
            logger.info(
                "[harness] step {} {}({}) → {}{}",
                step, tc["name"],
                _summarize_result(str(tc.get("args") or {}), 80),
                _summarize_result(text, 60),
                "（缓存）" if meta.get("cached") else "",
            )
            yield emit({
                "type": "tool_end",
                "name": tc["name"],
                "summary": summary,
                "result": text,          # 完整返回：结论溯源卡与数字核对要用
                "step": step,
                "elapsed_ms": meta.get("elapsed_ms", 0),
                "cached": bool(meta.get("cached")),
                "retries": int(meta.get("retries") or 0),
            })

    # 步数到顶仍沿用旧的 "cap" 语义（UI 与测试都按它判断）；只有 token / 墙钟 /
    # 成本这类预算才叫 "budget"，两者的收尾话术也不同。
    stopped = "cap" if budget_hit in (None, "max_steps") else "budget"
    if budget_hit and budget_hit != "max_steps":
        note = (f"预算已到上限（{budget_hit}）。请只基于已收集到的信息直接给出结论，"
                f"并说明还有哪些信息没查到、对结论有什么影响。")
    else:
        note = ("工具步数已用完。请只基于已收集到的信息直接给出结论，"
                "并明确说明还有哪些信息没查到、对结论有什么影响。")
    messages.append(HumanMessage(content=note))

    parts: List[str] = []
    if stream:
        for chunk in llm.stream(messages):  # 原生 llm（未绑工具），保证不再产生 tool_calls
            content = getattr(chunk, "content", "") or ""
            if content:
                parts.append(content)
                yield emit({"type": "token", "text": content})
    else:
        parts = [_as_text(llm.invoke(messages).content)]

    yield emit({
        "type": "done",
        "answer": "".join(parts),
        "trajectory": trajectory,
        "steps_used": steps_used,
        "stopped": stopped,
        "budget_reason": budget_hit,
        "usage": budget.summary(),
    })
