# 📈 股票智能预测工作流

基于 **LangGraph** 编排的 A 股分析 **LLM 工作流**，综合技术面、消息面、基本面与**公告全文**进行多源分析，输出短期趋势预测。

> 📌 **关于名字**：本项目常被叫作 "Agent"，但它严格来说是**工作流**——分析路径由代码写死，LLM 只在指定的节点里生成内容，**不参与"下一步做什么"的决策**。这条分界线的判定依据，见下面「🏗️ 架构」里的 **「说清楚：这是『工作流』，不是『Agent』」** 一节。

> ⚠️ **重要声明**：本工具仅供学习研究使用，AI 预测不构成投资建议。股市有风险，投资需谨慎。

---

## ✨ 功能特性

- 🔍 **技术分析**：自动计算 MA、MACD、RSI、KDJ、布林带等指标，LLM 专业解读
- 📰 **新闻情绪分析**：获取个股相关新闻，LLM 分析情绪和影响强度
- 📢 **公告全文检索（RAG）**：从巨潮资讯拉取公司公告 PDF 全文，用向量检索出减持、回购、业绩预告、重大合同等关键事项，作为预测的额外信号
- 💰 **基本面概览**：PE、PB、ROE 等关键财务指标
- 🎯 **综合预测**：多源信息融合，输出趋势判断 + 置信度 + 目标价位
- 📊 **交互式图表**：Plotly K 线图 + 技术指标叠加（均线、布林带、MACD、RSI）
- 🧪 **回测框架**：规则信号 walk-forward 回测 + 显著性检验（t 值），可证伪地检验"信号有没有预测力"
- 🤖 **多模型支持**：Claude / GPT-4o / DeepSeek / Ollama 等兼容 API

---

## 🏗️ 架构

一条 **LangGraph LLM 工作流**：**5 个节点、7 条边，全部静态**。路径由代码写死，LLM 只负责在指定节点里生成内容。

```
用户界面 (Streamlit)
    ↓
LangGraph LLM 工作流（5 节点 / 7 边，全部静态）
    ├── 📡 数据采集 (AKShare)
    ├── 📊 技术分析 (Python计算 + LLM解读)  ┐
    ├── 📰 新闻情绪 (LLM分析)               ├─ 三条并行
    ├── 📢 公告检索 (RAG 向量检索)          ┘
    ├── 🧠 综合预测 (LLM JSON输出)
    └── 📝 报告生成 (LLM Markdown输出)
    ↓
结果展示 (Plotly图表 + 预测面板 + 分析报告)
```

技术分析、新闻情绪、公告检索三者互不依赖，**并行执行**；三者完成后才进入综合预测。

其中 **📡 数据采集** 和 **📢 公告检索** 是纯代码节点，**不调 LLM**。LLM 只出现在技术分析、新闻情绪、综合预测、报告生成四处，**且各调一次**——这正是"工作流"的特征：调用次数和位置都由代码定死。

### 说清楚：这是「工作流」，不是「Agent」

分界线只有一条：

> **谁决定"下一步做什么"？**

| | Agent | 工作流（本项目） |
|---|---|---|
| 下一步做什么 | **LLM 自己决定** | **代码写死** |
| 控制流 | 有循环：想 → 调工具 → 看结果 → 再想 | 直线 + 一次并行分叉，跑到头就结束 |
| 怎么用数据 | LLM 通过 tool calling **主动去调** | 代码先取好，**塞进 prompt** 让它读 |
| 运行路径 | 每次可能都不同 | 每次都一样 |

本项目的实测证据（都在代码里可查）：

| 检查项 | 结果 |
|---|---|
| `add_conditional_edges`（动态路由） | **0 处** |
| `bind_tools` / `tool_calls` / `ToolNode`（LLM 调工具） | **0 处** |
| `create_react_agent`（ReAct 循环） | **0 处** |
| 循环结构 | **0 处** |
| 图的形状 | 5 个节点、7 条边，**全部静态** |
| 每个 LLM 节点的调用次数 | **各 1 次**——单发，不是"想→做→看→再想" |

`agent/graph.py` 里那 7 条 `add_edge` 全是硬编码的，一个条件分支都没有。**LLM 从头到尾只做一件事：拿到已经准备好的材料，写一段文字。** 它从没决定过"下一步干什么"。

