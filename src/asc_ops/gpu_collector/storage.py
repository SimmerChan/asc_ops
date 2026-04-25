# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GPU 知识存储

支持 ChromaDB + Redis 双存储
"""

import logging
import os
from typing import List, Optional, Dict, Any

from .models import (
    GPUKernelKnowledge,
    GPURepository,
    GPUAPIInfo,
    CrossPlatformMapping,
    GPUPlatform,
    MappingEquivalenceLevel,
)

logger = logging.getLogger(__name__)


class GPUStorageError(Exception):
    """GPU 存储异常"""
    pass


class GPUStorage:
    """
    GPU 知识存储

    使用 ChromaDB 存储向量知识，Redis 存储映射关系
    """

    def __init__(
        self,
        chroma_client=None,
        redis_client=None,
        use_mock: bool = True,
        embedder=None,
    ):
        """
        初始化 GPU 存储

        Args:
            chroma_client: ChromaDB 客户端 (None 时自动从环境初始化)
            redis_client: Redis 客户端 (None 时自动从环境初始化)
            use_mock: 是否使用 mock 模式
            embedder: 向量化器，用于生成 embeddings（推荐使用 Qwen3-Embedding-0.6B）
        """
        self._chroma_client = chroma_client
        self._redis_client = redis_client
        self._use_mock = use_mock
        self._embedder = embedder

        # Mock 数据存储
        self._kernel_store: Dict[str, GPUKernelKnowledge] = {}
        self._api_store: Dict[str, GPUAPIInfo] = {}
        self._mapping_store: Dict[str, CrossPlatformMapping] = {}
        self._repo_store: Dict[str, GPURepository] = {}

        if use_mock:
            logger.info("GPU Storage initialized in mock mode")
        else:
            self._auto_init_clients()
            self._init_collections()

    def _auto_init_clients(self):
        """自动从环境变量初始化 ChromaDB 和 Redis 客户端"""
        # 初始化 ChromaDB
        if self._chroma_client is None:
            try:
                import chromadb
                import os
                chroma_path = os.environ.get("CHROMA_DB_PATH", "./data/chroma_db")
                self._chroma_client = chromadb.PersistentClient(path=chroma_path)
                logger.info(f"ChromaDB client initialized: {chroma_path}")
            except Exception as e:
                logger.warning(f"Failed to initialize ChromaDB client: {e}")

        # 初始化 Redis
        if self._redis_client is None:
            try:
                import redis
                redis_host = os.environ.get("REDIS_HOST", "localhost")
                redis_port = int(os.environ.get("REDIS_PORT", "6379"))
                redis_db = int(os.environ.get("REDIS_DB", "0"))
                redis_password = os.environ.get("REDIS_PASSWORD", None)

                self._redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    password=redis_password if redis_password else None,
                    decode_responses=True,
                )
                # 测试连接
                self._redis_client.ping()
                logger.info(f"Redis client initialized: {redis_host}:{redis_port}")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis client: {e}")
                self._redis_client = None

    def _init_collections(self):
        """初始化 ChromaDB collections"""
        if self._chroma_client is not None:
            # 创建 collections，明确指定 embedding_function=None
            # 避免 ChromaDB 默认使用 all-MiniLM-L6-v2 生成 embedding
            self._kernels_collection = self._chroma_client.get_or_create_collection(
                "gpu_kernels",
                embedding_function=None,
            )
            self._apis_collection = self._chroma_client.get_or_create_collection(
                "gpu_apis",
                embedding_function=None,
            )
            self._cross_platform_collection = self._chroma_client.get_or_create_collection(
                "cross_platform_mappings",
                embedding_function=None,
            )

    def store_kernel(self, kernel: GPUKernelKnowledge, embedder=None) -> bool:
        """
        存储 GPU Kernel 知识

        Args:
            kernel: GPUKernelKnowledge 对象
            embedder: 可选 embedder，用于生成 description_embedding
        """
        try:
            if self._use_mock:
                self._kernel_store[kernel.kernel_id] = kernel
                logger.debug(f"Stored kernel (mock): {kernel.kernel_id}")
                return True

            # 生成 embedding（使用 embedder 避免 ChromaDB 默认 all-MiniLM-L6-v2）
            kernel_embedding = None
            effective_embedder = embedder or self._embedder
            if effective_embedder and kernel.description:
                kernel_embedding = effective_embedder.encode(kernel.description)

            # ChromaDB 存储
            # 注意：需要先将 kernel 转为 embedding 格式
            metadata = {
                "kernel_name": kernel.kernel_name,
                "platform": kernel.platform.value,
                "category": kernel.category,
            }
            self._kernels_collection.upsert(
                ids=[kernel.kernel_id],
                metadatas=[metadata],
                documents=[kernel.description],
                embeddings=[kernel_embedding] if kernel_embedding else None,
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store kernel: {e}")
            raise GPUStorageError(f"Kernel storage failed: {e}")

    def store_api(self, api: GPUAPIInfo, embedder=None) -> bool:
        """
        存储 GPU API 信息

        Args:
            api: GPUAPIInfo 对象
            embedder: 可选 embedder，用于生成 description_embedding
        """
        try:
            if self._use_mock:
                self._api_store[api.api_id] = api
                logger.debug(f"Stored API (mock): {api.api_id}")
                return True

            # 生成 embedding（使用 embedder 避免 ChromaDB 默认 all-MiniLM-L6-v2）
            api_embedding = None
            effective_embedder = embedder or self._embedder
            if effective_embedder and api.description:
                api_embedding = effective_embedder.encode(api.description)

            # ChromaDB 存储
            metadata = {
                "api_name": api.api_name,
                "platform": api.platform.value,
                "category": api.category,
            }
            self._apis_collection.upsert(
                ids=[api.api_id],
                metadatas=[metadata],
                documents=[api.description],
                embeddings=[api_embedding] if api_embedding else None,
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store API: {e}")
            raise GPUStorageError(f"API storage failed: {e}")

    def store_api_with_embedding(
        self,
        api: GPUAPIInfo,
        embedder=None,
    ) -> bool:
        """
        存储 GPU API 信息（带 embedding 向量）

        Args:
            api: GPUAPIInfo 对象，需包含 description 和 description_embedding
            embedder: 可选 embedder，用于生成 description_embedding

        Returns:
            是否存储成功
        """
        try:
            if self._use_mock:
                self._api_store[api.api_id] = api
                logger.debug(f"Stored API with embedding (mock): {api.api_id}")
                return True

            # 如果没有 embedding 但有 embedder，则生成
            if api.description_embedding is None and embedder is not None:
                api.description_embedding = embedder.encode(api.description)

            # ChromaDB 存储（带 embedding）
            metadata = {
                "api_name": api.api_name,
                "platform": api.platform.value,
                "category": api.category,
            }
            self._apis_collection.upsert(
                ids=[api.api_id],
                metadatas=[metadata],
                documents=[api.description],
                embeddings=[api.description_embedding] if api.description_embedding else None,
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store API with embedding: {e}")
            raise GPUStorageError(f"API with embedding storage failed: {e}")

    def store_mapping(self, mapping: CrossPlatformMapping) -> bool:
        """存储跨平台映射"""
        try:
            if self._use_mock:
                self._mapping_store[mapping.mapping_id] = mapping
                logger.debug(f"Stored mapping (mock): {mapping.mapping_id}")
                return True

            # Redis 存储映射
            if self._redis_client is not None:
                key = f"mapping:{mapping.gpu_api.lower()}"
                value = f"{mapping.npu_api}:{mapping.equivalence_level.value}"
                self._redis_client.set(key, value)

                # 存储完整映射信息到 hash
                mapping_key = f"mapping:full:{mapping.mapping_id}"
                self._redis_client.hset(mapping_key, mapping={
                    "gpu_api": mapping.gpu_api,
                    "npu_api": mapping.npu_api,
                    "platform": mapping.platform.value,
                    "equivalence": mapping.equivalence_level.value,
                    "notes": mapping.adaptation_notes,
                })
            return True

        except Exception as e:
            logger.error(f"Failed to store mapping: {e}")
            raise GPUStorageError(f"Mapping storage failed: {e}")

    def store_cross_platform_mapping(
        self,
        mapping: CrossPlatformMapping,
        source: str = "llm_suggested",
    ) -> bool:
        """
        存储跨平台映射（双写：ChromaDB + Redis）

        Args:
            mapping: 跨平台映射对象
            source: 来源标记 (llm_high_conf/llm_suggested)

        Returns:
            是否存储成功
        """
        try:
            if self._use_mock:
                self._mapping_store[mapping.mapping_id] = mapping
                logger.debug(f"Stored cross-platform mapping (mock): {mapping.mapping_id}")
                return True

            # 先写 Redis
            if self._redis_client is not None:
                mapping_key = f"mapping:{mapping.mapping_id}"
                self._redis_client.hset(mapping_key, mapping={
                    "gpu_api": mapping.gpu_api,
                    "npu_api": mapping.npu_api,
                    "platform": mapping.platform.value,
                    "equivalence_level": mapping.equivalence_level.value,
                    "adaptation_notes": mapping.adaptation_notes,
                    "confidence": str(mapping.confidence),
                    "source": source,
                })
                # 添加到映射列表
                self._redis_client.sadd("mapping:list", mapping.mapping_id)
                # 按 GPU API 索引
                self._redis_client.sadd(f"mapping:gpu:{mapping.gpu_api.lower()}", mapping.mapping_id)

            # 再写 ChromaDB（用于语义检索）
            if self._chroma_client is not None:
                metadata = {
                    "gpu_api": mapping.gpu_api,
                    "npu_api": mapping.npu_api,
                    "platform": mapping.platform.value,
                    "equivalence_level": mapping.equivalence_level.value,
                    "confidence": mapping.confidence,
                    "source": source,
                }
                document = f"{mapping.gpu_api} -> {mapping.npu_api}: {mapping.adaptation_notes}"

                # 生成 embedding（使用 embedder 避免 ChromaDB 默认 all-MiniLM-L6-v2）
                doc_embedding = None
                if self._embedder:
                    doc_embedding = self._embedder.encode(document)

                self._cross_platform_collection.upsert(
                    ids=[mapping.mapping_id],
                    metadatas=[metadata],
                    documents=[document],
                    embeddings=[doc_embedding] if doc_embedding else None,
                )

            logger.info(f"Stored cross-platform mapping: {mapping.mapping_id} (source={source})")
            return True

        except Exception as e:
            logger.error(f"Failed to store cross-platform mapping: {e}")
            raise GPUStorageError(f"Cross-platform mapping storage failed: {e}")

    def get_kernel(self, kernel_id: str) -> Optional[GPUKernelKnowledge]:
        """获取 GPU Kernel"""
        if self._use_mock:
            return self._kernel_store.get(kernel_id)

        # ChromaDB 查询
        results = self._kernels_collection.get(ids=[kernel_id])
        if results and results["ids"]:
            # 返回 mock 对象 (实际应重建完整对象)
            return None
        return None

    def get_api(self, api_id: str) -> Optional[GPUAPIInfo]:
        """获取 GPU API"""
        if self._use_mock:
            return self._api_store.get(api_id)
        return None

    def get_api_by_name(self, api_name: str) -> Optional[GPUAPIInfo]:
        """
        根据 API 名称精确查找 GPU API

        Args:
            api_name: API 名称（如 "cudaMalloc"）

        Returns:
            GPUAPIInfo 或 None
        """
        if self._use_mock:
            for api in self._api_store.values():
                if api.api_name.lower() == api_name.lower():
                    return api
            return None

        # ChromaDB 精确查询
        results = self._apis_collection.get(
            where={"api_name": api_name},
            include=["documents", "metadatas", "embeddings"]
        )
        if results and results["ids"]:
            # 重建 GPUAPIInfo 对象
            doc = results["documents"][0] if results["documents"] else ""
            meta = results["metadatas"][0] if results["metadatas"] else {}
            # ChromaDB 返回的 embeddings 是 (1, 1024) numpy array，需要先取 [0] 再转换
            emb_raw = results.get("embeddings")
            if emb_raw is not None and len(emb_raw) > 0:
                embedding = emb_raw[0]
                # 转换为 list 以便后续处理
                import numpy as np
                if isinstance(embedding, np.ndarray):
                    embedding = embedding.tolist()
            else:
                embedding = None
            from .models import GPUPlatform
            return GPUAPIInfo(
                api_id=results["ids"][0],
                api_name=meta.get("api_name", ""),
                platform=GPUPlatform(meta.get("platform", "cuda")),
                description=doc,
                description_embedding=embedding,
                category=meta.get("category", ""),
            )
        return None

    def get_mapping(self, gpu_api: str) -> Optional[CrossPlatformMapping]:
        """获取 GPU API 的跨平台映射"""
        if self._use_mock:
            for mapping in self._mapping_store.values():
                if mapping.gpu_api.lower() == gpu_api.lower():
                    return mapping
            return None

        # Redis 查询
        if self._redis_client is not None:
            key = f"mapping:{gpu_api.lower()}"
            value = self._redis_client.get(key)
            if value:
                parts = value.decode().split(":")
                if len(parts) >= 2:
                    # 返回 mock 对象
                    from .models import GPUPlatform
                    return CrossPlatformMapping(
                        mapping_id="",
                        gpu_api=gpu_api,
                        npu_api=parts[0],
                        platform=GPUPlatform.CUDA,
                        equivalence_level=MappingEquivalenceLevel(parts[1]),
                    )
        return None

    def get_cross_platform_mapping(
        self,
        mapping_id: str,
    ) -> Optional[CrossPlatformMapping]:
        """
        获取跨平台映射（通过 ID）

        Args:
            mapping_id: 映射 ID

        Returns:
            CrossPlatformMapping 或 None
        """
        if self._use_mock:
            return self._mapping_store.get(mapping_id)

        if self._redis_client is not None:
            key = f"mapping:{mapping_id}"
            data = self._redis_client.hgetall(key)
            if data:
                from .models import GPUPlatform
                return CrossPlatformMapping(
                    mapping_id=mapping_id,
                    gpu_api=data.get("gpu_api", ""),
                    npu_api=data.get("npu_api", ""),
                    platform=GPUPlatform(data.get("platform", "cuda")),
                    equivalence_level=MappingEquivalenceLevel(data.get("equivalence_level", "similar")),
                    adaptation_notes=data.get("adaptation_notes", ""),
                    confidence=float(data.get("confidence", "0.5")),
                    source=data.get("source", "llm_suggested"),
                )
        return None

    def search_cross_platform_mappings(
        self,
        query: str,
        platform: Optional[GPUPlatform] = None,
        source: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 10,
    ) -> List[CrossPlatformMapping]:
        """
        搜索跨平台映射

        Args:
            query: 查询文本（用于 ChromaDB 向量搜索）
            platform: GPU 平台过滤
            source: 来源过滤 (llm_high_conf/llm_suggested)
            min_confidence: 最低置信度
            limit: 返回数量限制

        Returns:
            CrossPlatformMapping 列表
        """
        if self._use_mock:
            results = []
            for mapping in self._mapping_store.values():
                if query.lower() in mapping.gpu_api.lower() or query.lower() in mapping.npu_api.lower():
                    if platform is None or mapping.platform == platform:
                        if mapping.confidence >= min_confidence:
                            results.append(mapping)
            return sorted(results, key=lambda x: x.confidence, reverse=True)[:limit]

        results = []
        if self._chroma_client is not None:
            # 使用 embedder 生成查询向量，避免 ChromaDB 默认 all-MiniLM-L6-v2
            embedder = self._embedder
            if embedder is None:
                from ..collector.embedder import get_embedder
                embedder = get_embedder()

            query_embedding = embedder.encode([query])[0]

            chroma_results = self._cross_platform_collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
            )
            if chroma_results and chroma_results["ids"]:
                # ChromaDB returns list of lists: [[id1, id2], [id3, id4]] for 2 query_texts
                # We only queried with one query_text, so we get one inner list
                ids_list = chroma_results["ids"][0] if chroma_results["ids"] else []
                metadatas_list = chroma_results["metadatas"][0] if chroma_results["metadatas"] else []
                documents_list = chroma_results["documents"][0] if chroma_results["documents"] else []

                for i, mid in enumerate(ids_list):
                    metadata = metadatas_list[i]
                    confidence = float(metadata.get("confidence", 0.0))
                    if confidence < min_confidence:
                        continue
                    if source and metadata.get("source") != source:
                        continue
                    if platform and metadata.get("platform") != platform.value:
                        continue
                    from .models import GPUPlatform
                    results.append(CrossPlatformMapping(
                        mapping_id=mid,
                        gpu_api=metadata.get("gpu_api", ""),
                        npu_api=metadata.get("npu_api", ""),
                        platform=GPUPlatform(metadata.get("platform", "cuda")),
                        equivalence_level=MappingEquivalenceLevel(metadata.get("equivalence_level", "similar")),
                        adaptation_notes=metadata.get("adaptation_notes", ""),
                        confidence=confidence,
                        source=metadata.get("source", "llm_suggested"),
                    ))
        return sorted(results, key=lambda x: x.confidence, reverse=True)[:limit]

    def search_kernels(
        self,
        query: str,
        platform: Optional[GPUPlatform] = None,
        limit: int = 10,
    ) -> List[GPUKernelKnowledge]:
        """搜索 GPU Kernels"""
        if self._use_mock:
            results = []
            for kernel in self._kernel_store.values():
                if query.lower() in kernel.kernel_name.lower():
                    if platform is None or kernel.platform == platform:
                        results.append(kernel)
            return results[:limit]

        # ChromaDB 向量搜索
        embedder = self._embedder
        if embedder is None:
            from ..collector.embedder import get_embedder
            embedder = get_embedder()

        query_embedding = embedder.encode([query])[0]

        results = self._kernels_collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
        )
        # 返回 mock 结果
        return []

    def search_apis(
        self,
        query: str,
        platform: Optional[GPUPlatform] = None,
        limit: int = 10,
    ) -> List[GPUAPIInfo]:
        """搜索 GPU APIs"""
        if self._use_mock:
            results = []
            for api in self._api_store.values():
                if query.lower() in api.api_name.lower():
                    if platform is None or api.platform == platform:
                        results.append(api)
            return results[:limit]
        return []

    def store_repository(self, repo: GPURepository) -> bool:
        """存储仓库信息"""
        if self._use_mock:
            self._repo_store[repo.repo_id] = repo
            return True
        return True

    def get_repository(self, repo_id: str) -> Optional[GPURepository]:
        """获取仓库信息"""
        return self._repo_store.get(repo_id)

    def list_repositories(self) -> List[GPURepository]:
        """列出所有仓库"""
        return list(self._repo_store.values())

    def get_stats(self) -> Dict[str, int]:
        """获取存储统计"""
        return {
            "kernels": len(self._kernel_store),
            "apis": len(self._api_store),
            "mappings": len(self._mapping_store),
            "repositories": len(self._repo_store),
        }
