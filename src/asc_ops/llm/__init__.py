# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
LLM Client Module

统一 LLM 客户端，支持多 Provider (Anthropic/OpenAI/Zhipu/MiniMax)
"""

from .messages import Message, MessageRole, ClaudeMessage, ClaudeRequest
from .responses import LLMResponse, LLMUsage
from .exceptions import (
    LLMException,
    LLMConfigurationError,
    LLMResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnsupportedError,
)
from .base import LLMProvider
from .client import UnifiedLLMClient
from .providers import AnthropicProvider, OpenAIProvider, ZhipuProvider, MiniMaxProvider

__all__ = [
    # Messages
    "Message",
    "MessageRole",
    "ClaudeMessage",
    "ClaudeRequest",
    # Responses
    "LLMResponse",
    "LLMUsage",
    # Exceptions
    "LLMException",
    "LLMConfigurationError",
    "LLMResponseError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMUnsupportedError",
    # Core
    "LLMProvider",
    "UnifiedLLMClient",
    # Providers
    "AnthropicProvider",
    "OpenAIProvider",
    "ZhipuProvider",
    "MiniMaxProvider",
]
