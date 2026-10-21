"""
LLM 工厂模块 - 支持 Claude / GPT / DeepSeek / 智谱 GLM 等多种后端
"""
from typing import Optional
from urllib.parse import urlparse

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
        "deepseek-v4-flash",
        "deepseek-chat",
        "deepseek-reasoner",
    ],
    # 智谱 GLM（OpenAI 兼容）。glm-5.3-flash 是快速版，flashx 是更快的版本，
    # 注意 ID 里是点号，不要写成 glm-5-3-flash（那是第三方网关的写法）
    "zhipu": [
        "glm-5.3-flash",
        "glm-5.3-flashx",
        "glm-5.3",
    ],
}

# 模型名前缀能唯一确定厂商时，用它自动补 base_url，省得用户手填出错
DEFAULT_BASE_URLS = {
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "deepseek": "https://api.deepseek.com/v1",
}


def default_base_url_for(model: str) -> Optional[str]:
    """按模型名推断默认的 OpenAI 兼容端点；推断不出返回 None"""
    if model.startswith("glm"):
        return DEFAULT_BASE_URLS["zhipu"]
    if model.startswith("deepseek"):
        return DEFAULT_BASE_URLS["deepseek"]
    return None


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
    if model.startswith("glm"):
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

    # 没填 base_url 时，按模型名前缀补厂商默认端点（智谱/DeepSeek）。
    # 用户显式填了就尊重用户的（自建代理、Ollama、Coding Plan 专用域名等）。
    auto_base_url = default_base_url_for(model)
    if not base_url:
        if auto_base_url:
            base_url = auto_base_url
            logger.info(f"  base_url 未指定，按模型名使用默认端点: {auto_base_url}")
    elif auto_base_url:
        # 填了 base_url 但看起来是别家的端点：不覆盖（可能是自建代理），但要说出来。
        # 之前那次 403 就是"模型换成 Claude、地址还指向 DeepSeek"造成的，肉眼很难发现。
        expected_host = urlparse(auto_base_url).netloc
        if expected_host not in base_url:
            logger.warning(
                f"⚠️ 模型 {model} 通常请求 {expected_host}，但当前 base_url 是 {base_url}；"
                f"若出现 404/403，请先检查端点是否用错"
            )

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
