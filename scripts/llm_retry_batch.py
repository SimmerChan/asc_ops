#!/usr/bin/env python3
# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
LLM 批量重试抽取脚本

对优先级队列中的 Bug 记录批量调用 LLM 抽取，补全 root_cause 和 fix_pattern 字段。

Usage:
    # 查看当前质量报告
    python scripts/llm_retry_batch.py --report-only

    # 预览优先级队列（不执行抽取）
    python scripts/llm_retry_batch.py --dry-run

    # 执行批量抽取（前 100 条）
    python scripts/llm_retry_batch.py --limit 100

    # 执行批量抽取（指定批次大小）
    python scripts/llm_retry_batch.py --limit 100 --batch-size 20

Environment:
    ANTHROPIC_API_KEY: Claude API 密钥
    CHROMA_DB_PATH: ChromaDB 路径 (默认: ./data/chroma_db)
    REDIS_HOST: Redis 主机 (默认: localhost)
    REDIS_PORT: Redis 端口 (默认: 6379)
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from asc_ops.extractor.priority_scorer import PriorityScorer
from asc_ops.extractor.batch_extractor import BatchBugExtractor
from asc_ops.extractor.quality_reporter import ExtractionQualityReporter
from asc_ops.extractor.knowledge_storage import KnowledgeStorage
from asc_ops.storage.redis_client import RedisClient
from asc_ops.storage.chroma_client import ChromaDBClient
from asc_ops.quality.citation_tracker import CitationTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_storage(mock_redis: bool = False) -> KnowledgeStorage:
    """创建知识存储实例

    Args:
        mock_redis: 是否使用 mock Redis (用于测试)
    """
    redis_client = RedisClient(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        db=int(os.environ.get("REDIS_DB", "0")),
        password=os.environ.get("REDIS_PASSWORD"),
        mock=mock_redis,
    )
    chroma_client = ChromaDBClient(
        persist_directory=os.environ.get("CHROMA_DB_PATH", "./data/chroma_db"),
    )

    return KnowledgeStorage(
        chroma_client=chroma_client,
        redis_client=redis_client,
    )


def create_priority_scorer(storage: KnowledgeStorage) -> PriorityScorer:
    """创建优先级评分器

    Args:
        storage: 知识存储实例
    """
    citation_tracker = CitationTracker(storage._redis)
    return PriorityScorer(
        chroma_client=storage._chroma,
        redis_client=storage._redis,
        citation_tracker=citation_tracker,
    )


async def create_batch_extractor(storage: KnowledgeStorage) -> BatchBugExtractor:
    """创建批量抽取器

    Args:
        storage: 知识存储实例
    """
    priority_scorer = create_priority_scorer(storage)
    return BatchBugExtractor(
        priority_scorer=priority_scorer,
        knowledge_storage=storage,
    )


