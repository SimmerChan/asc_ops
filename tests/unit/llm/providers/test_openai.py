# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
OpenAI Provider 测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.asc_ops.llm.providers.openai import OpenAIProvider
from src.asc_ops.llm import Message, MessageRole
from src.asc_ops.llm.exceptions import LLMConfigurationError, LLMResponseError


class TestOpenAIProvider:
    """OpenAI Provider 测试"""

    def test_init_default(self):
        """测试默认初始化"""
        provider = OpenAIProvider(api_key="test_key")
        assert provider.provider_name == "openai"
        assert provider.DEFAULT_MODEL == "gpt-4o"

    def test_init_missing_api_key(self):
        """测试缺少 API Key"""
        with pytest.raises(LLMConfigurationError):
            OpenAIProvider(api_key="")

    def test_supports_system_prompt(self):
        """测试支持独立 system prompt"""
        provider = OpenAIProvider(api_key="test_key")
        assert provider.supports_system_prompt is True

    @pytest.mark.asyncio
    async def test_chat_request_format(self):
        """测试 chat 请求格式"""
        provider = OpenAIProvider(api_key="test_key")
        provider._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl_123",
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Test response"}
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
        provider._client.post = AsyncMock(return_value=mock_response)

        messages = [Message(role=MessageRole.USER, content="Hello")]
        response = await provider.chat(
            messages=messages,
            model="gpt-4o",
            max_tokens=100,
        )

        assert response.content == "Test response"
        assert response.provider == "openai"

    @pytest.mark.asyncio
    async def test_chat_with_system_prompt(self):
        """测试带 system prompt 的请求"""
        provider = OpenAIProvider(api_key="test_key")
        provider._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl_123",
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Test response"}
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
        provider._client.post = AsyncMock(return_value=mock_response)

        messages = [Message(role=MessageRole.USER, content="Hello")]
        response = await provider.chat(
            messages=messages,
            model="gpt-4o",
            max_tokens=100,
            system="You are a helpful assistant.",
        )

        assert response.content == "Test response"

    @pytest.mark.asyncio
    async def test_chat_error_response(self):
        """测试错误响应"""
        provider = OpenAIProvider(api_key="test_key")
        provider._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": {"message": "Bad request"}}'
        mock_response.json.return_value = {"error": {"message": "Bad request"}}
        provider._client.post = AsyncMock(return_value=mock_response)

        messages = [Message(role=MessageRole.USER, content="Hello")]
        with pytest.raises(LLMResponseError) as exc_info:
            await provider.chat(messages=messages, model="gpt-4o", max_tokens=100)
        assert exc_info.value.provider == "openai"
