# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
MCP 工具测试
"""

import pytest

from src.asc_ops.mcp.tools import MCPTools
from src.asc_ops.mcp.models import MCPTool, MCPToolResult, MCPContentBlock


class TestMCPTools:
    """MCP 工具测试"""

    def setup_method(self):
        """设置测试"""
        self.tools = MCPTools()

    def test_list_tools(self):
        """列出所有工具"""
        tools = self.tools.list_tools()

        assert len(tools) == 4
        tool_names = [t.name for t in tools]
        assert "query_for_development" in tool_names
        assert "query_for_troubleshooting" in tool_names
        assert "query_api" in tool_names
        assert "query_cross_platform" in tool_names

    def test_get_tool(self):
        """获取指定工具"""
        tool = self.tools.get_tool("query_for_development")

        assert tool is not None
        assert tool.name == "query_for_development"
        assert "operator_name" in tool.input_schema["properties"]

    def test_get_nonexistent_tool(self):
        """获取不存在的工具"""
        tool = self.tools.get_tool("nonexistent")

        assert tool is None

    def test_tool_descriptions(self):
        """验证工具描述"""
        tools = self.tools.list_tools()

        for tool in tools:
            assert tool.description
            assert len(tool.description) > 10

    def test_query_for_development_schema(self):
        """验证 query_for_development 参数 schema"""
        tool = self.tools.get_tool("query_for_development")

        assert "operator_name" in tool.input_schema["required"]
        assert tool.input_schema["properties"]["operator_name"]["type"] == "string"
        assert tool.input_schema["properties"]["query_type"]["enum"] == ["bug", "optimization", "all"]

    def test_query_for_troubleshooting_schema(self):
        """验证 query_for_troubleshooting 参数 schema"""
        tool = self.tools.get_tool("query_for_troubleshooting")

        assert "symptom" in tool.input_schema["required"]
        assert tool.input_schema["properties"]["symptom"]["type"] == "string"

    def test_query_api_schema(self):
        """验证 query_api 参数 schema"""
        tool = self.tools.get_tool("query_api")

        assert tool.input_schema["properties"]["api_name"]["type"] == "string"
        assert tool.input_schema["properties"]["semantic_query"]["type"] == "string"
        assert tool.input_schema["properties"]["category"]["enum"] == ["memory", "compute", "sync", "tensor", "util"]

    def test_query_cross_platform_schema(self):
        """验证 query_cross_platform 参数 schema"""
        tool = self.tools.get_tool("query_cross_platform")

        assert "gpu_api" in tool.input_schema["required"]
        assert tool.input_schema["properties"]["gpu_platform"]["enum"] == ["cuda", "cutlass", "cublas", "cudnn"]

    @pytest.mark.asyncio
    async def test_call_tool_without_service(self):
        """无服务时调用工具"""
        result = await self.tools.call_tool(
            name="query_for_development",
            arguments={"operator_name": "Matmul"},
            knowledge_query_service=None,
        )

        assert isinstance(result, MCPToolResult)
        assert len(result.content) == 1
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self):
        """调用未知工具"""
        result = await self.tools.call_tool(
            name="unknown_tool",
            arguments={},
            knowledge_query_service=None,
        )

        assert isinstance(result, MCPToolResult)
        assert "Unknown tool" in result.content[0].text
        assert result.is_error is True


class TestMCPToolResult:
    """MCPToolResult 测试"""

    def test_tool_result_creation(self):
        """创建工具结果"""
        result = MCPToolResult(
            content=[
                MCPContentBlock(type="text", text="Test result")
            ],
            is_error=False
        )

        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert result.content[0].text == "Test result"
        assert result.is_error is False

    def test_tool_result_with_multiple_blocks(self):
        """多内容块结果"""
        result = MCPToolResult(
            content=[
                MCPContentBlock(type="text", text="Block 1"),
                MCPContentBlock(type="text", text="Block 2"),
            ],
            is_error=False
        )

        assert len(result.content) == 2


class TestMCPContentBlock:
    """MCPContentBlock 测试"""

    def test_text_block(self):
        """文本块"""
        block = MCPContentBlock(type="text", text="Hello, world!")

        assert block.type == "text"
        assert block.text == "Hello, world!"
        assert block.data is None

    def test_resource_block(self):
        """资源块"""
        block = MCPContentBlock(
            type="resource",
            data="base64_encoded_data",
            mime_type="image/png"
        )

        assert block.type == "resource"
        assert block.data == "base64_encoded_data"
        assert block.mime_type == "image/png"
