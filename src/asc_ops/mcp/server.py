# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
MCP Server 实现

基于 stdio 的 JSON-RPC 服务器
"""

import json
import logging
import sys
from typing import Optional, Dict, Any

from .models import (
    MCPMessage,
    MCPRequest,
    MCPResponse,
    MCPError,
    MCPErrorCode,
    MCPToolsResponse,
    MCPInitializeResult,
)
from .tools import MCPTools

logger = logging.getLogger(__name__)


class MCPServer:
    """
    MCP Server

    使用 stdio 传输的 JSON-RPC 服务器
    """

    def __init__(self):
        """初始化 MCP Server"""
        self._initialized = False
        self._protocol_version = "2024-11-05"
        self._tools = MCPTools()
        self._knowledge_query_service = None
        self._mapper_engine = None

        logger.info("MCP Server initialized")

    def set_knowledge_query_service(self, service):
        """设置知识查询服务"""
        self._knowledge_query_service = service

    def set_mapper_engine(self, engine):
        """设置跨平台映射引擎"""
        self._mapper_engine = engine

    def run(self):
        """
        运行 MCP Server

        从 stdin 读取请求，写入 stdout 响应
        """
        logger.info("MCP Server starting...")

        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                try:
                    request_data = json.loads(line)
                    response = self._handle_request(request_data)

                    if response:
                        response_json = json.dumps(response, ensure_ascii=False)
                        print(response_json, flush=True)

                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    error_response = self._create_error_response(
                        None,
                        MCPErrorCode.PARSE_ERROR,
                        f"Invalid JSON: {str(e)}"
                    )
                    print(json.dumps(error_response, ensure_ascii=False), flush=True)

                except Exception as e:
                    logger.error(f"Error handling request: {e}")
                    error_response = self._create_error_response(
                        request_data.get("id") if isinstance(request_data, dict) else None,
                        MCPErrorCode.INTERNAL_ERROR,
                        f"Internal error: {str(e)}"
                    )
                    print(json.dumps(error_response, ensure_ascii=False), flush=True)

        except KeyboardInterrupt:
            logger.info("MCP Server shutting down...")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            sys.exit(1)

    def _handle_request(self, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理 MCP 请求"""
        if not isinstance(request_data, dict):
            return self._create_error_response(
                None,
                MCPErrorCode.INVALID_REQUEST,
                "Request must be a JSON object"
            )

        request_id = request_data.get("id")
        method = request_data.get("method")

        if not method:
            return self._create_error_response(
                request_id,
                MCPErrorCode.INVALID_REQUEST,
                "Method is required"
            )

        # 处理方法
        if method == "initialize":
            return self._handle_initialize(request_id)
        elif method == "tools/list":
            return self._handle_tools_list(request_id)
        elif method == "tools/call":
            return self._handle_tools_call(request_id, request_data.get("params", {}))
        elif method == "shutdown":
            return self._handle_shutdown(request_id)
        else:
            return self._create_error_response(
                request_id,
                MCPErrorCode.METHOD_NOT_FOUND,
                f"Method not found: {method}"
            )

    def _handle_initialize(self, request_id) -> Dict[str, Any]:
        """处理 initialize 请求"""
        logger.info("Handling initialize request")

        self._initialized = True

        result = MCPInitializeResult(
            protocol_version=self._protocol_version,
            capabilities={"tools": {}},
            server_info={
                "name": "asc-ops-mcp",
                "version": "0.1.0"
            }
        )

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": result.protocol_version,
                "capabilities": result.capabilities,
                "serverInfo": result.server_info,
            }
        }

    def _handle_tools_list(self, request_id) -> Dict[str, Any]:
        """处理 tools/list 请求"""
        logger.info("Handling tools/list request")

        tools = self._tools.list_tools()

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                    }
                    for tool in tools
                ]
            }
        }

    def _handle_tools_call(self, request_id, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 tools/call 请求"""
        logger.info(f"Handling tools/call request: {params}")

        import asyncio

        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return self._create_error_response(
                request_id,
                MCPErrorCode.INVALID_PARAMS,
                "Tool name is required"
            )

        # 异步调用工具
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self._tools.call_tool(
                    name=tool_name,
                    arguments=arguments,
                    knowledge_query_service=self._knowledge_query_service,
                    mapper_engine=self._mapper_engine,
                )
            )
        finally:
            loop.close()

        # 格式化响应
        content = []
        for block in result.content:
            if block.type == "text":
                content.append({
                    "type": "text",
                    "text": block.text
                })

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": content,
                "isError": result.is_error,
            }
        }

    def _handle_shutdown(self, request_id) -> Dict[str, Any]:
        """处理 shutdown 请求"""
        logger.info("Handling shutdown request")

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {}
        }

    def _create_error_response(
        self,
        request_id,
        error_code: MCPErrorCode,
        message: str,
        data: Any = None
    ) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": error_code.value,
                "message": message,
                "data": data,
            }
        }
