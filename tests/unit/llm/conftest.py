# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
LLM 模块测试 fixtures
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient"""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.fixture
def anthropic_response():
    """Anthropic API 响应"""
    return {
        "id": "msg_123",
        "type": "message",
        "model": "claude-3-5-sonnet-20241022",
        "content": [
            {"type": "text", "text": "This is a test response"}
        ],
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
        }
    }


@pytest.fixture
def openai_response():
    """OpenAI API 响应"""
    return {
        "id": "chatcmpl_123",
        "model": "gpt-4o",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "This is a test response"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    }


@pytest.fixture
def zhipu_response():
    """Zhipu API 响应"""
    return {
        "id": "1234567890",
        "model": "glm-4",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "This is a test response"
                }
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    }


@pytest.fixture
def minimax_response():
    """MiniMax API 响应"""
    return {
        "id": "1234567890",
        "model": "MiniMax-Text-01",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "This is a test response"
                }
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    }
