# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
AscendC API 采集调度器

编排链接发现和详情提取为完整采集流程
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

from .official_docs import OfficialDocsClient
from .link_discovery import LinkDiscoveryResult, discover_api_links, _generate_api_id
from .parsers import parse_api_page, ParsingResult
from .api_storage import APIStorage
from .checkpoint import CheckpointManager, CollectionCheckpoint
from ..models import AscendCAPIDefinition

logger = logging.getLogger(__name__)


@dataclass
class CollectionStats:
    """采集统计"""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "duration_seconds": round(self.duration_seconds, 2),
        }


class APICollector:
    """
    AscendC API 采集调度器

    负责:
    - 从昇腾官方文档发现 API 链接
    - 批量采集 API 详情
    - 存储到 ChromaDB 和 Redis
    - 断点续采支持
    """

    # 采集类型标识
    COLLECTION_TYPE = "ascendc_api"

    # 限速配置
    DEFAULT_RATE_LIMIT = 0.5  # 秒/请求

    def __init__(
        self,
        docs_client: Optional[OfficialDocsClient] = None,
        storage: Optional[APIStorage] = None,
        checkpoint: Optional[CheckpointManager] = None,
        rate_limit: float = DEFAULT_RATE_LIMIT,
        chroma_db_path: Optional[str] = None,
        redis_config: Optional[Any] = None,
    ):
        """
        初始化采集器

        Args:
            docs_client: 文档 HTTP 客户端
            storage: API 存储 (优先级最高)
            checkpoint: 断点管理器
            rate_limit: 请求间隔 (秒)
            chroma_db_path: ChromaDB 持久化路径
            redis_config: Redis 配置
        """
        from ..config import get_config

        config = get_config()

        self._docs_client = docs_client or OfficialDocsClient()
        self._storage = storage or APIStorage(
            chroma_db_path=chroma_db_path or str(config.chroma.db_path),
            redis_config=redis_config or config.redis,
            embedder_config=config.embedding,
        )
        self._checkpoint = checkpoint or CheckpointManager(
            storage_path=str(config.data_dir / "checkpoints")
        )
        self._rate_limit = rate_limit

    async def run_full_collection(
        self,
        limit: Optional[int] = None,
        resume: bool = True,
    ) -> Dict[str, Any]:
        """
        执行全量或限量采集

        Args:
            limit: 限制采集数量 (None = 全量)
            resume: 是否从断点继续

        Returns:
            采集结果统计
        """
        import time
        start_time = time.time()

        stats = CollectionStats()

        # Step 1: 发现所有 API 链接
        logger.info("Step 1: Discovering API links...")
        discovery_result = await self._discover_links()

        if not discovery_result.new_links and not discovery_result.cached_links:
            logger.warning("No API links discovered")
            return stats.to_dict()

        all_links = discovery_result.new_links + discovery_result.cached_links
        stats.total = len(all_links)

        logger.info(f"Discovered {stats.total} API links")

        # Step 2: 获取待采集列表
        if resume:
            pending_links = self._get_pending_links(all_links)
        else:
            pending_links = all_links

        logger.info(f"Pending APIs to collect: {len(pending_links)}")

        # Step 3: 限流采集详情
        await self._collect_details(pending_links[:limit], stats)

        stats.duration_seconds = time.time() - start_time

        logger.info(
            f"Collection completed: {stats.success} success, "
            f"{stats.failed} failed, {stats.skipped} skipped, "
            f"elapsed {stats.duration_seconds:.2f}s"
        )

        return stats.to_dict()

    async def _discover_links(self) -> LinkDiscoveryResult:
        """
        发现 API 链接

        Returns:
            链接发现结果
        """
        from .link_discovery import DEFAULT_API_LIST_URL

        # 获取已采集的 API IDs
        checkpoint = self._checkpoint.load_checkpoint(self.COLLECTION_TYPE)
        cached_ids = set(checkpoint.completed) if checkpoint else set()

        # 发现链接
        result = await discover_api_links(
            list_page_url=DEFAULT_API_LIST_URL,
            cached_api_ids=cached_ids,
        )

        return result

    def _get_pending_links(self, all_links: List) -> List:
        """
        获取待采集的链接

        Args:
            all_links: 所有链接

        Returns:
            待采集链接列表
        """
        pending = []

        for link in all_links:
            if not self._checkpoint.is_completed(self.COLLECTION_TYPE, link.api_id):
                pending.append(link)

        return pending

    async def _collect_details(
        self,
        links: List,
        stats: CollectionStats,
    ) -> None:
        """
        采集 API 详情

        Args:
            links: 待采集链接列表
            stats: 统计对象
        """
        for i, link in enumerate(links):
            try:
                # 获取页面内容
                html = await self._docs_client.fetch_page(link.url)

                # 解析页面
                parsing_result = parse_api_page(
                    html=html,
                    api_id=link.api_id,
                    name=link.name,
                    url=link.url,
                    category=link.category,
                    subcategory=link.subcategory,
                )

                if parsing_result.success and parsing_result.api_definition:
                    # 存储到 ChromaDB/Redis
                    self._storage.store_api(parsing_result.api_definition)

                    # 标记完成
                    self._checkpoint.mark_completed(
                        self.COLLECTION_TYPE,
                        link.api_id,
                    )

                    stats.success += 1
                else:
                    # 解析失败但有部分数据
                    if parsing_result.api_definition:
                        self._storage.store_api(
                            parsing_result.api_definition,
                            skip_embedding=True,
                        )
                        self._checkpoint.mark_completed(
                            self.COLLECTION_TYPE,
                            link.api_id,
                        )
                        stats.success += 1
                    else:
                        self._checkpoint.mark_failed(
                            self.COLLECTION_TYPE,
                            link.api_id,
                            str(parsing_result.parse_errors),
                        )
                        stats.failed += 1

                # 限速
                await asyncio.sleep(self._rate_limit)

                # 进度日志
                if (i + 1) % 10 == 0:
                    logger.info(f"Progress: {i + 1}/{len(links)}")

            except Exception as e:
                logger.error(f"Failed to collect {link.api_id}: {e}")
                self._checkpoint.mark_failed(
                    self.COLLECTION_TYPE,
                    link.api_id,
                    str(e),
                )
                stats.failed += 1

    def get_progress(self) -> Dict[str, Any]:
        """
        获取采集进度

        Returns:
            进度信息
        """
        return self._checkpoint.get_progress(self.COLLECTION_TYPE)
