# -*- coding: utf-8 -*-
"""确定性打分器：轨迹 + 答案 → pass/fail 列表

用例字段（JSONL 一行一条）：
    id / question / stock_code
    must_call         必须调用的工具
    must_not_call     不允许调用的工具
    must_contain      答案里必须出现的字符串
    must_not_contain  答案里不允许出现的字符串
    max_steps         步数上限（效率闸）
    max_seconds       耗时上限
    note              给读报告的人看的意图说明
"""
import json
from pathlib import Path
from typing import List, Tuple


def check_case(case: dict, result: dict) -> Tuple[bool, List[str]]:
    """返回 (是否通过, 失败原因列表)；原因写给初学者看，不用错误码"""
    failures: List[str] = []
    tools = [t.get("tool") for t in (result.get("trajectory") or [])]
    answer = result.get("answer") or ""

    for name in case.get("must_call") or []:
        if name not in tools:
            failures.append(f"未调用工具 {name}")
    for name in case.get("must_not_call") or []:
        if name in tools:
            failures.append(f"不应调用工具 {name}")
    for text in case.get("must_contain") or []:
        if text not in answer:
            failures.append(f"答案缺关键词「{text}」")
    for text in case.get("must_not_contain") or []:
        if text in answer:
            failures.append(f"答案出现禁用词「{text}」")

    steps = int(result.get("steps_used") or 0)
    limit = case.get("max_steps")
    if limit is not None and steps > int(limit):
        failures.append(f"步数 {steps} 超过上限 {limit}")

    elapsed = float((result.get("usage") or {}).get("elapsed_s") or 0.0)
    max_s = case.get("max_seconds")
    if max_s is not None and elapsed > float(max_s):
        failures.append(f"耗时 {elapsed:.0f}s 超过上限 {max_s}s")
    return (not failures), failures


def load_suite(path) -> List[dict]:
    """读 JSONL 用例集；空行和 # 注释行跳过，坏行带行号报错"""
    cases: List[dict] = []
    with Path(path).open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno} JSON 解析失败：{exc}") from exc
            case.setdefault("id", f"case-{lineno}")
            cases.append(case)
    return cases
