# -*- coding: utf-8 -*-
"""「自选股简报」页面 —— 可演示商业 Demo 的主界面

视觉稿见 design/ui_mockup.html。Streamlit 不执行 <script>，所以交互
（弹窗、切换、悬停）全部换成原生控件：付费墙用 st.dialog，行情条用一次性
HTML 块，简报正文用 st.markdown 渲染模型输出的 Markdown。

合规边界：只做信息整理和解读，不输出买卖建议。
"""
import re
from datetime import date

import streamlit as st

from utils.watchlist import (
    FREE_LIMIT, PRO_LIMIT, add_stock, load_state, quota, remove_stock, set_plan,
)


# ===================== 小工具 =====================
def _llm_from(cfg: dict):
    from utils.llm_factory import create_chat_model
    return create_chat_model(
        model=cfg.get("llm_model"),
        api_key=cfg.get("llm_api_key"),
        base_url=cfg.get("llm_base_url"),
        temperature=0.3,
        max_tokens=1200,
    )


def _market_tag(code: str) -> str:
    if code.startswith("688"):
        return "科创"
    if code.startswith("6"):
        return "沪"
    if code.startswith("3"):
        return "创"
    return "深"


def _delta_html(pct: float) -> str:
    """涨跌必须带 ▲▼ 与正负号：红绿两色色盲区分度只有 ΔE 6.5，颜色不能单独承载信息"""
    if pct > 0:
        return f'<span class="delta up">▲ +{pct:.2f}%</span>'
    if pct < 0:
        return f'<span class="delta down">▼ −{abs(pct):.2f}%</span>'
    return '<span class="delta flat">— 0.00%</span>'


@st.cache_data(ttl=300, show_spinner=False)
def _load_quotes(codes: tuple) -> dict:
    """取行情给行情条用。拿不到就放弃，页面不能为行情卡住。

    akshare 的 import 本身要几秒，必须放在计时之外，否则冷启动必然超时。
    """
    from concurrent.futures import ThreadPoolExecutor

    from data.akhare_client import AKShareClient

    client = AKShareClient()
    pool = ThreadPoolExecutor(max_workers=max(len(codes), 1))
    futures = {c: pool.submit(client.get_realtime_quote, c) for c in codes}
    out = {}
    for code, fut in futures.items():
        try:
            q = fut.result(timeout=8)
            if q:
                out[code] = q
        except Exception:
            continue
    pool.shutdown(wait=False)
    return out


# ===================== 页面 =====================
def render_briefing_page(llm_cfg: dict) -> None:
    q = quota()
    stocks = load_state()["stocks"]

    _render_topbar(stocks)
    _render_quote_strip(stocks)
    _render_toolbar(q, stocks, llm_cfg)

    if not stocks:
        st.info(f"先添加几只自选股。免费版 {FREE_LIMIT} 只，专业版 {PRO_LIMIT} 只。")
        return

    _render_split(stocks, llm_cfg)


