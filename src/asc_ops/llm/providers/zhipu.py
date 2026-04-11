# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Zhipu AI Provider

智谱 AI (BigModel) API 适配器
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


class ZhipuProvider(LLMProvider):
    """Zhipu AI (BigModel) API Provider"""

    DEFAULT_MODEL = "glm-4"

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://open.bigmodel.cn/api/paas/v4",
        timeout: float = 60.0,
    ):
        """
        初始化 Zhipu Provider

        Args:
            api_key: Zhipu API Key
            api_base: API Base URL
            timeout: 请求超时时间（秒）
        """
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

        if not api_key:
            raise LLMConfigurationError("Zhipu API key is required", provider="zhipu")

    @property
    def provider_name(self) -> str:
        return "zhipu"

    @property
    def supports_system_prompt(self) -> bool:
        return True

    async def __aenter__(self) -> "ZhipuProvider":
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
                    "Accept-Language": "en",  # 支持中英文
                },
            )

    async def close(self) -> None:
        """关闭连接"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def adapt_request(self, request) -> dict:
        """
        将 Anthropic 格式转换为 Zhipu 格式

        Anthropic -> Zhipu:
        - system 参数 -> 放入 messages 作为第一条 system 消息
        - max_tokens 保持不变
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
            "max_tokens": request.max_tokens,
            "stream": request.stream,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "do_sample": True,  # Zhipu 特有参数
        }

    def normalize_response(self, raw_response: dict, model: str) -> LLMResponse:
        """将 Zhipu 响应标准化"""
        # Zhipu 响应格式与 OpenAI 类似
        # {"choices": [{"message": {"content": "..."}}]}
        content_text = ""
        if raw_response.get("choices"):
            choice = raw_response["choices"][0]
            message = choice.get("message", {})
            content_text = message.get("content", "")

        usage = LLMUsage.from_dict(raw_response.get("usage", {}), "zhipu")

        return LLMResponse(
            content=content_text,
            model=raw_response.get("model", model),
            provider="zhipu",
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

        # 构建 Zhipu 格式消息
        zhipu_messages = []

        if system:
            zhipu_messages.append({"role": "system", "content": system})

        for msg in messages:
            zhipu_messages.append({"role": msg.role.value, "content": msg.content})

        body = {
            "model": model or self.DEFAULT_MODEL,
            "messages": zhipu_messages,
            "max_tokens": max_tokens,
            "do_sample": True,
        }
        if temperature is not None:
            body["temperature"] = temperature

        try:
            response = await self._client.post(
                f"{self._api_base}/chat/completions",
                json=body,
            )

            if response.status_code == 429:
                raise LLMRateLimitError(provider="zhipu")
            elif response.status_code == 401:
                raise LLMConfigurationError("Invalid Zhipu API key", provider="zhipu")
            elif response.status_code >= 400:
                error_data = response.json() if response.text else {}
                raise LLMResponseError(
                    f"Zhipu API error",
                    provider="zhipu",
                    status_code=response.status_code,
                    details=error_data,
                )

            response.raise_for_status()
            raw = response.json()
            return self.normalize_response(raw, model or self.DEFAULT_MODEL)

        except httpx.TimeoutException as e:
            raise LLMTimeoutError(
                f"Zhipu request timeout: {e}",
                provider="zhipu",
                timeout=self._timeout,
            )
        except httpx.HTTPError as e:
            raise LLMResponseError(f"Zhipu HTTP error: {e}", provider="zhipu")

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

        zhipu_messages = []
        if system:
            zhipu_messages.append({"role": "system", "content": system})
        for msg in messages:
            zhipu_messages.append({"role": msg.role.value, "content": msg.content})

        body = {
            "model": model or self.DEFAULT_MODEL,
            "messages": zhipu_messages,
            "max_tokens": max_tokens,
            "stream": True,
            "do_sample": True,
        }
        if temperature is not None:
            body["temperature"] = temperature

        async with self._client.stream(
            "POST",
            f"{self._api_base}/chat/completions",
            json=body,
        ) as response:
            if response.status_code == 429:
                raise LLMRateLimitError(provider="zhipu")
            elif response.status_code >= 400:
                raise LLMResponseError(
                    f"Zhipu stream error: {response.status_code}",
                    provider="zhipu",
                    status_code=response.status_code,
                )

            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    yield data_str
