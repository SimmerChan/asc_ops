# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Anthropic Provider

Anthropic API 适配器
"""

import logging
from typing import List, Optional, AsyncIterator

import httpx

from ..base import LLMProvider
from ..messages import Message, ClaudeMessage, ClaudeRequest
from ..responses import LLMResponse, LLMUsage
from ..exceptions import (
    LLMConfigurationError,
    LLMResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic API Provider"""

    API_VERSION = "2023-06-01"
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.anthropic.com",
        timeout: float = 60.0,
    ):
        """
        初始化 Anthropic Provider

        Args:
            api_key: Anthropic API Key
            api_base: API Base URL
            timeout: 请求超时时间（秒）
        """
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

        if not api_key:
            raise LLMConfigurationError("Anthropic API key is required", provider="anthropic")

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def supports_system_prompt(self) -> bool:
        return True

    async def __aenter__(self) -> "AnthropicProvider":
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def connect(self) -> None:
        """建立连接"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": self.API_VERSION,
                    "Content-Type": "application/json",
                },
            )

    async def close(self) -> None:
        """关闭连接"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        messages: List[Message],
        model: str,
        max_tokens: int,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """
        发送聊天完成请求

        Anthropic API:
        - 使用 x-api-key header
        - max_tokens 是必填参数
        - system 通过单独的参数传递
        """
        if self._client is None:
            await self.connect()

        # 构建 Anthropic 格式消息
        claude_messages = []
        for msg in messages:
            if msg.role.value == "user":
                claude_messages.append({"role": "user", "content": msg.content})
            elif msg.role.value == "assistant":
                claude_messages.append({"role": "assistant", "content": msg.content})
            # Anthropic 不支持 system 角色，会被忽略

        # 构建请求体
        body = {
            "model": model or self.DEFAULT_MODEL,
            "messages": claude_messages,
            "max_tokens": max_tokens,
        }
        if system:
            body["system"] = system
        if temperature is not None:
            body["temperature"] = temperature

        try:
            response = await self._client.post(
                f"{self._api_base}/v1/messages",
                json=body,
            )

            if response.status_code == 429:
                retry_after = int(response.headers.get("retry-after", 60))
                raise LLMRateLimitError(
                    "Anthropic rate limit exceeded",
                    provider="anthropic",
                    retry_after=retry_after,
                )
            elif response.status_code == 401:
                raise LLMConfigurationError(
                    "Invalid Anthropic API key",
                    provider="anthropic",
                )
            elif response.status_code >= 400:
                error_data = response.json() if response.text else {}
                raise LLMResponseError(
                    f"Anthropic API error: {error_data.get('error', {}).get('type', 'unknown')}",
                    provider="anthropic",
                    status_code=response.status_code,
                    details=error_data,
                )

            response.raise_for_status()
            raw = response.json()

            # 解析响应
            # Anthropic 响应格式: {"content": [{"type": "text", "text": "..."}]}
            content_text = ""
            if raw.get("content"):
                for block in raw["content"]:
                    if block.get("type") == "text":
                        content_text += block.get("text", "")

            usage = LLMUsage.from_dict(raw.get("usage", {}), "anthropic")

            return LLMResponse(
                content=content_text,
                model=raw.get("model", model or self.DEFAULT_MODEL),
                provider="anthropic",
                usage=usage,
                raw_response=raw,
            )

        except httpx.TimeoutException as e:
            raise LLMTimeoutError(
                f"Anthropic request timeout: {e}",
                provider="anthropic",
                timeout=self._timeout,
            )
        except httpx.HTTPError as e:
            raise LLMResponseError(
                f"Anthropic HTTP error: {e}",
                provider="anthropic",
            )

    async def chat_stream(
        self,
        messages: List[Message],
        model: str,
        max_tokens: int,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """流式聊天完成请求 (SSE)"""
        if self._client is None:
            await self.connect()

        # 构建 Anthropic 格式消息
        claude_messages = []
        for msg in messages:
            if msg.role.value == "user":
                claude_messages.append({"role": "user", "content": msg.content})
            elif msg.role.value == "assistant":
                claude_messages.append({"role": "assistant", "content": msg.content})

        body = {
            "model": model or self.DEFAULT_MODEL,
            "messages": claude_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system:
            body["system"] = system
        if temperature is not None:
            body["temperature"] = temperature

        async with self._client.stream(
            "POST",
            f"{self._api_base}/v1/messages",
            json=body,
        ) as response:
            if response.status_code == 429:
                raise LLMRateLimitError(provider="anthropic")
            elif response.status_code >= 400:
                raise LLMResponseError(
                    f"Anthropic stream error: {response.status_code}",
                    provider="anthropic",
                    status_code=response.status_code,
                )

            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    # 简化处理，实际应解析 SSE 格式
                    yield data_str
