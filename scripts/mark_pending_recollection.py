#!/usr/bin/env python3
# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
标记待重新采集的API

将低置信度或采集失败的API标记到Redis，在下次采集时优先处理
"""

import sys
sys.path.insert(0, 'src')

from asc_ops.storage import RedisClient
from asc_ops.config import get_config


# 4个待重新采集的API
PENDING_RECOLLECTION_APIS = [
    {"api_id": "331a92a5c1cedfa0", "name": "TPipe"},
    {"api_id": "8012946116b5b370", "name": "TBufPool"},
    {"api_id": "e18d9b52bfc4c250", "name": "TBuf"},
    {"api_id": "e3d85f753ee47431", "name": "OpMC2Def"},
]

# Redis键名
PENDING_COLLECTION_KEY = "ascendc:apis:pending_recollection"


def mark_for_recollection(redis: RedisClient, api_ids: list, dry_run: bool = True):
    """
    标记API为待重新采集

    Args:
        redis: Redis客户端
        api_ids: API ID列表
        dry_run: 是否仅模拟
    """
    if dry_run:
        print(f"[DRY-RUN] 将标记 {len(api_ids)} 个API为待重新采集:")
        for api_id in api_ids:
            print(f"  - {api_id}")
    else:
        # 添加到Set
        for api_id in api_ids:
            redis._client.sadd(PENDING_COLLECTION_KEY, api_id)
        print(f"✅ 已标记 {len(api_ids)} 个API为待重新采集")
        print(f"   Redis key: {PENDING_COLLECTION_KEY}")


def get_pending_apis(redis: RedisClient) -> list:
    """获取所有待重新采集的API"""
    api_ids = redis._client.smembers(PENDING_COLLECTION_KEY)
    return list(api_ids) if api_ids else []


def clear_pending(redis: RedisClient, api_ids: list = None):
    """清除待采集标记"""
    if api_ids:
        redis._client.srem(PENDING_COLLECTION_KEY, *api_ids)
        print(f"✅ 已清除 {len(api_ids)} 个待采集标记")
    else:
        redis._client.delete(PENDING_COLLECTION_KEY)
        print("✅ 已清除所有待采集标记")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='标记待重新采集的API')
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='仅显示，不执行')
    parser.add_argument('--execute', action='store_true',
                        help='执行标记')
    parser.add_argument('--clear', action='store_true',
                        help='清除待采集标记')
    parser.add_argument('--list', action='store_true',
                        help='列出当前待采集的API')
    parser.add_argument('--api-id', action='append',
                        help='指定API ID（可多次使用）')

    args = parser.parse_args()

    # 初始化Redis
    redis = RedisClient(mock=False)

    if args.clear:
        if args.dry_run and not args.execute:
            api_ids = get_pending_apis(redis)
            print(f"[DRY-RUN] 将清除 {len(api_ids)} 个待采集标记")
        else:
            api_ids = args.api_id
            clear_pending(redis, api_ids)
        return

    if args.list:
        pending = get_pending_apis(redis)
        print(f"当前待重新采集的API数量: {len(pending)}")
        for api_id in pending:
            print(f"  - {api_id}")
        return

    # 获取要标记的API
    if args.api_id:
        api_ids = args.api_id
    else:
        api_ids = [api["api_id"] for api in PENDING_RECOLLECTION_APIS]

    mark_for_recollection(redis, api_ids, dry_run=not args.execute)


if __name__ == '__main__':
    main()
