# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
AscendC知识库存储层

提供 ChromaDB (向量存储) 和 Redis (KV存储) 的统一抽象
"""

from .chroma_client import ChromaDBClient
from .collections import CollectionType, get_collection_config
from .redis_client import RedisClient

__all__ = [
    "ChromaDBClient",
    "CollectionType",
    "get_collection_config",
    "RedisClient",
]
