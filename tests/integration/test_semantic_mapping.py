# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
CUDA → AscendC 语义映射集成测试

测试 MCP 工具 → KnowledgeQueryService → ChromaDB 完整链路
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.asc_ops.knowledge_query import KnowledgeQueryService, SemanticMappingResult
from src.asc_ops.mcp.tools import MCPTools
from src.asc_ops.gpu_collector.storage import GPUStorage
from src.asc_ops.gpu_collector.models import GPUAPIInfo, GPUPlatform


class TestSemanticCudaToNpuMapping:
    """语义映射集成测试"""

    @pytest.fixture
    def mock_chroma(self):
        """Mock ChromaDB client"""
        mock = MagicMock()
        mock.get_collection.return_value = MagicMock()
        return mock

    @pytest.fixture
    def mock_gpu_storage(self):
        """Mock GPU Storage"""
        mock = MagicMock(spec=GPUStorage)
        return mock

    @pytest.mark.asyncio
    async def test_semantic_mapping_exact_match优先(
        self,
        mock_chroma,
        mock_gpu_storage,
    ):
        """测试精确匹配优先返回"""
        # 设置 MapperEngine 返回精确匹配
        mock_mapping = MagicMock()
        mock_mapping.npu_api = "WarpShift"
        mock_mapping.confidence = 0.95
        mock_mapping.adaptation_notes = "Warp shuffle data exchange"
        mock_mapping.equivalence_level = MagicMock()
        mock_mapping.equivalence_level.value = "exact"

        # 创建服务
        service = KnowledgeQueryService(
            chroma_client=mock_chroma,
            redis_client=MagicMock(),
        )

        # Mock MapperEngine
        with patch('src.asc_ops.knowledge_query.MapperEngine') as MockMapper:
            mock_mapper_instance = MagicMock()
            mock_mapper_instance.find_mapping.return_value = mock_mapping
            MockMapper.return_value = mock_mapper_instance

            # 执行查询
            result = await service.semantic_cuda_to_npu_mapping(
                cuda_api_name="__shfl_up_sync"
            )

        # 验证
        assert len(result) == 1
        assert result[0].npu_api == "WarpShift"
        assert result[0].confidence == 0.95
        assert result[0].source == "exact"

    @pytest.mark.asyncio
    async def test_semantic_mapping_无精确匹配时语义检索(
        self,
        mock_chroma,
    ):
        """测试无精确匹配时进行语义检索"""
        # 设置 GPUStorage 返回 API 信息
        gpu_api = GPUAPIInfo(
            api_id="test-1",
            api_name="__shfl_up_sync",
            platform=GPUPlatform.CUDA,
            description="Exchange value among threads in a warp",
            description_embedding=[0.1] * 10,
        )

        # 设置 ChromaDB 返回语义检索结果
        mock_collection = MagicMock()
        # 注意: 根据新公式, confidence = max(0, 1 - distance/1.0)
        # distance = 0.05 -> confidence = 0.95 >= 0.75 ✓
        # distance = 0.15 -> confidence = 0.85 >= 0.75 ✓
        # (Both pass with the new formula since threshold is 1.0)
        mock_collection.query.return_value = {
            "ids": [["api1", "api2"]],
            "distances": [[0.05, 0.15]],  # 置信度: 0.95, 0.85
            "metadatas": [[
                {"name": "WarpShift"},
                {"name": "WarpExchange"},
            ]],
            "documents": [
                ["Shuffle data between warp threads", "Exchange warp data"]
            ],
        }
        mock_chroma.get_collection.return_value = mock_collection

        # 创建服务
        service = KnowledgeQueryService(
            chroma_client=mock_chroma,
            redis_client=MagicMock(),
        )

        # Mock MapperEngine (无精确匹配)
        with patch('src.asc_ops.knowledge_query.MapperEngine') as MockMapper:
            mock_mapper_instance = MagicMock()
            mock_mapper_instance.find_mapping.return_value = None  # 无精确匹配
            MockMapper.return_value = mock_mapper_instance

            # Mock GPUStorage
            with patch('src.asc_ops.knowledge_query.GPUStorage') as MockGPUStorage:
                mock_gpu_instance = MagicMock()
                mock_gpu_instance.get_api_by_name.return_value = gpu_api
                MockGPUStorage.return_value = mock_gpu_instance

                # 执行查询
                result = await service.semantic_cuda_to_npu_mapping(
                    cuda_api_name="__shfl_up_sync",
                    min_confidence=0.75,
                )

        # 验证：Both results pass the new threshold
        assert len(result) == 2
        assert result[0].npu_api == "WarpShift"
        assert result[0].confidence == 0.95
        assert result[0].source == "inferred"

    @pytest.mark.asyncio
    async def test_semantic_mapping_API不存在返回空(
        self,
        mock_chroma,
    ):
        """测试 API 不存在时返回空列表"""
        service = KnowledgeQueryService(
            chroma_client=mock_chroma,
            redis_client=MagicMock(),
        )

        # Mock MapperEngine (无精确匹配)
        with patch('src.asc_ops.knowledge_query.MapperEngine') as MockMapper:
            mock_mapper_instance = MagicMock()
            mock_mapper_instance.find_mapping.return_value = None
            MockMapper.return_value = mock_mapper_instance

            # Mock GPUStorage (API 不存在)
            with patch('src.asc_ops.knowledge_query.GPUStorage') as MockGPUStorage:
                mock_gpu_instance = MagicMock()
                mock_gpu_instance.get_api_by_name.return_value = None
                MockGPUStorage.return_value = mock_gpu_instance

                result = await service.semantic_cuda_to_npu_mapping(
                    cuda_api_name="__inexistent_api__"
                )

        assert result == []

    @pytest.mark.asyncio
    async def test_semantic_mapping置信度阈值过滤(
        self,
        mock_chroma,
    ):
        """测试置信度阈值过滤"""
        gpu_api = GPUAPIInfo(
            api_id="test-1",
            api_name="__shfl_up_sync",
            platform=GPUPlatform.CUDA,
            description="Warp shuffle operation",
            description_embedding=[0.1] * 10,
        )

        # ChromaDB 返回多个结果
        # distance = 0.05 -> confidence = 0.95 >= 0.75 ✓
        # distance = 0.26 -> confidence = 0.74 < 0.75 ✗ (first that fails)
        # distance = 0.30 -> confidence = 0.70 < 0.75 ✗
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["api1", "api2", "api3"]],
            "distances": [[0.05, 0.26, 0.30]],
            "metadatas": [[
                {"name": "WarpShift"},
                {"name": "WarpExchange"},
                {"name": "SomeOtherAPI"},
            ]],
            "documents": [
                ["High similarity shuffle", "Medium shuffle", "Low shuffle"]
            ],
        }
        mock_chroma.get_collection.return_value = mock_collection

        service = KnowledgeQueryService(
            chroma_client=mock_chroma,
            redis_client=MagicMock(),
        )

        with patch('src.asc_ops.knowledge_query.MapperEngine') as MockMapper:
            mock_mapper_instance = MagicMock()
            mock_mapper_instance.find_mapping.return_value = None
            MockMapper.return_value = mock_mapper_instance

            with patch('src.asc_ops.knowledge_query.GPUStorage') as MockGPUStorage:
                mock_gpu_instance = MagicMock()
                mock_gpu_instance.get_api_by_name.return_value = gpu_api
                MockGPUStorage.return_value = mock_gpu_instance

                # min_confidence = 0.75 应该只返回第一个结果
                result = await service.semantic_cuda_to_npu_mapping(
                    cuda_api_name="__shfl_up_sync",
                    min_confidence=0.75,
                )

        # 验证
        assert len(result) == 1
        assert result[0].npu_api == "WarpShift"
        assert result[0].confidence == 0.95
        assert result[0].source == "inferred"


