# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
ChromaDB Collections 配置

定义知识库的 collection 类型和配置
"""

from enum import Enum
from typing import Optional


class CollectionType(Enum):
    """知识库 collection 类型"""

    ASCEND_APIS = "ascend_apis"
    BUG_FIXES = "bug_fixes"
    OPTIMIZATIONS = "optimizations"
    CROSS_PLATFORM_MAPPINGS = "cross_platform_mappings"
    GPU_APIS = "gpu_apis"  # GPU API 知识库（CUDA/CUB/CUTLASS 等）


# Collection 配置映射
COLLECTION_CONFIGS: dict[CollectionType, dict] = {
    CollectionType.ASCEND_APIS: {
        "name": "ascend_apis",
        "metadata": {
            "description": "AscendC API 知识向量库",
            "version": "1.0",
            "knowledge_type": "api",
        },
        "index_params": {
            "hnsw_space_type": "cosine",
            "hnsw_construction_ef": 100,
            "hnsw_search_ef": 100,
        },
    },
    CollectionType.BUG_FIXES: {
        "name": "bug_fixes",
        "metadata": {
            "description": "NPU 算子 Bug 修复知识库",
            "version": "1.0",
            "knowledge_type": "bug_fix",
        },
        "index_params": {
            "hnsw_space_type": "cosine",
            "hnsw_construction_ef": 100,
            "hnsw_search_ef": 100,
        },
    },
    CollectionType.OPTIMIZATIONS: {
        "name": "optimizations",
        "metadata": {
            "description": "NPU 算子优化知识库",
            "version": "1.0",
            "knowledge_type": "optimization",
        },
        "index_params": {
            "hnsw_space_type": "cosine",
            "hnsw_construction_ef": 100,
            "hnsw_search_ef": 100,
        },
    },
    CollectionType.CROSS_PLATFORM_MAPPINGS: {
        "name": "cross_platform_mappings",
        "metadata": {
            "description": "GPU-NPU 跨平台映射知识库",
            "version": "1.0",
            "knowledge_type": "cross_platform_mapping",
        },
        "index_params": {
            "hnsw_space_type": "cosine",
            "hnsw_construction_ef": 100,
            "hnsw_search_ef": 100,
        },
    },
    CollectionType.GPU_APIS: {
        "name": "gpu_apis",
        "metadata": {
            "description": "GPU API 知识库（CUDA/CUB/CUTLASS 等）",
            "version": "1.0",
            "knowledge_type": "gpu_api",
        },
        "index_params": {
            "hnsw_space_type": "cosine",
            "hnsw_construction_ef": 100,
            "hnsw_search_ef": 100,
        },
    },
}


def get_collection_config(collection_type: CollectionType) -> dict:
    """
    获取指定 collection 类型的配置

    Args:
        collection_type: CollectionType 枚举值

    Returns:
        Collection 配置字典
    """
    return COLLECTION_CONFIGS[collection_type]


def get_collection_name(collection_type: CollectionType) -> str:
    """
    获取指定 collection 类型的名称

    Args:
        collection_type: CollectionType 枚举值

    Returns:
        Collection 名称字符串
    """
    return COLLECTION_CONFIGS[collection_type]["name"]


def get_all_collection_names() -> list[str]:
    """
    获取所有 collection 名称

    Returns:
        Collection 名称列表
    """
    return [config["name"] for config in COLLECTION_CONFIGS.values()]


def ensure_collection_exists(
    chroma_client, collection_type: CollectionType
) -> "chromadb.Collection":
    """
    确保指定的 collection 存在，不存在则创建

    Args:
        chroma_client: ChromaDBClient 实例
        collection_type: CollectionType 枚举值

    Returns:
        ChromaDB Collection 对象
    """
    config = get_collection_config(collection_type)
    return chroma_client.get_or_create_collection(
        name=config["name"],
        metadata=config["metadata"],
    )
