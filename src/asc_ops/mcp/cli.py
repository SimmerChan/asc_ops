# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
MCP Server CLI 入口
"""

import logging
import sys

from .server import MCPServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)


def main():
    """MCP Server 入口"""
    server = MCPServer()

    # 可以在这里初始化知识查询服务和映射引擎
    # from asc_ops.knowledge_query import KnowledgeQueryService
    # from asc_ops.mapper import MapperEngine
    #
    # server.set_knowledge_query_service(KnowledgeQueryService())
    # server.set_mapper_engine(MapperEngine())

    # 运行服务器
    server.run()


if __name__ == "__main__":
    main()
