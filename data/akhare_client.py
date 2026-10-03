"""
AKShare 数据获取客户端 - 封装所有 A 股数据接口
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
from loguru import logger

from .cache_manager import CacheManager
from .models import KlineData, RealtimeQuote, FinancialData, NewsItem


class AKShareClient:
    """AKShare 数据获取封装，带缓存和重试"""

    AK_CALL_TIMEOUT = 12  # 单次 AKShare 调用超时秒数

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()

    @staticmethod
    def _call_with_timeout(fn, timeout: int = None):
        """在线程中调用 AKShare 函数，带超时控制

        使用 daemon 线程：超时后线程自动被遗弃，不会阻止进程退出，
        也不会像 ThreadPoolExecutor 那样 shutdown(wait=True) 死等
        """
        import threading
        t = timeout or AKShareClient.AK_CALL_TIMEOUT
        result = []
        error = []

        def wrapper():
            try:
                result.append(fn())
            except Exception as e:
                error.append(e)

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        thread.join(timeout=t)
        if thread.is_alive():
            raise TimeoutError(f"AKShare call timed out after {t}s")
        if error:
            raise error[0]
        return result[0]

    # ===================== K线数据 =====================

    def get_stock_kline(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "",
        end_date: str = "",
    ) -> pd.DataFrame:
        """
        获取 A 股历史 K 线数据（东方财富优先，新浪财经备用）

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

        # 东方财富优先（更稳定），新浪备用
        df = self._try_eastmoney_kline(symbol, period, start_date, end_date)
        if df is None:
            df = self._try_sina_kline(symbol, start_date, end_date)

        if df is None or df.empty:
            raise ValueError(f"未找到股票代码 {symbol} 的K线数据，请检查代码是否正确")

        # 缓存
        from config import settings
        self.cache.set(cache_key, df.to_dict(orient="records"), ttl=settings.kline_cache_ttl)

        return df

    @staticmethod
    def _to_sina_symbol(symbol: str) -> str:
        """600519 → sh600519, 000001 → sz000001"""
        code = symbol.strip()
        if code.startswith(("6", "68")):
            return f"sh{code}"
        else:
            return f"sz{code}"

    def _try_sina_kline(self, symbol: str, start_date: str, end_date: str):
        """新浪财经 K 线 (stock_zh_a_daily)"""
        import akshare as ak
        sina_sym = self._to_sina_symbol(symbol)
        logger.info(f"  尝试新浪: {sina_sym}")
        try:
            df = self._call_with_timeout(
                lambda: ak.stock_zh_a_daily(
                    symbol=sina_sym,
                    start_date=f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}",
                    end_date=f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}",
                    adjust="qfq",
                )
            )
        except Exception:
            logger.warning(f"  新浪 K 线请求失败或超时")
            return None
        if df is not None and not df.empty:
            df = self._normalize_sina_columns(df)
            logger.info(f"  ✅ 新浪K线: {len(df)} 条")
            return df
        return None

    def _try_eastmoney_kline(self, symbol: str, period: str, start_date: str, end_date: str):
        """东方财富 K 线 (stock_zh_a_hist)"""
        import akshare as ak
        logger.info(f"  尝试东方财富: {symbol}")
        try:
            df = self._call_with_timeout(
                lambda: ak.stock_zh_a_hist(
                    symbol=symbol, period=period,
                    start_date=start_date, end_date=end_date,
                    adjust="qfq",
                )
            )
            if df is not None and not df.empty:
                df = self._normalize_kline_columns(df)
                logger.info(f"  ✅ 东方财富K线: {len(df)} 条")
                return df
            return None
        except Exception:
            logger.warning(f"  东方财富 K 线请求失败或超时")
            return None

    @staticmethod
    def _normalize_sina_columns(df: pd.DataFrame) -> pd.DataFrame:
        """新浪财经列名标准化 + 补充涨跌幅/振幅"""
        # rename
        col_map = {
            "outstanding_share": "outstanding_share",  # 保留
        }
        df = df.rename(columns=col_map)
        # 计算涨跌幅
        if "close" in df.columns:
            df["change_pct"] = df["close"].pct_change() * 100
            df["change_amount"] = df["close"].diff()
        # 计算振幅
        if "high" in df.columns and "low" in df.columns and "close" in df.columns:
            prev_close = df["close"].shift(1)
            df["amplitude"] = ((df["high"] - df["low"]) / prev_close.replace(0, pd.NA)) * 100
        # 确保数值类型
        for col in ["open", "close", "high", "low", "volume", "amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
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
            df = self._call_with_timeout(
                lambda: ak.stock_financial_analysis_indicator(symbol=symbol)
            )
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
                df = self._call_with_timeout(
                    lambda: ak.stock_financial_abstract(symbol=symbol)
                )

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
            df = self._call_with_timeout(
                lambda: ak.stock_news_em(symbol=symbol)
            )

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

        try:
            df = self._call_with_timeout(
                lambda: ak.stock_info_global_em()
            )
        except Exception:
            return []
        # 筛选相关新闻 - 这是一个简化的备用方案
        return []

    # ===================== 股票搜索 =====================

    def search_stock(self, keyword: str) -> List[Dict]:
        """根据代码或名称搜索股票"""
        logger.info(f"搜索股票: {keyword}")
        import akshare as ak

        try:
            # 获取 A 股股票列表
            df = self._call_with_timeout(
                lambda: ak.stock_info_a_code_name(),
                timeout=20,  # 这个接口数据量大
            )

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
            df = self._call_with_timeout(
                lambda: ak.stock_info_a_code_name(),
                timeout=15,  # 这个接口数据量大，多给点时间
            )
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
            df = self._call_with_timeout(
                lambda: ak.stock_zh_index_spot_em()
            )
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
