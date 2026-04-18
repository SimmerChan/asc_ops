# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
MCP 集成测试

测试 MCP Server 与其他组件的集成
"""

import pytest
import json

from src.asc_ops.mcp.server import MCPServer
from src.asc_ops.mcp.tools import MCPTools
from src.asc_ops.mapper import MapperEngine
from src.asc_ops.gpu_collector.storage import GPUStorage
from src.asc_ops.gpu_collector.models import CrossPlatformMapping, GPUPlatform, MappingEquivalenceLevel


class TestMCPIntegration:
    """MCP 集成测试"""

    def setup_method(self):
        """设置测试"""
        self.server = MCPServer()
        self.tools = MCPTools()
        # 使用 mock 存储
        self.storage = GPUStorage(use_mock=True)
        # 种子测试数据：__syncthreads -> SyncAll
        self.storage.store_cross_platform_mapping(CrossPlatformMapping(
            mapping_id="test-sync",
            gpu_api="__syncthreads",
            npu_api="SyncAll",
            platform=GPUPlatform.CUDA,
            equivalence_level=MappingEquivalenceLevel.EXACT,
            adaptation_notes="CUDA sync threads to AscendC sync",
            confidence=0.95,
            source="test",
        ))
        self.mapper = MapperEngine(storage=self.storage)

    def test_server_with_mapper_engine(self):
        """服务器配置映射引擎"""
        self.server.set_mapper_engine(self.mapper)

        assert self.server._mapper_engine is not None

    def test_server_with_knowledge_service(self):
        """服务器配置知识查询服务"""
        mock_service = object()
        self.server.set_knowledge_query_service(mock_service)

        assert self.server._knowledge_query_service is mock_service

    def test_tools_list_all_tools(self):
        """工具列表包含所有工具"""
        tools = self.tools.list_tools()

        assert len(tools) == 4

        tool_names = [t.name for t in tools]
        assert "query_for_development" in tool_names
        assert "query_for_troubleshooting" in tool_names
        assert "query_api" in tool_names
        assert "query_cross_platform" in tool_names

    def test_cross_platform_tool_with_mapper(self):
        """跨平台工具使用映射引擎"""
        # 设置映射引擎
        self.server.set_mapper_engine(self.mapper)

        # 使用映射引擎直接查询
        result = self.mapper.find_mapping("__syncthreads", "cuda")

        assert result is not None
        assert result.npu_api == "SyncAll"

    def test_initialize_request(self):
        """处理 initialize 请求"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        }

        response = self.server._handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["serverInfo"]["name"] == "asc-ops-mcp"

    def test_tools_list_request(self):
        """处理 tools/list 请求"""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }

        response = self.server._handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert len(response["result"]["tools"]) == 4

    def test_tools_call_unknown_tool(self):
        """调用未知工具返回错误"""
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "unknown_tool",
                "arguments": {}
            }
        }

        response = self.server._handle_request(request)

        assert response["result"]["isError"] is True
        assert "Unknown tool" in response["result"]["content"][0]["text"]

    def test_tools_call_without_service(self):
        """调用工具但服务不可用"""
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "query_for_development",
                "arguments": {"operator_name": "Matmul"}
            }
        }

        response = self.server._handle_request(request)

        assert response["result"]["isError"] is True


class TestMCPWithMapper:
    """MCP 与映射引擎集成测试"""

    def test_query_cross_platform_flow(self):
        """跨平台查询完整流程"""
        mapper = MapperEngine()
        server = MCPServer()
        server.set_mapper_engine(mapper)

        # 模拟请求
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "query_cross_platform",
                "arguments": {
                    "gpu_api": "__syncthreads",
                    "gpu_platform": "cuda"
                }
            }
        }

        response = server._handle_request(request)

        assert "result" in response
        assert response["result"]["isError"] is False
