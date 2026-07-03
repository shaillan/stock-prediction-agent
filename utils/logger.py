"""
结构化日志模块 - 基于 loguru
"""
import sys
from loguru import logger


def setup_logger(log_level: str = "INFO") -> None:
    """配置全局日志"""
    logger.remove()  # 移除默认 handler

    # 控制台输出（彩色）
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True,
    )

    # 文件输出（保留最近7天）
    logger.add(
        "logs/stock_agent_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        encoding="utf-8",
    )

    return logger


# 默认初始化
setup_logger()
