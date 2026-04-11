# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
UnifiedLLMClient 测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.asc_ops.llm import UnifiedLLMClient, Message, MessageRole
from src.asc_ops.llm.exceptions import LLMUnsupportedError


class TestUnifiedLLMClient:
    """UnifiedLLMClient 测试"""

    def test_init_default_provider(self):
        """测试默认 provider"""
        client = UnifiedLLMClient(api_key="test_key")
        assert client.provider_name == "anthropic"

    def test_init_openai_provider(self):
        """测试 OpenAI provider"""
        client = UnifiedLLMClient(provider="openai", api_key="test_key")
        assert client.provider_name == "openai"

    def test_init_unsupported_provider(self):
        """测试不支持的 provider"""
        with pytest.raises(LLMUnsupportedError) as exc_info:
            UnifiedLLMClient(provider="invalid", api_key="test_key")
        assert "Unsupported provider" in str(exc_info.value)

    def test_switch_provider(self):
        """测试切换 provider"""
        client = UnifiedLLMClient(provider="anthropic", api_key="test_key")
        client.switch_provider("openai")
        assert client.provider_name == "openai"

    def test_switch_to_same_provider(self):
        """测试切换到相同 provider (无操作)"""
        client = UnifiedLLMClient(provider="anthropic", api_key="test_key")
        # 不应该抛出异常
        client.switch_provider("anthropic")
        assert client.provider_name == "anthropic"

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """测试上下文管理器"""
        client = UnifiedLLMClient(provider="anthropic", api_key="test_key")
        # Mock connect 以避免真实网络连接
        with patch.object(client._provider_class, 'connect', new_callable=AsyncMock):
            with patch.object(client._provider_class, 'close', new_callable=AsyncMock):
                async with client:
                    pass  # 应该能正常进入和退出

    def test_provider_case_insensitive(self):
        """测试 provider 名称大小写不敏感"""
        client = UnifiedLLMClient(provider="OPENAI", api_key="test_key")
        assert client.provider_name == "openai"

    def test_provider_mixed_case(self):
        """测试 provider 混写"""
        client = UnifiedLLMClient(provider="Zhipu", api_key="test_key")
        assert client.provider_name == "zhipu"
