"""
股票代码注册表 - 用于股票搜索和自动补全
"""
from typing import List, Dict, Optional
from loguru import logger
from .cache_manager import CacheManager


class StockRegistry:
    """股票代码注册表，支持搜索和缓存"""

    # 内置常用 A 股股票列表
    COMMON_STOCKS = [
        {"code": "600519", "name": "贵州茅台", "market": "A"},
        {"code": "000858", "name": "五粮液", "market": "A"},
        {"code": "601318", "name": "中国平安", "market": "A"},
        {"code": "600036", "name": "招商银行", "market": "A"},
        {"code": "000333", "name": "美的集团", "market": "A"},
        {"code": "600276", "name": "恒瑞医药", "market": "A"},
        {"code": "002415", "name": "海康威视", "market": "A"},
        {"code": "600900", "name": "长江电力", "market": "A"},
        {"code": "601012", "name": "隆基绿能", "market": "A"},
        {"code": "300750", "name": "宁德时代", "market": "A"},
        {"code": "002594", "name": "比亚迪", "market": "A"},
        {"code": "601398", "name": "工商银行", "market": "A"},
        {"code": "000001", "name": "平安银行", "market": "A"},
        {"code": "600030", "name": "中信证券", "market": "A"},
        {"code": "601166", "name": "兴业银行", "market": "A"},
        {"code": "000651", "name": "格力电器", "market": "A"},
        {"code": "600887", "name": "伊利股份", "market": "A"},
        {"code": "601888", "name": "中国中免", "market": "A"},
        {"code": "300059", "name": "东方财富", "market": "A"},
        {"code": "002475", "name": "立讯精密", "market": "A"},
        {"code": "601899", "name": "紫金矿业", "market": "A"},
        {"code": "600809", "name": "山西汾酒", "market": "A"},
        {"code": "300015", "name": "爱尔眼科", "market": "A"},
        {"code": "002714", "name": "牧原股份", "market": "A"},
        {"code": "600031", "name": "三一重工", "market": "A"},
        {"code": "603259", "name": "药明康德", "market": "A"},
        {"code": "688981", "name": "中芯国际", "market": "A"},
        {"code": "000725", "name": "京东方A", "market": "A"},
        {"code": "300124", "name": "汇川技术", "market": "A"},
        {"code": "600585", "name": "海螺水泥", "market": "A"},
    ]

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()
        self._all_stocks: Optional[List[Dict]] = None

    def search(self, keyword: str, limit: int = 10) -> List[Dict]:
        """搜索股票代码或名称

        优先从缓存/内置列表搜索，如果关键词匹配不到，则尝试通过 AKShare 在线搜索
        """
        keyword = keyword.strip().lower() if keyword else ""

        if not keyword:
            return self.COMMON_STOCKS[:limit]

        results = []
        for stock in self.COMMON_STOCKS:
            if keyword in stock["code"] or keyword in stock["name"].lower() or \
               any(c in stock["name"].lower() for c in keyword):
                results.append(stock)

        # 如果内置列表没找到，尝试在线搜索
        if not results:
            results = self._online_search(keyword, limit)

        return results[:limit]

    def _online_search(self, keyword: str, limit: int = 10) -> List[Dict]:
        """通过 AKShare 在线搜索"""
        cache_key = f"stock_search_{keyword}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached[:limit]

        try:
            from .akhare_client import AKShareClient
            client = AKShareClient(cache_manager=self.cache)
            results = client.search_stock(keyword)

            # 缓存7天
            self.cache.set(cache_key, results, ttl=604800)
            return results[:limit]
        except Exception as e:
            logger.warning(f"在线搜索股票失败: {e}")
            return []

    def get_by_code(self, code: str) -> Optional[Dict]:
        """通过代码获取股票信息"""
        for stock in self.COMMON_STOCKS:
            if stock["code"] == code:
                return stock
        # 尝试在线查找
        results = self._online_search(code, limit=1)
        return results[0] if results else None

    def get_name(self, code: str) -> str:
        """通过代码获取股票名称"""
        stock = self.get_by_code(code)
        return stock["name"] if stock else ""
