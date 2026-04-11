# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Anthropic Provider 测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.asc_ops.llm.providers.anthropic import AnthropicProvider
from src.asc_ops.llm import Message, MessageRole
from src.asc_ops.llm.exceptions import LLMConfigurationError, LLMRateLimitError


class TestAnthropicProvider:
    """Anthropic Provider 测试"""

    def test_init_default(self):
        """测试默认初始化"""
        provider = AnthropicProvider(api_key="test_key")
        assert provider.provider_name == "anthropic"
        assert provider.DEFAULT_MODEL == "claude-3-5-sonnet-20241022"

    def test_init_custom_api_base(self):
        """测试自定义 API Base"""
        provider = AnthropicProvider(
            api_key="test_key",
            api_base="https://custom.anthropic.com",
        )
        assert provider._api_base == "https://custom.anthropic.com"

    def test_init_missing_api_key(self):
        """测试缺少 API Key"""
        with pytest.raises(LLMConfigurationError):
            AnthropicProvider(api_key="")

    def test_supports_system_prompt(self):
        """测试支持独立 system prompt"""
        provider = AnthropicProvider(api_key="test_key")
        assert provider.supports_system_prompt is True

    @pytest.mark.asyncio
    async def test_chat_request_format(self):
        """测试 chat 请求格式"""
        provider = AnthropicProvider(api_key="test_key")
        provider._client = AsyncMock()

        # Mock 响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "msg_123",
            "type": "message",
            "model": "claude-3-5-sonnet-20241022",
            "content": [{"type": "text", "text": "Test response"}],
            "usage": {"input_tokens": 10, "output_tokens": 5}
        }
        provider._client.post = AsyncMock(return_value=mock_response)

        messages = [Message(role=MessageRole.USER, content="Hello")]
        response = await provider.chat(
            messages=messages,
            model="claude-3-5-sonnet-20241022",
            max_tokens=100,
        )

        assert response.content == "Test response"
        assert response.provider == "anthropic"

    @pytest.mark.asyncio
    async def test_chat_rate_limit(self):
        """测试限流错误"""
        provider = AnthropicProvider(api_key="test_key")
        provider._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "60"}
        provider._client.post = AsyncMock(return_value=mock_response)

        messages = [Message(role=MessageRole.USER, content="Hello")]
        with pytest.raises(LLMRateLimitError) as exc_info:
            await provider.chat(messages=messages, model="test", max_tokens=100)
        assert exc_info.value.provider == "anthropic"
        assert exc_info.value.retry_after == 60

    @pytest.mark.asyncio
    async def test_chat_with_system_prompt(self):
        """测试带 system prompt 的请求"""
        provider = AnthropicProvider(api_key="test_key")
        provider._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "msg_123",
            "type": "message",
            "model": "claude-3-5-sonnet-20241022",
            "content": [{"type": "text", "text": "Test response"}],
            "usage": {"input_tokens": 10, "output_tokens": 5}
        }
        provider._client.post = AsyncMock(return_value=mock_response)

        messages = [Message(role=MessageRole.USER, content="Hello")]
        response = await provider.chat(
            messages=messages,
            model="claude-3-5-sonnet-20241022",
            max_tokens=100,
            system="You are a helpful assistant.",
        )

        assert response.content == "Test response"
