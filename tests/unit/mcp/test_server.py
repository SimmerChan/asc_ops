# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
MCP Server 测试
"""

import json
import pytest

from src.asc_ops.mcp.server import MCPServer
from src.asc_ops.mcp.models import MCPErrorCode


class TestMCPServer:
    """MCP Server 测试"""

    def setup_method(self):
        """设置测试"""
        self.server = MCPServer()

    def test_server_initialization(self):
        """服务器初始化"""
        assert self.server._initialized is False
        assert self.server._protocol_version == "2024-11-05"
        assert self.server._tools is not None

    def test_set_knowledge_query_service(self):
        """设置知识查询服务"""
        mock_service = object()
        self.server.set_knowledge_query_service(mock_service)
        assert self.server._knowledge_query_service is mock_service

    def test_set_mapper_engine(self):
        """设置映射引擎"""
        mock_engine = object()
        self.server.set_mapper_engine(mock_engine)
        assert self.server._mapper_engine is mock_engine

    def test_handle_initialize(self):
        """处理 initialize 请求"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        }

        response = self.server._handle_request(request_data)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["protocolVersion"] == "2024-11-05"
        assert response["result"]["serverInfo"]["name"] == "asc-ops-mcp"
        assert self.server._initialized is True

    def test_handle_tools_list(self):
        """处理 tools/list 请求"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }

        response = self.server._handle_request(request_data)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert "result" in response
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) == 4

        tool_names = [t["name"] for t in response["result"]["tools"]]
        assert "query_for_development" in tool_names
        assert "query_for_troubleshooting" in tool_names
        assert "query_api" in tool_names
        assert "query_cross_platform" in tool_names

    def test_handle_tools_call_unknown_tool(self):
        """处理 tools/call 调用未知工具"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "unknown_tool",
                "arguments": {}
            }
        }

        response = self.server._handle_request(request_data)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 3
        assert "result" in response
        assert response["result"]["isError"] is True
        assert "Unknown tool" in response["result"]["content"][0]["text"]

    def test_handle_tools_call_missing_name(self):
        """处理 tools/call 缺少工具名"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "arguments": {}
            }
        }

        response = self.server._handle_request(request_data)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 4
        assert "error" in response
        assert response["error"]["code"] == MCPErrorCode.INVALID_PARAMS.value

    def test_handle_shutdown(self):
        """处理 shutdown 请求"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "shutdown"
        }

        response = self.server._handle_request(request_data)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 5
        assert "result" in response
        assert response["result"] == {}

    def test_handle_method_not_found(self):
        """处理未知方法"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "unknown_method"
        }

        response = self.server._handle_request(request_data)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 6
        assert "error" in response
        assert response["error"]["code"] == MCPErrorCode.METHOD_NOT_FOUND.value

    def test_handle_invalid_request_no_method(self):
        """处理无效请求（无 method）"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 7
        }

        response = self.server._handle_request(request_data)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 7
        assert "error" in response
        assert response["error"]["code"] == MCPErrorCode.INVALID_REQUEST.value

    def test_handle_invalid_request_not_dict(self):
        """处理无效请求（非字典）"""
        response = self.server._handle_request("not a dict")

        assert response["jsonrpc"] == "2.0"
        assert response["id"] is None
        assert "error" in response
        assert response["error"]["code"] == MCPErrorCode.INVALID_REQUEST.value

    def test_create_error_response(self):
        """创建错误响应"""
        response = self.server._create_error_response(
            request_id=1,
            error_code=MCPErrorCode.INTERNAL_ERROR,
            message="Test error",
            data={"extra": "info"}
        )

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["error"]["code"] == MCPErrorCode.INTERNAL_ERROR.value
        assert response["error"]["message"] == "Test error"
        assert response["error"]["data"] == {"extra": "info"}

    def test_tools_call_with_service_unavailable(self):
        """tools/call 服务不可用时返回错误"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "query_for_development",
                "arguments": {"operator_name": "Matmul"}
            }
        }

        response = self.server._handle_request(request_data)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 8
        assert "result" in response
        assert response["result"]["isError"] is True
        assert "not available" in response["result"]["content"][0]["text"]
