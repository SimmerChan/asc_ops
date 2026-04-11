# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Zhipu Provider 测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.asc_ops.llm.providers.zhipu import ZhipuProvider
from src.asc_ops.llm import Message, MessageRole
from src.asc_ops.llm.exceptions import LLMConfigurationError


class TestZhipuProvider:
    """Zhipu Provider 测试"""

    def test_init_default(self):
        """测试默认初始化"""
        provider = ZhipuProvider(api_key="test_key")
        assert provider.provider_name == "zhipu"
        assert provider.DEFAULT_MODEL == "glm-4"
        assert provider._api_base == "https://open.bigmodel.cn/api/paas/v4"

    def test_init_missing_api_key(self):
        """测试缺少 API Key"""
        with pytest.raises(LLMConfigurationError):
            ZhipuProvider(api_key="")

    def test_supports_system_prompt(self):
        """测试支持独立 system prompt"""
        provider = ZhipuProvider(api_key="test_key")
        assert provider.supports_system_prompt is True

    @pytest.mark.asyncio
    async def test_chat_request_format(self):
        """测试 chat 请求格式"""
        provider = ZhipuProvider(api_key="test_key")
        provider._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "1234567890",
            "model": "glm-4",
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
            model="glm-4",
            max_tokens=100,
        )

        assert response.content == "Test response"
        assert response.provider == "zhipu"

    @pytest.mark.asyncio
    async def test_chat_with_temperature(self):
        """测试带 temperature 的请求"""
        provider = ZhipuProvider(api_key="test_key")
        provider._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "1234567890",
            "model": "glm-4",
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
            model="glm-4",
            max_tokens=100,
            temperature=0.7,
        )

        assert response.content == "Test response"
