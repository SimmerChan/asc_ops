# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GPU 知识存储

支持 ChromaDB + Redis 双存储
"""

import logging
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
    ):
        """
        初始化 GPU 存储

        Args:
            chroma_client: ChromaDB 客户端 (None 时使用 mock)
            redis_client: Redis 客户端 (None 时使用 mock)
            use_mock: 是否使用 mock 模式
        """
        self._chroma_client = chroma_client
        self._redis_client = redis_client
        self._use_mock = use_mock

        # Mock 数据存储
        self._kernel_store: Dict[str, GPUKernelKnowledge] = {}
        self._api_store: Dict[str, GPUAPIInfo] = {}
        self._mapping_store: Dict[str, CrossPlatformMapping] = {}
        self._repo_store: Dict[str, GPURepository] = {}

        if use_mock:
            logger.info("GPU Storage initialized in mock mode")
        else:
            self._init_collections()

    def _init_collections(self):
        """初始化 ChromaDB collections"""
        if self._chroma_client is not None:
            # 创建 collections
            self._kernels_collection = self._chroma_client.get_or_create_collection(
                "gpu_kernels"
            )
            self._apis_collection = self._chroma_client.get_or_create_collection(
                "gpu_apis"
            )

    def store_kernel(self, kernel: GPUKernelKnowledge) -> bool:
        """存储 GPU Kernel 知识"""
        try:
            if self._use_mock:
                self._kernel_store[kernel.kernel_id] = kernel
                logger.debug(f"Stored kernel (mock): {kernel.kernel_id}")
                return True

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
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store kernel: {e}")
            raise GPUStorageError(f"Kernel storage failed: {e}")

    def store_api(self, api: GPUAPIInfo) -> bool:
        """存储 GPU API 信息"""
        try:
            if self._use_mock:
                self._api_store[api.api_id] = api
                logger.debug(f"Stored API (mock): {api.api_id}")
                return True

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
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store API: {e}")
            raise GPUStorageError(f"API storage failed: {e}")

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
        results = self._kernels_collection.query(
            query_texts=[query],
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