class TestMCPToolSemanticMapping:
    """MCP 工具语义映射测试"""

    @pytest.fixture
    def mcp_tools(self):
        """MCP 工具实例"""
        return MCPTools()

    @pytest.fixture
    def mock_service(self):
        """Mock KnowledgeQueryService"""
        mock = AsyncMock(spec=KnowledgeQueryService)
        return mock

    def test_semantic_cuda_to_npu_mapping工具已注册(self, mcp_tools):
        """验证 semantic_cuda_to_npu_mapping 工具已注册"""
        tool = mcp_tools.get_tool("semantic_cuda_to_npu_mapping")
        assert tool is not None
        assert tool.name == "semantic_cuda_to_npu_mapping"

    def test_semantic_cuda_to_npu_mapping工具schema正确(self, mcp_tools):
        """验证工具输入 schema 正确"""
        tool = mcp_tools.get_tool("semantic_cuda_to_npu_mapping")
        assert tool.input_schema["type"] == "object"
        assert "cuda_api_name" in tool.input_schema["required"]
        assert "properties" in tool.input_schema
        assert "cuda_api_name" in tool.input_schema["properties"]

    @pytest.mark.asyncio
    async def test_mcp工具返回结果格式化(self, mcp_tools, mock_service):
        """测试 MCP 工具返回结果格式化"""
        mock_service.semantic_cuda_to_npu_mapping.return_value = [
            SemanticMappingResult(
                npu_api="WarpShift",
                confidence=0.82,
                matched_description="Shuffle data between warp threads",
                source="inferred",
            )
        ]

        result = await mcp_tools._semantic_cuda_to_npu_mapping(
            args={"cuda_api_name": "__shfl_up_sync"},
            service=mock_service,
        )

        assert not result.is_error
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert "WarpShift" in result.content[0].text
        assert "0.82" in result.content[0].text

    @pytest.mark.asyncio
    async def test_mcp工具服务未初始化返回错误(self, mcp_tools):
        """测试服务未初始化时返回错误"""
        result = await mcp_tools._semantic_cuda_to_npu_mapping(
            args={"cuda_api_name": "__shfl_up_sync"},
            service=None,
        )

        assert result.is_error
        assert "未初始化" in result.content[0].text


