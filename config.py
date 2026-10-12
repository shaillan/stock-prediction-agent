"""
全局配置文件 - 所有可调参数集中管理
使用 Pydantic Settings 自动加载 .env 文件和环境变量
"""
from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    """应用全局配置"""

    # ========== LLM 配置 ==========
    llm_model: str = "claude-sonnet-4-20250514"
    llm_api_key: str = ""
    llm_base_url: str = ""  # OpenAI-compatible endpoint（留空则用官方API）
    llm_temperature: float = 0.6
    llm_max_tokens: int = 4096

    # ========== 数据配置 ==========
    default_kline_period: str = "daily"
    default_lookback_days: int = 365  # 默认获取1年历史数据
    max_news_items: int = 20
    realtime_quote_ttl: int = 30  # 实时行情缓存秒数
    kline_cache_ttl: int = 21600  # K线缓存6小时
    news_cache_ttl: int = 900  # 新闻缓存15分钟
    financial_cache_ttl: int = 86400  # 财务数据缓存24小时

    # ========== 技术指标参数 ==========
    ma_periods: list = [5, 10, 20, 60]
    macd_params: dict = {"fast": 12, "slow": 26, "signal": 9}
    rsi_periods: list = [6, 14, 24]
    kdj_params: dict = {"n": 9, "m1": 3, "m2": 3}
    bollinger_params: dict = {"period": 20, "std": 2}

    # ========== Agent 配置 ==========
    agent_max_retries: int = 2
    data_fetch_timeout: int = 15  # AKShare 单次调用超时秒数

    # ========== 公告检索 RAG ==========
    rag_enabled: bool = True        # 是否启用公告全文检索
    rag_top_k: int = 3              # 每个研究问题检索的片段数
    rag_announcement_days: int = 180  # 回溯多少天的公告

    # ========== UI 配置 ==========
    page_title: str = "📈 股票智能预测 Agent"
    default_stock: str = "600519"  # 贵州茅台

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# 全局单例
settings = Settings()
