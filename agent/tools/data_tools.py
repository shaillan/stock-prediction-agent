"""
LangChain Tool 定义 - 数据获取工具
LLM 可通过这些工具主动请求数据
"""
from langchain_core.tools import tool
from typing import Optional
import pandas as pd
from loguru import logger


def create_data_tools(akhare_client, cache_manager):
    """创建数据获取相关的 LangChain Tools"""

    @tool
    def get_kline_data(symbol: str, start_date: str, end_date: str = "") -> str:
        """获取A股日K线历史数据。

        Args:
            symbol: 股票代码，如 600519
            start_date: 起始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD（默认今天）

        Returns:
            最近60个交易日的K线数据JSON字符串
        """
        try:
            df = akhare_client.get_stock_kline(symbol, "daily", start_date, end_date)
            if df is not None and not df.empty:
                # 只返回最近60行以避免超长
                result = df.tail(60).to_dict(orient="records")
                return f"获取到 {len(result)} 条K线数据，最新一条: {result[-1] if result else '无'}"
            return f"未获取到 {symbol} 的K线数据"
        except Exception as e:
            return f"获取K线数据失败: {str(e)}"

    @tool
    def get_realtime_quote(symbol: str) -> str:
        """获取股票实时报价。

        Args:
            symbol: 股票代码

        Returns:
            实时行情JSON字符串
        """
        try:
            quote = akhare_client.get_realtime_quote(symbol)
            if quote:
                return (
                    f"股票: {quote.get('name', symbol)}\n"
                    f"最新价: {quote.get('price')}\n"
                    f"涨跌幅: {quote.get('change_pct')}%\n"
                    f"成交量: {quote.get('volume')}\n"
                    f"最高: {quote.get('high')}, 最低: {quote.get('low')}\n"
                    f"今开: {quote.get('open')}, 昨收: {quote.get('pre_close')}"
                )
            return f"未获取到 {symbol} 的实时行情"
        except Exception as e:
            return f"获取实时行情失败: {str(e)}"

    @tool
    def get_financial_data(symbol: str) -> str:
        """获取股票财务指标（PE、PB、ROE等）。

        Args:
            symbol: 股票代码

        Returns:
            财务指标JSON字符串
        """
        try:
            data = akhare_client.get_financial_indicators(symbol)
            if data:
                items = [f"- {k}: {v}" for k, v in data.items() if v is not None]
                return "财务指标:\n" + "\n".join(items) if items else "暂无财务数据"
            return f"未获取到 {symbol} 的财务数据"
        except Exception as e:
            return f"获取财务数据失败: {str(e)}"

    @tool
    def get_stock_name(symbol: str) -> str:
        """根据股票代码获取股票名称。

        Args:
            symbol: 股票代码

        Returns:
            股票名称
        """
        name = akhare_client.get_stock_name(symbol)
        return name if name else f"未找到代码 {symbol} 对应的股票"

    return [get_kline_data, get_realtime_quote, get_financial_data, get_stock_name]
