# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
E2E 测试配置

提供测试夹具和共享配置
"""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_data_dir():
    """创建临时数据目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "test_data"
        data_dir.mkdir()
        yield data_dir


@pytest.fixture
def mock_chroma_client():
    """Mock ChromaDB 客户端"""
    from unittest.mock import MagicMock

    client = MagicMock()
    return client


@pytest.fixture
def mock_redis_client():
    """Mock Redis 客户端"""
    from unittest.mock import MagicMock

    client = MagicMock()
    return client


@pytest.fixture
def gpu_storage(mock_chroma_client, mock_redis_client):
    """创建 GPU 存储实例 (mock 模式)"""
    from src.asc_ops.gpu_collector import GPUStorage

    storage = GPUStorage(
        chroma_client=mock_chroma_client,
        redis_client=mock_redis_client,
        use_mock=True,
    )
    return storage


@pytest.fixture
def mapper_engine():
    """创建映射引擎实例"""
    from src.asc_ops.mapper import MapperEngine

    engine = MapperEngine()
    return engine


@pytest.fixture
def mcp_tools():
    """创建 MCP 工具实例"""
    from src.asc_ops.mcp import MCPTools

    tools = MCPTools()
    return tools
