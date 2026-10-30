# -*- coding: utf-8 -*-
"""「智能问答」页面 —— Agent 模式（LLM 自主调工具）的聊天界面

和其他两条路径的分工：
- 个股深度分析：工作流，固定顺序，出结果页
- 自选股简报：产品层的每日简报
- 智能问答：真 Agent，模型自己决定查哪些工具，边调工具边流式回答

视觉沿用 briefing.py 的 topbar/卡片风格；聊天本身用原生 st.chat_message。
历史里除了 Q/A，还存这一轮调过的工具（name/args/summary 摘要）。只存答案的话，
页面一重跑，「查了什么」这段过程就凭空消失，用户看不到结论是怎么来的。
"""
import streamlit as st

_HISTORY_KEY = "agent_history"
# 默认头像是 Streamlit 自带的红色小人图标，跟本站的琥珀色暗主题撞色；换成 emoji，
# 同时让「实时流式」和「事后回放」两条渲染路径共用同一份头像定义
_AVATARS = {"user": "🧑", "assistant": "📈"}


def _llm_from(cfg: dict):
    from utils.llm_factory import create_chat_model
    return create_chat_model(
        model=cfg.get("llm_model"),
        api_key=cfg.get("llm_api_key"),
        base_url=cfg.get("llm_base_url"),
        temperature=0.3,
        max_tokens=2000,
    )


def _short(args: dict, limit: int = 60) -> str:
    text = "、".join(f"{k}={v}" for k, v in (args or {}).items())
    return text[:limit] + ("…" if len(text) > limit else "")


def _history() -> list:
    return st.session_state.setdefault(_HISTORY_KEY, [])


# ===================== 侧边栏 =====================
def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## 🎯 研究对象")
        st.text_input(
            "默认股票代码",
            key="agent_stock",
            value="600519",
            placeholder="如 600519",
            help="问到这只股票时模型会自动填工具的 stock_code；也可以直接在问题里指定别的股票",
        )

        st.markdown("## ⚙️ 运行设置")
        st.slider(
            "工具步数上限",
            min_value=2,
            max_value=20,
            value=8,
            key="agent_max_steps",
            help="模型最多调用多少次工具（每次工具调用算一步）。到顶后会强制基于已有信息收尾，"
                 "这是成本护栏。",
        )

        if st.button("🗑️ 清空对话", use_container_width=True):
            st.session_state.pop(_HISTORY_KEY, None)
            st.rerun()

        st.markdown("---")
        st.caption("💡 模型会自己决定查哪些数据；工具调用的过程会显示在回答上方。")
        st.caption("⚠️ AI 分析仅供参考，不构成投资建议。")


