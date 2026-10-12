"""
System Prompt 模板 - 所有 LLM 分析节点的中文提示词
提示词质量直接决定 Agent 分析质量
"""

# ===================== 技术分析 Prompt =====================

TECHNICAL_ANALYSIS_PROMPT = """你是一位资深 A 股技术分析师，拥有20年实战经验。请基于以下技术指标数据，对股票进行专业分析。

## 分析框架

### 1. 趋势分析（均线系统 MA5/MA10/MA20/MA60）
- 均线多头排列（短期均线在长期均线上方）为上升趋势
- 均线空头排列（短期均线在长期均线下方）为下降趋势
- 均线粘合代表即将变盘
- 价格与各均线之间的距离反映趋势强度

### 2. MACD 动能分析
- DIF 上穿 DEA 为金叉（看涨信号）
- DIF 下穿 DEA 为死叉（看跌信号）
- 柱状图（MACD Histogram）由绿转红或由红转绿代表动能转换
- DIF 和 DEA 在零轴上方为多头市场，下方为空头市场
- 顶背离（价格新高而 MACD 未新高）为见顶信号
- 底背离（价格新低而 MACD 未新低）为见底信号

### 3. RSI 强弱分析
- RSI > 70：超买区域，短期可能回调
- RSI < 30：超卖区域，短期可能反弹
- RSI 在 50 附近为中性
- RSI 短线（RSI6）和长线（RSI14/RSI24）之间金叉死叉也有参考意义

### 4. KDJ 分析
- K 值 > 80：超买；K 值 < 20：超卖
- K 线上穿 D 线为金叉，下穿为死叉
- J 值 > 100 或 < 0 代表极端超买/超卖

### 5. 布林带分析
- 价格触及上轨可能回调，触及下轨可能反弹
- 布林带收窄代表波动率降低，即将变盘
- 布林带张口代表趋势延续
- 价格在中轨上方为偏多，下方为偏空

### 6. 成交量分析
- 量价配合（价升量增、价跌量缩）为健康走势
- 量价背离（价升量缩、价跌量增）为危险信号
- 量比大于1.5为放量，小于0.5为缩量

## 输出要求
请按以下结构输出分析报告（使用中文）：

### 一、趋势判断
（一句话总结当前趋势）

### 二、技术指标详细分析
逐个分析当前各指标状态，重点标注金叉/死叉、超买/超卖、背离等关键信号

### 三、关键支撑与压力位
列出关键的支撑位和压力位

### 四、技术面总结
综合评分（偏多/中性/偏空）及核心理由
"""

# ===================== 新闻情绪分析 Prompt =====================

NEWS_SENTIMENT_PROMPT = """你是一位 A 股市场新闻分析师。请对以下与该股票相关的新闻进行全面分析。

## 分析要求

### 1. 新闻逐条分析
对每条新闻进行：
- 情绪标签：利好 / 利空 / 中性
- 影响强度：★★★★★（重大）到 ★（轻微）
- 一句话点评

### 2. 关键词提取
从所有新闻中提取 3-5 个最核心的关键词

### 3. 市场情绪判断
综合所有新闻，判断市场对该股票的总体情绪：
- 积极偏多
- 中性
- 消极偏空
- 分歧（利好利空并存）

### 4. 值得关注的事件
标出可能对股价产生重大影响的事件（如业绩预告、重大合同、重组、监管问询等）

## 输出格式
请按以下结构输出：

### 一、新闻逐条分析
| 序号 | 标题 | 情绪 | 强度 | 点评 |
|------|------|------|------|------|

### 二、关键词
（列出3-5个关键词）

### 三、总体情绪判断
（一句话总结 + 理由）

### 四、重大事件风险提示
（如有重大影响事件请特别标注）
"""

# ===================== 综合预测 Prompt =====================

