"""
数据模型定义 - 使用 Pydantic 进行类型校验
"""
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class StockInfo(BaseModel):
    """股票基本信息"""
    code: str = Field(..., description="股票代码，如 600519")
    name: str = Field(..., description="股票名称，如 贵州茅台")
    market: str = Field(default="A", description="市场: A=沪深, HK=港股")


class KlineData(BaseModel):
    """单条K线数据"""
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: float
    amount: float
    amplitude: Optional[float] = None  # 振幅
    change_pct: Optional[float] = None  # 涨跌幅
    turnover: Optional[float] = None  # 换手率


class RealtimeQuote(BaseModel):
    """实时行情"""
    code: str
    name: str
    price: float
    change_pct: float
    change_amount: float
    volume: float
    amount: float
    high: float
    low: float
    open: float
    pre_close: float
    turnover: Optional[float] = None
    update_time: Optional[str] = None


class FinancialData(BaseModel):
    """财务指标"""
    pe: Optional[float] = None  # 市盈率
    pb: Optional[float] = None  # 市净率
    ps: Optional[float] = None  # 市销率
    roe: Optional[float] = None  # ROE
    roa: Optional[float] = None  # ROA
    gross_margin: Optional[float] = None  # 毛利率
    net_margin: Optional[float] = None  # 净利率
    revenue_growth: Optional[float] = None  # 营收增长率
    profit_growth: Optional[float] = None  # 利润增长率
    debt_ratio: Optional[float] = None  # 资产负债率
    total_market_value: Optional[float] = None  # 总市值（亿）
    circulating_market_value: Optional[float] = None  # 流通市值（亿）


class NewsItem(BaseModel):
    """新闻条目"""
    title: str
    content: Optional[str] = None
    source: Optional[str] = None
    datetime: Optional[str] = None
    url: Optional[str] = None


class TechnicalIndicators(BaseModel):
    """技术指标快照（最近一个交易日）"""
    date: str
    close: float
    # 移动平均线
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    # MACD
    macd_dif: Optional[float] = None
    macd_dea: Optional[float] = None
    macd_hist: Optional[float] = None
    # RSI
    rsi6: Optional[float] = None
    rsi14: Optional[float] = None
    rsi24: Optional[float] = None
    # KDJ
    kdj_k: Optional[float] = None
    kdj_d: Optional[float] = None
    kdj_j: Optional[float] = None
    # 布林带
    boll_upper: Optional[float] = None
    boll_mid: Optional[float] = None
    boll_lower: Optional[float] = None
    # 成交量
    vol_ma5: Optional[float] = None
    volume_ratio: Optional[float] = None


class PredictionResult(BaseModel):
    """综合预测结果"""
    trend: str = Field(..., description="趋势判断: 看涨/看跌/震荡")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度 0-1")
    period: str = Field(default="1-5个交易日", description="预测周期")
    key_factors: List[str] = Field(default_factory=list, description="关键影响因素")
    risk_warnings: List[str] = Field(default_factory=list, description="风险提示")
    price_targets: Dict[str, float] = Field(
        default_factory=dict, description="目标价位: support, current, resistance, target_high"
    )
    reasoning_summary: str = Field(default="", description="综合分析摘要")
