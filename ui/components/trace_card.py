# -*- coding: utf-8 -*-
"""结论溯源卡：把答案里的数字和结论，指回产生它的那次工具调用

三层信息，全部来自 harness 的 tool_end 事件（已随会话历史一起保存）：
1. 数据来源：每次工具调用的参数、耗时、缓存/重试、原始返回
2. 数字核对：答案里的数字能不能在工具返回里找到；找不到的单独列出来
3. 公告依据：本次检索命中的公告标题 + 日期 + 片段

刻意不做"点击数字跳转"：Streamlit 原生 markdown 挂不了事件处理器，
硬做要引入自定义组件，收益不值。这里用「表格 + 原文展开」达到同样的核对目的。
"""
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

# 日期先摘掉，避免把 2026-11-13 拆成三个数字来核对
_DATE_RE = re.compile(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?")
_NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?%?")
_ANN_RE = re.compile(r"《([^》]{2,80})》\s*(\d{4}-\d{2}-\d{2})")

_TRIVIAL_MAX = 10      # 纯整数且 <= 10 的（"3 个步骤"）不参与核对
_TOLERANCE = 0.005     # 答案四舍五入 vs 工具原值，允许 0.5% 误差


def _norm(token: str) -> str:
    """去掉千分位、百分号、正号，只留下可比较的数字串"""
    return token.replace(",", "").replace("%", "").lstrip("+")


def _as_float(token: str) -> Optional[float]:
    try:
        return float(_norm(token))
    except (TypeError, ValueError):
        return None


def extract_numbers(text: str) -> List[str]:
    """挑出值得核对的数字：带小数、带百分号，或四位以上整数。

    纯小整数（近5日、3 个步骤）属于计数，不是数据点，全核对会把噪声当问题。
    """
    text = _DATE_RE.sub(" ", text or "")
    out: List[str] = []
    seen = set()
    for raw in _NUM_RE.findall(text):
        token = raw.rstrip(".,")
        norm = _norm(token)
        if not norm or norm in seen:
            continue
        has_decimal = "." in norm
        has_pct = token.endswith("%")
        digits = norm.lstrip("-")
        if not (has_decimal or has_pct or len(digits) >= 4):
            continue
        # 6 位纯整数当股票代码处理（600519/300750），不是数据点。
        # 代价是同样形状的大额整数（100000）也会被跳过——回答里更常见的写法是
        # 100,000 或 10 万，可接受。
        if not has_decimal and not has_pct and len(digits) == 6 and norm.isdigit():
            continue
        value = _as_float(norm)
        if value is None:
            continue
        if not has_decimal and not has_pct and abs(value) <= _TRIVIAL_MAX:
            continue
        seen.add(norm)
        out.append(token)
    return out


def _tool_numbers(tools: List[dict]) -> List[Tuple[float, str]]:
    """工具返回里出现的所有数字（含整数），(数值, 工具名)"""
    pool: List[Tuple[float, str]] = []
    for tool in tools:
        text = _DATE_RE.sub(" ", tool.get("result") or "")
        for raw in _NUM_RE.findall(text):
            value = _as_float(raw.rstrip(".,"))
            if value is not None:
                pool.append((value, tool.get("name") or "?"))
    return pool


def match_numbers(answer: str, tools: List[dict]) -> List[dict]:
    """逐个数字核对出处；先精确匹配，再允许 0.5% 的四舍五入误差"""
    pool = _tool_numbers(tools)
    rows = []
    for token in extract_numbers(answer):
        value = _as_float(token)
        source = None
        if value is not None:
            for cand, name in pool:
                if abs(cand - value) < 1e-9:
                    source = name
                    break
            if source is None:
                for cand, name in pool:
                    if cand and abs(cand - value) / abs(cand) <= _TOLERANCE:
                        source = name
                        break
        rows.append({"数字": token, "出处": source or "—",
                     "状态": "✅ 已溯源" if source else "⚠️ 未溯源"})
    return rows


def _snippet_after(text: str, title: str, limit: int = 220) -> str:
    """从公告检索返回里，取《标题》后面那一段片段"""
    idx = text.find(title)
    if idx < 0:
        return ""
    tail = text[idx + len(title):].lstrip("》")
    parts = [p.strip() for p in tail.splitlines() if p.strip()]
    if len(parts) <= 1:
        return ""
    return " ".join(parts[1:])[:limit]


def parse_announcements(tools: List[dict]) -> List[dict]:
    """从 search_announcements 的返回文本里，抽出命中的公告条目（跨多次调用去重）"""
    hits: List[dict] = []
    seen = set()
    for tool in tools:
        if tool.get("name") != "search_announcements":
            continue
        text = tool.get("result") or ""
        for title, date in _ANN_RE.findall(text):
            key = (title.strip(), date)
            if key in seen:
                continue
            seen.add(key)
            hits.append({
                "title": title.strip(),
                "date": date,
                "snippet": _snippet_after(text, title.strip()),
            })
    return hits


def _fmt_args(args: Optional[dict], limit: int = 120) -> str:
    text = "、".join(f"{k}={v}" for k, v in (args or {}).items())
    return text[:limit] + ("…" if len(text) > limit else "")


def render_trace_card(turn: Dict) -> None:
    """在一条 assistant 回答下面渲染溯源卡；没有工具轨迹时什么都不画"""
    tools = turn.get("tools") or []
    if not tools:
        return

    answer = turn.get("content") or ""
    rows = match_numbers(answer, tools)
    ungrounded = [r["数字"] for r in rows if r["出处"] == "—"]
    announcements = parse_announcements(tools)
    usage = turn.get("usage") or {}

    title = f"🔎 结论溯源 · {len(rows)} 个数字 / {len(tools)} 次工具调用"
    if ungrounded:
        title += f" · {len(ungrounded)} 个未溯源"

    with st.expander(title, expanded=False):
        if ungrounded:
            st.caption("⚠️ 这些数字没在本轮工具返回里找到，可能是模型换算/概括，"
                       "也可能是编的——引用前先核对：" + "、".join(ungrounded[:8]))

        tab_data, tab_nums, tab_ann = st.tabs(["数据来源", "数字核对", "公告依据"])
        with tab_data:
            for i, tool in enumerate(tools, 1):
                meta = []
                if tool.get("elapsed_ms"):
                    meta.append(f"{int(tool['elapsed_ms'])} ms")
                if tool.get("cached"):
                    meta.append("缓存命中")
                if tool.get("retries"):
                    meta.append(f"重试 {int(tool['retries'])} 次")
                label = f"{i}. {tool.get('name') or '?'} · {' · '.join(meta) or '—'}"
                with st.expander(label, expanded=False):
                    st.caption("参数：" + (_fmt_args(tool.get("args")) or "—"))
                    st.text(tool.get("result") or tool.get("summary") or "（无返回）")

        with tab_nums:
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
                st.caption("核对口径：答案里带小数/百分号/四位以上的数字，"
                           "本轮工具返回里必须能对上；允许 0.5% 的四舍五入误差。"
                           "纯计数（近5日、3 个步骤）不参与核对。")
            else:
                st.caption("这条回答里没有需要核对的数据型数字。")

        with tab_ann:
            if announcements:
                for item in announcements:
                    st.markdown(f"**《{item['title']}》**　`{item['date']}`")
                    if item["snippet"]:
                        st.caption(item["snippet"])
            else:
                st.caption("本轮没有检索公告，或返回里没有可识别的公告条目。")
            st.caption("页码引用需要 RAG 切块带上 page 元数据，"
                       "属于建库口径升级，当前先给到标题 + 日期。")

        footer = []
        if usage.get("total_tokens"):
            footer.append(f"token {usage['total_tokens']}")
        if usage.get("elapsed_s"):
            footer.append(f"{float(usage['elapsed_s']):.1f}s")
        if turn.get("trace"):
            footer.append(f"轨迹 {turn['trace']}")
        if footer:
            st.caption(" · ".join(footer))
