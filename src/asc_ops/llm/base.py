# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
LLM Provider Base

Provider 抽象基类
"""

from abc import ABC, abstractmethod
from typing import List, Optional, AsyncIterator

from .messages import Message, ClaudeRequest
from .responses import LLMResponse


class LLMProvider(ABC):
    """LLM Provider 抽象基类"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 名称"""
        pass

    @property
    def supports_system_prompt(self) -> bool:
        """
        是否支持独立的 system prompt

        Anthropic: 支持（通过单独的 system 参数）
        OpenAI/Zhipu/MiniMax: 不支持（需要放入 messages 数组）
        """
        return True

    @abstractmethod
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

        Args:
            messages: 消息列表（统一格式）
            model: 模型名称
            max_tokens: 最大生成 token 数
            system: system prompt（如 Provider 支持）
            temperature: 温度参数

        Returns:
            LLMResponse: 统一响应格式
        """
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Message],
        model: str,
        max_tokens: int,
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
        pass

    def adapt_request(self, request: ClaudeRequest) -> dict:
        """
        将 Anthropic 格式请求转换为 Provider 特定格式

        Args:
            request: Anthropic 格式请求

        Returns:
            dict: Provider 特定的请求字典
        """
        # 默认实现：直接返回 ClaudeRequest 的字典形式
        # 子类可覆盖进行转换
        return request.to_dict()

    def normalize_response(self, raw_response: dict, model: str) -> LLMResponse:
        """
        将 Provider 响应标准化为统一格式

        Args:
            raw_response: Provider 原始响应字典
            model: 使用的模型

        Returns:
            LLMResponse: 统一响应格式
        """
        # 子类必须实现
        raise NotImplementedError
