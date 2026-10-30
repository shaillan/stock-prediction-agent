# -*- coding: utf-8 -*-
"""
Agent 模式核心：带步数上限和轨迹记录的 ReAct 循环

README「工作流 vs Agent」的分界线在这里兑现：
- 工作流：代码写死调用顺序，LLM 只拿到材料写作文
- 这里：LLM 拿到**工具清单**，看着每轮工具结果自己决定「下一步查什么、
  够不够下结论」——调用次数不固定，唯一的上限是 max_steps（成本护栏）

`_iter_agent_events` 是唯一的核心实现：每走一步 yield 一条结构化事件。
两个出口都从它派生，避免两份循环逻辑慢慢分叉——
- `run_agent_mode`：消费事件拼回 dict（CLI / 测试用，行为与旧版一致）
- `stream_agent_mode`：把事件直接交给 UI（流式 token + 工具状态）

手写循环而不是 langgraph.prebuilt.create_react_agent：教学价值（每一步都看得见）
+ 轨迹日志要进返回值 + 步数上限的行为要自己说了算。
"""
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from langchain_core.messages import (
    AIMessage, HumanMessage, SystemMessage, ToolMessage,
)
from loguru import logger

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


def _dispatch(name: str, args: dict, impls: Dict[str, object]) -> str:
    """执行一个工具调用，永远返回字符串（结果或报错信息）。

    报错不抛出而是作为 ToolMessage 内容回喂模型——延续「缺口诚实」哲学：
    模型看到的失败信息足够具体，才能自己决定换条路还是放弃并说明缺什么。
    """
    if name not in impls:
        known = "、".join(sorted(impls))
        return f"未知工具 {name}。可用工具: {known}"
    try:
        result = impls[name](**args)
        text = result if isinstance(result, str) else str(result)
        return text or "（工具返回空）"
    except Exception as e:
        return f"工具执行失败: {type(e).__name__}: {e}（最多重试一次，然后改用其它信息）"


