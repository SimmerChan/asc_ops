#!/usr/bin/env python3
# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
迁移脚本：为已采集的 API 更新 nav_path

基于官方导航结构映射表，批量更新 ChromaDB 中现有 API 的 nav_path 字段
"""

import sys
import json
import logging
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chromadb import PersistentClient
from asc_ops.storage.collections import CollectionType
from asc_ops.config import get_config
from asc_ops.collector.browser_client import API_NAV_MAPPING

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_nav_path_by_name(name: str) -> str:
    """根据 API 名称获取 nav_path JSON 字符串"""
    if name in API_NAV_MAPPING:
        nav_tuple = API_NAV_MAPPING[name]
        return json.dumps(nav_tuple)
    return ""


def migrate_nav_path(dry_run: bool = True) -> dict:
    """
    迁移 nav_path

    Args:
        dry_run: 如果为 True，只打印将要进行的更改，不实际执行

    Returns:
        迁移统计
    """
    config = get_config()
    client = PersistentClient(path=str(config.chroma.db_path))
    collection = client.get_collection(CollectionType.ASCEND_APIS.value)

    # 获取所有数据（包含 embeddings 和 documents）
    results = collection.get(include=["metadatas", "embeddings", "documents"])

    stats = {
        "total": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    # 按批次处理
    batch_size = 100
    ids = results.get("ids", [])
    embeddings = results.get("embeddings", [])
    documents = results.get("documents", [])
    metadatas = results.get("metadatas", [])

    stats["total"] = len(ids)
    logger.info(f"开始迁移 {stats['total']} 个 API 的 nav_path...")

    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i + batch_size]
        batch_embeddings = embeddings[i:i + batch_size]
        batch_documents = documents[i:i + batch_size]
        batch_metas = metadatas[i:i + batch_size]

        updated_metas = []
        needs_update = False

        for j, meta in enumerate(batch_metas):
            if not meta:
                stats["skipped"] += 1
                updated_metas.append(meta)
                continue

            api_name = meta.get("name", "")
            current_nav_path = meta.get("nav_path", "")

            # 获取新的 nav_path
            new_nav_path = get_nav_path_by_name(api_name)

            if new_nav_path and new_nav_path != current_nav_path:
                # 需要更新
                if dry_run:
                    logger.info(f"[DRY RUN] Would update: {api_name} -> {new_nav_path}")
                updated_metas.append({**meta, "nav_path": new_nav_path})
                stats["updated"] += 1
                needs_update = True
            elif current_nav_path:
                # 已有 nav_path，跳过
                stats["skipped"] += 1
                updated_metas.append(meta)
            else:
                # 没有对应映射，跳过
                stats["skipped"] += 1
                updated_metas.append(meta)

        # 批量更新
        if not dry_run and needs_update:
            try:
                collection.upsert(
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    documents=batch_documents,
                    metadatas=updated_metas,
                )
                logger.info(f"Batch {i}-{i+batch_size} updated successfully")
            except Exception as e:
                logger.error(f"Batch update failed at {i}: {e}")
                stats["errors"] += len(batch_ids)

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="迁移 API nav_path",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/migrate_nav_path.py              # 只打印将要进行的更改
  python scripts/migrate_nav_path.py --execute    # 执行迁移
        """,
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行迁移（默认只打印将要进行的更改）",
    )

    args = parser.parse_args()

    print("\n" + "=" * 50)
    print("  API nav_path 迁移脚本")
    print("=" * 50)

    if args.execute:
        print("\n⚠️  执行迁移（不是 dry run）")
        stats = migrate_nav_path(dry_run=False)
    else:
        print("\n🔍 Dry run 模式，只打印将要进行的更改")
        stats = migrate_nav_path(dry_run=True)

    print("\n" + "=" * 50)
    print("  迁移统计")
    print("=" * 50)
    print(f"  总数:     {stats['total']}")
    print(f"  待更新:   {stats['updated']}")
    print(f"  跳过:    {stats['skipped']}")
    print(f"  错误:    {stats['errors']}")

    if not args.execute and stats['updated'] > 0:
        print("\n" + "=" * 50)
        print(f"执行以下命令完成迁移:")
        print(f"  python scripts/migrate_nav_path.py --execute")

    return 0


if __name__ == "__main__":
    sys.exit(main())