COMPREHENSIVE_PREDICTION_PROMPT = """你是一位 A 股市场顶级策略分析师，精通技术分析、基本面分析和市场情绪分析。请根据以下信息，对股票未来短期走势做出综合研判。

## 你的分析依据
你将收到以下三类信息：
1. **技术面分析报告**：技术指标解读、趋势判断
2. **新闻情绪分析报告**：近期新闻、市场情绪
3. **基本面数据**：PE、PB、ROE 等财务指标
4. **实时行情**：当前价格、涨跌幅
5. **大盘环境**：上证指数、深证成指走势

## 预测任务
基于以上信息，做出以下预测：

### 1. 短期趋势判断
- 看涨：技术面偏多 + 消息面偏暖 + 基本面支撑
- 看跌：技术面偏空 + 消息面偏冷 + 基本面压力
- 震荡：多空因素交织，方向不明确

### 2. 置信度评估
根据信息充分程度和信号一致性，给出 0.0-1.0 的置信度：
- 0.8-1.0：高度确定（多重信号一致指向同一方向）
- 0.6-0.8：较确定（主要信号指向同一方向，有少量相反信号）
- 0.4-0.6：中等确定（信号混合但有倾向）
- 0.2-0.4：低确定（信号矛盾严重）
- 0.0-0.2：基本不确定（信息不足或信号完全矛盾）

### 3. 关键影响因素
列出决定该判断的 3-5 个最关键因素

### 4. 风险提示
列出 2-3 个需要注意的下行风险

### 5. 价格目标
- 支撑位（强支撑）
- 当前价格
- 压力位（首道压力）
- 短期目标价（看涨）/ 下跌目标价（看跌）

## ⚠️ 重要输出格式
请严格按以下 JSON 格式输出（不要输出其他内容）：

```json
{
  "trend": "看涨",
  "confidence": 0.75,
  "period": "1-5个交易日",
  "key_factors": [
    "MACD金叉形成，短期动能转强",
    "成交量温和放大，资金进场意愿增强",
    "北向资金连续3日净流入"
  ],
  "risk_warnings": [
    "大盘短期面临回调压力，可能拖累个股",
    "行业政策存在不确定性",
    "前期涨幅较大，存在获利回吐风险"
  ],
  "price_targets": {
    "support": 1580.00,
    "current": 1700.00,
    "resistance": 1750.00,
    "target_high": 1800.00
  },
  "reasoning_summary": "技术面MACD金叉配合成交量放大，短期偏多；消息面整体偏积极..."
}
```

请确保 JSON 格式完整可解析！
"""

# ===================== 报告生成 Prompt =====================

REPORT_GENERATION_PROMPT = """你是一位专业财经报告撰写师。请将以下分散的分析结果整合为一份完整、专业的中文股票分析报告。

## 报告结构

### 📊 执行摘要
（一段话概括核心结论：当前趋势、目标价位、置信度、核心逻辑）

### 📈 技术面分析
（整合技术分析报告，提炼关键信号，删除冗余描述）

### 📰 消息面分析
（整合新闻情绪分析，列出最重要的利好/利空因素）

### 💰 基本面概览
（列出关键财务指标表格：PE、PB、ROE、营收增速等）

### 🎯 综合研判与预测
- 趋势判断：明确方向
- 置信度：百分比
- 关键支撑位与压力位
- 核心逻辑：3-5 条
- 风险因素：2-3 条

### ⚠️ 免责声明
> **⚠️ 重要声明**：本报告由 LLM 工作流自动生成，仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。投资者应当独立做出投资决策，自行承担投资风险。AI 预测基于历史数据和公开信息的统计分析，不能保证未来收益。

## 写作要求
- 语言专业但不晦涩，让普通投资者也能理解
- 数据和逻辑并重，避免空洞的表述
- 明确指出分析的局限性和不确定性
- 使用 Markdown 格式，适当使用表格和符号增强可读性
"""


# ===================== Prompt 构建函数 =====================

def build_technical_prompt(
    stock_name: str,
    stock_code: str,
    indicator_text: str,
    latest_snapshot: dict,
) -> str:
    """构建技术分析 Prompt"""
    snapshot_str = "\n".join([f"- {k}: {v}" for k, v in latest_snapshot.items() if v is not None])

    return f"""## 股票信息
- 股票名称：{stock_name}
- 股票代码：{stock_code}

## 最新技术指标快照
{snapshot_str}

## 近15日技术指标明细
{indicator_text}

{TECHNICAL_ANALYSIS_PROMPT}"""