def _summarize_result(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text[:limit] + ("…" if len(text) > limit else "")


def _as_text(content) -> str:
    """最终回答统一成纯文本：部分模型会把 content 返回成块列表而非字符串"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            c.get("text", "") if isinstance(c, dict) else str(c) for c in content
        )
    return str(content or "")


def _aggregate(tool_chunks: List[dict]) -> List[dict]:
    """把流式分片的工具调用拼回完整调用。

    流式返回时，一次工具调用的 args 是**分片 JSON 字符串**，例如：
        {index:0, name:"query_market", args:""}
        {index:0, args:"{\"stock_code\":"}
        {index:0, args:"\"600519\"}"}
    必须按 index 拼起来再 json.loads，否则拿到的永远是半截参数。
    """
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
            # 参数没拼完整就回退空参：交给 _dispatch 报「缺参数」，比吞掉整轮好
            args = {}
        out.append({
            "name": slot["name"],
            "args": args,
            "id": slot["id"] or f"call_{i}",
        })
    return out


def _iter_agent_events(
    question: str,
    stock_code: str = "",
    max_steps: int = DEFAULT_MAX_STEPS,
    llm=None,
    tool_impls: Optional[Dict[str, object]] = None,
    history: Optional[List[dict]] = None,
    stream: bool = False,
):
    """ReAct 主循环的事件生成器（唯一核心实现）。

    yield 的事件类型：
    - {"type": "tool_start", "name", "args", "step"}  一轮内所有工具先宣告开始
    - {"type": "tool_end",   "name", "summary", "step"} 并行执行完按调用顺序回填
    - {"type": "token",      "text"}                   仅 stream=True
    - {"type": "done", "answer", "trajectory", "steps_used", "stopped"}

    Args:
        history: 多轮对话的上文，形如 [{"role": "user"|"assistant", "content": str}]，
                 不含本轮问题
        stream: True 时用 llm.stream 逐 token 产出；False 时用 invoke 一次性拿
    """
    from agent_mode.tools import TOOL_SPECS, TOOL_IMPLS

    impls = tool_impls if tool_impls is not None else TOOL_IMPLS
    sys_prompt = SYSTEM_PROMPT.format(
        stock=stock_code or "用户提到的股票", max_steps=max_steps)
    messages = [SystemMessage(content=sys_prompt)]

    # 多轮记忆：把前几轮的 Q/A 铺在系统提示之后、本轮问题之前
    for turn in (history or []):
        content = (turn or {}).get("content", "")
        if (turn or {}).get("role") == "user":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=question))

    bound = llm.bind_tools(TOOL_SPECS)
    trajectory: List[dict] = []
    steps_used = 0

    for _ in range(max_steps):
        text_parts: List[str] = []
        tool_chunks: List[dict] = []

        if not stream:
            resp: AIMessage = bound.invoke(messages)
            text_parts.append(_as_text(resp.content))
            calls = resp.tool_calls or []
            ai_msg = resp
        else:
            for chunk in bound.stream(messages):
                content = getattr(chunk, "content", "") or ""
                if content:
                    text_parts.append(content)
                    yield {"type": "token", "text": content}
                tool_chunks.extend(getattr(chunk, "tool_call_chunks", None) or [])

            calls = _aggregate(tool_chunks)
            # 兜底：个别厂商的流式分片格式不同，拼不出工具名。若此时还没吐出
            # 任何 token，就回退非流式拿完整 tool_calls（ChatAnthropic 走这条）。
            if tool_chunks and not any(tc.get("name") for tc in calls) and not text_parts:
                resp = bound.invoke(messages)
                text_parts = [_as_text(resp.content)]
                calls = resp.tool_calls or []
            ai_msg = AIMessage(content="".join(text_parts), tool_calls=calls)

        if not calls:
            # 模型不再要工具 = 它认为能答了
            yield {
                "type": "done",
                "answer": "".join(text_parts),
                "trajectory": trajectory,
                "steps_used": steps_used,
                "stopped": "answered",
            }
            return

        # 先把整条 AIMessage（含全部 tool_calls）放进历史，再逐个回填 ToolMessage；
        # 顺序不能反——langchain 校验每个 tool_call_id 都要有对应的 ToolMessage
        messages.append(ai_msg)

        # 先全部宣告「开始」，让 UI 能把它们同时显示成进行中
        started = []
        for tc in calls:
            steps_used += 1
            started.append((steps_used, tc))
            yield {
                "type": "tool_start",
                "name": tc["name"],
                "args": tc.get("args") or {},
                "step": steps_used,
            }

        # 并行执行：这些工具都是网络/IO 调用（AKShare 尤其慢），串行会白白叠加等待。
        # 用 map 而不是 as_completed —— map 保序返回，轨迹和 ToolMessage 的顺序就是
        # 模型的调用顺序，测试与 CLI 输出都稳定。
        with ThreadPoolExecutor(max_workers=max(1, len(started))) as pool:
            results = list(pool.map(
                lambda item: _dispatch(item[1]["name"], item[1].get("args") or {}, impls),
                started,
            ))

        for (step, tc), result in zip(started, results):
            messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
            summary = _summarize_result(result)
            trajectory.append({
                "step": step,
                "tool": tc["name"],
                "args": tc.get("args") or {},
                "summary": summary,
            })
            logger.info(
                "[agent_mode] step {} {}({}) → {}",
                step, tc["name"],
                _summarize_result(str(tc.get("args") or {}), 80),
                _summarize_result(result, 60),
            )
            yield {
                "type": "tool_end",
                "name": tc["name"],
                "summary": summary,
                "step": step,
            }

    # 步数到顶：循环没有自然 break。给模型最后一次机会，不带工具、
    # 只基于已收集的信息收尾——这是「cap」分支和普通 LLM 尾调用的差别
    messages.append(HumanMessage(
        content="工具步数已用完。请只基于已收集到的信息直接给出结论，"
                "并明确说明还有哪些信息没查到、对结论有什么影响。"
    ))
    parts: List[str] = []
    if stream:
        for chunk in llm.stream(messages):  # 原生 llm（未绑工具），保证不再产生 tool_calls
            content = getattr(chunk, "content", "") or ""
            if content:
                parts.append(content)
                yield {"type": "token", "text": content}
    else:
        parts = [_as_text(llm.invoke(messages).content)]

    yield {
        "type": "done",
        "answer": "".join(parts),
        "trajectory": trajectory,
        "steps_used": steps_used,
        "stopped": "cap",
    }


def run_agent_mode(
    question: str,
    stock_code: str = "",
    max_steps: int = DEFAULT_MAX_STEPS,
    llm=None,
    tool_impls: Optional[Dict[str, object]] = None,
    history: Optional[List[dict]] = None,
) -> dict:
    """ReAct 主循环（非流式）：阻塞跑完再返回，CLI 与测试用这个。

    实现上只是 `_iter_agent_events` 的薄包装——两条出口共用同一份循环逻辑。

    Returns:
        dict: answer(最终结论) / trajectory(每步轨迹) / steps_used /
              stopped("answered" 自然收尾 | "cap" 步数到顶)
    """
    final = {
        "answer": "",
        "trajectory": [],
        "steps_used": 0,
        "stopped": "answered",
    }
    for ev in _iter_agent_events(
        question=question,
        stock_code=stock_code,
        max_steps=max_steps,
        llm=llm,
        tool_impls=tool_impls,
        history=history,
        stream=False,
    ):
        if ev["type"] == "done":
            final = {
                "answer": ev["answer"],
                "trajectory": ev["trajectory"],
                "steps_used": ev["steps_used"],
                "stopped": ev["stopped"],
            }
    return final


def stream_agent_mode(
    question: str,
    stock_code: str = "",
    max_steps: int = DEFAULT_MAX_STEPS,
    llm=None,
    tool_impls: Optional[Dict[str, object]] = None,
    history: Optional[List[dict]] = None,
):
    """流式版 ReAct：返回事件生成器，交给 UI 逐条渲染。

    事件类型见 `_iter_agent_events` 的 docstring。
    """
    return _iter_agent_events(
        question=question,
        stock_code=stock_code,
        max_steps=max_steps,
        llm=llm,
        tool_impls=tool_impls,
        history=history,
        stream=True,
    )
