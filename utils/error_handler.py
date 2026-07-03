"""
错误处理模块 - 提供统一错误类型和装饰器
"""
import functools
from typing import Callable, Any, Optional
from loguru import logger


class AgentError(Exception):
    """Agent 基础异常"""

    def __init__(self, message: str, detail: Optional[str] = None):
        self.message = message
        self.detail = detail
        super().__init__(self.message)

    def to_user_message(self) -> str:
        """转为用户可读的中文消息"""
        msg = f"❌ {self.message}"
        if self.detail:
            msg += f"\n详情: {self.detail}"
        return msg


class DataFetchError(AgentError):
    """数据获取异常"""
    pass


class LLMError(AgentError):
    """LLM 调用异常"""
    pass


class InvalidStockError(AgentError):
    """无效股票代码异常"""
    pass


def safe_call(default_return: Any = None, error_msg: str = "操作失败"):
    """
    安全调用装饰器 - 捕获异常并返回默认值，不中断程序
    用于数据获取等非关键操作
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"{error_msg}: {e}")
                return default_return

        return wrapper

    return decorator
