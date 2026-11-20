# Harness 教程：Agent 运行时是怎么跑起来的

这份教程讲一件事：**模型是怎么被驱动着去查数据、什么时候该停、每一步留下什么证据、改完怎么验证**。所有结论都来自这套代码的实测，不是理论。

配套阅读：

- [rag/TUTORIAL.md](../rag/TUTORIAL.md)：检索准不准
- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)：每个文件干什么

## 目录

1. [先记住一句话](#一先记住一句话)
2. [没有 harness 会怎样](#二没有-harness-会怎样)
3. [一次运行的全过程](#三一次运行的全过程)
4. [事件契约](#四事件契约)
5. [循环怎么转](#五循环怎么转runtime)
6. [工具注册表](#六工具注册表registry)
7. [预算](#七预算budget)
8. [轨迹](#八轨迹trace)
9. [上下文与模型适配](#九上下文与模型适配)
10. [评测](#十评测evals)
11. [常见坑](#十一常见坑)
12. [三个动手改的配方](#十二三个动手改的配方)
13. [已知遗留](#十三已知遗留)
14. [命令速查](#十四命令速查)

---

## 一、先记住一句话

> **事件是唯一真相：循环只产出四种事件，CLI、界面、评测都只是听众。**

第二个必须记住的原则：**预算由代码执行，不靠模型自觉**。模型说"我还想再查"，预算说"不行"，那就得停。

第三个：**轨迹脱敏后才能落盘**。API Key、`sk-` 开头的串、`api_key=` 这类键值，写文件前统一打码。

---

## 二、没有 harness 会怎样

| 缺口 | 没有 harness 时的表现 | harness 补上什么 |
|---|---|---|
| 工具卡死 | 一个慢接口把整轮拖住，进程退不掉 | 每件工具有超时，daemon 线程可丢弃 |
| 乱花钱 | 模型反复调工具，直到你手动关窗口 | 步数 / token / 墙钟 / 成本四道预算 |
| 不可复盘 | 只看到最终答案，不知道查了什么 | 逐事件 JSONL，含工具原始返回 |
| 改完没底 | 改完 prompt 只能"感觉好点了" | 固定用例集 + 确定性打分 + 报告 |
| 换模型要改代码 | 每家消息格式、usage 字段都不同 | `adapters.py` 统一成同一套 |

---

## 三、一次运行的全过程

```
用户提问
  → 入口（CLI / 聊天页 / 评测脚本）
  → runtime.iter_agent_events
      1. budget.limit_reason()      每轮开头先查预算
      2. context.build_messages()   系统提示 + 历史 + 本轮问题
      3. llm.bind_tools()           把工具 schema 交给模型
      4. 循环：
           模型要工具 → registry.execute（并行 + 超时 + 重试 + 缓存）
                      → ToolMessage 回喂 → 模型再想
           模型不要工具 → done
      5. 步数或预算到顶 → 强制"不带工具"收尾
  → 事件流：tool_start / tool_end / token / done
  → 听众：CLI 拼 dict ｜ 界面渲染 ｜ Tracer 落盘 ｜ 评测打分
```

关键点：**循环只有一份实现**（`runtime.iter_agent_events`），`agent_mode/loop.py` 只是薄壳。CLI 用 `run_agent_mode` 把事件拼回 dict，界面用 `stream_agent_mode` 逐条渲染——两条路不会跑偏。

---

## 四、事件契约

循环只产出四种事件（契约定义在 `harness/types.py` 顶部）：

| 事件 | 关键字段 | 消费方 | 用途 |
|---|---|---|---|
| `tool_start` | `name` / `args` / `step` | 界面、轨迹 | 先把本轮所有工具宣告为"进行中" |
| `tool_end` | `name` / `summary` / `result` / `elapsed_ms` / `cached` / `retries` | 界面、轨迹、溯源卡 | 工具出结果；`result` 是完整原文 |
| `token` | `text` | 界面 | 仅流式；逐字渲染答案 |
| `done` | `answer` / `trajectory` / `steps_used` / `stopped` / `usage` | 所有人 | 收尾，带用量和停止原因 |

`stopped` 有三种：

- `answered`：模型自己说"够了"
- `cap`：步数用完（或预算里的 `max_steps` 触顶）
- `budget`：token / 墙钟 / 成本触顶

`tool_end.result` 是后来加的：**结论溯源卡靠它核对"答案里的数字是不是来自工具"**。只有 `summary`（160 字）不够——数字可能被截掉。

---

## 五、循环怎么转（runtime）

**非流式**：`bound.invoke(messages)` 一次拿完整回复；失败由 `adapters.invoke_with_retry` 重试两次。

**流式**：`bound.stream(messages)` 边到边 yield `token`。两个坑：

1. **工具调用的参数是分片 JSON**（`{"stock_code":` / `"600519"}` 分几块到），必须按 `index` 拼起来再 `json.loads`，否则永远拿到半截参数。
2. **厂商格式不同**：有的流式分片拼不出工具名（ChatAnthropic 走这条路），此时回退非流式 `invoke`。兜底条件写死为"有分片、但一个工具名都没拼出来、且还没吐过 token"。

**并行执行**：模型一轮要 3 个工具，就同时跑 3 个。用 `ThreadPoolExecutor.map` 而不是 `as_completed`——**map 保序**，轨迹和 `ToolMessage` 的顺序就是模型的调用顺序，测试和日志才稳定。

**步数怎么算**：一次工具调用算一步。并行查行情 + 财务 = 2 步，不是 1 轮。

**到顶收尾**：循环结束后，用**未绑定工具的 llm** 再调一次，明确要求"只基于已收集信息下结论，并说明缺了什么"。为什么不用绑工具的模型？防止它继续要工具，形成死循环。

---

## 六、工具注册表（registry）

一个工具 = 一个 `ToolSpec`：

| 字段 | 作用 |
|---|---|
| `name` / `description` / `schema` | 给模型看的"说明书" |
| `impl` | 真正执行的函数 |
| `timeout_s` | 单次调用最多等多久 |
| `retries` | 失败后自动再来几次（超时不重试） |
| `cache_ttl_s` | 同一参数多久内直接复用结果 |

`execute()` **永远不抛异常**，失败也返回一段说明文本。四种口径：

```
未知工具 bad_tool。可用工具: ...
工具执行超时（25s）：query_market 没有在限定时间内返回，先改用其它信息，别重复调用它。
工具执行失败: ConnectionError: ...（最多重试一次，然后改用其它信息）
（工具返回空）
```

为什么要这样：模型看到的报错越具体，越能自己决定"换条路"还是"如实说缺什么"。抛异常只会让整轮挂掉。

**超时为什么用裸 daemon 线程**：`ThreadPoolExecutor` 退出时会 join 工作线程，一个卡死的 AKShare 请求会让整个进程退不掉；daemon 线程允许被丢弃。

项目里的 5 个工具（`agent_mode/tools.py` 的 `_TOOL_RUNTIME`）：

| 工具 | 超时 | 重试 | 缓存 TTL | 为什么这样设 |
|---|---|---|---|---|
| `query_market` | 25s | 1 次 | 60s | 网络慢，但盘中数据变得快 |
| `get_financials` | 20s | 1 次 | 1 小时 | 财报当天基本不变 |
| `get_news` | 20s | 1 次 | 10 分钟 | 新闻会更新，但不用每次重查 |
| `search_announcements` | 30s | 1 次 | 5 分钟 | 建库/检索慢 |
| `get_track_record` | 10s | 1 次 | 60s | 本地文件，很快 |

**测试/定制场景**可以传 `impls_override`：这时只用注册表里的超时，**不重试、不走缓存**，实现由调用方负责。`cache/harness_check.py` 和 `cache/agent_mode_check.py` 用的就是这条路。

缓存 key = 工具名 + 参数 JSON（排序后）。缓存是**进程内**的，重启即清空。

---

## 七、预算（budget）

四道上限 + 三个账本 + 一个秒表：

| 字段 | 默认 | 说明 |
|---|---|---|
| `max_steps` | 12 | 最多几次工具调用 |
| `max_tokens` | 60000 | 输入 + 输出总 token |
| `max_seconds` | 180 | 墙钟，等慢接口的时间也算 |
| `max_cost_cny` | None | 成本上限；None = 不限 |
| `prompt_tokens` / `completion_tokens` | 0 | 运行时累加 |
| `cost_cny` | None | 按单价算出的花费；None = 未配置 |
| `_started` | 0.0 | 单调时钟起点，算 `elapsed_s` |

每轮开头按 **步数 → 秒数 → token → 成本** 的顺序检查。

**`0` 和 `None` 不是一回事**：

| 设置 | 效果 |
|---|---|
| `max_steps=0` | 立刻停 |
| `max_tokens=0` / `max_seconds=0` | **关闭**该项检查（代码用真值判断） |
| `max_cost_cny=None` | 关闭成本检查 |
| `max_cost_cny=0` | 立刻停 |

**怎么改**：

| 参数 | 入口 |
|---|---|
| 步数 | CLI `--max-steps`、界面滑块（2–20，默认 8）、函数参数 |
| token / 时间 | `config.py` 的 `harness_max_tokens` / `harness_max_seconds`；CLI `--max-tokens` / `--max-seconds` |
| 成本 | **目前没有入口接线**：`from_settings()` 没设 `max_cost_cny` |

成本上限要真正生效，需要同时做两件事：在 `config.py` 填单价、在 `from_settings()` 里传入 `max_cost_cny`。只设上限不填单价时，`cost_cny` 是 `None`，比较时按 0 算，**永远不会触发**。

```bash
python -m agent_mode "600519 最近走势如何" --code 600519 \
  --max-steps 5 --max-tokens 20000 --max-seconds 60
```

改 `config.py` 后**必须重启进程**；`Settings` 在 import 时只加载一次。界面上的步数滑块是实时生效的。

---

## 八、轨迹（trace）

两层文件：

| 文件 | 内容 | 用途 |
|---|---|---|
| `runs/<日期>/<run_id>.jsonl` | 每轮的全部事件（含工具原文） | 复盘单轮 |
| `runs/index.jsonl` | 每轮一行摘要 | `tail` / `grep` 看全部运行 |

**逐事件写盘**，不是结束时一次性写：进程崩了、用户 Ctrl-C，前面发生过什么仍然留在磁盘上。

**脱敏是硬约束**，不是可选项。落盘前统一过 `mask_obj`：

- `sk-` 开头的 key
- `api_key=` / `authorization:` / `access_token=` 这类键值

摘要行字段：`run_id / question / stock_code / model / steps_used / stopped / tools / usage / wall_s / trace_path`。**注意：摘要里没有"评测通过与否"**，那是 `runs/evals/*.json` 的事。

谁创建 `Tracer`：

- CLI（默认开，`--no-trace` 关）
- 聊天页（每轮一次）
- 评测脚本（每条用例一次）

`runs/` 已 gitignore；删掉不影响代码，只会丢历史记录。

常用查法：

```bash
tail -n 5 runs/index.jsonl                          # 最近几轮
grep '"stopped": "cap"' runs/index.jsonl            # 哪些撞了步数上限
grep '"stock_code": "600519"' runs/index.jsonl      # 只看茅台的
```

---

## 九、上下文与模型适配

**`context.py`**：把系统提示、历史对话、本轮问题装配成消息列表。历史有一个字符预算 `max_chars=12000`，超了从**最旧**的消息开始丢。

一个已知的小瑕疵：裁剪是按"单条消息"丢的，可能留下一条没有对应提问的 assistant 消息。当前量级下不会影响模型，但改成按 Q/A 对丢会更干净。

**`adapters.py`** 做两件事：

1. **统一 token 用量**：新版 LangChain 在 `usage_metadata`，OpenAI 兼容在 `response_metadata["token_usage"]`，流式只有最后一个 chunk 可能带。统一成 `prompt_tokens / completion_tokens / total_tokens`，拿不到就返回空。
2. **非流式重试**：`invoke_with_retry` 默认重试 2 次，指数退避（0.8s、1.6s）。

拿不到用量时，预算里的 token 计数会一直是 0——不是"没花钱"，是"没拿到账"。

---

## 十、评测（evals）

用例是 JSONL，一行一条：

```json
{"id":"announce-1","question":"600519 大股东最近有没有减持？","stock_code":"600519",
 "must_call":["search_announcements"],"max_steps":6,"note":"减持只能从公告原文里查"}
```

支持的断言：

| 字段 | 含义 |
|---|---|
| `must_call` / `must_not_call` | 必须调 / 不许调的工具 |
| `must_contain` / `must_not_contain` | 答案里必须有 / 不能有的字符串 |
| `max_steps` / `max_seconds` | 效率闸 |

```bash
python -m harness.evals.run                    # 全量
python -m harness.evals.run --case market      # 按 id 过滤
python -m harness.evals.run --limit 3          # 只跑前 3 条
python -m harness.evals.run --no-trace         # 不落逐条轨迹
python -m harness.evals.run --model deepseek-chat
```

产物：控制台逐条 `✅/❌` + 失败原因、`runs/evals/<时间戳>.json`、每条用例的 `runs/<日期>/*.jsonl`。全过退出码 0，有失败 1。

**看报告先看失败列表**，比看通过率有用。比如"步数 9 超过上限 8"会直接告诉你是效率问题，不是能力问题。

---

## 十一、常见坑

1. **改了模块没重启**：Streamlit 的 `runOnSave` 只重跑 `main.py`，不会重新导入 `harness/*`。改预算、改工具后必须重启进程。
2. **流式工具参数是分片的**：必须按 `index` 拼接再 `json.loads`，否则拿到半截 JSON，工具会报"缺参数"。
3. **流式失败才回退非流式**：只有在"还没吐过 token"时才回退；已经吐了一半再回退，界面会重复。
4. **工具异常不能抛**：`registry.execute` 的设计就是"报错当内容回喂"，抛出去整轮就死了。
5. **`0` vs `None`**：`max_tokens=0` 是关闭检查，不是零预算；`max_cost_cny=0` 才是零预算。
6. **成本上限没接线**：不填单价、不传 `max_cost_cny`，这道预算等于不存在。
7. **相对路径**：`runs/`、`runs/evals/` 都是相对当前工作目录的。换目录启动，文件会写到别处。
8. **测试用的 FakeLLM** 只实现了 `invoke` / `bind_tools`，不要在里面偷偷加 `stream` 调用，否则 T1–T4 会误报。
9. **`agent_mode.loop._dispatch` 是兼容层**：测试还在用旧签名，改内部实现时别把它删了。
10. **评测集只有 14 条且是手写的**：它能防回归，不能证明"系统很好"。要证明质量，得靠更大的人工标注集。

---

## 十二、三个动手改的配方

### 配方 1：加一个工具

在 `agent_mode/tools.py` 里：

```python
def _get_dividend_impl(stock_code: str) -> str:
    # 真正实现；返回给模型读的字符串，失败也要返回说明
    ...

@tool
def get_dividend(stock_code: str) -> str:
    """查询该公司最近一次分红方案（每股派息、除权日）。"""
    return _get_dividend_impl(stock_code)

TOOL_SPECS.append(get_dividend)
TOOL_IMPLS["get_dividend"] = _get_dividend_impl
_TOOL_RUNTIME["get_dividend"] = dict(timeout_s=15.0, retries=1,
                                     cache_ttl_s=3600.0)
```

`register_tools()` 在模块底部自动执行；确保你改的是它**之前**的内容，或者手动再调一次。然后重启进程，用 `cache/agent_mode_check.py` 的 FakeLLM 模式验证轨迹。

### 配方 2：加一条评测用例

往 `harness/evals/suites/smoke.jsonl` 追加一行：

```json
{"id":"dividend-1","question":"600519 最近一次分红方案是什么？","stock_code":"600519",
 "must_call":["get_dividend"],"max_steps":5,"note":"新工具上线后的回归"}
```

```bash
python -m harness.evals.run --case dividend
```

先只跑这一条，确认断言写得合理（阈值太严会把正常波动判成失败）。

### 配方 3：从 trace 定位一次失败

```bash
# 1) 找到那一轮
tail -n 20 runs/index.jsonl

# 2) 打开对应轨迹
#    重点看 tool_end 的 result / elapsed_ms / cached / retries
cat runs/20261118/<run_id>.jsonl | grep tool_end

# 3) 确认是"工具没返回"还是"模型没用返回"
```

三种典型结论：

- `retries>0` 且 `result` 是超时文本 → 数据源慢，调超时或换工具
- `result` 有数据但答案没引用 → 提示词/上下文问题
- `result` 是"未知工具" → 工具没注册或名字拼错

---

## 十三、已知遗留

这些不是 bug，是还没做，按当前优先级列出来：

1. **成本上限没接线**：`max_cost_cny` 没有配置项、没有 CLI 参数；单价不填时 `cost_cny` 是 `None`。
2. **工作流没有轨迹**：`agent/` 走 LangGraph，没有 `Tracer`；结论溯源卡目前只覆盖「智能问答」页。
3. **评测集是手写的 14 条**：能防回归，不能证明系统质量；扩到 30–50 条并人工复核才有说服力。
4. **没有回放命令**：只能人读 JSONL，没有 `--replay` 把一轮重新跑一遍并 diff。
5. **trace 不带 prompt 版本哈希**：改 prompt 前后，只能靠时间戳区分。
6. **没有工具级次数上限**：同一轮里模型可能把同一个工具问三遍（实测问"能不能买"时检索了 3 次公告）。
7. **流式 usage 可能缺失**：部分厂商只在最后一块给用量，拿不到就是 0。
8. **界面上只看得到轨迹路径**：没有展开查看每一步耗时/缓存/原文的轨迹查看器。

---

## 十四、命令速查

| 目的 | 命令 |
|---|---|
| 跑一次 Agent（默认落轨迹） | `python -m agent_mode "600519 最近走势如何" --code 600519` |
| 不落轨迹 / 收紧预算 | `... --no-trace --max-steps 5 --max-seconds 60` |
| 跑评测全集 | `python -m harness.evals.run` |
| 只跑子集 | `... --case market --limit 3` |
| 看最近运行 | `tail -n 5 runs/index.jsonl` |
| 找预算触顶 | `grep '"stopped": "budget"' runs/index.jsonl` |
| 离线自检 | `python cache/harness_check.py` |
| 旧循环回归 | `python cache/agent_mode_check.py` |
| 溯源卡自检 | `python cache/trace_card_check.py` |

---

## 最后一句

> **harness 不产生业务结论，但它决定这些结论能不能被信任：数据有没有查到、钱有没有花超、出问题能不能回放、改完有没有变好。**
