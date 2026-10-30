# -*- coding: utf-8 -*-
"""
自选股存储 + 套餐额度 —— 可演示商业 Demo 的「用户数据层」

为什么不放数据库：这是单用户、本地跑的演示版本。真正的多用户产品需要
账号体系、鉴权、计费和并发控制，那是另一个量级的事。把存储集中在这一个
文件里，以后换 SQLite / 云端只需要改这里，上层不用动。

免费版 3 只 / 付费版 20 只——这个数字不是随手写的：
免费额度要够用户体验到价值（3 只足以覆盖大部分人的核心持仓观察），
又明显不够用（观察型用户通常盯 5-10 只），付费动机才成立。
"""
import json
import os
from pathlib import Path
from typing import Dict, Tuple

FREE_LIMIT = 3
PRO_LIMIT = 20
_PLANS = {"free": FREE_LIMIT, "pro": PRO_LIMIT}


def _path() -> Path:
    root = Path(__file__).resolve().parent.parent
    return root / "records" / "watchlist.json"


def _default() -> dict:
    return {"plan": "free", "stocks": []}


def load_state() -> dict:
    """读自选股状态；文件缺失/损坏都退回默认值，不让 Demo 崩在启动上"""
    p = _path()
    if not p.exists():
        return _default()
    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _default()
    if not isinstance(data, dict):
        return _default()
    data.setdefault("plan", "free")
    data.setdefault("stocks", [])
    return data


def save_state(state: dict) -> None:
    """原子写入：先写 tmp 再 replace，避免中途崩溃留下半个 JSON"""
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def limit_for(plan: str) -> int:
    return _PLANS.get(plan, FREE_LIMIT)


def add_stock(code: str, name: str = "") -> Tuple[bool, str]:
    """加自选股。返回 (是否成功, 失败原因)"""
    state = load_state()
    code = (code or "").strip()
    if not code:
        return False, "股票代码不能为空"
    if any(s.get("code") == code for s in state["stocks"]):
        return False, f"{code} 已在自选股里"
    limit = limit_for(state["plan"])
    if len(state["stocks"]) >= limit:
        plan_name = "免费版" if state["plan"] == "free" else "付费版"
        return False, f"{plan_name}最多 {limit} 只，已达上限（升级可到 {PRO_LIMIT} 只）"
    state["stocks"].append({"code": code, "name": name or code})
    save_state(state)
    return True, ""


def remove_stock(code: str) -> bool:
    state = load_state()
    before = len(state["stocks"])
    state["stocks"] = [s for s in state["stocks"] if s.get("code") != code]
    if len(state["stocks"]) == before:
        return False
    save_state(state)
    return True


def set_plan(plan: str) -> None:
    state = load_state()
    state["plan"] = plan if plan in _PLANS else "free"
    save_state(state)


def quota(state: dict = None) -> Dict:
    """当前套餐用量，给 UI 显示「已用 2/3」和决定是否弹付费墙"""
    state = state or load_state()
    limit = limit_for(state["plan"])
    used = len(state["stocks"])
    return {"plan": state["plan"], "limit": limit, "used": used, "left": max(limit - used, 0)}
