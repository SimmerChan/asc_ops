# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
批量LLM抽取器

对优先级队列中的bug记录批量调用LLM抽取
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

from .bug_extractor import BugExtractor, BugExtractionResult
from .priority_scorer import BugPriorityItem, PriorityScorer
from .knowledge_storage import KnowledgeStorage
from .git_diff_provider import GitDiffProvider
from .gitcode_diff_provider import GitCodeDiffProvider
from ..llm import UnifiedLLMClient

logger = logging.getLogger(__name__)


@dataclass
class BatchExtractionStats:
    """批量抽取统计"""
    total: int = 0
    success: int = 0
    partial: int = 0  # 部分成功（有null字段）
    failed: int = 0
    skipped: int = 0
    root_cause_filled: int = 0
    fix_pattern_filled: int = 0
    low_confidence: int = 0  # 置信度 < 0.5 标记待审核
    with_diff: int = 0  # 有 diff 的记录数
    total_duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "success": self.success,
            "partial": self.partial,
            "failed": self.failed,
            "skipped": self.skipped,
            "root_cause_filled": self.root_cause_filled,
            "fix_pattern_filled": self.fix_pattern_filled,
            "low_confidence": self.low_confidence,
            "with_diff": self.with_diff,
            "duration_seconds": round(self.total_duration_seconds, 2),
        }


@dataclass
class BatchExtractionResult:
    """批量抽取结果"""
    stats: BatchExtractionStats
    updated_bugs: List[Dict[str, Any]]  # 更新后的bug列表
    failed_bugs: List[Dict[str, Any]]  # 失败的bug列表


