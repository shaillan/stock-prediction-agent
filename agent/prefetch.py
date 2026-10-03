"""
预取数据共享模块 - 绕过 LangGraph msgpack 序列化限制
main.py 预取的 DataFrame 存入这里，data_collection_node 从这里读取
"""
from typing import Any, Dict, Optional
import pandas as pd

_pre_fetched: Dict[str, Any] = {}


def set_pre_fetched(kline_df=None, quote=None, stock_name=""):
    """main.py 调用，存入预取数据"""
    _pre_fetched["kline"] = kline_df
    _pre_fetched["quote"] = quote
    _pre_fetched["stock_name"] = stock_name


def get_pre_fetched_kline():
    """data_collection_node 调用，获取预取K线"""
    return _pre_fetched.get("kline")


def get_pre_fetched_quote():
    """data_collection_node 调用，获取预取行情"""
    return _pre_fetched.get("quote")


def get_pre_fetched_name():
    """获取预取股票名称"""
    return _pre_fetched.get("stock_name", "")


def clear():
    """清空缓存"""
    _pre_fetched.clear()
