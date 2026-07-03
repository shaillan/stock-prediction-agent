"""
LLM 工厂模块 - 支持 Claude / GPT / OpenAI兼容API 多种后端
"""
from typing import Optional
from langchain_core.language_models import BaseChatModel
from loguru import logger

SUPPORTED_MODELS = {
    "claude": [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
        "claude-haiku-3-5-20241022",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-4o-mini",
    ],
    "deepseek": [
        "deepseek-chat",
        "deepseek-reasoner",
    ],
}


def detect_provider(model: str, base_url: Optional[str] = None) -> str:
    """
    根据模型名或 base_url 自动检测 API Provider

    Returns:
        "anthropic" | "openai" | "openai_compatible"
    """
    if model.startswith("claude-"):
        return "anthropic"
    if model.startswith("deepseek"):
        return "openai_compatible"
    if base_url and "anthropic" not in base_url:
        return "openai_compatible"
    return "openai"


def create_chat_model(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> BaseChatModel:
    """
    创建 LLM 对话模型实例

    Args:
        model: 模型名称。None 则从 config 读取
        api_key: API Key。None 则从 config 读取
        base_url: 自定义 API 地址
        temperature: 温度参数 (0-1)
        max_tokens: 最大输出 Token

    Returns:
        LangChain BaseChatModel 实例
    """
    from config import settings

    model = model or settings.llm_model
    api_key = api_key or settings.llm_api_key
    base_url = base_url or settings.llm_base_url or None

    if not api_key:
        raise ValueError("❌ LLM API Key 未设置！请在侧边栏或 .env 文件中配置")

    provider = detect_provider(model, base_url)

    logger.info(f"创建 LLM 连接: provider={provider}, model={model}")

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        from langchain_openai import ChatOpenAI

        kwargs = {
            "model": model,
            "api_key": api_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if base_url:
            kwargs["base_url"] = base_url

        return ChatOpenAI(**kwargs)


def get_model_display_name(model: str) -> str:
    """获取模型显示名称"""
    for provider, models in SUPPORTED_MODELS.items():
        if model in models:
            return f"{model} ({provider})"
    return model
