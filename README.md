# 📈 股票智能预测 Agent

基于 **LangGraph + LLM** 的 A 股智能分析系统，综合技术面、消息面、基本面进行多源分析，输出短期趋势预测。

> ⚠️ **重要声明**：本工具仅供学习研究使用，AI 预测不构成投资建议。股市有风险，投资需谨慎。

---

## ✨ 功能特性

- 🔍 **技术分析**：自动计算 MA、MACD、RSI、KDJ、布林带等指标，LLM 专业解读
- 📰 **新闻情绪分析**：获取个股相关新闻，LLM 分析情绪和影响强度
- 💰 **基本面概览**：PE、PB、ROE 等关键财务指标
- 🎯 **综合预测**：多源信息融合，输出趋势判断 + 置信度 + 目标价位
- 📊 **交互式图表**：Plotly K 线图 + 技术指标叠加（均线、布林带、MACD、RSI）
- 🤖 **多模型支持**：Claude / GPT-4o / DeepSeek / Ollama 等兼容 API

---

## 🏗️ 架构

```
用户界面 (Streamlit)
    ↓
LangGraph Agent 流水线
    ├── 📡 数据采集 (AKShare)
    ├── 📊 技术分析 (Python计算 + LLM解读)
    ├── 📰 新闻情绪 (LLM分析)
    ├── 🧠 综合预测 (LLM JSON输出)
    └── 📝 报告生成 (LLM Markdown输出)
    ↓
结果展示 (Plotly图表 + 预测面板 + 分析报告)
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- pip

### 2. 安装依赖

```bash
cd stock-prediction-agent
pip install -r requirements.txt
```

### 3. 配置 API Key

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env，填入你的 API Key
# LLM_API_KEY=your-api-key-here
```

或直接在 Web 界面侧边栏配置。

### 4. 启动

```bash
streamlit run main.py
```

浏览器访问 `http://localhost:8501`

### 5. 使用

1. 左侧选择或输入 A 股代码（如 600519 贵州茅台）
2. 选择分析周期
3. 配置 LLM 模型和 API Key
4. 点击 **"🚀 开始分析"**
5. 等待约 30秒-2分钟（取决于 LLM 响应速度）
6. 查看 K 线图、预测结果和详细分析报告

---

## 📁 项目结构

```
stock-prediction-agent/
├── main.py                    # Streamlit 入口
├── config.py                  # 全局配置
├── .env.example               # API Key 模板
├── requirements.txt           # 依赖清单
│
├── agent/                     # LangGraph Agent
│   ├── state.py               # AgentState 定义
│   ├── graph.py               # StateGraph 编排
│   ├── nodes/                 # 5个工作流节点
│   │   ├── data_collection.py
│   │   ├── technical_analysis.py
│   │   ├── news_sentiment.py
│   │   ├── comprehensive_prediction.py
│   │   └── report_generation.py
│   ├── tools/                 # LangChain Tools
│   └── prompts/               # 中文 System Prompt
│
├── data/                      # 数据层
│   ├── akhare_client.py       # AKShare 封装
│   ├── technical_indicators.py # 技术指标计算
│   ├── cache_manager.py       # 二级缓存
│   ├── stock_registry.py      # 股票代码搜索
│   └── models.py              # Pydantic 数据模型
│
├── ui/                        # Streamlit UI
│   ├── styles.py              # 自定义CSS
│   └── components/
│       ├── sidebar.py         # 侧边栏
│       ├── kline_chart.py     # K线图 (Plotly)
│       ├── prediction_panel.py # 预测面板
│       ├── analysis_reasoning.py # 分析详情
│       └── progress_display.py  # 进度指示
│
└── utils/                     # 工具层
    ├── llm_factory.py         # 多Provider LLM工厂
    ├── error_handler.py       # 错误处理
    └── logger.py              # 日志
```

---

## 🔧 支持的 LLM 后端

| Provider | 模型 | 配置 |
|----------|------|------|
| Anthropic | claude-sonnet-4, claude-opus-4 | 设置 `LLM_API_KEY` |
| OpenAI | gpt-4o, gpt-4-turbo, gpt-4o-mini | 设置 `LLM_API_KEY` |
| DeepSeek | deepseek-chat | 设置 `LLM_BASE_URL=https://api.deepseek.com/v1` |
| Ollama | 本地模型 | 设置 `LLM_BASE_URL=http://localhost:11434/v1` |

---

## 📊 预测输出格式

```json
{
  "trend": "看涨",
  "confidence": 0.78,
  "period": "1-5个交易日",
  "key_factors": ["MACD金叉形成", "成交量放大"],
  "risk_warnings": ["大盘系统性风险"],
  "price_targets": {
    "support": 1650.00,
    "current": 1700.00,
    "resistance": 1750.00,
    "target_high": 1780.00
  },
  "reasoning_summary": "综合技术面偏多..."
}
```

---

## ⚠️ 免责声明

1. 本工具 **仅供学习研究**，不构成任何投资建议
2. AI 预测基于历史数据和公开信息，**不能保证未来收益**
3. 预测结果可能受数据质量、模型能力、市场突发事件等因素影响
4. 投资者应**独立决策**，自行承担投资风险
5. 过往表现不代表未来收益

---

## 📝 License

MIT License - 仅供学习研究使用