class BatchBugExtractor:
    """
    批量LLM抽取器

    支持批次并发调用LLM，处理null返回情况，记录置信度
    """

    # LLM调用参数
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    DEFAULT_MAX_TOKENS = 2048
    DEFAULT_TEMPERATURE = 0.3
    DEFAULT_BATCH_SIZE = 10
    DEFAULT_CONCURRENCY = 3  # 同时最多3个批次

    def __init__(
        self,
        priority_scorer: PriorityScorer,
        knowledge_storage: KnowledgeStorage,
        llm_client: Optional[UnifiedLLMClient] = None,
        provider: str = "anthropic",
        batch_size: int = DEFAULT_BATCH_SIZE,
        concurrency: int = DEFAULT_CONCURRENCY,
    ):
        """
        初始化批量抽取器

        Args:
            priority_scorer: 优先级评分器
            knowledge_storage: 知识存储
            llm_client: LLM 客户端
            provider: LLM provider
            batch_size: 每批数量
            concurrency: 最大并发数
        """
        self._priority_scorer = priority_scorer
        self._storage = knowledge_storage
        self._llm_client = llm_client
        self._provider = provider
        self._batch_size = batch_size
        self._concurrency = concurrency
        self._bug_extractor: Optional[BugExtractor] = None
        self._git_diff_provider = GitDiffProvider()
        self._gitcode_diff_provider = GitCodeDiffProvider()

    async def _get_llm_client(self) -> UnifiedLLMClient:
        """获取或创建LLM客户端"""
        import os
        from pathlib import Path

        if self._llm_client:
            return self._llm_client

        # 尝试加载 .env 文件
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            from dotenv import load_dotenv
            load_dotenv(env_path)

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        api_base = os.environ.get("ANTHROPIC_API_BASE")

        client = UnifiedLLMClient(
            provider=self._provider,
            api_key=api_key,
            api_base=api_base,
        )
        await client.connect()
        return client

    async def _get_bug_extractor(self) -> BugExtractor:
        """获取或创建BugExtractor"""
        if self._bug_extractor is None:
            llm_client = await self._get_llm_client()
            self._bug_extractor = BugExtractor(llm_client=llm_client)
        return self._bug_extractor

    async def extract_batch(
        self,
        bug_items: List[BugPriorityItem],
        dry_run: bool = False,
    ) -> BatchExtractionResult:
        """
        批量抽取

        Args:
            bug_items: 优先级队列中的bug列表
            dry_run: 是否仅预览不执行

        Returns:
            BatchExtractionResult: 抽取结果
        """
        import time
        start_time = time.time()

        stats = BatchExtractionStats(total=len(bug_items))
        updated_bugs = []
        failed_bugs = []

        if dry_run:
            logger.info(f"Dry run: would extract {len(bug_items)} bugs")
            return BatchExtractionResult(
                stats=stats,
                updated_bugs=[],
                failed_bugs=[],
            )

        if not bug_items:
            logger.info("No bugs to extract")
            return BatchExtractionResult(
                stats=stats,
                updated_bugs=[],
                failed_bugs=[],
            )

        bug_extractor = await self._get_bug_extractor()

        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(self._concurrency)

        async def process_bug(bug: BugPriorityItem) -> Optional[Dict[str, Any]]:
            """处理单个bug"""
            async with semaphore:
                try:
                    # 优先使用 GitCodeDiffProvider（从 API 获取 PR diff）
                    # 如果失败则使用本地 GitDiffProvider
                    pr_diff = self._gitcode_diff_provider.get_diff(bug.bug_id)

                    if pr_diff is None:
                        # 降级到本地 Git 仓库
                        pr_diff = self._git_diff_provider.get_diff(bug.bug_id)

                    # 调用LLM抽取
                    # 注意：这里使用 pr_body="" 因为冷启动记录只有标题
                    result = await bug_extractor.extract_async(
                        pr_title=bug.bug_title,
                        pr_body="",  # 冷启动记录没有pr_body
                        source_repo=bug.source_repo,
                        source_pr=bug.source_pr,
                        use_llm=True,
                        pr_diff=pr_diff,
                    )

                    return {
                        "bug": bug,
                        "result": result,
                        "success": result.extraction_success,
                        "has_diff": pr_diff is not None,
                    }
                except Exception as e:
                    logger.error(f"Error extracting {bug.bug_id}: {e}")
                    return None

        # 并发处理所有bug
        logger.info(f"Starting batch extraction of {len(bug_items)} bugs")
        tasks = [process_bug(bug) for bug in bug_items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        for i, result in enumerate(results):
            bug = bug_items[i]

            if isinstance(result, Exception):
                logger.error(f"Task exception for {bug.bug_id}: {result}")
                stats.failed += 1
                failed_bugs.append({"bug_id": bug.bug_id, "error": str(result)})
                continue

            if result is None:
                stats.skipped += 1
                continue

            bug_result: BugExtractionResult = result["result"]

            if bug_result.extraction_success:
                # 跟踪是否有 diff
                if result.get("has_diff"):
                    stats.with_diff += 1

                # 更新存储
                success = self._storage.store_bugfix(bug_result, store_failed=False)

                if success:
                    stats.success += 1
                    updated_bugs.append(bug_result.to_dict())

                    # 检查字段填充情况
                    if bug_result.root_cause:
                        stats.root_cause_filled += 1
                    if bug_result.fix_pattern:
                        stats.fix_pattern_filled += 1

                    # 检查置信度（基于是否有完整信息）
                    confidence = self._calculate_confidence(bug_result)
                    if confidence < 0.5:
                        stats.low_confidence += 1
                        logger.info(f"Bug {bug.bug_id} marked as low confidence ({confidence})")
                else:
                    stats.failed += 1
                    failed_bugs.append({"bug_id": bug.bug_id, "error": "storage failed"})
            else:
                # 抽取失败但可能有部分数据
                if bug_result.root_cause or bug_result.fix_pattern:
                    stats.partial += 1
                    self._storage.store_bugfix(bug_result, store_failed=False)
                    updated_bugs.append(bug_result.to_dict())
                else:
                    stats.failed += 1
                    failed_bugs.append({
                        "bug_id": bug.bug_id,
                        "error": bug_result.error_message or "extraction failed"
                    })

        stats.total_duration_seconds = time.time() - start_time
        logger.info(f"Batch extraction complete: {stats.success} success, {stats.failed} failed, {stats.partial} partial, {stats.with_diff} with diff")

        return BatchExtractionResult(
            stats=stats,
            updated_bugs=updated_bugs,
            failed_bugs=failed_bugs,
        )

    def _calculate_confidence(self, result: BugExtractionResult) -> float:
        """
        计算抽取置信度

        基于字段完整度和信息量
        """
        score = 0.0
        count = 0

        # root_cause 权重 0.4
        if result.root_cause:
            score += 0.4
            # 长度作为质量指标
            if len(result.root_cause) > 20:
                score += 0.1
        count += 0.4

        # fix_pattern 权重 0.4
        if result.fix_pattern:
            score += 0.4
            if len(result.fix_pattern) > 20:
                score += 0.1
        count += 0.4

        # trigger_conditions 权重 0.1
        if result.trigger_conditions:
            score += 0.1

        # related_apis 权重 0.1
        if result.related_apis:
            score += 0.1

        # 归一化
        if count > 0:
            return min(1.0, score / count * 1.2)  # 稍微奖励完整的结果
        return 0.0

    async def extract_by_priority(
        self,
        limit: int = 100,
        dry_run: bool = False,
    ) -> BatchExtractionResult:
        """
        按优先级队列抽取

        Args:
            limit: 处理数量限制
            dry_run: 是否仅预览

        Returns:
            BatchExtractionResult: 抽取结果
        """
        # 获取优先级队列
        queue = self._priority_scorer.calculate_priority_queue(limit=limit)

        if not queue:
            logger.warning("Priority queue is empty")
            return BatchExtractionResult(
                stats=BatchExtractionStats(),
                updated_bugs=[],
                failed_bugs=[],
            )

        logger.info(f"Extracting top {len(queue)} bugs by priority")

        return await self.extract_batch(queue, dry_run=dry_run)

    def get_pending_bugs(self, limit: int = 100) -> List[BugPriorityItem]:
        """
        获取待抽取的bug列表（优先级队列中缺失字段的）

        Args:
            limit: 返回数量

        Returns:
            待抽取的bug列表
        """
        queue = self._priority_scorer.calculate_priority_queue(limit=None)

        # 只返回缺失字段的
        pending = [
            bug for bug in queue
            if not bug.has_root_cause or not bug.has_fix_pattern
        ]

        return pending[:limit]