# ===================== 页面 =====================
def _render_topbar() -> None:
    code = st.session_state.get("agent_stock", "")
    st.markdown(
        f"""
        <div class="term-topbar">
          <div>
            <h1>智能问答</h1>
            <p class="sub">模型自主调用工具 · 默认研究 {code or '—'}</p>
          </div>
          <span class="term-badge">Agent · 边走边查</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_history() -> None:
    history = _history()
    for turn in history:
        role = turn.get("role", "assistant")
        with st.chat_message(role, avatar=_AVATARS.get(role)):
            # 回放上一轮调过的工具（已完成态）。不存这一层的话，页面一重跑，
            # 屏幕上就只剩最终答案，「查了什么」这段过程凭空消失。
            for t in turn.get("tools") or []:
                box = st.status(
                    f"{t.get('name')}（{_short(t.get('args'))}）",
                    state="complete", expanded=False,
                )
                box.write(t.get("summary", ""))
            st.markdown(turn.get("content", ""))

    if not history:
        with st.container(border=True):
            st.markdown(
                '<div class="empty-state">问个开放式问题试试——模型会自己决定查哪些数据。<br>'
                '比如「600519 最近走势如何，现在适合关注吗」'
                '「大股东最近有没有减持」。</div>',
                unsafe_allow_html=True,
            )


def _answer(question: str, llm_cfg: dict) -> None:
    from agent_mode.loop import DEFAULT_MAX_STEPS, stream_agent_mode

    # 先取历史（不含本轮），再把本轮问题记进去
    history = list(_history())
    _history().append({"role": "user", "content": question})

    with st.chat_message("user", avatar=_AVATARS["user"]):
        st.markdown(question)

    def _fail(msg: str) -> None:
        """出错时也把一句话记进历史：聊天要保持一问一答，而不是留个悬空的问题"""
        _history().append({"role": "assistant", "content": msg})
        with st.chat_message("assistant", avatar=_AVATARS["assistant"]):
            st.error(msg)

    if not llm_cfg.get("llm_api_key"):
        _fail("请先在侧边栏配置 LLM API Key")
        return

    try:
        llm = _llm_from(llm_cfg)
    except Exception as e:  # noqa: BLE001
        _fail(f"LLM 初始化失败：{e}")
        return

    code = st.session_state.get("agent_stock", "")
    max_steps = st.session_state.get("agent_max_steps", DEFAULT_MAX_STEPS)
    final = ""
    trace = []          # 本轮工具轨迹，结束后跟答案一起进历史
    record = {}         # step → trace 里的那条，tool_end 时把 summary 补进去

    with st.chat_message("assistant", avatar=_AVATARS["assistant"]):
        # 占位符**延迟创建**：一上来就 st.empty() 的话，它在 DOM 里排在最前，
        # 后面渲染的工具状态就只能排在它下面，页面顺序变成「答案 → 工具」，
        # 和实际发生的顺序反了。等第一个 token 真到了再建，工具状态就先出现。
        placeholder = None
        boxes = {}
        parts = []
        try:
            for ev in stream_agent_mode(
                question=question,
                stock_code=code,
                max_steps=max_steps,
                llm=llm,
                history=history,
            ):
                if ev["type"] == "tool_start":
                    boxes[ev["step"]] = st.status(
                        f"🔧 {ev['name']}（{_short(ev['args'])}）", expanded=False)
                    # tool_start 一轮内按调用顺序全局先发，在这里入列即可保序
                    record[ev["step"]] = {"name": ev["name"], "args": ev["args"],
                                           "summary": ""}
                    trace.append(record[ev["step"]])
                elif ev["type"] == "tool_end":
                    if ev["step"] in record:
                        record[ev["step"]]["summary"] = ev["summary"]
                    box = boxes.get(ev["step"])
                    if box is not None:
                        # state="complete" 自带一个对勾图标，标签里再写 ✅ 会变成双勾
                        box.update(label=ev["name"], state="complete")
                        box.write(ev["summary"])
                elif ev["type"] == "token":
                    if placeholder is None:
                        placeholder = st.empty()
                    parts.append(ev["text"])
                    placeholder.markdown("".join(parts))
                elif ev["type"] == "done":
                    # 用累积的 token 而不是 ev["answer"]：模型在调工具前常有一段
                    # "我先查一下…"的铺垫，那段已经流式显示出来了，历史里也得有，
                    # 否则一刷新，屏幕上的字就少了一截
                    final = "".join(parts) or ev["answer"]
                    if ev["stopped"] == "cap":
                        st.caption("（已到步数上限，基于已收集到的信息收尾）")
                    break
        except Exception as e:  # noqa: BLE001
            # 已经在 assistant 气泡里了，别再套一层 chat_message
            msg = f"运行失败：{e}"
            st.error(msg)
            _history().append({"role": "assistant", "content": msg})
            return

        # 兜底：没有流式 token（例如厂商不支持流式）时，一次性把答案补上
        if final and not parts:
            if placeholder is None:
                placeholder = st.empty()
            placeholder.markdown(final)

    _history().append({"role": "assistant", "content": final, "tools": trace})
    # 重跑一趟：这一趟的「空状态」引导卡是在提问之前就画上去的，
    # 不清掉的话它会一直挂在对话上方，直到用户碰下一个控件才消失。
    # 重跑后这轮由 _render_history 统一回放（工具 + 答案），不会重复。
    st.rerun()



def render_agent_page(llm_cfg: dict) -> None:
    _render_sidebar()
    _render_topbar()
    _render_history()

    question = st.chat_input("问点什么，比如「600519 最近走势如何」")
    if question:
        _answer(question, llm_cfg)

    st.markdown(
        '<p class="disclaimer"><b>关于这个回答：</b>模型会自行调用行情/财务/新闻/公告工具'
        '收集信息，但数据可能缺失或延迟。结论是分析参考，<b>不构成投资建议</b>，'
        '也不预测涨跌。数据来源：巨潮资讯网（公告）、东方财富（行情与新闻）。</p>',
        unsafe_allow_html=True,
    )
