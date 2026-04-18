#!/usr/bin/env python3
# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
C API 全量采集脚本

使用 Playwright 浏览器渲染采集完整的 C API 列表，
C API 使用不同的 URL 格式 (context/{category}/{api_name}.md)

使用方法:
    python scripts/collect_c_api.py [--limit N] [--headless] [--dry-run]
"""

import argparse
import asyncio
import logging
import sys
import time
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Set

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
import hashlib

from asc_ops.storage.collections import CollectionType
from asc_ops.config import get_config
from asc_ops.collector.api_storage import APIStorage


# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# C API 分类到导航路径的映射
C_API_NAV_MAPPING = {
    "struct": ("C API", "数据结构", ""),
    "cube_datamove": ("C API", "Cube数据搬运", ""),
    "vector_compute": ("C API", "向量计算", ""),
    "vector_datamove": ("C API", "向量数据搬运", ""),
    "scalar_compute": ("C API", "标量计算", ""),
    "cube_compute": ("C API", "Cube计算", ""),
    "sync": ("C API", "同步", ""),
    "sys_var": ("C API", "系统变量", ""),
    "cache_ctrl": ("C API", "缓存控制", ""),
    "simd_atomic": ("C API", "SIMD Atomic", ""),
    "misc": ("C API", "杂项", ""),
    "reg": ("C API", "寄存器操作", ""),
}


# SIMT API 前缀 (这些是SIMT API，不是C API)
SIMT_PREFIXES = [
    'asc_vf_call', 'asc_syncthreads', 'asc_threadfence', 'asc_atomic_',
    'asc_all', 'asc_any', 'asc_ballot', 'asc_activemask', 'asc_shfl',
    'asc_reduce_', 'asc_ldc', 'asc_stc'
]


@dataclass
class CAPICollectionStats:
    """采集统计"""
    discovered: int = 0
    new_apis: int = 0
    collected: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    elapsed_seconds: float = 0.0


def is_simt_api(name: str) -> bool:
    """判断是否是SIMT API"""
    return any(name.startswith(p) for p in SIMT_PREFIXES)


def get_c_api_nav_path(category: str, api_name: str) -> tuple:
    """获取C API的导航路径"""
    if category in C_API_NAV_MAPPING:
        base = C_API_NAV_MAPPING[category]
        return (*base, api_name)
    return ("C API", category, api_name)


def get_existing_api_ids() -> set:
    """获取现有知识库中的 API IDs"""
    import chromadb
    config = get_config()
    client = chromadb.PersistentClient(path=str(config.chroma.db_path))
    collection = client.get_collection(CollectionType.ASCEND_APIS.value)
    existing = collection.get(include=["metadatas"])

    existing_ids = set()
    for meta in existing.get("metadatas", []):
        if meta and "api_id" in meta:
            existing_ids.add(meta["api_id"])
    return existing_ids


async def fetch_page_content(url: str, timeout: int = 60000) -> str:
    """获取页面内容"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=timeout)
            await page.wait_for_load_state("networkidle", timeout=timeout)
            await asyncio.sleep(1)  # 等待JS执行
            content = await page.content()
            return content
        finally:
            await browser.close()


def parse_c_api_links(html: str) -> List[dict]:
    """解析C API页面，提取API链接"""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()

    BASE_URL = "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/context/"

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        name = a_tag.get_text(strip=True)

        # C API URL格式可能是:
        # 1. vector_datamove/asc_copy_gm2ub.md (相对路径)
        # 2. /document/detail/.../context/vector_datamove/asc_copy_gm2ub.md (绝对路径)
        if not name.startswith("asc_"):
            continue
        if name in seen:
            continue
        if is_simt_api(name):
            continue

        # 判断是否是C API链接 (在vector_datamove, cube_datamove等目录下)
        is_c_api = False
        category = ""
        if "vector_datamove/" in href or href.startswith("vector_datamove/"):
            category = "vector_datamove"
            is_c_api = True
        elif "cube_datamove/" in href or href.startswith("cube_datamove/"):
            category = "cube_datamove"
            is_c_api = True
        elif "vector_compute/" in href or href.startswith("vector_compute/"):
            category = "vector_compute"
            is_c_api = True
        elif "scalar_compute/" in href or href.startswith("scalar_compute/"):
            category = "scalar_compute"
            is_c_api = True
        elif "cube_compute/" in href or href.startswith("cube_compute/"):
            category = "cube_compute"
            is_c_api = True
        elif "sync/" in href or href.startswith("sync/"):
            category = "sync"
            is_c_api = True
        elif "sys_var/" in href or href.startswith("sys_var/"):
            category = "sys_var"
            is_c_api = True
        elif "cache_ctrl/" in href or href.startswith("cache_ctrl/"):
            category = "cache_ctrl"
            is_c_api = True
        elif "simd_atomic/" in href or href.startswith("simd_atomic/"):
            category = "simd_atomic"
            is_c_api = True
        elif "struct/" in href or href.startswith("struct/"):
            category = "struct"
            is_c_api = True
        elif "misc/" in href or href.startswith("misc/"):
            category = "misc"
            is_c_api = True
        elif "reg/" in href or href.startswith("reg/"):
            category = "reg"
            is_c_api = True

        if not is_c_api:
            continue

        seen.add(name)

        # 构建完整URL
        if href.startswith("http"):
            full_url = href
        else:
            full_url = BASE_URL + href.replace("./", "")

        links.append({
            "name": name,
            "url": full_url,
            "category": category
        })

    return links


