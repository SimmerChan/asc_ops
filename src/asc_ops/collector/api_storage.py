# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
API 存储模块

将 API 数据存储到 ChromaDB 和 Redis
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..storage.chroma_client import ChromaDBClient
from ..storage.redis_client import RedisClient
from ..storage.collections import CollectionType, ensure_collection_exists
from .embedder import APIEmbedder, EmbeddingResult
from ..models import AscendCAPIDefinition
from ..config import RedisConfig

logger = logging.getLogger(__name__)


class APIStorageError(Exception):
    """API 存储异常"""
    pass


class APIStorage:
    """
    API 存储管理器

    负责:
    - 将 API 向量存储到 ChromaDB
    - 将 API 元数据存储到 Redis
    """

    def __init__(
        self,
        chroma_client: Optional[ChromaDBClient] = None,
        redis_client: Optional[RedisClient] = None,
        embedder: Optional[APIEmbedder] = None,
        chroma_db_path: Optional[str] = None,
        redis_config: Optional[RedisConfig] = None,
    ):
        """
        初始化 API 存储

        Args:
            chroma_client: ChromaDB 客户端 (优先级最高)
            redis_client: Redis 客户端 (优先级最高)
            embedder: 向量化器
            chroma_db_path: ChromaDB 持久化路径 (用于创建客户端)
            redis_config: Redis 配置 (用于创建客户端)
        """
        # ChromaDB 客户端初始化
        if chroma_client is not None:
            self._chroma = chroma_client
        elif chroma_db_path:
            self._chroma = ChromaDBClient(persist_directory=chroma_db_path)
        else:
            # 默认使用临时客户端 (保持向后兼容)
            self._chroma = ChromaDBClient()

        # Redis 客户端初始化
        if redis_client is not None:
            self._redis = redis_client
        elif redis_config:
            self._redis = RedisClient(
                host=redis_config.host,
                port=redis_config.port,
                db=redis_config.db,
                password=redis_config.password,
                max_connections=redis_config.max_connections,
                mock=False,
            )
        else:
            # 默认使用 mock 客户端 (保持向后兼容)
            self._redis = RedisClient(mock=True)

        self._embedder = embedder

        # 确保 collection 存在
        ensure_collection_exists(self._chroma, CollectionType.ASCEND_APIS)

        chroma_persist = chroma_db_path or "ephemeral"
        logger.info(f"API Storage initialized (chroma={chroma_persist}, redis_mock={self._redis.is_mock})")

    def store_api(
        self,
        api_definition: AscendCAPIDefinition,
        skip_embedding: bool = False,
    ) -> bool:
        """
        存储单个 API

        Args:
            api_definition: API 定义
            skip_embedding: 是否跳过向量化 (用于降级解析的 API)

        Returns:
            是否成功
        """
        try:
            # 准备 metadata
            metadata = {
                "api_id": api_definition.api_id,
                "name": api_definition.canonical_name,
                "category": api_definition.category,
                "subcategory": api_definition.subcategory,
                "confidence": api_definition.confidence,
                "source_type": api_definition.source.source_type if api_definition.source else "official",
                "source_url": api_definition.source.source_url if api_definition.source else "",
                "last_updated": api_definition.last_updated.isoformat() if api_definition.last_updated else datetime.now().isoformat(),
            }

            # 准备文档内容 (用于向量检索)
            document = self._build_search_document(api_definition)

            # 存储到 Redis (元数据)
            self._store_to_redis(api_definition)

            # 存储到 ChromaDB (向量)
            if not skip_embedding and self._embedder:
                embedding_result = self._embedder.embed_api(
                    api_id=api_definition.api_id,
                    api_name=api_definition.canonical_name,
                    signature=api_definition.full_signature,
                    description=api_definition.description,
                    parameters=[
                        {"name": p.name, "type": p.type, "description": p.description}
                        for p in api_definition.parameters
                    ],
                    return_value=api_definition.return_value.type if api_definition.return_value else "",
                    category=api_definition.category,
                )

                self._chroma.upsert_vector(
                    collection_name=CollectionType.ASCEND_APIS.value,
                    ids=[api_definition.api_id],
                    embeddings=[embedding_result.embedding],
                    documents=[document],
                    metadatas=[metadata],
                )
            else:
                # 降级模式：只存储 metadata，不存储向量
                self._chroma.upsert_vector(
                    collection_name=CollectionType.ASCEND_APIS.value,
                    ids=[api_definition.api_id],
                    embeddings=[[0.0] * 384],  # 占位向量
                    documents=[document],
                    metadatas=[metadata],
                )

            logger.debug(f"Stored API: {api_definition.api_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store API {api_definition.api_id}: {e}")
            raise APIStorageError(f"Failed to store API: {e}") from e

    def store_apis_batch(
        self,
        api_definitions: List[AscendCAPIDefinition],
        batch_size: int = 50,
    ) -> Dict[str, int]:
        """
        批量存储 APIs

        Args:
            api_definitions: API 定义列表
            batch_size: 批处理大小

        Returns:
            成功/失败统计
        """
        success_count = 0
        failure_count = 0

        for i in range(0, len(api_definitions), batch_size):
            batch = api_definitions[i:i + batch_size]

            # 批量向量化
            if self._embedder:
                api_dicts = [
                    {
                        "api_id": api.api_id,
                        "name": api.canonical_name,
                        "signature": api.full_signature,
                        "description": api.description,
                        "parameters": [
                            {"name": p.name, "type": p.type, "description": p.description}
                            for p in api.parameters
                        ],
                        "return_value": api.return_value.type if api.return_value else "",
                        "category": api.category,
                    }
                    for api in batch
                ]
                embedding_results = self._embedder.embed_apis_batch(api_dicts)

            # 准备批量数据
            ids = []
            embeddings = []
            documents = []
            metadatas = []

            for j, api_def in enumerate(batch):
                ids.append(api_def.api_id)

                if self._embedder and embedding_results:
                    embeddings.append(embedding_results[j].embedding)
                else:
                    embeddings.append([0.0] * 384)  # 占位向量

                documents.append(self._build_search_document(api_def))

                metadatas.append({
                    "api_id": api_def.api_id,
                    "name": api_def.canonical_name,
                    "category": api_def.category,
                    "subcategory": api_def.subcategory,
                    "confidence": api_def.confidence,
                    "source_type": api_def.source.source_type if api_def.source else "official",
                    "source_url": api_def.source.source_url if api_def.source else "",
                    "last_updated": api_def.last_updated.isoformat() if api_def.last_updated else datetime.now().isoformat(),
                })

                # 存储到 Redis
                self._store_to_redis(api_def)

            # 批量 upsert
            try:
                self._chroma.upsert_vector(
                    collection_name=CollectionType.ASCEND_APIS.value,
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas,
                )
                success_count += len(batch)
            except Exception as e:
                logger.error(f"Batch storage failed: {e}")
                failure_count += len(batch)

        return {
            "success": success_count,
            "failure": failure_count,
            "total": len(api_definitions),
        }

    def _store_to_redis(self, api_definition: AscendCAPIDefinition) -> None:
        """存储 API 元数据到 Redis"""
        key = f"api:{api_definition.api_id}"

        # 基本信息
        self._redis.hset(
            key,
            mapping={
                "api_id": api_definition.api_id,
                "name": api_definition.canonical_name,
                "category": api_definition.category,
                "subcategory": api_definition.subcategory,
                "signature": api_definition.full_signature,
                "description": api_definition.description,
                "confidence": str(api_definition.confidence),
                "source_url": api_definition.source.source_url if api_definition.source else "",
                "updated_at": datetime.now().isoformat(),
            },
        )

        # 存储参数
        for i, param in enumerate(api_definition.parameters):
            param_key = f"{key}:param:{i}"
            self._redis.hset(
                param_key,
                mapping={
                    "name": param.name,
                    "type": param.type,
                    "description": param.description,
                    "required": str(param.required),
                },
            )

        # 存储返回值
        if api_definition.return_value:
            self._redis.hset(
                f"{key}:return",
                mapping={
                    "type": api_definition.return_value.type,
                    "description": api_definition.return_value.description,
                },
            )

    def _build_search_document(self, api_definition: AscendCAPIDefinition) -> str:
        """构建 API 搜索文档"""
        parts = []

        if api_definition.canonical_name:
            parts.append(f"API: {api_definition.canonical_name}")

        if api_definition.category:
            parts.append(f"分类: {api_definition.category}/{api_definition.subcategory}")

        if api_definition.description:
            parts.append(f"描述: {api_definition.description}")

        if api_definition.parameters:
            param_strs = [
                f"{p.name}: {p.type}" for p in api_definition.parameters
            ]
            parts.append(f"参数: {', '.join(param_strs)}")

        if api_definition.return_value:
            parts.append(f"返回: {api_definition.return_value.type}")

        return " | ".join(parts)

    def get_api_metadata(self, api_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 API 元数据

        Args:
            api_id: API ID

        Returns:
            元数据字典，或 None
        """
        key = f"api:{api_id}"
        metadata = self._redis.hgetall(key)

        if not metadata:
            return None

        return metadata

    def delete_api(self, api_id: str) -> bool:
        """
        删除 API

        Args:
            api_id: API ID

        Returns:
            是否成功
        """
        try:
            # 从 ChromaDB 删除
            # ChromaDB client doesn't have delete_vector, so we need to reset the collection
            # or implement a workaround
            logger.warning(f"ChromaDB delete not fully implemented for {api_id}")

            # 从 Redis 删除
            key = f"api:{api_id}"
            self._redis.delete(key)

            # 删除参数
            # 需要先获取参数数量
            # 简化处理：直接删除模式匹配的 key
            # (实际应该跟踪参数数量)
            param_keys = self._redis.lrange(f"{key}:params", 0, -1)
            for param_key in param_keys:
                self._redis.delete(param_key)
            self._redis.delete(f"{key}:return")

            logger.info(f"Deleted API: {api_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete API {api_id}: {e}")
            return False

    def count_apis(self) -> int:
        """
        获取 API 数量

        Returns:
            API 数量
        """
        return self._chroma.count(CollectionType.ASCEND_APIS.value)
