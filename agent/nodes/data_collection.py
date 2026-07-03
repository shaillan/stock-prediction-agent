"""
节点1: 数据采集
获取 K线、实时行情、财务指标、新闻、大盘指数
此节点不调用 LLM，纯数据获取
"""
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

from ..state import AgentState
from data.akhare_client import AKShareClient
from data.cache_manager import CacheManager


def data_collection_node(state: AgentState) -> Dict[str, Any]:
    """数据采集节点 - 并行获取所有数据源"""
    logger.info(f"📡 开始数据采集: {state.get('stock_code')}")

    cache = CacheManager()
    client = AKShareClient(cache_manager=cache)

    result = {
        "status": "collecting",
        "errors": state.get("errors", []),
    }

    stock_code = state["stock_code"]
    start_date = state.get("start_date", "")
    end_date = state.get("end_date", "")

    # 获取股票名称
    stock_name = client.get_stock_name(stock_code)
    if not stock_name:
        stock_name = state.get("stock_name", "")
    result["stock_name"] = stock_name

    import time as _time
    from config import settings

    # 并行获取数据（减少并发数 + 错开请求，避免被上游限流）
    tasks = {}

    with ThreadPoolExecutor(max_workers=2) as executor:
        # K线数据
        tasks["kline"] = executor.submit(
            client.get_stock_kline, stock_code, "daily", start_date, end_date
        )
        _time.sleep(0.3)

        # 财务数据
        tasks["finance"] = executor.submit(client.get_financial_indicators, stock_code)
        _time.sleep(0.3)

        # 新闻
        tasks["news"] = executor.submit(
            client.get_stock_news, stock_code, settings.max_news_items
        )

        # 收集结果
        for name, future in as_completed(tasks):
            try:
                value = future.result(timeout=settings.data_fetch_timeout)
                if name == "kline":
                    result["kline_data"] = value
                    logger.info(f"  ✅ K线数据: {len(value) if value is not None else 0} 条")
                elif name == "finance":
                    result["financial_data"] = value
                    logger.info(f"  ✅ 财务数据: {'有数据' if value else '暂无'}")
                elif name == "news":
                    result["news_data"] = value
                    logger.info(f"  ✅ 新闻: {len(value) if value else 0} 条")
            except Exception as e:
                logger.error(f"  ❌ {name} 获取失败: {e}")
                result["errors"].append(f"获取{name}失败: {str(e)}")

    # 从K线提取实时行情（无需额外调API）
    kline_df = result.get("kline_data")
    if kline_df is not None and not (hasattr(kline_df, "empty") and kline_df.empty):
        quote = client.get_realtime_quote(stock_code, kline_df=kline_df)
        result["realtime_quote"] = quote
        logger.info(f"  ✅ 实时行情(从K线): {quote.get('price') if quote else 'N/A'}")
    else:
        logger.warning("  ⚠️ 无K线数据，跳过实时行情")

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
