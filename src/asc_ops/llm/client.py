# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Unified LLM Client

统一 LLM 客户端门面，支持多 Provider 切换
"""

import logging
import os
from typing import List, Optional, AsyncIterator

from .base import LLMProvider
from .messages import Message
from .responses import LLMResponse
from .providers import AnthropicProvider, OpenAIProvider, ZhipuProvider, MiniMaxProvider
from .exceptions import LLMConfigurationError, LLMUnsupportedError

logger = logging.getLogger(__name__)

# Provider 映射
_PROVIDER_CLASSES = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "zhipu": ZhipuProvider,
    "minimax": MiniMaxProvider,
}


class UnifiedLLMClient:
    """
    统一 LLM 客户端

    提供统一的 chat 接口，支持在多个 Provider 之间切换
    """

    def __init__(
        self,
        provider: str = "anthropic",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: float = 60.0,
        **provider_kwargs,
    ):
        """
        初始化 UnifiedLLMClient

        Args:
            provider: Provider 名称 (anthropic/openai/zhipu/minimax)
            api_key: API Key (如不提供则从环境变量或配置获取)
            api_base: API Base URL (可选，覆盖默认值)
            timeout: 请求超时时间（秒）
            **provider_kwargs: 传递给特定 Provider 的额外参数
        """
        self._provider_name = provider.lower()
        if self._provider_name not in _PROVIDER_CLASSES:
            supported = ", ".join(_PROVIDER_CLASSES.keys())
            raise LLMUnsupportedError(
                f"Unsupported provider: {provider}. Supported: {supported}",
                provider=provider,
            )

        self._provider: Optional[LLMProvider] = None
        self._provider_class = _PROVIDER_CLASSES[self._provider_name]
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._api_base = api_base or os.environ.get("ANTHROPIC_API_BASE", "")
        self._timeout = timeout
        self._provider_kwargs = provider_kwargs

    @property
    def provider_name(self) -> str:
        """当前 Provider 名称"""
        return self._provider_name

    async def __aenter__(self) -> "UnifiedLLMClient":
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def connect(self) -> None:
        """建立连接"""
        if self._provider is None:
            self._provider = self._provider_class(
                api_key=self._api_key or "",
                api_base=self._api_base or "",
                timeout=self._timeout,
                **self._provider_kwargs,
            )
            await self._provider.connect()

    async def close(self) -> None:
        """关闭连接"""
        if self._provider is not None:
            await self._provider.close()
            self._provider = None

    def switch_provider(self, provider: str) -> None:
        """
        切换 Provider

        Args:
            provider: 新的 Provider 名称
        """
        provider = provider.lower()
        if provider == self._provider_name and self._provider is not None:
            return

        if provider not in _PROVIDER_CLASSES:
            supported = ", ".join(_PROVIDER_CLASSES.keys())
            raise LLMUnsupportedError(
                f"Unsupported provider: {provider}. Supported: {supported}",
                provider=provider,
            )

        # 关闭旧连接
        if self._provider is not None:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._provider.close())
            except RuntimeError:
                pass

        self._provider_name = provider
        self._provider_class = _PROVIDER_CLASSES[provider]
        self._provider = None

    async def chat(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        max_tokens: int = 1024,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """
        发送聊天完成请求

        Args:
            messages: 消息列表
            model: 模型名称（可选，使用 Provider 默认值）
            max_tokens: 最大生成 token 数
            system: system prompt（如 Provider 支持）
            temperature: 温度参数

        Returns:
            LLMResponse: 统一响应格式
        """
        if self._provider is None:
            await self.connect()

        return await self._provider.chat(
            messages=messages,
            model=model or "",
            max_tokens=max_tokens,
            system=system,
            temperature=temperature,
        )

    async def chat_stream(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        max_tokens: int = 1024,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """
        流式聊天完成请求

        Args:
            messages: 消息列表
            model: 模型名称
            max_tokens: 最大生成 token 数
            system: system prompt
            temperature: 温度参数

        Yields:
            str: 增量文本片段
        """
        if self._provider is None:
            await self.connect()

        async for chunk in self._provider.chat_stream(
            messages=messages,
            model=model or "",
            max_tokens=max_tokens,
            system=system,
            temperature=temperature,
        ):
            yield chunk