async def collect_c_api_details(url: str, name: str, category: str, storage) -> tuple:
    """
    采集单个C API详情

    Returns:
        (success, error_message)
    """
    try:
        html = await fetch_page_content(url)

        # 解析页面
        from asc_ops.collector.parsers import parse_api_page
        result = parse_api_page(
            html=html,
            api_id=f"c_api_{name}",
            name=name,
            url=url,
            category="C API",
            subcategory=category,
        )

        if result.success and result.api_definition:
            result.api_definition.nav_path = get_c_api_nav_path(category, name)
            storage.store_api(result.api_definition)
            return True, ""
        elif result.api_definition:
            result.api_definition.nav_path = get_c_api_nav_path(category, name)
            storage.store_api(result.api_definition, skip_embedding=False)
            return True, f"degraded: {result.parse_errors}"
        else:
            return False, str(result.parse_errors)

    except Exception as e:
        return False, str(e)


async def run_c_api_collection(
    limit: int = None,
    headless: bool = True,
    dry_run: bool = False,
    rate_limit: float = 0.3,
) -> CAPICollectionStats:
    """
    执行C API全量采集

    Args:
        limit: 限制采集数量 (None = 全量)
        headless: 是否使用无头浏览器
        dry_run: 只发现不采集
        rate_limit: 请求间隔 (秒)

    Returns:
        CAPICollectionStats: 采集统计
    """
    stats = CAPICollectionStats()
    start_time = time.time()

    # 初始化存储
    config = get_config()
    storage = APIStorage(chroma_db_path=str(config.chroma.db_path))

    # Step 1: 获取现有 API IDs
    logger.info("=" * 50)
    logger.info("Step 1: 获取现有知识库 API IDs...")
    existing_ids = get_existing_api_ids()
    logger.info(f"现有知识库 API 数量: {len(existing_ids)}")

    # Step 2: 发现C API列表
    logger.info("=" * 50)
    logger.info("Step 2: 发现C API列表...")

    C_API_LIST_URL = "https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/ascendcopapi/context/c_api_list.md"

    html = await fetch_page_content(C_API_LIST_URL)
    all_links = parse_c_api_links(html)

    # 过滤新增API
    all_links = [l for l in all_links if f"c_api_{l['name']}" not in existing_ids]

    stats.discovered = len(all_links) + len(existing_ids)
    stats.new_apis = len(all_links)
    logger.info(f"C API总数: {stats.discovered}")
    logger.info(f"新增 C API 数量: {stats.new_apis}")

    if stats.new_apis == 0:
        logger.info("没有新增 C API，采集完成")
        stats.elapsed_seconds = time.time() - start_time
        return stats

    if dry_run:
        logger.info("=" * 50)
        logger.info("Dry run 模式，不执行采集")
        stats.elapsed_seconds = time.time() - start_time
        return stats

    # Step 3: 采集新增C API详情
    logger.info("=" * 50)
    logger.info("Step 3: 采集新增C API详情...")

    if limit:
        all_links = all_links[:limit]

    stats.collected = len(all_links)
    logger.info(f"待采集 C API 数量: {stats.collected}")

    for i, link in enumerate(all_links):
        success, error = await collect_c_api_details(
            link["url"], link["name"], link["category"], storage
        )

        if success:
            stats.succeeded += 1
        else:
            stats.failed += 1
            logger.warning(f"Failed to collect {link['name']}: {error}")

        await asyncio.sleep(rate_limit)

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

    stats.elapsed_seconds = time.time() - start_time
    return stats


def print_report(stats: CAPICollectionStats):
    """打印采集报告"""
    print("\n" + "=" * 50)
    print("  C API 全量采集报告")
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
        description="C API 全量采集脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/collect_c_api.py                    # 全量采集
  python scripts/collect_c_api.py --limit 50        # 只采集 50 个
  python scripts/collect_c_api.py --dry-run         # 只发现不采集
        """,
    )

    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="限制采集数量 (默认: 全量)",
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

    args = parser.parse_args()

    print("\n" + "=" * 50)
    print("  C API 全量采集 (Playwright 渲染版)")
    print("=" * 50)
    print(f"\n配置:")
    print(f"  - 采集限制:  {args.limit or '全量'}")
    print(f"  - Dry run:    {'是' if args.dry_run else '否'}")
    print(f"  - 请求间隔:   {args.rate_limit}s")

    stats = await run_c_api_collection(
        limit=args.limit,
        dry_run=args.dry_run,
        rate_limit=args.rate_limit,
    )

    print_report(stats)

    return 0 if stats.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