按 Anthropic《Building Effective Agents》的分类，本项目属于 **prompt chaining（提示链）+ parallelization（并行化）**：把任务拆成固定的小步，每步让 LLM 干一件明确的事，其中三步并行跑。

**工作流不是"低配版 Agent"。** 在这个场景里它反而是更正确的选择：

- **步骤是确定的**——指标一定要算、新闻一定要看，没有需要 LLM 临场判断的岔路
- **每步可单独验证**——指标算错就是算错，跟 LLM 无关，能分开排查
- **便宜且可预期**——固定几次 LLM 调用，不会因为模型"想多了"跑出二十次，账单可控
- **好定位问题**——哪一步挂了，日志里一眼看得出来

**那什么情况下才该上 Agent？** 当"下一步做什么"真的需要临场判断时。例如：

> 先去查公告 → 发现有笔大额回购 → 于是决定**再去查**资金流和股东户数 → 两边数据对不上 → **再回去**核对是不是口径不同

这种**路径事前写不出来**的任务，才是 Agent 的用武之地。

**要把它改成真 Agent，需要补三样东西**（目前一样都没有）：

1. `bind_tools` + `ToolNode` —— 让 LLM 能**主动调**数据接口，而不是代码提前把数据塞给它
2. `add_conditional_edges` —— 让"下一步走哪里"由 LLM 判断，而不是写死
3. 一个循环 —— 允许"做完一步后，根据结果决定要不要再来一轮"

> 📌 **代码里为什么还叫 `agent`**：目录名 `agent/`、类名 `AgentState`、入口函数 `run_agent` 都是历史命名，改名会牵动全项目的 import（风险大、收益为零）。所以本次**只改了用户可见的文案**，代码标识符原样保留——取舍是：**承认命名不精确，但保证它唯一且稳定**，好过"文档说 A、代码说 B"。

### 公告检索 RAG 是怎么工作的

预测流程里没有"用户提问"，所以 RAG 用一组**固定研究问题**去检索：

> 大股东减持/增持？回购？业绩预告？重大合同？分红方案？诉讼处罚？

对每个问题做**混合检索**（向量 + 关键词 BM25，RRF 融合），把命中的公告片段拼成"公告动态"喂给预测与报告 LLM。

- 公告数据来自**巨潮资讯**（`rag/fetch.py` 直接打其 HTTP 接口，绕过坏掉的 akshare 封装）
- 向量库用 chromadb 持久化，**按股票分集合**，首次分析某只股票约 30-60 秒建索引，之后走缓存
- **默认丢弃两类零信息文书**：定期报告（半年报/年报/季报，占向量库六成以上却只贡献数字碎片）、独董模板文书（候选人/提名人声明、述职报告，通篇套话只为"股东"二字而中选）。要查营收等财务数字时用 `--keep-reports`
- 两类过滤规则都记在向量库 metadata 里当"口径"，**改了口径会自动重建索引**，不会让你对着旧库怀疑改动没生效
- 为什么是混合检索：纯向量匹配"主题"，问"大股东有没有减持"会命中一堆《股东会通知》而漏掉真正的答案；加关键词这一路后答案从"榜上无名"升到第 1 名
- 可在侧边栏关闭（首次运行较慢时）

> 📖 **检索怎么调、怎么验证**：见 [`rag/TUTORIAL.md`](rag/TUTORIAL.md) —— 含"为什么相似度距离没有意义，要看 gap"、实测前后对照、`diagnose` 命令的用法，以及一个反直觉的坑（**别顺手删《法律意见书》**：RRF 是排名制，删它反而会把错答案顶上第 1 名）。

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.9+
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

> 注：公告检索的 embedding 用**本地模型**，首次使用会自动从 HuggingFace 镜像下载（约 100MB），不需要额外 API Key。

### 4. 启动

```bash
streamlit run main.py
```

浏览器访问 `http://localhost:8501`

### 5. 使用

1. 左侧选择或输入 A 股代码（如 600519 贵州茅台）
2. 选择分析周期
3. 配置 LLM 模型和 API Key
4. （可选）开关"公告全文检索"
5. 点击 **"🚀 开始分析"**
6. 等待约 30秒-2分钟（取决于 LLM 响应速度；首次公告检索需额外下载建索引）
7. 查看 K 线图、预测结果和详细分析报告（详情区共 5 个标签页：技术分析 / 新闻情绪 / **公告** / 基本面 / 完整报告）