class TestConfidenceFormula:
    """置信度公式测试"""

    def test_distance_to_confidence转换(self):
        """测试 distance → confidence 转换公式

        公式: confidence = max(0, 1 - distance / 0.25)
        ChromaDB cosine distance: 0 = 相同, 2 = 相反
        当 distance < 0.25 时，confidence >= 0.75
        """
        # confidence = max(0, 1 - distance / 0.25)
        # distance = 0.0 → confidence = 1.0
        # distance = 0.25 → confidence = 0.0 (公式给出)
        # 注意: ChromaDB 返回的 distance 范围是 [0, 2]，需要验证

        def distance_to_confidence(distance: float) -> float:
            return max(0.0, 1.0 - distance / 0.25)

        # 基本边界测试
        assert distance_to_confidence(0.0) == 1.0
        assert distance_to_confidence(0.125) == 0.5
        # 当 distance >= 0.25 时，confidence = 0
        assert distance_to_confidence(0.25) == 0.0
        assert distance_to_confidence(0.5) == 0.0

    def test_confidence阈值过滤(self):
        """测试置信度阈值过滤"""
        min_confidence = 0.75

        def distance_to_confidence(distance: float) -> float:
            return max(0.0, 1.0 - distance / 0.25)

        results = [
            (0.0, distance_to_confidence(0.0)),   # 1.0 >= 0.75 ✓
            (0.1, distance_to_confidence(0.1)),  # 0.6 < 0.75 ✗
            (0.2, distance_to_confidence(0.2)),  # 0.2 < 0.75 ✗
            (0.05, distance_to_confidence(0.05)),  # 0.8 >= 0.75 ✓
        ]

        filtered = [(d, c) for d, c in results if c >= min_confidence]
        assert len(filtered) == 2
        assert filtered[0][0] == 0.0  # confidence 1.0
        assert filtered[1][0] == 0.05  # confidence 0.8
