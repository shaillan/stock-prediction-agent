"""
自定义 Streamlit CSS 样式
"""
import streamlit as st


def apply_custom_css():
    """应用自定义 CSS 样式"""
    st.markdown("""
    <style>
        /* ===== 全局样式 ===== */
        .main-header {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 1rem;
            text-align: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        /* ===== 预测结果卡片 ===== */
        .prediction-card {
            border-radius: 12px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .prediction-bullish {
            background: linear-gradient(135deg, #f0fff4, #c6f6d5);
            border-left: 4px solid #e53e3e;
        }
        .prediction-bearish {
            background: linear-gradient(135deg, #fff5f5, #fed7d7);
            border-left: 4px solid #38a169;
        }
        .prediction-neutral {
            background: linear-gradient(135deg, #fffff0, #fefcbf);
            border-left: 4px solid #d69e2e;
        }

        /* ===== 指标卡片 ===== */
        .metric-card {
            text-align: center;
            padding: 1rem;
            border-radius: 8px;
            background: #f7fafc;
            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        }
        .metric-value {
            font-size: 1.5rem;
            font-weight: 700;
        }
        .metric-label {
            font-size: 0.85rem;
            color: #718096;
        }
        .metric-up { color: #e53e3e; }
        .metric-down { color: #38a169; }
        .metric-warn { color: #d69e2e; }

        /* ===== 步骤进度 ===== */
        .step-container {
            display: flex;
            justify-content: space-between;
            margin: 1rem 0;
            padding: 0.5rem;
        }
        .step-item {
            text-align: center;
            flex: 1;
        }
        .step-dot {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            display: inline-block;
            line-height: 30px;
            font-size: 0.8rem;
            font-weight: 700;
        }
        .step-dot-active {
            background: #667eea;
            color: white;
        }
        .step-dot-done {
            background: #38a169;
            color: white;
        }
        .step-dot-pending {
            background: #e2e8f0;
            color: #a0aec0;
        }
        .step-label {
            font-size: 0.75rem;
            margin-top: 0.25rem;
        }

        /* ===== 风险提示 ===== */
        .risk-warning {
            background: #fffaf0;
            border: 1px solid #fbd38d;
            border-radius: 8px;
            padding: 1rem;
            margin-top: 1rem;
        }

        /* ===== 免责声明 ===== */
        .disclaimer {
            background: #edf2f7;
            border-radius: 8px;
            padding: 1rem;
            font-size: 0.85rem;
            color: #4a5568;
            margin-top: 2rem;
        }

        /* ===== 响应式调整 ===== */
        @media (max-width: 768px) {
            .metric-value { font-size: 1.2rem; }
        }
    </style>
    """, unsafe_allow_html=True)
