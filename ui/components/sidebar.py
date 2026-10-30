"""
侧边栏组件 - 股票选择、日期范围、LLM配置
"""
import streamlit as st
from datetime import date, timedelta
from data.stock_registry import StockRegistry


def render_mode_selector() -> str:
    """侧边栏最上方的功能模式切换。返回 "analysis" / "briefing" / "agent"。

    放在侧边栏而不是 st.tabs：几种模式用的是完全不同的控件组合，
    挤在一个页面里会让侧边栏出现大量「在这个模式下没意义」的输入框。
    """
    with st.sidebar:
        st.markdown("## 🧭 功能模式")
        mode = st.radio(
            "功能模式",
            ["📈 个股深度分析", "🔔 自选股简报", "💬 智能问答"],
            label_visibility="collapsed",
            key="app_mode",
        )
        st.markdown("---")
    if mode.startswith("🔔"):
        return "briefing"
    if mode.startswith("💬"):
        return "agent"
    return "analysis"


def render_llm_config() -> dict:
    """LLM 模型配置控件（两种模式共用，所以在侧边栏原地渲染）"""
    with st.sidebar:
        st.markdown("## ⚙️ LLM 模型配置")
        with st.expander("展开配置", expanded=False):
            from config import settings

            from utils.llm_factory import default_base_url_for

            model_options = [
                "claude-sonnet-4-20250514",
                "claude-opus-4-20250514",
                "gpt-4o",
                "gpt-4-turbo",
                "gpt-4o-mini",
                "deepseek-v4-flash",
                "glm-5.3-flash",
                "glm-5.3-flashx",
            ]

            def _sync_base_url():
                """切换模型时把 Base URL 带到该厂商的默认端点，避免沿用上一家的地址"""
                auto = default_base_url_for(st.session_state.llm_model_select)
                if auto:
                    st.session_state.llm_base_url_input = auto
                else:
                    st.session_state.llm_base_url_input = ""

            llm_model = st.selectbox(
                "模型选择",
                options=model_options,
                index=model_options.index(settings.llm_model)
                if settings.llm_model in model_options else 0,
                key="llm_model_select",
                on_change=_sync_base_url,
                help="选择用于分析的 LLM 模型；切换后 Base URL 会自动带出对应厂商的端点",
            )

            llm_api_key = st.text_input(
                "API Key",
                value=settings.llm_api_key,
                type="password",
                placeholder="输入你的 API Key",
                help="注意：不同厂商的 Key 不通用，切换模型后请换成对应的 Key",
            )

            # Base URL 用 key 绑定 session_state：切换模型时由上面的回调改写
            if "llm_base_url_input" not in st.session_state:
                st.session_state.llm_base_url_input = (
                    default_base_url_for(settings.llm_model) or settings.llm_base_url
                )

            llm_base_url = st.text_input(
                "Base URL（可选）",
                key="llm_base_url_input",
                placeholder="留空则按模型名自动选择端点",
                help="智谱 GLM: https://open.bigmodel.cn/api/paas/v4\n"
                     "DeepSeek: https://api.deepseek.com/v1\n"
                     "Ollama: http://localhost:11434/v1",
            )

        st.markdown("---")

    return {
        "llm_model": llm_model,
        "llm_api_key": llm_api_key,
        "llm_base_url": llm_base_url,
    }


def render_sidebar() -> dict:
    """渲染侧边栏，返回用户配置

    Returns:
        dict: {
            "stock_code": str,
            "stock_name": str,
            "start_date": str,
            "end_date": str,
            "llm_model": str,
            "llm_api_key": str,
            "llm_base_url": str,
            "run_clicked": bool,
        }
    """
    registry = StockRegistry()

    with st.sidebar:
        st.markdown("## 🔍 股票选择")

        # 初始化 session state
        if "stock_code" not in st.session_state:
            st.session_state.stock_code = "600519"
        if "stock_name" not in st.session_state:
            st.session_state.stock_name = "贵州茅台"

        # 快速选择常用股票
        common_stocks = registry.COMMON_STOCKS[:10]
        common_options = [f"{s['code']} - {s['name']}" for s in common_stocks]
        # 找到当前股票的索引
        current_idx = 0
        for i, s in enumerate(common_stocks):
            if s["code"] == st.session_state.stock_code:
                current_idx = i
                break

        selected = st.selectbox(
            "快速选择（常用股票）",
            options=common_options,
            index=current_idx,
            help="从常用股票列表中选择",
        )
        if selected:
            code = selected.split(" - ")[0]
            name = selected.split(" - ")[1]
            st.session_state.stock_code = code
            st.session_state.stock_name = name

        # 手动输入股票代码
        manual_code = st.text_input(
            "或手动输入股票代码",
            value=st.session_state.stock_code,
            placeholder="如: 600519",
            help="输入6位A股代码",
        ).strip()

        if manual_code and manual_code != st.session_state.stock_code:
            st.session_state.stock_code = manual_code
            # 尝试查找名称
            stock = registry.get_by_code(manual_code)
            if stock:
                st.session_state.stock_name = stock["name"]
                st.caption(f"✅ {stock['name']}")
            else:
                st.caption("⚠️ 未在常用列表中找到该股票")

        st.markdown("---")

        # 日期范围
        st.markdown("## 📅 分析周期")
        start_date = st.date_input(
            "起始日期",
            value=date.today() - timedelta(days=365),
            max_value=date.today(),
        )
        end_date = st.date_input(
            "结束日期",
            value=date.today(),
            max_value=date.today(),
        )

        st.markdown("---")

        # LLM 配置（控件在 render_llm_config 里，两种模式共用）
        llm_cfg = render_llm_config()

        # 公告检索 RAG 开关
        from config import settings

        rag_enabled = st.toggle(
            "📢 公告全文检索（RAG）",
            value=settings.rag_enabled,
            help="检索该股票近期公告全文，作为预测的额外信号。\n"
                 "首次分析某只股票需下载公告建索引（约30-60秒），之后走缓存。",
        )

        # 运行按钮
        run_clicked = st.button(
            "🚀 开始分析",
            type="primary",
            use_container_width=True,
        )

        # 信息提示
        st.markdown("---")
        st.caption("💡 提示：分析需要约30秒-2分钟，取决于LLM响应速度")
        st.caption("⚠️ AI预测仅供参考，不构成投资建议")

    return {
        "stock_code": st.session_state.stock_code,
        "stock_name": st.session_state.stock_name,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        **llm_cfg,
        "rag_enabled": rag_enabled,
        "run_clicked": run_clicked,
    }