async def run_extraction(
    limit: int = 100,
    batch_size: int = 10,
    dry_run: bool = False,
    mock_redis: bool = False,
) -> int:
    """
    执行批量抽取

    Args:
        limit: 处理数量限制
        batch_size: 批次大小
        dry_run: 是否仅预览不执行
        mock_redis: 是否使用 mock Redis

    Returns:
        int: 成功返回 0，失败返回 1
    """
    storage = create_storage(mock_redis=mock_redis)

    if dry_run:
        # Dry run: 只预览优先级队列
        priority_scorer = create_priority_scorer(storage)
        queue = priority_scorer.calculate_priority_queue(limit=limit)

        print("\n" + "=" * 80)
        print("  优先级队列预览 (Dry Run)")
        print("=" * 80)
        print(f"\n共 {len(queue)} 条记录待处理:\n")
        print(f"{'Rank':<6} {'Bug ID':<30} {'Operator':<12} {'RC':<4} {'FP':<4} {'Score':<6}")
        print("-" * 70)

        for item in queue:
            print(
                f"{item.priority_rank:<6} {item.bug_id:<30} {item.operator_id:<12} "
                f"{'Y' if item.has_root_cause else 'N':<4} {'Y' if item.has_fix_pattern else 'N':<4} "
                f"{item.priority_score:.3f}"
            )

        print("\nDry Run 完成 - 无数据实际抽取")
        return 0

    # 实际执行抽取
    batch_extractor = await create_batch_extractor(storage)

    print("\n" + "=" * 80)
    print("  LLM 批量重试抽取")
    print("=" * 80)
    print(f"\n处理参数:")
    print(f"  - 限制: {limit} 条")
    print(f"  - 批次大小: {batch_size}")
    print(f"  - 模式: {'Dry Run' if dry_run else '实际抽取'}")
    print()

    result = await batch_extractor.extract_by_priority(limit=limit, dry_run=dry_run)

    # 打印统计
    print("\n" + "=" * 80)
    print("  抽取结果统计")
    print("=" * 80)
    stats = result.stats
    print(f"\n总记录数: {stats.total}")
    print(f"  - 成功: {stats.success}")
    print(f"  - 部分成功: {stats.partial}")
    print(f"  - 失败: {stats.failed}")
    print(f"  - 跳过: {stats.skipped}")
    print(f"\n字段填充:")
    print(f"  - root_cause: {stats.root_cause_filled}")
    print(f"  - fix_pattern: {stats.fix_pattern_filled}")
    print(f"\n低置信度 (待审核): {stats.low_confidence}")
    print(f"总耗时: {stats.total_duration_seconds:.2f} 秒")

    if result.updated_bugs:
        print(f"\n已更新 {len(result.updated_bugs)} 条记录")
    if result.failed_bugs:
        print(f"\n失败记录 ({len(result.failed_bugs)} 条):")
        for failed in result.failed_bugs[:10]:
            print(f"  - {failed['bug_id']}: {failed.get('error', 'unknown error')}")
        if len(result.failed_bugs) > 10:
            print(f"  ... 还有 {len(result.failed_bugs) - 10} 条")

    print("\n" + "=" * 80)

    # 关闭存储连接
    storage._redis.close() if storage._redis else None

    return 0 if stats.failed == 0 else 1


def run_report_only(mock_redis: bool = False) -> int:
    """
    仅生成质量报告

    Args:
        mock_redis: 是否使用 mock Redis

    Returns:
        int: 成功返回 0
    """
    storage = create_storage(mock_redis=mock_redis)
    reporter = ExtractionQualityReporter(
        chroma_client=storage._chroma,
        redis_client=storage._redis,
    )

    print("\n" + "=" * 80)
    print("  Bug 知识抽取质量报告")
    print("=" * 80)

    # 打印摘要
    reporter.print_summary()

    # 生成 Markdown 报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"data/quality_report_{timestamp}.md"
    markdown = reporter.generate_markdown_report(
        output_path=report_path,
        include_problems=True,
        problem_limit=50,
    )

    print(f"\n详细报告已保存到: {report_path}")

    # 关闭存储连接
    storage._redis.close() if storage._redis else None

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="LLM 批量重试抽取 - 补全 Bug 知识的 root_cause 和 fix_pattern 字段",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 查看当前质量报告
  python scripts/llm_retry_batch.py --report-only

  # 预览优先级队列（不执行抽取）
  python scripts/llm_retry_batch.py --dry-run

  # 执行批量抽取（前 100 条，按优先级）
  python scripts/llm_retry_batch.py --limit 100

  # 执行批量抽取（指定批次大小）
  python scripts/llm_retry_batch.py --limit 100 --batch-size 20

Environment:
  ANTHROPIC_API_KEY must be set for actual LLM extraction
  CHROMA_DB_PATH defaults to ./data/chroma_db
  REDIS_HOST defaults to localhost
  REDIS_PORT defaults to 6379
        """,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="处理数量限制 (默认: 100)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="批次大小 (默认: 10)",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="仅生成质量报告，不执行抽取",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览优先级队列，不执行抽取",
    )
    parser.add_argument(
        "--mock-redis",
        action="store_true",
        help="使用 mock Redis (用于测试)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 参数验证
    if args.limit <= 0:
        print("错误: --limit 必须大于 0")
        return 1

    if args.batch_size <= 0:
        print("错误: --batch-size 必须大于 0")
        return 1

    # --report-only 模式
    if args.report_only:
        return run_report_only(mock_redis=args.mock_redis)

    # 执行抽取
    return asyncio.run(run_extraction(
        limit=args.limit,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        mock_redis=args.mock_redis,
    ))


if __name__ == "__main__":
    sys.exit(main())
