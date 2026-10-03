"""
节点1: 数据采集
获取 K线、实时行情、财务指标、新闻、大盘指数
优先使用 main.py 预取的数据，避免重复调用 AKShare
"""
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
from loguru import logger

from ..state import AgentState
from ..prefetch import get_pre_fetched_kline, get_pre_fetched_quote, get_pre_fetched_name
from data.akhare_client import AKShareClient
from data.cache_manager import CacheManager


def data_collection_node(state: AgentState) -> Dict[str, Any]:
    """数据采集节点 - 优先使用已有数据，仅增量获取缺失部分"""
    logger.info(f"📡 开始数据采集: {state.get('stock_code')}")

    cache = CacheManager()
    client = AKShareClient(cache_manager=cache)

    stock_code = state["stock_code"]
    start_date = state.get("start_date", "")
    end_date = state.get("end_date", "")

    result = {
        "status": "collecting",
        "errors": state.get("errors", []),
        "stock_name": state.get("stock_name", "") or get_pre_fetched_name(),
    }

    # 如果 main.py 已经预取了数据，直接复用（通过模块级变量，绕过 msgpack 序列化）
    pre_fetched_kline = get_pre_fetched_kline()
    pre_fetched_quote = get_pre_fetched_quote()

    if pre_fetched_kline is not None:
        result["kline_data"] = pre_fetched_kline
        logger.info(f"  ✅ K线数据(复用): {len(pre_fetched_kline)} 条")
    if pre_fetched_quote is not None:
        result["realtime_quote"] = pre_fetched_quote
        logger.info(f"  ✅ 实时行情(复用): {pre_fetched_quote.get('price')}")

    # 仅获取预取没有的数据
    need_kline = pre_fetched_kline is None
    need_name = not result["stock_name"]

    if need_name:
        stock_name = client.get_stock_name(stock_code)
        if stock_name:
            result["stock_name"] = stock_name

    if not need_kline and not need_name:
        # 只需要补充财务和新闻
        logger.info("  K线和行情已预取，仅补充财务+新闻")
        _fetch_remaining(client, stock_code, result)
    elif need_kline:
        # 完整获取
        _fetch_all(client, stock_code, start_date, end_date, result)

    # 大盘指数（失败不阻塞）
    try:
        result["market_index"] = client.get_market_index()
        if result["market_index"]:
            logger.info("  ✅ 大盘指数")
    except Exception as e:
        logger.warning(f"  ⚠️ 大盘指数获取失败（非致命）: {e}")

    # 检查关键数据
    if result.get("kline_data") is None or (
        hasattr(result["kline_data"], "empty") and result["kline_data"].empty
    ):
        result["errors"].append(f"未能获取股票 {stock_code} 的K线数据，请检查股票代码")

    logger.info(f"📡 数据采集完成，共 {len(result.get('errors', []))} 个错误")
    return result


def _fetch_remaining(client, stock_code, result):
    """仅获取财务和新闻（K线已预取）"""
    from config import settings
    import time as _time

    executor = ThreadPoolExecutor(max_workers=2)
    try:
        f_finance = executor.submit(client.get_financial_indicators, stock_code)
        _time.sleep(0.3)
        f_news = executor.submit(client.get_stock_news, stock_code, settings.max_news_items)

        done, not_done = wait(
            {f_finance, f_news},
            timeout=settings.data_fetch_timeout + 5,
            return_when=ALL_COMPLETED,  # 等两个都完成或超时，避免丢弃数据
        )
        # 收集已完成的结果
        for future in done:
            try:
                val = future.result(timeout=5)
                if future == f_finance:
                    result["financial_data"] = val
                    logger.info(f"  ✅ 财务数据: {'有数据' if val else '暂无'}")
                elif future == f_news:
                    result["news_data"] = val
                    logger.info(f"  ✅ 新闻: {len(val) if val else 0} 条")
            except Exception as e:
                logger.error(f"  ❌ 获取失败: {e}")

        # 超时未完成的，忽略（不阻塞流水线）
        for future in not_done:
            logger.warning(f"  ⚠️ 任务超时跳过")
    finally:
        executor.shutdown(wait=False)  # 不等待卡死的线程


def _fetch_all(client, stock_code, start_date, end_date, result):
    """完整获取所有数据"""
    from config import settings
    import time as _time

    executor = ThreadPoolExecutor(max_workers=3)  # 3 个任务，3 个 worker 同时跑
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

        # 使用 wait + timeout 防止无限等待
        all_futures = {f_kline, f_finance, f_news}
        name_map = {f_kline: "kline", f_finance: "finance", f_news: "news"}
        deadline = settings.data_fetch_timeout + 5

        done, not_done = wait(all_futures, timeout=deadline)

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
                result["errors"].append(f"获取{name}失败: {str(e)}")

        for future in not_done:
            logger.warning(f"  ⚠️ {name_map[future]} 超时跳过")
    finally:
        executor.shutdown(wait=False)  # 不等待卡死的线程

    # 从K线提取实时行情
    kline_df = result.get("kline_data")
    if kline_df is not None and not (hasattr(kline_df, "empty") and kline_df.empty):
        quote = client.get_realtime_quote(stock_code, kline_df=kline_df)
        result["realtime_quote"] = quote
        logger.info(f"  ✅ 实时行情(从K线): {quote.get('price') if quote else 'N/A'}")
