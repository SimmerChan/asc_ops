# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
OpenAI Provider

OpenAI API 适配器
"""

import logging
from typing import List, Optional, AsyncIterator

import httpx

from ..base import LLMProvider
from ..messages import Message
from ..responses import LLMResponse, LLMUsage
from ..exceptions import (
    LLMConfigurationError,
    LLMResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI API Provider"""

    DEFAULT_MODEL = "gpt-4o"

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
    ):
        """
        初始化 OpenAI Provider

        Args:
            api_key: OpenAI API Key
            api_base: API Base URL
            timeout: 请求超时时间（秒）
        """
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

        if not api_key:
            raise LLMConfigurationError("OpenAI API key is required", provider="openai")

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def supports_system_prompt(self) -> bool:
        return True  # OpenAI 支持在 messages 中放 system 角色

    async def __aenter__(self) -> "OpenAIProvider":
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
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )

    async def close(self) -> None:
        """关闭连接"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def adapt_request(self, request) -> dict:
        """
        将 Anthropic 格式转换为 OpenAI 格式

        Anthropic -> OpenAI:
        - system 参数 -> 放入 messages 作为第一条 system 消息
        - max_tokens 保持不变（OpenAI 也支持）
        """
        messages = []

        # system 消息
        if request.system:
            messages.append({"role": "system", "content": request.system})

        # 转换 messages
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})

        return {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "stream": request.stream,
            "temperature": request.temperature,
        }

    def normalize_response(self, raw_response: dict, model: str) -> LLMResponse:
        """将 OpenAI 响应标准化"""
        # OpenAI 响应格式: {"choices": [{"message": {"content": "..."}}]}
        content_text = ""
        if raw_response.get("choices"):
            choice = raw_response["choices"][0]
            message = choice.get("message", {})
            content_text = message.get("content", "")

        usage = LLMUsage.from_dict(raw_response.get("usage", {}), "openai")

        return LLMResponse(
            content=content_text,
            model=raw_response.get("model", model),
            provider="openai",
            usage=usage,
            raw_response=raw_response,
        )

    async def chat(
        self,
        messages: List[Message],
        model: str,
        max_tokens: int,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """发送聊天完成请求"""
        if self._client is None:
            await self.connect()

        # 构建 OpenAI 格式消息
        openai_messages = []

        # system 消息
        if system:
            openai_messages.append({"role": "system", "content": system})

        # user/assistant 消息
        for msg in messages:
            openai_messages.append({"role": msg.role.value, "content": msg.content})

        body = {
            "model": model or self.DEFAULT_MODEL,
            "messages": openai_messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            body["temperature"] = temperature

        try:
            response = await self._client.post(
                f"{self._api_base}/chat/completions",
                json=body,
            )

            if response.status_code == 429:
                raise LLMRateLimitError(provider="openai")
            elif response.status_code == 401:
                raise LLMConfigurationError("Invalid OpenAI API key", provider="openai")
            elif response.status_code >= 400:
                error_data = response.json() if response.text else {}
                raise LLMResponseError(
                    f"OpenAI API error: {error_data.get('error', {}).get('message', 'unknown')}",
                    provider="openai",
                    status_code=response.status_code,
                    details=error_data,
                )

            response.raise_for_status()
            raw = response.json()
            return self.normalize_response(raw, model or self.DEFAULT_MODEL)

        except httpx.TimeoutException as e:
            raise LLMTimeoutError(
                f"OpenAI request timeout: {e}",
                provider="openai",
                timeout=self._timeout,
            )
        except httpx.HTTPError as e:
            raise LLMResponseError(f"OpenAI HTTP error: {e}", provider="openai")

    async def chat_stream(
        self,
        messages: List[Message],
        model: str,
        max_tokens: int,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """流式聊天完成请求"""
        if self._client is None:
            await self.connect()

        openai_messages = []
        if system:
            openai_messages.append({"role": "system", "content": system})
        for msg in messages:
            openai_messages.append({"role": msg.role.value, "content": msg.content})

        body = {
            "model": model or self.DEFAULT_MODEL,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if temperature is not None:
            body["temperature"] = temperature

        async with self._client.stream(
            "POST",
            f"{self._api_base}/chat/completions",
            json=body,
        ) as response:
            if response.status_code == 429:
                raise LLMRateLimitError(provider="openai")
            elif response.status_code >= 400:
                raise LLMResponseError(
                    f"OpenAI stream error: {response.status_code}",
                    provider="openai",
                    status_code=response.status_code,
                )

            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    yield data_str