def _render_topbar(stocks: list) -> None:
    today = date.today()
    weekday = "一二三四五六日"[today.weekday()]
    st.markdown(
        f"""
        <div class="term-topbar">
          <div>
            <h1>自选股简报</h1>
            <p class="sub">{today:%Y-%m-%d} 周{weekday} · {len(stocks)} 只自选股
             · 数据来源 巨潮资讯 / 东方财富</p>
          </div>
          <span class="term-badge"><span class="live"></span>只做解读，不预测涨跌</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_quote_strip(stocks: list) -> None:
    if not stocks:
        return

    codes = tuple(s["code"] for s in stocks)
    with st.spinner("读取行情…"):
        quotes = _load_quotes(codes)

    cards = []
    for s in stocks:
        code = s["code"]
        q = quotes.get(code) or {}
        name = s.get("name") or q.get("name") or code
        if q.get("price"):
            price = f"{q['price']:,.2f}"
            delta = _delta_html(float(q.get("change_pct") or 0.0))
            meta = f"最高 {q.get('high', 0):,.2f} · 最低 {q.get('low', 0):,.2f}"
        else:
            price = "—"
            delta = '<span class="delta flat">行情不可用</span>'
            meta = "稍后重试或检查网络"
        cards.append(
            f'<div class="quote-card">'
            f'<div class="quote-top"><span class="quote-name">{name}</span>'
            f'<span class="quote-code">{code}</span>'
            f'<span class="quote-badge">{_market_tag(code)}</span></div>'
            f'<div class="quote-price-row"><span class="quote-price">{price}</span>{delta}</div>'
            f'<div class="quote-meta">{meta}</div></div>'
        )

    st.markdown(f'<div class="quote-strip">{"".join(cards)}</div>', unsafe_allow_html=True)


def _render_toolbar(q: dict, stocks: list, llm_cfg: dict) -> None:
    st.write("")
    c1, c2, c3 = st.columns([1.05, 1.5, 1.15], gap="medium")

    with c1:
        _render_plan_card(q)
    with c2:
        _render_manage(stocks, q)
    with c3:
        force = st.checkbox("忽略今日缓存", value=False,
                            help="勾选后强制重新调用模型；不勾选时同一天只生成一次")
        if st.button("📰 生成今日简报", type="primary", use_container_width=True):
            _generate(stocks, llm_cfg, force)


def _render_plan_card(q: dict) -> None:
    label = "免费版" if q["plan"] == "free" else "Pro"
    pct = min(q["used"] / q["limit"], 1.0) * 100 if q["limit"] else 0.0
    st.markdown(
        f'<div class="plan-card">'
        f'<div class="plan-row"><span class="plan-name">{label}</span>'
        f'<span class="plan-usage">{q["used"]} / {q["limit"]} 只</span></div>'
        f'<div class="plan-bar"><i style="width:{pct:.0f}%"></i></div></div>',
        unsafe_allow_html=True,
    )
    if q["plan"] == "free":
        if st.button("升级 Pro · ¥29/月", type="primary",
                     use_container_width=True, key="upgrade_top"):
            _open_paywall()
    else:
        if st.button("切回免费版", use_container_width=True, key="downgrade"):
            set_plan("free")
            st.rerun()


@st.dialog("升级到 Pro", width="large")
def _open_paywall() -> None:
    """付费墙：Demo 里「商业模式」的可视化部分，不是真支付

    标题固定写"升级到 Pro"：用户可能是主动点进来的，不一定是额度用完了，
    所以把"已用满"的信息放到正文里，按实际额度决定说不说。
    """
    q = quota()
    if q["used"] >= q["limit"]:
        st.markdown(
            f"免费额度 **{q['used']} / {q['limit']} 只** 已用满。"
            f"升级后可跟踪 **{PRO_LIMIT} 只**，并解锁历史简报回看。"
        )
    else:
        st.markdown(
            f"免费版最多跟踪 **{FREE_LIMIT} 只**股票（当前 {q['used']} 只）。"
            f"升级后可跟踪 **{PRO_LIMIT} 只**，并解锁历史简报回看。"
        )
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**免费版**")
            st.markdown("¥0 / 月")
            st.markdown(f"- 最多 {FREE_LIMIT} 只自选股\n- 每日简报（当日缓存）\n"
                        "- 个股深度分析\n- 不含历史简报回看")
            st.button("当前套餐", disabled=True, use_container_width=True, key="plan_free")
    with c2:
        with st.container(border=True):
            st.markdown("**Pro**　推荐")
            st.markdown("¥29 / 月")
            st.markdown(f"- 最多 {PRO_LIMIT} 只自选股\n- 每日简报（当日缓存）\n"
                        "- 个股深度分析\n- 历史简报回看（近 90 天）")
            if st.button("模拟支付 ¥29 / 月", type="primary",
                         use_container_width=True, key="plan_pay"):
                set_plan("pro")
                st.rerun()
    st.caption(
        "这是演示环境：**不会真实扣款**，点击后只在本地 records/watchlist.json "
        "写入一条套餐记录。本产品提供信息整理与解读，不提供任何买卖建议。"
    )


def _render_manage(stocks: list, q: dict) -> None:
    with st.expander(f"管理自选股（{len(stocks)} 只）", expanded=not stocks):
        with st.form("add_stock_form", clear_on_submit=True):
            c1, c2, c3 = st.columns([1.1, 1.6, 0.9])
            code = c1.text_input("股票代码", placeholder="600519",
                                 label_visibility="collapsed")
            name = c2.text_input("名称（可选）", placeholder="名称（可选）",
                                 label_visibility="collapsed")
            submitted = c3.form_submit_button("添加", use_container_width=True)

        if submitted:
            _add(code, name, q)

        if stocks:
            st.markdown('<div class="manage-sep"></div>', unsafe_allow_html=True)
        for s in stocks:
            cc1, cc2 = st.columns([4, 1])
            cc1.markdown(
                f'<span class="quote-code">{s["code"]}</span>　{s.get("name") or ""}',
                unsafe_allow_html=True,
            )
            if cc2.button("移除", key=f"del_{s['code']}", use_container_width=True):
                remove_stock(s["code"])
                st.session_state.pop("briefings", None)
                st.rerun()


def _add(code: str, name: str, q: dict) -> None:
    code, name = (code or "").strip(), (name or "").strip()
    if not code:
        st.warning("请输入股票代码")
        return
    if not name:
        try:
            from data.stock_registry import StockRegistry
            hit = StockRegistry().get_by_code(code)
            if hit:
                name = hit["name"]
        except Exception:
            pass
    ok, msg = add_stock(code, name)
    if ok:
        st.success(f"已添加 {code}")
        st.rerun()
    st.warning(msg)
    if q["plan"] == "free" and "上限" in msg:
        st.info("点击左上方「升级 Pro」可提高到 20 只。")


# ===================== 简报正文 =====================
_LABELS = ("一句话", "发生了什么", "值得留意")


def _prepare_digest(digest: str, name: str) -> str:
    """把模型输出的三段式转成小标题，并去掉它与卡片标题重复的那行标题"""
    text = (digest or "").strip()
    text = re.sub(r"^#+\s*.*\n+", "", text, count=1)
    for lab in _LABELS:
        text = re.sub(rf"\*\*{lab}\*\*\s*[:：]?", f"### {lab}\n\n", text, count=1)
    return text


def _render_split(stocks: list, llm_cfg: dict) -> None:
    results = st.session_state.get("briefings") or []
    st.write("")
    left, right = st.columns([1.62, 1], gap="medium")

    with left:
        if not results:
            with st.container(border=True):
                st.markdown(
                    '<div class="empty-state">今天的简报还没生成。<br>'
                    '点上方「生成今日简报」，每只股票会调用一次模型（约 10–30 秒）。</div>',
                    unsafe_allow_html=True,
                )
        for r in results:
            _brief_card(r)
        st.markdown(
            '<p class="disclaimer"><b>关于本简报：</b>内容由程序聚合公开信息后由模型改写，'
            '只描述「发生了什么」，不构成投资建议，也不预测涨跌。'
            '数据来源：巨潮资讯网（公告）、东方财富（行情与新闻）。</p>',
            unsafe_allow_html=True,
        )

    with right:
        _events_panel(results)
        _sources_panel(results)


def _brief_card(r: dict) -> None:
    name = r.get("name") or r.get("code")
    with st.container(border=True):
        if not r.get("digest"):
            st.markdown(
                f'<div class="card-head"><span class="card-title">{name}</span>'
                f'<span class="card-hint warn">生成失败</span></div>',
                unsafe_allow_html=True,
            )
            st.error(r.get("error") or "生成失败")
            return

        hint = "今日缓存 · 未重复调用模型" if r.get("cached") else "刚刚生成"
        st.markdown(
            f'<div class="card-head"><span class="card-title">{name} · {r["code"]}</span>'
            f'<span class="card-hint">{hint}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(_prepare_digest(r["digest"], name))
        if r.get("errors"):
            st.caption("；".join(r["errors"]))


def _events_panel(results: list) -> None:
    with st.container(border=True):
        st.markdown(
            '<div class="card-head"><span class="card-title">近期事件</span>'
            '<span class="card-hint">公告 + 新闻</span></div>',
            unsafe_allow_html=True,
        )
        if not results:
            st.caption("生成简报后显示")
            return

        names = {r["code"]: (r.get("name") or r["code"]) for r in results}
        picked = st.selectbox(
            "选择股票", list(names), format_func=lambda c: names[c],
            label_visibility="collapsed", key="evt_pick",
        ) if len(names) > 1 else list(names)[0]
        r = next((x for x in results if x["code"] == picked), results[0])

        items = []
        for a in (r.get("announcements") or [])[:6]:
            items.append((a.get("date", ""), a.get("title", ""), "巨潮资讯 · 公告", False))
        for n in (r.get("news") or [])[:6]:
            items.append((str(n.get("datetime", ""))[:10], n.get("title", ""),
                          f"{n.get('source', '')} · 新闻", True))
        items.sort(key=lambda x: x[0], reverse=True)
        items = items[:7]

        if not items:
            st.caption("近 90 天没有可显示的公告或新闻")
            return

        rows = "".join(
            f'<li class="tl-item"><span class="tl-dot{" hot" if hot else ""}"></span>'
            f'<div><div class="tl-date">{d}</div>'
            f'<div class="tl-title">{t}</div>'
            f'<div class="tl-src">{src}</div></div></li>'
            for d, t, src, hot in items
        )
        st.markdown(f'<ul class="tl">{rows}</ul>', unsafe_allow_html=True)


def _sources_panel(results: list) -> None:
    with st.container(border=True):
        st.markdown(
            '<div class="card-head"><span class="card-title">本期素材</span></div>',
            unsafe_allow_html=True,
        )
        if not results:
            st.caption("—")
            return
        ann = sum(len(r.get("announcements") or []) for r in results)
        news = sum(len(r.get("news") or []) for r in results)
        errs = sum(len(r.get("errors") or []) for r in results)
        failed = sum(1 for r in results if not r.get("digest"))
        row = ('<div class="stat-row"><span>{k}</span><b>{v}</b></div>')
        st.markdown(
            row.format(k="简报", v=f"{len(results) - failed} / {len(results)}") +
            row.format(k="公告", v=f"{ann} 条") +
            row.format(k="新闻", v=f"{news} 条") +
            row.format(k="数据获取失败", v=f"{errs} 项"),
            unsafe_allow_html=True,
        )


# ===================== 生成 =====================
def _generate(stocks: list, llm_cfg: dict, force: bool) -> None:
    from services.briefing import build_briefing

    if not llm_cfg.get("llm_api_key"):
        st.error("请先在侧边栏配置 LLM API Key")
        return
    try:
        llm = _llm_from(llm_cfg)
    except Exception as e:
        st.error(f"LLM 初始化失败：{e}")
        return

    results = []
    bar = st.progress(0.0, text="准备中…")
    for i, s in enumerate(stocks):
        bar.progress(i / len(stocks), text=f"正在生成 {s.get('name') or s['code']} …")
        try:
            results.append(build_briefing(s["code"], s.get("name", ""), llm=llm, force=force))
        except Exception as e:
            results.append({
                "code": s["code"], "name": s.get("name") or s["code"],
                "digest": "", "error": f"生成失败: {str(e)[:200]}",
                "errors": [], "news": [], "announcements": [],
                "quote": None, "quote_line": "", "cached": False,
            })
    bar.empty()
    st.session_state["briefings"] = results
