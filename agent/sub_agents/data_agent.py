"""
子 Agent: 数据采集
获取 K线、实时行情、财务指标、新闻、大盘指数
纯代码执行，不调用 LLM
"""
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
from loguru import logger

from langgraph.graph import StateGraph, END

from ..state import AgentState, DataAgentInput, DataAgentOutput
from ..prefetch import get_pre_fetched_kline, get_pre_fetched_quote, get_pre_fetched_name
from data.akhare_client import AKShareClient
from data.cache_manager import CacheManager


def _collect_data(state: AgentState) -> Dict[str, Any]:
    """数据采集主逻辑"""
    logger.info(f"📡 [DataAgent] 开始数据采集: {state.get('stock_code')}")

    cache = CacheManager()
    client = AKShareClient(cache_manager=cache)

    stock_code = state["stock_code"]
    start_date = state.get("start_date", "")
    end_date = state.get("end_date", "")

    # 只收集本次新增的错误。state 的 errors 带 add reducer，会自动与已有列表拼接；
    # 这里若把 state["errors"] 抄进来一起返回，并行执行时会被 reducer 重复叠加。
    errors: list = []

    result = {
        "status": "collecting",
        "stock_name": state.get("stock_name", "") or get_pre_fetched_name(),
    }

    # 复用 main.py 预取数据
    pre_fetched_kline = get_pre_fetched_kline()
    pre_fetched_quote = get_pre_fetched_quote()

    if pre_fetched_kline is not None:
        result["kline_data"] = pre_fetched_kline
        logger.info(f"  ✅ K线数据(复用): {len(pre_fetched_kline)} 条")
    if pre_fetched_quote is not None:
        result["realtime_quote"] = pre_fetched_quote
        logger.info(f"  ✅ 实时行情(复用): {pre_fetched_quote.get('price')}")

    need_kline = pre_fetched_kline is None
    need_name = not result["stock_name"]

    if need_name:
        stock_name = client.get_stock_name(stock_code)
        if stock_name:
            result["stock_name"] = stock_name

    if not need_kline and not need_name:
        logger.info("  K线和行情已预取，仅补充财务+新闻")
        _fetch_remaining(client, stock_code, result, errors)
    elif need_kline:
        _fetch_all(client, stock_code, start_date, end_date, result, errors)

    # 大盘指数（非阻塞，但失败要如实记录 —— 否则报告缺一块市场环境却毫无提示）
    try:
        result["market_index"] = client.get_market_index()
        if result["market_index"]:
            logger.info("  ✅ 大盘指数")
        else:
            logger.warning("  ⚠️ 大盘指数返回为空")
            errors.append("大盘指数返回为空，报告将缺少市场环境参考")
    except Exception as e:
        logger.warning(f"  ⚠️ 大盘指数获取失败（非致命）: {e}")
        errors.append(f"大盘指数获取失败，报告将缺少市场环境参考（{type(e).__name__}）")

    if result.get("kline_data") is None or (
        hasattr(result["kline_data"], "empty") and result["kline_data"].empty
    ):
        errors.append(f"未能获取股票 {stock_code} 的K线数据，请检查股票代码")

    result["errors"] = errors
    logger.info(f"📡 [DataAgent] 完成，共 {len(errors)} 个错误")
    return result


def _fetch_remaining(client, stock_code, result, errors):
    """仅获取财务和新闻"""
    from config import settings
    import time as _time

    executor = ThreadPoolExecutor(max_workers=2)
    try:
        f_finance = executor.submit(client.get_financial_indicators, stock_code)
        _time.sleep(0.3)
        f_news = executor.submit(client.get_stock_news, stock_code, settings.max_news_items)

        # 记下每个 future 对应的（中文名, 结果字段），失败/超时时才能说清是谁失败了
        name_map = {f_finance: ("财务数据", "financial_data"), f_news: ("新闻", "news_data")}

        done, not_done = wait(
            {f_finance, f_news},
            timeout=settings.data_fetch_timeout + 5,
            return_when=ALL_COMPLETED,
        )
        for future in done:
            label, key = name_map[future]
            try:
                val = future.result(timeout=5)
                result[key] = val
                if key == "news_data":
                    logger.info(f"  ✅ {label}: {len(val) if val else 0} 条")
                else:
                    logger.info(f"  ✅ {label}: {'有数据' if val else '暂无'}")
            except Exception as e:
                logger.error(f"  ❌ {label}获取失败: {e}")
                errors.append(f"{label}获取失败（{type(e).__name__}）")

        for future in not_done:
            label, _ = name_map[future]
            logger.warning(f"  ⚠️ {label}超时跳过")
            errors.append(f"{label}获取超时，报告可能缺少相应内容")
    finally:
        executor.shutdown(wait=False)


def _fetch_all(client, stock_code, start_date, end_date, result, errors):
    """完整获取所有数据"""
    from config import settings
    import time as _time

    executor = ThreadPoolExecutor(max_workers=3)
    try:
        f_kline = executor.submit(
            client.get_stock_kline, stock_code, "daily", start_date, end_date
        )
        _time.sleep(0.3)
        f_finance = executor.submit(client.get_financial_indicators, stock_code)
        _time.sleep(0.3)
        f_news = executor.submit(
            client.get_stock_news, stock_code, settings.max_news_items
        )

        all_futures = {f_kline, f_finance, f_news}
        name_map = {f_kline: "kline", f_finance: "finance", f_news: "news"}

        done, not_done = wait(all_futures, timeout=settings.data_fetch_timeout + 5)

        for future in done:
            name = name_map[future]
            try:
                val = future.result(timeout=5)
                if name == "kline":
                    result["kline_data"] = val
                    logger.info(f"  ✅ K线数据: {len(val) if val is not None else 0} 条")
                elif name == "finance":
                    result["financial_data"] = val
                    logger.info(f"  ✅ 财务数据: {'有数据' if val else '暂无'}")
                elif name == "news":
                    result["news_data"] = val
                    logger.info(f"  ✅ 新闻: {len(val) if val else 0} 条")
            except Exception as e:
                logger.error(f"  ❌ {name} 获取失败: {e}")
                errors.append(f"获取{name}失败: {str(e)}")

        for future in not_done:
            logger.warning(f"  ⚠️ {name_map[future]} 超时跳过")
            errors.append(f"{name_map[future]}获取超时，报告可能缺少相应内容")
    finally:
        executor.shutdown(wait=False)

    kline_df = result.get("kline_data")
    if kline_df is not None and not (hasattr(kline_df, "empty") and kline_df.empty):
        quote = client.get_realtime_quote(stock_code, kline_df=kline_df)
        result["realtime_quote"] = quote
        logger.info(f"  ✅ 实时行情(从K线): {quote.get('price') if quote else 'N/A'}")


def build_data_agent() -> StateGraph:
    """构建数据采集子 Agent

    input/output 契约见 AgentState 下方注释：只回传自己产出的键，
    这样并行执行时不会和其它分支争抢同一个状态字段。
    """
    workflow = StateGraph(AgentState, input=DataAgentInput, output=DataAgentOutput)
    workflow.add_node("collect", _collect_data)
    workflow.set_entry_point("collect")
    workflow.add_edge("collect", END)
    return workflow.compile()
