"""
技术指标计算器 - 纯 Python 计算，不依赖 LLM
所有计算基于 numpy + pandas 向量化操作
"""
from typing import Dict, Optional
import pandas as pd
import numpy as np
from loguru import logger


class TechnicalIndicatorCalculator:
    """技术指标计算器"""

    def __init__(self, df: pd.DataFrame):
        """
        Args:
            df: K线 DataFrame，需包含列: date, open, high, low, close, volume
        """
        self.df = df.copy()
        self._ensure_columns()
        self._indicators: Dict[str, pd.Series] = {}

    def _ensure_columns(self):
        """确保必要列存在，支持中英文列名"""
        column_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
        }
        self.df = self.df.rename(columns=column_map)

        required = ["close", "high", "low", "volume"]
        missing = [c for c in required if c not in self.df.columns]
        if missing:
            raise ValueError(f"DataFrame 缺少必要列: {missing}，当前列: {list(self.df.columns)}")

    def calc_ma(self, periods: list = None) -> Dict[str, pd.Series]:
        """计算移动平均线"""
        periods = periods or [5, 10, 20, 60]
        result = {}
        for p in periods:
            if len(self.df) >= p:
                result[f"ma{p}"] = self.df["close"].rolling(window=p).mean()
            else:
                result[f"ma{p}"] = pd.Series([np.nan] * len(self.df))
        self._indicators.update(result)
        return result

    def calc_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """计算 MACD"""
        ema_fast = self.df["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = self.df["close"].ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        hist = 2 * (dif - dea)
        result = {"macd_dif": dif, "macd_dea": dea, "macd_hist": hist}
        self._indicators.update(result)
        return result

    def calc_rsi(self, periods: list = None) -> Dict[str, pd.Series]:
        """计算 RSI 相对强弱指标"""
        periods = periods or [6, 14, 24]
        result = {}
        close = self.df["close"]
        delta = close.diff()

        for p in periods:
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta).where(delta < 0, 0.0)
            avg_gain = gain.ewm(alpha=1 / p, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1 / p, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            result[f"rsi{p}"] = rsi

        self._indicators.update(result)
        return result

    def calc_kdj(self, n: int = 9, m1: int = 3, m2: int = 3) -> Dict[str, pd.Series]:
        """计算 KDJ 指标"""
        high_n = self.df["high"].rolling(window=n).max()
        low_n = self.df["low"].rolling(window=n).min()
        close = self.df["close"]

        rsv = (close - low_n) / (high_n - low_n).replace(0, np.nan) * 100
        rsv = rsv.fillna(50)

        k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
        d = k.ewm(alpha=1 / m2, adjust=False).mean()
        j = 3 * k - 2 * d

        result = {"kdj_k": k, "kdj_d": d, "kdj_j": j}
        self._indicators.update(result)
        return result

    def calc_bollinger(self, period: int = 20, std: int = 2) -> Dict[str, pd.Series]:
        """计算布林带"""
        mid = self.df["close"].rolling(window=period).mean()
        std_dev = self.df["close"].rolling(window=period).std()
        upper = mid + std * std_dev
        lower = mid - std * std_dev

        result = {"boll_upper": upper, "boll_mid": mid, "boll_lower": lower}
        self._indicators.update(result)
        return result

    def calc_volume_ma(self, period: int = 5) -> Dict[str, pd.Series]:
        """计算成交量均线和量比"""
        vol_ma = self.df["volume"].rolling(window=period).mean()
        volume_ratio = self.df["volume"] / vol_ma.replace(0, np.nan)

        result = {"vol_ma5": vol_ma, "volume_ratio": volume_ratio}
        self._indicators.update(result)
        return result

    def calc_wr(self, period: int = 14) -> Dict[str, pd.Series]:
        """计算威廉指标 WR"""
        high_n = self.df["high"].rolling(window=period).max()
        low_n = self.df["low"].rolling(window=period).min()
        wr = (high_n - self.df["close"]) / (high_n - low_n).replace(0, np.nan) * 100

        result = {"wr": wr}
        self._indicators.update(result)
        return result

    def calc_all(self) -> Dict[str, pd.Series]:
        """一键计算所有技术指标"""
        logger.info("开始计算所有技术指标...")
        self.calc_ma()
        self.calc_macd()
        self.calc_rsi()
        self.calc_kdj()
        self.calc_bollinger()
        self.calc_volume_ma()
        self.calc_wr()
        logger.info(f"技术指标计算完成，共 {len(self._indicators)} 个序列")
        return self._indicators

    def get_latest_values(self, n_rows: int = 30) -> pd.DataFrame:
        """获取最近 N 行的指标值，用于构造 LLM Prompt"""
        if not self._indicators:
            self.calc_all()

        result_df = self.df[["date", "open", "high", "low", "close", "volume"]].copy()
        for name, series in self._indicators.items():
            result_df[name] = series

        return result_df.tail(n_rows)

    def get_latest_snapshot(self) -> Dict[str, Optional[float]]:
        """获取最新一个交易日的指标快照"""
        if not self._indicators:
            self.calc_all()

        idx = len(self.df) - 1
        snapshot = {"date": str(self.df.iloc[idx].get("date", "")), "close": float(self.df.iloc[idx]["close"])}

        for name, series in self._indicators.items():
            val = series.iloc[idx]
            snapshot[name] = round(float(val), 4) if not np.isnan(val) else None

        return snapshot

    def get_indicator_text_table(self, n_rows: int = 15) -> str:
        """获取最近 N 行指标数据表格（用于 LLM Prompt 文本）"""
        df = self.get_latest_values(n_rows)
        # 保留必要的列
        cols = ["date", "close", "volume"]
        cols += [c for c in df.columns if c.startswith(("ma", "macd", "rsi", "kdj", "boll", "vol", "wr"))]
        cols = [c for c in cols if c in df.columns]
        return df[cols].to_string(index=False)
