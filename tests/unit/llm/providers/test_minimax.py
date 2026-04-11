# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
MiniMax Provider 测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.asc_ops.llm.providers.minimax import MiniMaxProvider
from src.asc_ops.llm import Message, MessageRole
from src.asc_ops.llm.exceptions import LLMConfigurationError


class TestMiniMaxProvider:
    """MiniMax Provider 测试"""

    def test_init_default(self):
        """测试默认初始化"""
        provider = MiniMaxProvider(api_key="test_key")
        assert provider.provider_name == "minimax"
        assert provider.DEFAULT_MODEL == "MiniMax-Text-01"
        assert provider._api_base == "https://api.minimax.chat/v1"

    def test_init_with_group_id(self):
        """测试带 group_id 初始化"""
        provider = MiniMaxProvider(
            api_key="test_key",
            group_id="test_group",
        )
        assert provider._group_id == "test_group"

    def test_init_missing_api_key(self):
        """测试缺少 API Key"""
        with pytest.raises(LLMConfigurationError):
            MiniMaxProvider(api_key="")

    def test_supports_system_prompt(self):
        """测试支持独立 system prompt"""
        provider = MiniMaxProvider(api_key="test_key")
        assert provider.supports_system_prompt is True

    @pytest.mark.asyncio
    async def test_chat_request_format(self):
        """测试 chat 请求格式"""
        provider = MiniMaxProvider(api_key="test_key")
        provider._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "1234567890",
            "model": "MiniMax-Text-01",
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
            model="MiniMax-Text-01",
            max_tokens=100,
        )

        assert response.content == "Test response"
        assert response.provider == "minimax"

    @pytest.mark.asyncio
    async def test_chat_uses_max_completion_tokens(self):
        """测试 MiniMax 使用 max_completion_tokens 字段"""
        provider = MiniMaxProvider(api_key="test_key")
        provider._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "1234567890",
            "model": "MiniMax-Text-01",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Test response"}
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
        provider._client.post = AsyncMock(return_value=mock_response)

        messages = [Message(role=MessageRole.USER, content="Hello")]
        await provider.chat(
            messages=messages,
            model="MiniMax-Text-01",
            max_tokens=100,
        )

        # 验证调用参数
        call_args = provider._client.post.call_args
        body = call_args.kwargs.get("json", {})
        assert "max_completion_tokens" in body
        assert body["max_completion_tokens"] == 100
