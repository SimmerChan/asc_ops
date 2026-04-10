# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
MCP 协议数据模型
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from enum import Enum


class MCPMethod(Enum):
    """MCP 方法"""
    INITIALIZE = "initialize"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    SHUTDOWN = "shutdown"


class MCPErrorCode(Enum):
    """MCP 错误码"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


@dataclass
class MCPMessage:
    """MCP 消息基类"""
    jsonrpc: str = "2.0"


@dataclass
class MCPRequest(MCPMessage):
    """MCP 请求"""
    id: Optional[str] = None
    method: str = ""


@dataclass
class MCPResponse(MCPMessage):
    """MCP 响应"""
    id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional["MCPError"] = None


@dataclass
class MCPError:
    """MCP 错误"""
    code: int
    message: str
    data: Optional[Any] = None


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPToolCall:
    """MCP 工具调用"""
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolsResponse:
    """tools/list 响应"""
    tools: List[MCPTool]


@dataclass
class MCPToolResult:
    """工具执行结果"""
    content: List["MCPContentBlock"]
    is_error: bool = False


@dataclass
class MCPContentBlock:
    """MCP 内容块"""
    type: str  # "text" | "image" | "resource"
    text: Optional[str] = None
    data: Optional[str] = None
    mime_type: Optional[str] = None


@dataclass
class MCPInitializeResult:
    """initialize 响应"""
    protocol_version: str = "2024-11-05"
    capabilities: Dict[str, Any] = field(default_factory=lambda: {
        "tools": {}
    })
    server_info: Dict[str, str] = field(default_factory=lambda: {
        "name": "asc-ops-mcp",
        "version": "0.1.0"
    })
