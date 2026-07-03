"""
AKShare 数据获取客户端 - 封装所有 A 股数据接口
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .cache_manager import CacheManager
from .models import KlineData, RealtimeQuote, FinancialData, NewsItem


class AKShareClient:
    """AKShare 数据获取封装，带缓存和重试"""

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()

    # ===================== K线数据 =====================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    )
    def get_stock_kline(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "",
        end_date: str = "",
    ) -> pd.DataFrame:
        """
        获取 A 股历史 K 线数据

        Args:
            symbol: 股票代码，如 "600519"
            period: K线周期 "daily" / "weekly" / "monthly"
            start_date: 起始日期 "YYYYMMDD" 或 "YYYY-MM-DD"
            end_date: 结束日期

        Returns:
            DataFrame 包含列: date, open, high, low, close, volume, amount, amplitude, change_pct, turnover
        """
        start_date = start_date.replace("-", "")
        end_date = end_date.replace("-", "")

        cache_key = f"kline_{symbol}_{period}_{start_date}_{end_date}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        logger.info(f"获取K线数据: {symbol}, period={period}, {start_date}~{end_date}")
        import akshare as ak

        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",  # 前复权
            )
        except Exception as e:
            # 尝试不带 adjust 参数
            logger.warning(f"前复权获取失败，尝试默认方式: {e}")
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
            )

        if df is None or df.empty:
            raise ValueError(f"未找到股票代码 {symbol} 的K线数据，请检查代码是否正确")

        # 标准化列名
        df = self._normalize_kline_columns(df)

        # 缓存
        from config import settings
        self.cache.set(cache_key, df.to_dict(orient="records"), ttl=settings.kline_cache_ttl)

        return df

    def _normalize_kline_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """将 AKShare 返回的列名标准化为英文"""
        column_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "涨跌幅": "change_pct",
            "涨跌额": "change_amount",
            "换手率": "turnover",
        }
        df = df.rename(columns=column_map)
        # 确保数值类型
        for col in ["open", "close", "high", "low", "volume", "amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    # ===================== 实时行情 =====================

    def get_realtime_quote(self, symbol: str, kline_df: "pd.DataFrame | None" = None) -> Optional[Dict]:
        """获取实时行情（从K线末行提取，避免调重量级全市场接口）

        Args:
            symbol: 股票代码
            kline_df: 可选，已有的K线DataFrame，从中直接提取最新行情
        """
        cache_key = f"quote_{symbol}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        logger.info(f"获取实时行情: {symbol}")

        # 1. 如果有K线数据，直接从末尾提取
        if kline_df is not None and not kline_df.empty:
            return self._extract_quote_from_kline(symbol, kline_df)

        # 2. 否则只拉最近2天K线来推算
        try:
            df = self.get_stock_kline(symbol, "daily",
                                       (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
                                       datetime.now().strftime("%Y-%m-%d"))
            if df is not None and len(df) >= 1:
                return self._extract_quote_from_kline(symbol, df)
        except Exception:
            pass

        return None

    def _extract_quote_from_kline(self, symbol: str, df: "pd.DataFrame") -> Dict:
        """从K线DataFrame提取最新行情快照"""
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last

        price = float(last.get("close", 0))
        pre_close = float(prev.get("close", price))
        change_pct = ((price - pre_close) / pre_close * 100) if pre_close != 0 else 0.0

        name = str(last.get("name", "")) if "name" in df.columns else self.get_stock_name(symbol)

        quote = {
            "code": symbol,
            "name": name,
            "price": price,
            "change_pct": round(change_pct, 2),
            "change_amount": round(price - pre_close, 2),
            "volume": float(last.get("volume", 0)),
            "amount": float(last.get("amount", 0)) if "amount" in df.columns else None,
            "high": float(last.get("high", 0)),
            "low": float(last.get("low", 0)),
            "open": float(last.get("open", 0)),
            "pre_close": pre_close,
            "turnover": float(last.get("turnover", 0)) if "turnover" in df.columns else None,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        from config import settings
        self.cache.set(f"quote_{symbol}", quote, ttl=settings.realtime_quote_ttl)
        return quote

    # ===================== 财务数据 =====================

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
    def get_financial_indicators(self, symbol: str) -> Optional[Dict]:
        """获取财务指标（自动回退到备用接口）"""
        cache_key = f"finance_{symbol}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        logger.info(f"获取财务指标: {symbol}")
        financial = self._try_financial_primary(symbol)
        if financial is None:
            logger.info("  主接口未获取到，尝试备用接口...")
            financial = self._try_financial_sina(symbol)
        if financial is None:
            return None

        from config import settings
        self.cache.set(cache_key, financial, ttl=settings.financial_cache_ttl)
        return financial

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _try_financial_primary(self, symbol: str) -> Optional[Dict]:
        """主接口：stock_financial_analysis_indicator"""
        import akshare as ak
        try:
            df = ak.stock_financial_analysis_indicator(symbol=symbol)
            if df is None or df.empty or len(df.columns) == 0:
                return None
            latest = df.iloc[0]
            return {
                "pe": self._safe_float(latest.get("市盈率")),
                "pb": self._safe_float(latest.get("市净率")),
                "ps": self._safe_float(latest.get("市销率")),
                "roe": self._safe_float(latest.get("净资产收益率")),
                "roa": self._safe_float(latest.get("总资产收益率")),
                "gross_margin": self._safe_float(latest.get("销售毛利率")),
                "net_margin": self._safe_float(latest.get("销售净利率")),
                "revenue_growth": self._safe_float(latest.get("营业收入增长率")),
                "profit_growth": self._safe_float(latest.get("净利润增长率")),
                "debt_ratio": self._safe_float(latest.get("资产负债率")),
                "total_market_value": self._safe_float(latest.get("总市值")),
                "circulating_market_value": self._safe_float(latest.get("流通市值")),
            }
        except Exception:
            return None

    def _try_financial_sina(self, symbol: str) -> Optional[Dict]:
        """备用接口：stock_financial_abstract（新浪财经）"""
        import akshare as ak
        import warnings
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = ak.stock_financial_abstract(symbol=symbol)

            if df is None or df.empty:
                return None

            # 新浪财经的数据格式：行=指标名, 列=报告期（最新在第2列）
            latest_col = df.columns[2]
            indicator_map = {}
            for _, row in df.iterrows():
                name = str(row.iloc[1])
                val = self._safe_float(row[latest_col])
                if val is not None:
                    indicator_map[name] = val

            return {
                "pe": None,  # 新浪财报不含估值指标
                "pb": None,
                "ps": None,
                "roe": indicator_map.get("净资产收益率(ROE)")
                       or indicator_map.get("净资产收益率"),
                "roa": indicator_map.get("总资产报酬率(ROA)")
                       or indicator_map.get("总资产报酬率"),
                "gross_margin": indicator_map.get("毛利率"),
                "net_margin": indicator_map.get("销售净利率"),
                "revenue_growth": indicator_map.get("营业总收入增长率"),
                "profit_growth": indicator_map.get("归属母公司净利润增长率"),
                "debt_ratio": indicator_map.get("资产负债率"),
                "total_market_value": None,
                "circulating_market_value": None,
            }
        except Exception:
            return None

    # ===================== 新闻数据 =====================

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
    def get_stock_news(self, symbol: str, limit: int = 20) -> List[Dict]:
        """获取个股相关新闻"""
        cache_key = f"news_{symbol}_{limit}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        logger.info(f"获取新闻: {symbol}, limit={limit}")
        import akshare as ak

        try:
            # 使用东方财富个股新闻接口
            df = ak.stock_news_em(symbol=symbol)

            if df is None or df.empty:
                logger.warning(f"未获取到 {symbol} 的新闻")
                return []

            news_list = []
            for _, row in df.head(limit).iterrows():
                news_list.append({
                    "title": str(row.get("title", row.get("标题", ""))),
                    "content": str(row.get("content", row.get("内容", "")))[:500],
                    "source": str(row.get("source", row.get("来源", ""))),
                    "datetime": str(row.get("datetime", row.get("发布时间", ""))),
                    "url": str(row.get("url", row.get("链接", ""))),
                })

            from config import settings
            self.cache.set(cache_key, news_list, ttl=settings.news_cache_ttl)
            return news_list

        except Exception as e:
            logger.error(f"获取新闻失败: {e}")
            # 尝试备用接口
            try:
                return self._get_news_fallback(symbol, limit)
            except Exception:
                return []

    def _get_news_fallback(self, symbol: str, limit: int = 20) -> List[Dict]:
        """新闻备用接口"""
        import akshare as ak

        df = ak.stock_info_global_em()
        # 筛选相关新闻 - 这是一个简化的备用方案
        return []

    # ===================== 股票搜索 =====================

    def search_stock(self, keyword: str) -> List[Dict]:
        """根据代码或名称搜索股票"""
        logger.info(f"搜索股票: {keyword}")
        import akshare as ak

        try:
            # 获取 A 股股票列表
            df = ak.stock_info_a_code_name()

            if df is None or df.empty:
                return []

            # 模糊匹配
            keyword_lower = keyword.lower().strip()
            results = []
            for _, row in df.iterrows():
                code = str(row.get("code", row.get("代码", "")))
                name = str(row.get("name", row.get("名称", "")))

                if keyword_lower in code or keyword_lower in name.lower():
                    results.append({
                        "code": code,
                        "name": name,
                        "market": "A",
                    })

            return results[:20]  # 最多返回20个

        except Exception as e:
            logger.error(f"搜索股票失败: {e}")
            return []

    def get_stock_name(self, symbol: str) -> str:
        """通过代码获取股票名称"""
        import akshare as ak

        try:
            df = ak.stock_info_a_code_name()
            row = df[df["code"] == symbol]
            if not row.empty:
                return str(row.iloc[0].get("name", row.iloc[0].get("名称", "")))
        except Exception:
            pass
        return ""

    def get_market_index(self) -> Dict[str, float]:
        """获取主要大盘指数"""
        import akshare as ak

        try:
            df = ak.stock_zh_index_spot_em()
            indices = {}
            for _, row in df.iterrows():
                name = str(row.get("名称", ""))
                if "上证" in name:
                    indices["shanghai"] = float(row.get("最新价", 0))
                    indices["shanghai_change"] = float(row.get("涨跌幅", 0))
                elif "深证" in name and "成指" in name:
                    indices["shenzhen"] = float(row.get("最新价", 0))
                    indices["shenzhen_change"] = float(row.get("涨跌幅", 0))
                elif "创业" in name:
                    indices["chinext"] = float(row.get("最新价", 0))
                    indices["chinext_change"] = float(row.get("涨跌幅", 0))
            return indices
        except Exception as e:
            logger.error(f"获取大盘指数失败: {e}")
            return {}
