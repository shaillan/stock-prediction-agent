# -*- coding: utf-8 -*-
"""
自选股简报 —— 把「今天发生了什么」翻译成大白话

产品定位：卖的是**解读**，不是预测。所以这里严格不输出买/卖/目标价/仓位：
国内向不特定对象有偿提供证券投资建议需要牌照，而资讯/工具类产品不需要。
这条边界同时写在两处——prompt 里的硬性要求，和产品文案里的免责声明。

缓存：同一（日期, 股票）只生成一次。用户反复刷新页面不重复花钱，
这是这类订阅产品的单位经济能成立的前提。
"""
import json
import os
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger


def _cache_path(code: str) -> Path:
    root = Path(__file__).resolve().parent.parent
    return root / "cache" / "briefings" / f"{date.today():%Y%m%d}_{code}.json"


def _quote_line(quote: Optional[Dict], df=None) -> str:
    """把行情压成一行给 LLM 读；取不到就明说，不编数字"""
    if not quote:
        return "未获取到行情数据"
    parts = [f"最新收盘 {quote.get('price')} 元",
             f"今日 {quote.get('change_pct', 0):+.2f}%"]
    if df is not None and len(df) > 5:
        try:
            closes = [float(x) for x in df["close"].tolist()]
            chg5 = (closes[-1] / closes[-6] - 1) * 100
            parts.append(f"近5日 {chg5:+.2f}%")
            vols = [float(x) for x in df["volume"].tolist()]
            base = sum(vols[-6:-1]) / 5
            if base > 0:
                parts.append(f"成交量是近5日均值的 {vols[-1] / base:.1f} 倍")
        except Exception:
            pass
    return "，".join(parts)


def collect_events(code: str, name: str = "", news_limit: int = 6,
                   ann_days: int = 90, ann_limit: int = 8) -> Dict:
    """取三路素材：行情 / 新闻 / 公告标题。

    每一路失败都单独记进 errors，互不拖垮——和主流程的「缺口诚实」一致：
    缺了新闻就写「未获取到」，而不是假装今天没新闻。
    """
    from data.akhare_client import AKShareClient
    from datetime import timedelta

    client = AKShareClient()
    events: Dict = {
        "code": code, "name": name, "date": str(date.today()),
        "quote": None, "quote_line": "", "news": [], "announcements": [],
        "errors": [],
    }

    df = None
    try:
        end = date.today()
        start = end - timedelta(days=40)
        df = client.get_stock_kline(code, "daily",
                                    start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        if df is not None and not df.empty:
            events["quote"] = client.get_realtime_quote(code, kline_df=df)
    except Exception as e:
        events["errors"].append(f"行情获取失败: {str(e)[:150]}")
    events["quote_line"] = _quote_line(events["quote"], df)

    try:
        news = client.get_stock_news(code, limit=news_limit)
        # 东财是按关键词捞的，可能捞到一堆"顺带提到"的别家新闻。
        # 先按「标题里有没有本公司名」排序，让真正相关的排前面——不删，
        # 因为行业新闻对判断也有价值，只是不该占满篇幅。
        if name:
            news.sort(key=lambda n: name not in (n.get("title") or ""))
        events["news"] = news
    except Exception as e:
        events["errors"].append(f"新闻获取失败: {str(e)[:150]}")

    try:
        from rag.fetch import fetch_announcement_list
        events["announcements"] = fetch_announcement_list(
            code, days=ann_days, limit=ann_limit
        )
    except Exception as e:
        events["errors"].append(f"公告获取失败: {str(e)[:150]}")

    return events


_PROMPT = """你是「自选股简报」的撰稿人。读者是**看不懂专业术语的普通股民**。

股票：{name}（{code}）
行情：{quote_line}

近期新闻：
{news_text}

近期公告（可能不是今天的，注意看日期；没有新的就明确说"最近没有新公告"）：
{ann_text}

请输出 Markdown，严格按下面结构：

## {name}（{code}）

**一句话**：用一句大白话说清今天最值得知道的事；没有就写"今天比较平静"。

**发生了什么**
- 最多 3 条，每条 = 事实 + 一句白话解释（"这意味着……"）

**值得留意**
- 最多 2 条，只写之后可能影响股价的**具体事件或时间点**（财报日、解禁、股东大会等）

硬性要求：
1. **绝对不要**出现"买入/卖出/加仓/减仓/目标价/建议持有"这类字眼，也不要暗示该不该买
2. 数字只能来自上面素材，不要自己编；素材没有的写"未获取到"
3. 术语第一次出现时用括号解释，例如"量比（当天成交活跃度，1 以上算活跃）"
4. 全文不超过 350 字
5. 素材确实没什么可说时，诚实写"今天没有需要特别关注的消息"，不要凑字数"""


def _format_news(news: List[Dict]) -> str:
    if not news:
        return "（未获取到新闻）"
    return "\n".join(
        f"- [{n.get('datetime', '')[:16]}][{n.get('source', '')}] {n.get('title', '')}"
        for n in news
    )


def _format_ann(anns: List[Dict]) -> str:
    if not anns:
        return "（近 90 天没有公告）"
    return "\n".join(f"- [{a.get('date', '')}] {a.get('title', '')}" for a in anns)


def build_briefing(code: str, name: str = "", llm=None, force: bool = False) -> Dict:
    """生成一只股票当天的简报。命中当日缓存直接返回，不重复调用 LLM。

    Args:
        llm: BaseChatModel；不传则按 config 创建（CLI 场景）
        force: 忽略缓存重新生成
    """
    cache = _cache_path(code)
    if not force and cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            data["cached"] = True
            return data
        except (json.JSONDecodeError, OSError):
            pass

    events = collect_events(code, name)
    digest, error = "", None

    has_material = bool(events["quote"] or events["news"] or events["announcements"])
    if not has_material:
        error = "没有取到任何素材（行情/新闻/公告均失败），无法生成简报"
    else:
        try:
            if llm is None:
                from utils.llm_factory import create_chat_model
                llm = create_chat_model(temperature=0.3, max_tokens=1200)
            prompt = _PROMPT.format(
                name=events["name"] or code, code=code,
                quote_line=events["quote_line"],
                news_text=_format_news(events["news"]),
                ann_text=_format_ann(events["announcements"]),
            )
            resp = llm.invoke(prompt)
            digest = resp.content if hasattr(resp, "content") else str(resp)
            if not isinstance(digest, str):
                digest = str(digest)
        except Exception as e:
            logger.error(f"简报生成失败 {code}: {e}")
            error = f"解读生成失败: {str(e)[:200]}"

    result = {**events, "digest": digest, "error": error, "cached": False}
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        os.replace(tmp, cache)
    except OSError as e:
        logger.warning(f"简报缓存写入失败: {e}")
    return result
