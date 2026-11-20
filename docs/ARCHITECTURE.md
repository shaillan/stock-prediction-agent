# 代码结构说明

> 面向第一次读这个仓库的人：每个文件干什么、改一个需求该去哪。
> 核心代码共 70 个 Python 文件（不含 `cache/` 下的本地验证脚本），按子系统组织，不按字母顺序罗列。

## 0. 先看主干

```
Streamlit 界面 (ui/ + main.py)
   ├─ 个股深度分析 → LangGraph 工作流 (agent/) ─┬─ data/ 取数
   │                                            ├─ rag/ 查公告
   │                                            └─ utils/llm_factory 调模型
   ├─ 自选股简报 → services/briefing.py
   └─ 智能问答 → agent_mode/ → harness/ → data/ + rag/
                         ↓
                    backtest/（事后验证信号有没有用）
```

两条容易混淆的线：

- **工作流**（`agent/`）：路径由代码写死，LLM 只在指定节点写内容
- **Agent**（`agent_mode/` + `harness/`）：LLM 自己决定下一步调什么工具

两者共用 `data/`、`rag/`、`utils/`，不是替代关系。

## 目录

1. [入口与配置](#1-入口与配置)
2. [agent/：LangGraph 工作流](#2-agentlanggraph-工作流主流程)
3. [agent_mode/：Agent 模式](#3-agent_modeagent-模式)
4. [harness/：Agent 运行时层](#4-harnessagent-运行时层)
5. [rag/：公告全文检索](#5-rag公告全文检索)
6. [data/：数据层](#6-data数据层)
7. [backtest/：回测](#7-backtest回测证伪工具)
8. [services/ 与 utils/](#8-services-与-utils)
9. [ui/：界面](#9-ui界面)
10. [一条完整链路长什么样](#10-一条完整链路长什么样)
11. [非代码文件与运行目录](#11-非代码文件与运行目录)
12. [速查表](#12-速查表想改什么去哪)
13. [建议阅读路线](#13-建议阅读路线)
14. [维护约定](#14-维护约定)

## 1. 入口与配置

| 文件 | 作用 |
|---|---|
| `main.py` | Streamlit 主入口。管会话状态、预取数据、按侧边栏模式分发到三个页面；分析完成后存档预测 |
| `config.py` | 全局参数（模型、缓存时长、RAG 开关、harness 预算），从 `.env` 读密钥 |
| `.env` / `.env.example` | 实际密钥 / 模板。`.env` 不进 git，模板里保持占位符 |
| `requirements.txt` | 依赖清单 |
| `.streamlit/config.toml` | 深色主题的基础配置 |

## 2. `agent/`：LangGraph 工作流（主流程）

代码写死路径，LLM 只在指定节点写内容。当前是 7 个节点、8 条静态边 + 1 条条件边（正常/降级）。

| 文件 | 作用 |
|---|---|
| `graph.py` | 编排图：节点、并行分支、降级路由 |
| `state.py` | `AgentState` 数据契约：节点之间传什么 |
| `prefetch.py` | 跨节点传递 DataFrame 的临时变量（绕开 LangGraph 序列化限制） |
| `sub_agents/data_agent.py` | 取 K 线、行情、财务、大盘指数 |
| `sub_agents/tech_agent.py` | 算技术指标 + LLM 解读 |
| `sub_agents/sentiment_agent.py` | 新闻抓取 + LLM 判情绪 |
| `sub_agents/announcement_agent.py` | 调 RAG 查公告，产出第五路信号 |
| `sub_agents/prediction_agent.py` | 汇总所有信号出预测；盘点缺口；生成报告 |
| `prompts/system_prompts.py` | 所有节点的中文提示词 |

阅读顺序：`state.py` → `graph.py` → `sub_agents/data_agent.py` → `prediction_agent.py`。

## 3. `agent_mode/`：Agent 模式

| 文件 | 作用 |
|---|---|
| `tools.py` | 把 5 个数据能力包成 LLM 可调的函数（行情/财务/新闻/公告/战绩），并注册进 harness |
| `loop.py` | **薄壳**：`run_agent_mode` / `stream_agent_mode`，真正循环在 `harness/runtime.py` |
| `__main__.py` | 命令行入口 `python -m agent_mode` |

## 4. `harness/`：Agent 运行时层

| 文件 | 作用 |
|---|---|
| `types.py` | 数据结构：`ToolSpec`、`RunRecord`、事件契约 |
| `registry.py` | 工具注册表：超时、重试、TTL 缓存、统一错误文本 |
| `runtime.py` | ReAct 循环本体：事件流、预算检查、并行执行工具 |
| `budget.py` | 步数 / token / 墙钟 / 成本四类预算 |
| `trace.py` | 逐事件写 `runs/<日期>/<run_id>.jsonl`，落盘前脱敏 |
| `context.py` | 系统提示 + 历史 + 本轮问题装配，历史超长时从最旧丢 |
| `adapters.py` | LLM 重试 + 各家 token 用量归一 |
| `evals/scorers.py` | 用例打分：该调的工具调没调、该说的免责声明说没说、步数超没超 |
| `evals/run.py` | 评测运行器 `python -m harness.evals.run` |
| `evals/suites/smoke.jsonl` | 14 条回归用例 |
| [`TUTORIAL.md`](../harness/TUTORIAL.md) | harness 教程：事件契约、预算语义、轨迹排查、加工具/加用例 |

> `harness/__init__.py` 只做延迟导出，不承载逻辑。

## 5. `rag/`：公告全文检索

| 文件 | 作用 |
|---|---|
| `fetch.py` | 第 1 步：巨潮公告列表 → 下载 PDF → 抽纯文本，过滤噪音文书 |
| `index.py` | 第 2 步：文本切块 → embedding → 存 chromadb |
| `query.py` | 第 3、4 步：向量 + 关键词混合检索 → 拼上下文 → LLM 回答 |
| `lexical.py` | 关键词一路：jieba 分词 + BM25 |
| `service.py` | 给分析流水线用的封装：`build_stock_context`（6 个固定研究问题） |
| `diagnose.py` | 检索质量诊断：gap 值、两路冠军、融合后排名 |
| `eval.py` | 检索评测：Recall@k / Precision@k / MRR（文档级） |
| `gold_600519.jsonl` | 11 条标注问题，含 gold 公告标题与日期 |
| `cli.py` | 命令行：建库 / 提问 / 检索 / 诊断 / 看 collection |
| `TUTORIAL.md` | 检索优化教程 |

## 6. `data/`：数据层

> 当前只覆盖 A 股：港股/美股/ETF/北交所都没有适配。

| 文件 | 作用 |
|---|---|
| `akhare_client.py` | 所有 A 股接口（K 线、行情、财务、新闻、指数、搜索），含东财→新浪兜底链路 |
| `cache_manager.py` | 二级缓存：内存 LRU + SQLite 磁盘（`cache/stock_cache.db`） |
| `technical_indicators.py` | 纯 Python 算 MA/MACD/RSI/KDJ/BOLL 等，不依赖 LLM |
| `stock_registry.py` | 30 只常用股票 + 在线代码搜索 |
| `models.py` | Pydantic 数据模型（K 线、行情、预测结果等） |

## 7. `backtest/`：回测（证伪工具）

| 文件 | 作用 |
|---|---|
| `signals.py` | 8 个规则信号（趋势、均线、MACD、KDJ、放量、RSI、布林、威廉） |
| `engine.py` | walk-forward：每个时点出信号，对照未来 N 日真实涨跌 |
| `metrics.py` | 命中率、净胜率、t 值、结构性上限；两套标签口径 |
| `run.py` | 命令行入口 `python -m backtest.run` |

## 8. `services/` 与 `utils/`

| 文件 | 作用 |
|---|---|
| `services/briefing.py` | 自选股简报：行情 + 新闻 + 公告 → 大白话解读，当日缓存 |
| `utils/llm_factory.py` | 多厂商 LLM 工厂（Claude / OpenAI / DeepSeek / 智谱） |
| `utils/track_record.py` | 预测存档、到期自动复盘、置信度校准 |
| `utils/watchlist.py` | 自选股本地存储 + 免费/付费额度 |
| `utils/logger.py` | loguru 配置（控制台 + `logs/` 按天文件） |
| `utils/error_handler.py` | 统一错误类型与装饰器 |

## 9. `ui/`：界面

| 文件 | 作用 |
|---|---|
| `styles.py` | 全部 CSS 设计 token（深色金融终端风） |
| `chart_theme.py` | Plotly 统一配色与布局 |
| `components/sidebar.py` | 侧边栏：模式选择、股票、日期、LLM 配置、RAG 开关 |
| `components/kline_chart.py` | K 线图 + 均线/布林/MACD/RSI 叠加 |
| `components/prediction_panel.py` | 预测结论面板（趋势、置信度、目标价区间） |
| `components/analysis_reasoning.py` | 分析详情 7 个标签页（技术/情绪/公告/基本面/报告/战绩/科普） |
| `components/progress_display.py` | 工作流 5 步进度条 |
| `components/beginner_guide.py` | 14 个概念的大白话科普 |
| `components/guide_figures.py` | 科普配图（8 张教学小图） |
| `components/briefing.py` | 简报页：自选管理 + 付费墙 + 简报卡片 |
| `components/agent_chat.py` | 智能问答页：流式聊天、工具状态、多轮历史 |
| `components/trace_card.py` | 结论溯源卡：数字核对 / 数据来源 / 公告依据 |

## 10. 一条完整链路长什么样

**工作流（个股深度分析）**

```
用户点「开始分析」
  → main.py 预取 K 线，写进 agent/prefetch.py
  → agent/graph.py 启动
      ├─ data_agent      取行情/财务/大盘
      ├─ tech_agent      算指标 → LLM 解读
      ├─ sentiment_agent 取新闻 → LLM 判情绪
      └─ announcement_agent → rag/service → 检索 + LLM 回答
  → 汇合：prediction_agent 盘点缺口 → 预测 + 报告
  → utils/track_record 存档本次预测
  → ui/components/* 渲染图表与报告
```

**Agent（智能问答）**

```
用户提问
  → ui/components/agent_chat.py
  → agent_mode/loop.py（薄壳）
  → harness/runtime.py 循环
      ├─ harness/registry.py 执行工具（超时/重试/缓存）
      ├─ harness/budget.py 每轮检查预算
      └─ harness/trace.py 逐事件落盘
  → 事件流回 UI：工具状态 + 流式 token
  → ui/components/trace_card.py 渲染溯源卡
```

## 11. 非代码文件与运行目录

| 路径 | 作用 |
|---|---|
| `README.md` | 项目主文档 |
| `docs/ARCHITECTURE.md` | 本文件：代码地图 |
| `design/README.md`、`design/ui_mockup.html` | 高保真视觉稿与设计说明 |
| `rag/TUTORIAL.md` | 检索优化教程 |
| `LangChain_LangGraph_Agent.pptx` | 讲解用幻灯片 |
| `backtest_result.csv` | 某次回测导出的逐时点明细 |
| `records/predictions.jsonl` | 预测战绩存档（运行时生成） |
| `runs/` | harness 轨迹与评测报告（运行时生成，已 gitignore） |
| `logs/` | 按天日志 |
| `cache/` | 本地验证脚本与缓存（`_shot.py` 截图、各类 `*_check.py` 自检、`stock_cache.db`），整个目录不进 git |

## 12. 速查表：想改什么，去哪

| 需求 | 文件 |
|---|---|
| 改分析逻辑 / 加一路信号 | `agent/graph.py` + `agent/sub_agents/` + `prompts/` |
| 改提示词 | `agent/prompts/system_prompts.py`、`harness/runtime.py` 的 `SYSTEM_PROMPT` |
| 让 Agent 能查新数据 | `agent_mode/tools.py`（实现 + `@tool` + 注册） |
| 改预算 / 加成本 | `harness/budget.py` + `config.py` |
| 改检索效果 | `rag/index.py`（切块）、`rag/query.py`（融合） |
| 改数据源 | `data/akhare_client.py` |
| 改回测口径 | `backtest/metrics.py` |
| 改界面样式 | `ui/styles.py` + 对应 `ui/components/*` |
| 加评测用例 | `harness/evals/suites/smoke.jsonl` |

## 13. 建议阅读路线

1. `config.py` → `main.py`：先知道入口怎么跑
2. `agent/state.py` → `agent/graph.py`：主干流程
3. `data/akhare_client.py` + `data/technical_indicators.py`：数据从哪来
4. `agent/sub_agents/prediction_agent.py`：结论怎么合成
5. `harness/runtime.py`：Agent 模式怎么循环
6. `backtest/metrics.py`：怎么验证信号真没用

## 14. 维护约定

- `.env` 不进 git；提交前确认 `.env.example` 里仍是占位符
- `runs/`、`logs/`、`records/`、`cache/` 都是本地运行数据，不提交
- 改了 `ui/styles.py` 或任何被 Streamlit 页面 import 的模块，要重启进程才生效
  （`runOnSave` 只会重跑 `main.py`，不会重新导入模块）
- 改了 harness 的公共接口，至少跑一遍：
  `cache/harness_check.py`、`cache/agent_mode_check.py`、`cache/trace_card_check.py`
