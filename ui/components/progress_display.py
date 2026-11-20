"""
步骤进度指示器组件 - 显示工作流 5 步进度
"""
import streamlit as st
from typing import Optional


STEPS = [
    {"key": "collecting", "icon": "📡", "label": "数据采集"},
    {"key": "analyzing", "icon": "📊", "label": "技术分析"},
    {"key": "sentiment", "icon": "📰", "label": "新闻情绪"},
    {"key": "predicting", "icon": "🧠", "label": "综合预测"},
    {"key": "report", "icon": "📝", "label": "报告生成"},
]


def render_progress(status: str = "idle", errors: Optional[list] = None) -> None:
    """渲染步骤进度指示器

    Args:
        status: 当前状态 "idle" | "collecting" | "analyzing" | "predicting" | "done" | "error"
        errors: 错误列表
    """
    status_order = {
        "idle": 0,
        "collecting": 0,
        "analyzing": 1,
        "sentiment": 2,
        "predicting": 3,
        "report": 4,
        "reporting": 4,
        "done": 5,
        "error": 5,
    }

    current_idx = status_order.get(status, 0)
    finished = status in ("done", "error")

    parts = []
    for i, step in enumerate(STEPS):
        if i < current_idx or finished:
            dot_cls, mark, lab_cls = "step-dot step-dot-done", "✓", ""
        elif i == current_idx:
            dot_cls, mark, lab_cls = "step-dot step-dot-active", "⋯", " active"
        else:
            dot_cls, mark, lab_cls = "step-dot", str(i + 1), ""
        step_cls = "step done" if i < current_idx else "step"
        parts.append(
            f'<div class="{step_cls}">'
            f'<div class="{dot_cls}">{mark}</div>'
            f'<div class="step-label{lab_cls}">{step["icon"]} {step["label"]}</div>'
            f'</div>'
        )

    st.markdown(f'<div class="stepper">{"".join(parts)}</div>',
                unsafe_allow_html=True)

    if errors and len(errors) > 0:
        st.write("")
        with st.expander(f"⚠️ 分析过程中出现 {len(errors)} 个警告/错误", expanded=False):
            for e in errors:
                st.warning(e)


# 用于在 main.py 中作为上下文管理器使用
class AgentProgressContext:
    """Streamlit 进度上下文管理器"""

    def __init__(self):
        self.status_box = None
        self.progress_placeholder = None

    def __enter__(self):
        self.progress_placeholder = st.empty()
        self.status_box = st.status("正在初始化分析...", expanded=True)
        return self

    def __exit__(self, *args):
        if self.status_box:
            self.status_box.update(label="分析完成!", state="complete")
        if self.progress_placeholder:
            self.progress_placeholder.empty()

    def update(self, step: str, message: str = ""):
        """更新进度状态"""
        step_messages = {
            "idle": "准备中...",
            "collecting": "📡 正在获取行情数据...",
            "analyzing": "📊 正在计算技术指标...",
            "sentiment": "📰 正在分析新闻情绪...",
            "predicting": "🧠 正在生成综合预测...",
            "report": "📝 正在生成分析报告...",
            "done": "✅ 分析完成!",
            "error": "❌ 分析出错",
        }
        msg = message or step_messages.get(step, step)
        if self.status_box:
            self.status_box.write(msg)
