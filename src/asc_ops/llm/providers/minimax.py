# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
MiniMax Provider

MiniMax API 适配器
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


class MiniMaxProvider(LLMProvider):
    """MiniMax API Provider"""

    DEFAULT_MODEL = "MiniMax-Text-01"

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.minimax.chat/v1",
        group_id: str = None,
        timeout: float = 60.0,
    ):
        """
        初始化 MiniMax Provider

        Args:
            api_key: MiniMax API Key
            api_base: API Base URL
            group_id: MiniMax Group ID (用于区分用户)
            timeout: 请求超时时间（秒）
        """
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._group_id = group_id
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

        if not api_key:
            raise LLMConfigurationError("MiniMax API key is required", provider="minimax")

    @property
    def provider_name(self) -> str:
        return "minimax"

    @property
    def supports_system_prompt(self) -> bool:
        return True

    async def __aenter__(self) -> "MiniMaxProvider":
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
        将 Anthropic 格式转换为 MiniMax 格式

        Anthropic -> MiniMax:
        - system 参数 -> 放入 messages 作为第一条 system 消息
        - max_tokens -> max_completion_tokens
        - 其他参数基本兼容
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
            "max_completion_tokens": request.max_tokens,  # 关键差异
            "stream": request.stream,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }

    def normalize_response(self, raw_response: dict, model: str) -> LLMResponse:
        """将 MiniMax 响应标准化"""
        # MiniMax 响应格式与 OpenAI 类似
        # {"choices": [{"message": {"content": "..."}}]}
        content_text = ""
        if raw_response.get("choices"):
            choice = raw_response["choices"][0]
            message = choice.get("message", {})
            content_text = message.get("content", "")

        usage = LLMUsage.from_dict(raw_response.get("usage", {}), "minimax")

        return LLMResponse(
            content=content_text,
            model=raw_response.get("model", model),
            provider="minimax",
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

        # 构建 MiniMax 格式消息
        minimax_messages = []

        if system:
            minimax_messages.append({"role": "system", "content": system})

        for msg in messages:
            minimax_messages.append({"role": msg.role.value, "content": msg.content})

        body = {
            "model": model or self.DEFAULT_MODEL,
            "messages": minimax_messages,
            "max_completion_tokens": max_tokens,  # MiniMax 使用此字段名
        }
        if temperature is not None:
            body["temperature"] = temperature

        try:
            response = await self._client.post(
                f"{self._api_base}/text/chatcompletion_v2",
                json=body,
            )

            if response.status_code == 429:
                raise LLMRateLimitError(provider="minimax")
            elif response.status_code == 401:
                raise LLMConfigurationError("Invalid MiniMax API key", provider="minimax")
            elif response.status_code >= 400:
                error_data = response.json() if response.text else {}
                raise LLMResponseError(
                    f"MiniMax API error",
                    provider="minimax",
                    status_code=response.status_code,
                    details=error_data,
                )

            response.raise_for_status()
            raw = response.json()
            return self.normalize_response(raw, model or self.DEFAULT_MODEL)

        except httpx.TimeoutException as e:
            raise LLMTimeoutError(
                f"MiniMax request timeout: {e}",
                provider="minimax",
                timeout=self._timeout,
            )
        except httpx.HTTPError as e:
            raise LLMResponseError(f"MiniMax HTTP error: {e}", provider="minimax")

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

        minimax_messages = []
        if system:
            minimax_messages.append({"role": "system", "content": system})
        for msg in messages:
            minimax_messages.append({"role": msg.role.value, "content": msg.content})

        body = {
            "model": model or self.DEFAULT_MODEL,
            "messages": minimax_messages,
            "max_completion_tokens": max_tokens,
            "stream": True,
        }
        if temperature is not None:
            body["temperature"] = temperature

        async with self._client.stream(
            "POST",
            f"{self._api_base}/text/chatcompletion_v2",
            json=body,
        ) as response:
            if response.status_code == 429:
                raise LLMRateLimitError(provider="minimax")
            elif response.status_code >= 400:
                raise LLMResponseError(
                    f"MiniMax stream error: {response.status_code}",
                    provider="minimax",
                    status_code=response.status_code,
                )

            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    yield data_str
