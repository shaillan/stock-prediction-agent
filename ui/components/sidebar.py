"""
侧边栏组件 - 股票选择、日期范围、LLM配置
"""
import streamlit as st
from datetime import date, timedelta
from data.stock_registry import StockRegistry


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
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "起始日期",
                value=date.today() - timedelta(days=365),
                max_value=date.today(),
            )
        with col2:
            end_date = st.date_input(
                "结束日期",
                value=date.today(),
                max_value=date.today(),
            )

        st.markdown("---")

        # LLM 配置
        st.markdown("## ⚙️ LLM 模型配置")
        with st.expander("展开配置", expanded=False):
            from config import settings

            llm_model = st.selectbox(
                "模型选择",
                options=[
                    "claude-sonnet-4-20250514",
                    "claude-opus-4-20250514",
                    "gpt-4o",
                    "gpt-4-turbo",
                    "gpt-4o-mini",
                    "deepseek-v4-flash",
                ],
                index=0,
                help="选择用于分析的 LLM 模型",
            )

            llm_api_key = st.text_input(
                "API Key",
                value=settings.llm_api_key,
                type="password",
                placeholder="输入你的 API Key",
                help="Claude / OpenAI / 兼容 API 的 Key",
            )

            llm_base_url = st.text_input(
                "Base URL（可选）",
                value=settings.llm_base_url,
                placeholder="留空使用官方API，或填入兼容API地址",
                help="DeepSeek: https://api.deepseek.com/v1\nOllama: http://localhost:11434/v1",
            )

        st.markdown("---")

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
        "llm_model": llm_model,
        "llm_api_key": llm_api_key,
        "llm_base_url": llm_base_url,
        "run_clicked": run_clicked,
    }
