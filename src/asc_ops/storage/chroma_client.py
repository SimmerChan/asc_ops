# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
ChromaDB 客户端封装

提供向量存储的 CRUD 操作接口
"""

import chromadb
from chromadb.config import Settings
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class ChromaDBClient:
    """ChromaDB 客户端封装类"""

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_settings: Optional[Settings] = None,
    ):
        """
        初始化 ChromaDB 客户端

        Args:
            persist_directory: ChromaDB 持久化目录路径
            collection_settings: ChromaDB 配置
        """
        if persist_directory:
            self._client = chromadb.PersistentClient(
                path=persist_directory,
                settings=collection_settings or Settings(),
            )
        else:
            self._client = chromadb.EphemeralClient(
                settings=collection_settings or Settings()
            )
        logger.info(
            f"ChromaDB client initialized (persist_directory={persist_directory})"
        )

    def get_collection(self, name: str) -> "chromadb.Collection":
        """
        获取指定的 collection

        Args:
            name: collection 名称

        Returns:
            ChromaDB Collection 对象
        """
        return self._client.get_collection(name=name)

    def get_or_create_collection(
        self, name: str, metadata: Optional[dict] = None
    ) -> "chromadb.Collection":
        """
        获取或创建 collection

        Args:
            name: collection 名称
            metadata: collection 元数据

        Returns:
            ChromaDB Collection 对象
        """
        return self._client.get_or_create_collection(
            name=name, metadata=metadata
        )

    def delete_collection(self, name: str) -> None:
        """
        删除指定的 collection

        Args:
            name: collection 名称
        """
        self._client.delete_collection(name=name)
        logger.info(f"Collection '{name}' deleted")

    def list_collections(self) -> list["chromadb.Collection"]:
        """
        列出所有 collections

        Returns:
            Collection 对象列表
        """
        return self._client.list_collections()

    def upsert_vector(
        self,
        collection_name: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: Optional[list[str]] = None,
        metadatas: Optional[list[dict]] = None,
    ) -> None:
        """
        插入或更新向量

        Args:
            collection_name: collection 名称
            ids: 向量 ID 列表
            embeddings: 向量列表
            documents: 文档内容列表 (可选)
            metadatas: 元数据列表 (可选)
        """
        collection = self.get_collection(collection_name)
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.debug(
            f"Upserted {len(ids)} vectors into collection '{collection_name}'"
        )

    def add(
        self,
        collection: str,
        ids: list[str],
        documents: Optional[list[str]] = None,
        metadatas: Optional[list[dict]] = None,
        embeddings: Optional[list[list[float]]] = None,
    ) -> None:
        """
        添加向量到 collection (不带 embedding 的简化接口)

        注意: 如果不提供 embeddings，ChromaDB 会使用默认 embedding 函数。
        但为了一致性，建议使用 upsert_vector 并自行生成 embeddings。

        Args:
            collection: collection 名称
            ids: 向量 ID 列表
            documents: 文档内容列表 (可选)
            metadatas: 元数据列表 (可选)
            embeddings: 向量列表 (可选)
        """
        collection_obj = self.get_or_create_collection(collection)
        collection_obj.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        logger.debug(
            f"Added {len(ids)} items to collection '{collection}'"
        )

    def query(
        self,
        collection_name: str,
        query_embeddings: list[list[float]],
        n_results: int = 10,
        where: Optional[dict] = None,
        where_document: Optional[dict] = None,
        include: Optional[list[str]] = None,
    ) -> dict:
        """
        查询相似向量

        Args:
            collection_name: collection 名称
            query_embeddings: 查询向量列表
            n_results: 返回结果数量
            where: 元数据过滤条件
            where_document: 文档内容过滤条件
            include: 返回字段列表

        Returns:
            查询结果字典
        """
        collection = self.get_collection(collection_name)

        if include is None:
            include = ["documents", "metadatas", "distances"]

        return collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=include,
        )

    def get(
        self,
        collection_name: str,
        ids: Optional[list[str]] = None,
        where: Optional[dict] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include: Optional[list[str]] = None,
    ) -> dict:
        """
        获取指定 ID 的向量

        Args:
            collection_name: collection 名称
            ids: 向量 ID 列表 (可选)
            where: 元数据过滤条件 (可选)
            limit: 返回数量限制
            offset: 偏移量
            include: 返回字段列表

        Returns:
            向量数据字典
        """
        collection = self.get_collection(collection_name)

        if include is None:
            include = ["documents", "metadatas"]

        return collection.get(
            ids=ids,
            where=where,
            limit=limit,
            offset=offset,
            include=include,
        )

    def count(self, collection_name: str) -> int:
        """
        统计 collection 中的向量数量

        Args:
            collection_name: collection 名称

        Returns:
            向量数量
        """
        collection = self.get_collection(collection_name)
        return collection.count()

    def reset(self) -> None:
        """
        重置数据库 (删除所有 collections)
        """
        self._client.reset()
        logger.warning("ChromaDB database reset - all collections deleted")

    def reset_collection(self, collection_name: str) -> None:
        """
        重置指定 collection (删除并重建)

        Args:
            collection_name: collection 名称
        """
        collection = self.get_collection(collection_name)
        # 获取 collection 的原始 metadata
        metadata = collection.metadata
        self.delete_collection(collection_name)
        self.get_or_create_collection(
            name=collection_name, metadata=metadata
        )
        logger.info(f"Collection '{collection_name}' reset")
