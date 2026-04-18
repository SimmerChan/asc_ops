#!/usr/bin/env python3
# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
AscendC API 全量采集脚本

使用 Playwright 浏览器渲染采集完整的 AscendC API 列表，
对比现有知识库找出新增 API，进行全量采集和向量化存储。

使用方法:
    python scripts/full_collection.py [--limit N] [--headless] [--dry-run]
"""

import argparse
import asyncio
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from asc_ops.collector.browser_client import BrowserClient, BrowserAPILink
from asc_ops.collector.official_docs import OfficialDocsClient
from asc_ops.collector.parsers import parse_api_page
from asc_ops.collector.api_storage import APIStorage
from asc_ops.storage.collections import CollectionType
from asc_ops.config import get_config


# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class CollectionStats:
    """采集统计"""
    discovered: int = 0
    new_apis: int = 0
    collected: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    elapsed_seconds: float = 0.0


def get_existing_api_ids(storage: APIStorage) -> set:
    """获取现有知识库中的 API IDs"""
    import chromadb
    client = chromadb.PersistentClient(path=str(get_config().chroma.db_path))
    collection = client.get_collection(CollectionType.ASCEND_APIS.value)
    existing = collection.get(include=["metadatas"])

    existing_ids = set()
    for meta in existing.get("metadatas", []):
        if meta and "api_id" in meta:
            existing_ids.add(meta["api_id"])
    return existing_ids


async def collect_api_details(
    link: BrowserAPILink,
    docs_client: OfficialDocsClient,
    storage: APIStorage,
    rate_limit: float = 0.5,
) -> tuple[bool, str]:
    """
    采集单个 API 详情

    Returns:
        (success, error_message)
    """
    try:
        # 获取页面内容
        html = await docs_client.fetch_page(link.url)

        # 解析页面
        result = parse_api_page(
            html=html,
            api_id=link.api_id,
            name=link.name,
            url=link.url,
            category=link.category,
            subcategory=link.subcategory,
        )

        if result.success and result.api_definition:
            # 设置导航路径
            result.api_definition.nav_path = link.nav_path
            storage.store_api(result.api_definition)
            return True, ""
        elif result.api_definition:
            # 降级解析
            result.api_definition.nav_path = link.nav_path
            storage.store_api(result.api_definition, skip_embedding=False)
            return True, f"degraded: {result.parse_errors}"
        else:
            return False, str(result.parse_errors)

    except Exception as e:
        return False, str(e)


async def run_full_collection(
    limit: int = None,
    headless: bool = True,
    dry_run: bool = False,
    rate_limit: float = 0.3,
) -> CollectionStats:
    """
    执行全量采集

    Args:
        limit: 限制采集数量 (None = 全量)
        headless: 是否使用无头浏览器
        dry_run: 只发现不采集
        rate_limit: 请求间隔 (秒)

    Returns:
        CollectionStats: 采集统计
    """
    stats = CollectionStats()
    start_time = time.time()

    # 初始化存储 (使用配置的持久化路径)
    config = get_config()
    storage = APIStorage(chroma_db_path=str(config.chroma.db_path))

    # Step 1: 获取现有 API IDs
    logger.info("=" * 50)
    logger.info("Step 1: 获取现有知识库 API IDs...")
    existing_ids = get_existing_api_ids(storage)
    logger.info(f"现有知识库 API 数量: {len(existing_ids)}")

    # Step 2: 使用 Playwright 发现完整 API 列表
    logger.info("=" * 50)
    logger.info("Step 2: 使用 Playwright 发现完整 API 列表...")
    browser_client = BrowserClient(headless=headless)

    try:
        discovery_result = await browser_client.discover_api_links(cached_ids=existing_ids)
        stats.discovered = discovery_result.total_discovered

        # 找出新增 API
        all_links = discovery_result.new_links
        if existing_ids:
            all_links = [l for l in all_links if l.api_id not in existing_ids]

        stats.new_apis = len(all_links)
        logger.info(f"发现 API 总数: {stats.discovered}")
        logger.info(f"新增 API 数量: {stats.new_apis}")

        if stats.new_apis == 0:
            logger.info("没有新增 API，采集完成")
            stats.elapsed_seconds = time.time() - start_time
            return stats

    finally:
        await browser_client.close()

    # Step 3: 采集新增 API 详情
    if dry_run:
        logger.info("=" * 50)
        logger.info("Dry run 模式，不执行采集")
        stats.elapsed_seconds = time.time() - start_time
        return stats

    logger.info("=" * 50)
    logger.info("Step 3: 采集新增 API 详情...")

    # 限制采集数量
    if limit:
        all_links = all_links[:limit]

    stats.collected = len(all_links)
    logger.info(f"待采集 API 数量: {stats.collected}")

    # 初始化文档客户端
    docs_client = OfficialDocsClient()

    for i, link in enumerate(all_links):
        success, error = await collect_api_details(link, docs_client, storage, rate_limit)

        if success:
            stats.succeeded += 1
        else:
            stats.failed += 1
            logger.warning(f"Failed to collect {link.name}: {error}")

        # 限速
        await asyncio.sleep(rate_limit)

        # 进度报告
        if (i + 1) % 20 == 0 or (i + 1) == len(all_links):
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (len(all_links) - i - 1) / rate if rate > 0 else 0
            logger.info(
                f"进度: {i + 1}/{len(all_links)} "
                f"({100 * (i + 1) / len(all_links):.1f}%) "
                f"成功: {stats.succeeded} 失败: {stats.failed} "
                f"预计剩余: {remaining:.0f}s"
            )

    await docs_client.close()

    stats.elapsed_seconds = time.time() - start_time
    return stats


def print_report(stats: CollectionStats):
    """打印采集报告"""
    print("\n" + "=" * 50)
    print("  AscendC API 全量采集报告")
    print("=" * 50)
    print(f"\n采集统计:")
    print(f"  - 发现 API 总数:    {stats.discovered}")
    print(f"  - 新增 API 数量:    {stats.new_apis}")
    print(f"  - 实际采集数量:     {stats.collected}")
    print(f"  - 成功:             {stats.succeeded}")
    print(f"  - 失败:             {stats.failed}")
    print(f"  - 跳过:             {stats.skipped}")
    print(f"  - 总耗时:           {stats.elapsed_seconds:.1f}s")

    if stats.succeeded > 0:
        print(f"  - 平均速度:         {stats.succeeded / stats.elapsed_seconds:.1f} API/s")

    print("\n" + "=" * 50)

    if stats.failed > 0:
        print(f"\n警告: 有 {stats.failed} 个 API 采集失败")
        print("可重新运行脚本重试失败的 API")


async def main():
    parser = argparse.ArgumentParser(
        description="AscendC API 全量采集脚本 (Playwright 渲染版)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/full_collection.py                    # 全量采集
  python scripts/full_collection.py --limit 50         # 只采集 50 个
  python scripts/full_collection.py --dry-run            # 只发现不采集
  python scripts/full_collection.py --headless=False    # 显示浏览器窗口
        """,
    )

    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="限制采集数量 (默认: 全量)",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="使用无头模式 (默认: True)",
    )

    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="显示浏览器窗口 (调试用)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只发现新增 API，不执行采集",
    )

    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.3,
        help="请求间隔秒数 (默认: 0.3)",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 确定 headless 模式
    headless = args.headless and not args.no_headless

    print("\n" + "=" * 50)
    print("  AscendC API 全量采集 (Playwright 渲染版)")
    print("=" * 50)
    print(f"\n配置:")
    print(f"  - 采集限制:  {args.limit or '全量'}")
    print(f"  - 无头模式:   {'是' if headless else '否'}")
    print(f"  - Dry run:    {'是' if args.dry_run else '否'}")
    print(f"  - 请求间隔:   {args.rate_limit}s")

    # 执行采集
    stats = await run_full_collection(
        limit=args.limit,
        headless=headless,
        dry_run=args.dry_run,
        rate_limit=args.rate_limit,
    )

    # 打印报告
    print_report(stats)

    return 0 if stats.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
