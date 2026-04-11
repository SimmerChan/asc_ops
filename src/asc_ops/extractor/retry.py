# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
LLM 重试模块

对抽取失败的 BugFix/Optimization 使用 LLM 重新抽取
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Literal

from ..llm import UnifiedLLMClient
from .bug_extractor import BugExtractor
from .opt_extractor import OptimizationExtractor
from .knowledge_storage import KnowledgeStorage

logger = logging.getLogger(__name__)


@dataclass
class RetryStats:
    """重试统计"""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0


class LLMBasedRetry:
    """
    基于 LLM 的知识抽取重试器

    从存储层获取失败记录，使用 LLM 增强的抽取器重新抽取
    """

    def __init__(
        self,
        storage: KnowledgeStorage,
        llm_client: Optional[UnifiedLLMClient] = None,
        provider: str = "minimax",
    ):
        """
        初始化 LLM 重试器

        Args:
            storage: 知识存储实例
            llm_client: 可选的 LLM 客户端
            provider: 默认 Provider (llm_client 未提供时使用)
        """
        self._storage = storage
        self._llm_client = llm_client
        self._provider = provider

    async def _get_llm_client(self) -> UnifiedLLMClient:
        """获取或创建 LLM 客户端"""
        import os
        from pathlib import Path

        if self._llm_client:
            return self._llm_client

        # 尝试加载 .env 文件
        # 从项目根目录加载 .env
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        if env_path.exists():
            from dotenv import load_dotenv
            load_dotenv(env_path)

        # 从环境变量获取 API key
        api_key = ""
        api_base = None

        provider_lower = self._provider.lower()
        if provider_lower == "minimax":
            # MiniMax 可能使用 Anthropic 兼容 API
            api_key = os.environ.get("MINIMAX_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
            api_base = os.environ.get("MINIMAX_API_BASE") or os.environ.get("ANTHROPIC_API_BASE")
        elif provider_lower == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            api_base = os.environ.get("ANTHROPIC_API_BASE")
        elif provider_lower == "openai":
            api_key = os.environ.get("OPENAI_API_KEY", "")
            api_base = os.environ.get("OPENAI_API_BASE")
        elif provider_lower == "zhipu":
            api_key = os.environ.get("ZHIPU_API_KEY", "")
            api_base = os.environ.get("ZHIPU_API_BASE")

        client = UnifiedLLMClient(
            provider=self._provider,
            api_key=api_key,
            api_base=api_base,
        )
        await client.connect()
        return client

    async def retry_failed_bugfixes(
        self,
        limit: int = 100,
        provider: Optional[str] = None,
    ) -> RetryStats:
        """
        重试抽取失败的 BugFix

        Args:
            limit: 最大重试数量
            provider: 可选的 Provider 覆盖

        Returns:
            RetryStats: 重试统计
        """
        stats = RetryStats()

        # 获取失败列表
        failed_list = self._storage.get_failed_bugfixes(limit=limit)
        stats.total = len(failed_list)

        if not failed_list:
            logger.info("No failed bugfixes to retry")
            return stats

        logger.info(f"Found {len(failed_list)} failed bugfixes to retry")

        # 获取 LLM 客户端
        llm_client = await self._get_llm_client()
        bug_extractor = BugExtractor(llm_client=llm_client)

        for failed in failed_list:
            bug_id = failed.get("bug_id", "")
            pr_title = failed.get("bug_title", "")
            source_repo = failed.get("source_repo", "")
            source_pr = failed.get("source_pr", "")

            if not pr_title:
                logger.warning(f"BugFix {bug_id} has no title, skipping")
                stats.skipped += 1
                continue

            try:
                # 使用 LLM 重新抽取
                result = await bug_extractor.extract_async(
                    pr_title=pr_title,
                    pr_body="",  # 失败记录中没有 PR body
                    source_repo=source_repo,
                    source_pr=source_pr,
                    use_llm=True,
                )

                if result.extraction_success:
                    # 重新存储（成功的）
                    self._storage.store_bugfix(result, store_failed=False)
                    # 标记重试成功
                    self._storage.mark_retry_success(bug_id=bug_id)
                    stats.success += 1
                    logger.info(f"BugFix {bug_id} retry succeeded")
                else:
                    stats.failed += 1
                    logger.warning(f"BugFix {bug_id} retry still failed")

            except Exception as e:
                stats.failed += 1
                logger.error(f"BugFix {bug_id} retry error: {e}")

        return stats

    async def retry_failed_optimizations(
        self,
        limit: int = 100,
        provider: Optional[str] = None,
    ) -> RetryStats:
        """
        重试抽取失败的 Optimization

        Args:
            limit: 最大重试数量
            provider: 可选的 Provider 覆盖

        Returns:
            RetryStats: 重试统计
        """
        stats = RetryStats()

        # 获取失败列表
        failed_list = self._storage.get_failed_optimizations(limit=limit)
        stats.total = len(failed_list)

        if not failed_list:
            logger.info("No failed optimizations to retry")
            return stats

        logger.info(f"Found {len(failed_list)} failed optimizations to retry")

        # 获取 LLM 客户端
        llm_client = await self._get_llm_client()
        opt_extractor = OptimizationExtractor(llm_client=llm_client)

        for failed in failed_list:
            opt_id = failed.get("opt_id", "")
            pr_title = failed.get("opt_title", "")
            source_repo = failed.get("source_repo", "")
            source_pr = failed.get("source_pr", "")

            if not pr_title:
                logger.warning(f"Optimization {opt_id} has no title, skipping")
                stats.skipped += 1
                continue

            try:
                # 使用 LLM 重新抽取
                result = await opt_extractor.extract_async(
                    pr_title=pr_title,
                    pr_body="",  # 失败记录中没有 PR body
                    source_repo=source_repo,
                    source_pr=source_pr,
                    use_llm=True,
                )

                if result.extraction_success:
                    # 重新存储（成功的）
                    self._storage.store_optimization(result, store_failed=False)
                    # 标记重试成功
                    self._storage.mark_retry_success(opt_id=opt_id)
                    stats.success += 1
                    logger.info(f"Optimization {opt_id} retry succeeded")
                else:
                    stats.failed += 1
                    logger.warning(f"Optimization {opt_id} retry still failed")

            except Exception as e:
                stats.failed += 1
                logger.error(f"Optimization {opt_id} retry error: {e}")

        return stats

    async def retry_all(
        self,
        limit: int = 100,
        bugfix: bool = True,
        optimization: bool = True,
        provider: Optional[str] = None,
    ) -> dict:
        """
        重试所有失败记录

        Args:
            limit: 最大重试数量（每种类型）
            bugfix: 是否重试 BugFix
            optimization: 是否重试 Optimization
            provider: 可选的 Provider 覆盖

        Returns:
            dict: 每种类型的重试统计
        """
        results = {}

        if bugfix:
            results["bugfix"] = await self.retry_failed_bugfixes(
                limit=limit,
                provider=provider,
            )

        if optimization:
            results["optimization"] = await self.retry_failed_optimizations(
                limit=limit,
                provider=provider,
            )

        return results

    async def close(self):
        """关闭 LLM 客户端"""
        if self._llm_client:
            await self._llm_client.close()


async def create_retry_instance(
    storage: Optional[KnowledgeStorage] = None,
    llm_client: Optional[UnifiedLLMClient] = None,
    provider: str = "minimax",
) -> LLMBasedRetry:
    """
    创建 LLM 重试实例

    Args:
        storage: 知识存储实例（可选）
        llm_client: LLM 客户端（可选）
        provider: 默认 Provider

    Returns:
        LLMBasedRetry 实例
    """
    if storage is None:
        import os
        from ..storage.redis_client import RedisClient
        from ..storage.chroma_client import ChromaDBClient

        redis_client = RedisClient(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=int(os.environ.get("REDIS_DB", "0")),
            password=os.environ.get("REDIS_PASSWORD"),
        )
        chroma_client = ChromaDBClient(
            persist_directory=os.environ.get("CHROMA_DB_PATH", "./data/chroma_db"),
        )
        storage = KnowledgeStorage(chroma_client=chroma_client, redis_client=redis_client)

    return LLMBasedRetry(
        storage=storage,
        llm_client=llm_client,
        provider=provider,
    )