> **"公告"标签页**里显示的就是 RAG 检索到的片段原文——和喂给预测模型的那段字符完全一致。
> 如果这页是空的，它会明确告诉你是**检索被关掉了**、**检索报错了**，还是**确实没命中**：
> 公告检索在流水线里是静默降级的（失败不中断分析，只少一路信号），不给提示的话根本看不出来。
> 想进一步看每条的排名 / 距离 / gap，用 `python -m rag.cli diagnose`，见 [rag/TUTORIAL.md](rag/TUTORIAL.md)。

---

## 🧪 回测

`backtest/` 提供一套**可证伪的验证框架**：规则信号 + walk-forward 回测 + 显著性检验（净胜率的 t 值），回答"某个信号到底有没有预测力"。

```bash
# 跑默认股票池，输出各信号对比表
python -m backtest.run

# 指定股票与日期，只看趋势信号详细报告
python -m backtest.run --stocks 600519,000858 --start 2022-01-01 --end 2024-12-31 --signals trend

# 8 个信号全跑一遍对照
python -m backtest.run --signals all
```

> ⚠️ **一个诚实的结论**：实测 8 个技术指标规则信号（趋势跟随、均线排列、MACD、KDJ、放量突破、RSI/布林/威廉反转）在 A 股大盘股上**都没有稳健的预测力**——全池净胜率 ≤ 0，最强的 RSI 反转 t 值仅 +1.27（|t|<2 即噪声）。详见 `backtest/signals.py` 与记忆文档。这正是把公告全文作为**新信号源**引入的动机：技术指标这条路已被证明走不通。

## 📁 项目结构

```
stock-prediction-agent/
├── main.py                    # Streamlit 入口
├── config.py                  # 全局配置
├── .env.example               # API Key 模板
├── requirements.txt           # 依赖清单
│
├── agent/                     # LangGraph 工作流定义（目录名保留 agent/，见上文说明）
│   ├── state.py               # AgentState 与子图输入/输出契约
│   ├── graph.py               # StateGraph 编排（含并行分支）
│   ├── prefetch.py            # DataFrame 预取，绕过 msgpack 序列化限制
│   ├── prompts/
│   │   └── system_prompts.py  # 中文 System Prompt
│   └── sub_agents/
│       ├── data_agent.py      # 数据采集
│       ├── tech_agent.py      # 技术分析（指标计算 + LLM 解读）
│       ├── sentiment_agent.py # 新闻情绪
│       ├── announcement_agent.py # 公告检索（RAG）
│       └── prediction_agent.py   # 综合预测 + 报告生成
│
├── rag/                       # 公告全文 RAG
│   ├── fetch.py               # 巨潮公告列表 + PDF 下载 + 抽文本 + 噪音文书判定
│   ├── index.py               # 切块 + embedding + chromadb
│   ├── lexical.py             # 关键词检索（jieba 分词 + BM25 + RRF 融合）
│   ├── query.py               # 混合检索 + LLM 回答
│   ├── diagnose.py            # 检索质量诊断（gap / 两路冠军 / 融合排名）
│   ├── service.py             # 供流水线调用的 build_stock_context
│   ├── cli.py                 # 命令行入口（index/ask/retrieve/diagnose/collections/context）
│   └── TUTORIAL.md            # 检索优化教程（怎么判断准不准、怎么调）
│
├── backtest/                  # 回测框架
│   ├── signals.py             # 规则信号 + 注册表
│   ├── engine.py              # walk-forward 回测
│   ├── metrics.py             # 命中率 / 净胜率 / t 值显著性
│   └── run.py                 # CLI 入口
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
│       ├── sidebar.py         # 侧边栏（含 RAG 开关）
│       ├── kline_chart.py     # K线图 (Plotly)
│       ├── prediction_panel.py # 预测面板
│       ├── analysis_reasoning.py # 分析详情
│       └── progress_display.py  # 进度指示
│
├── utils/                     # 工具层
│   ├── llm_factory.py         # 多Provider LLM工厂
│   ├── error_handler.py       # 错误处理
│   └── logger.py              # 日志
│
├── create_codex_ppt.py        # 生成项目介绍 PPT
└── generate_ppt.py            # 生成分析结果 PPT
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
  "key_factors": ["MACD金叉形成", "成交量放大", "控股股东增持"],
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