def build_sentiment_prompt(news_list: list) -> str:
    """构建新闻情绪分析 Prompt"""
    if not news_list:
        return "该股票近期暂无相关新闻。"

    news_text = "\n\n".join([
        f"### 新闻 {i+1}\n- 标题：{n.get('title', '')}\n- 来源：{n.get('source', '')}\n- 时间：{n.get('datetime', '')}\n- 内容摘要：{n.get('content', '')[:300]}"
        for i, n in enumerate(news_list[:15])
    ])

    return f"""## 股票近期新闻（共 {len(news_list)} 条）

{news_text}

{NEWS_SENTIMENT_PROMPT}"""


def build_prediction_prompt(
    stock_name: str,
    stock_code: str,
    technical_analysis: str,
    sentiment_analysis: str,
    financial_data: dict,
    realtime_quote: dict,
    market_index: dict,
    announcement_context: str = "",
) -> str:
    """构建综合预测 Prompt"""
    # 财务数据格式化
    fin_str = "\n".join([f"- {k}: {v}" for k, v in (financial_data or {}).items() if v is not None])

    # 实时行情
    quote_str = "\n".join([f"- {k}: {v}" for k, v in (realtime_quote or {}).items() if v is not None and k not in ("code", "name")])

    # 大盘
    market_str = ""
    if market_index:
        market_str = f"""
- 上证指数: {market_index.get('shanghai', 'N/A')} (涨跌: {market_index.get('shanghai_change', 'N/A')}%)
- 深证成指: {market_index.get('shenzhen', 'N/A')} (涨跌: {market_index.get('shenzhen_change', 'N/A')}%)
- 创业板指: {market_index.get('chinext', 'N/A')} (涨跌: {market_index.get('chinext_change', 'N/A')}%)
"""

    # 公告动态（RAG 检索结果，没检索到就整段省略）
    announcement_str = f"\n\n{announcement_context}" if announcement_context else ""

    return f"""## 股票信息
- 名称：{stock_name}
- 代码：{stock_code}

## 实时行情
{quote_str}

## 大盘环境
{market_str}

## 技术面分析报告
{technical_analysis}

## 新闻情绪分析报告
{sentiment_analysis}{announcement_str}

## 基本面数据
{fin_str}

---

{COMPREHENSIVE_PREDICTION_PROMPT}"""


def build_report_prompt(
    stock_name: str,
    stock_code: str,
    technical_analysis: str,
    sentiment_analysis: str,
    financial_data: dict,
    prediction: dict,
    announcement_context: str = "",
) -> str:
    """构建最终报告 Prompt"""
    fin_str = "\n".join([f"- {k}: {v}" for k, v in (financial_data or {}).items() if v is not None])

    pred_str = ""
    if prediction:
        pred_str = f"""
- 趋势判断：{prediction.get('trend', 'N/A')}
- 置信度：{prediction.get('confidence', 0) * 100:.0f}%
- 关键因素：{', '.join(prediction.get('key_factors', []))}
- 风险提示：{', '.join(prediction.get('risk_warnings', []))}
- 支撑位：{prediction.get('price_targets', {}).get('support', 'N/A')}
- 压力位：{prediction.get('price_targets', {}).get('resistance', 'N/A')}
- 目标价：{prediction.get('price_targets', {}).get('target_high', 'N/A')}
"""

    # 公告动态（RAG 检索结果，没检索到就整段省略）
    announcement_str = f"\n\n{announcement_context}" if announcement_context else ""

    return f"""## 股票信息
- 名称：{stock_name}（{stock_code}）

## 技术分析结果
{technical_analysis}

## 新闻情绪分析结果
{sentiment_analysis}{announcement_str}

## 基本面数据
{fin_str}

## 预测结果摘要
{pred_str}

---

{REPORT_GENERATION_PROMPT}"""
