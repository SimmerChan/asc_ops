# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
MCP Server CLI 入口
"""

import logging
import sys
import os

from .server import MCPServer

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


def initialize_services():
    """
    初始化知识查询服务和映射引擎

    Returns:
        tuple: (knowledge_query_service, mapper_engine) 或 (None, None) 如果初始化失败
    """
    knowledge_service = None
    mapper_engine = None

    try:
        # 导入依赖
        from ..knowledge_query import KnowledgeQueryService
        from ..mapper import MapperEngine
        from ..gpu_collector.storage import GPUStorage

        # 获取配置
        chroma_db_path = os.environ.get("CHROMA_DB_PATH", "./data/chroma_db")
        redis_host = os.environ.get("REDIS_HOST", "localhost")
        redis_port = int(os.environ.get("REDIS_PORT", "6379"))
        redis_db = int(os.environ.get("REDIS_DB", "0"))
        redis_password = os.environ.get("REDIS_PASSWORD", None)

        # 初始化 GPU 存储 (use_mock=False 使用真实存储)
        use_mock_storage = os.environ.get("USE_MOCK_STORAGE", "false").lower() == "true"
        gpu_storage = GPUStorage(use_mock=use_mock_storage)

        # 初始化知识查询服务
        knowledge_service = KnowledgeQueryService(
            chroma_db_path=chroma_db_path,
            base_url="http://localhost:8000",
        )
        logger.info("KnowledgeQueryService initialized successfully")

        # 初始化映射引擎
        mapper_engine = MapperEngine(storage=gpu_storage)
        logger.info("MapperEngine initialized successfully")

        return knowledge_service, mapper_engine

    except ImportError as e:
        logger.warning(f"Failed to import required modules: {e}")
        return None, None
    except Exception as e:
        logger.warning(f"Failed to initialize services: {e}")
        return None, None


def main():
    """MCP Server 入口"""
    server = MCPServer()

    # 初始化服务
    knowledge_service, mapper_engine = initialize_services()

    if knowledge_service is not None and mapper_engine is not None:
        server.set_knowledge_query_service(knowledge_service)
        server.set_mapper_engine(mapper_engine)
        logger.info("MCP Server services configured successfully")
    else:
        logger.warning("MCP Server starting without services - tools will return 'service not available'")

    # 运行服务器
    server.run()


if __name__ == "__main__":
    main()
