#!/usr/bin/env python3
# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Redis 键前缀迁移脚本

将旧的 Redis 键前缀统一为新前缀：
- ascendc:citations:* → ascendc:stats:citation:*
- ascendc:corrections:* → ascendc:stats:correction:*
- ascendc:last_cited:* → ascendc:stats:last_cited:*
- ascendc:last_corrected:* → ascendc:stats:last_corrected:*
- ascendc:corrections:{entity}:{id}:{type} → ascendc:corrections:detail:{entity}:{id}:{type}
- ascendc:correction_reports:* → ascendc:corrections:*
- ascendc:correction_threshold:* → ascendc:corrections:threshold:*
"""

import sys
sys.path.insert(0, 'src')

from asc_ops.storage import RedisClient


# 旧前缀 → 新前缀映射
KEY_MIGRATIONS = [
    # CitationTracker 键
    ("ascendc:citations:", "ascendc:stats:citation:"),
    ("ascendc:corrections:", "ascendc:stats:correction:"),
    ("ascendc:last_cited:", "ascendc:stats:last_cited:"),
    ("ascendc:last_corrected:", "ascendc:stats:last_corrected:"),
    # FeedbackAPI 键
    ("ascendc:correction_reports:", "ascendc:corrections:reports:"),
    ("ascendc:correction_threshold:", "ascendc:corrections:threshold:"),
]


def migrate_keys(redis: RedisClient, dry_run: bool = True):
    """
    执行键迁移

    Args:
        redis: Redis 客户端
        dry_run: 是否仅模拟
    """
    migrated_count = 0
    deleted_count = 0

    # 1. 迁移 CitationTracker 键 (按类型处理)
    # citations 和 corrections 是 Sorted Set
    for old_prefix, new_prefix in [
        ("ascendc:citations:", "ascendc:stats:citation:"),
        ("ascendc:corrections:", "ascendc:stats:correction:"),
    ]:
        pattern = f"{old_prefix}*"
        keys = redis._client.keys(pattern)

        for old_key in keys:
            # 跳过已迁移的键
            if "ascendc:stats:" in old_key or "ascendc:corrections:detail:" in old_key:
                continue

            # 计算新键名
            new_key = old_key.replace(old_prefix, new_prefix, 1)

            if dry_run:
                print(f"[DRY-RUN] 会将: {old_key}")
                print(f"          迁移到: {new_key}")
            else:
                key_type = redis._client.type(old_key)
                if key_type == 'zset':
                    members = redis._client.zrange(old_key, 0, -1, withscores=True)
                    if members:
                        redis._client.zadd(new_key, dict(members))
                        redis._client.delete(old_key)
                        migrated_count += 1
                        print(f"  迁移: {old_key} → {new_key} ({len(members)} members)")
                elif key_type == 'string':
                    value = redis._client.get(old_key)
                    if value:
                        redis._client.set(new_key, value)
                        redis._client.delete(old_key)
                        migrated_count += 1
                        print(f"  迁移: {old_key} → {new_key}")

    # 2. 迁移 last_cited 和 last_corrected (String 类型)
    for old_prefix, new_prefix in [
        ("ascendc:last_cited:", "ascendc:stats:last_cited:"),
        ("ascendc:last_corrected:", "ascendc:stats:last_corrected:"),
    ]:
        pattern = f"{old_prefix}*"
        keys = redis._client.keys(pattern)

        for old_key in keys:
            if "ascendc:stats:" in old_key:
                continue

            new_key = old_key.replace(old_prefix, new_prefix, 1)

            if dry_run:
                print(f"[DRY-RUN] 会将: {old_key}")
                print(f"          迁移到: {new_key}")
            else:
                value = redis._client.get(old_key)
                if value:
                    redis._client.set(new_key, value)
                    redis._client.delete(old_key)
                    migrated_count += 1
                    print(f"  迁移: {old_key} → {new_key}")

    # 3. 迁移 FeedbackAPI 详细纠错键
    # ascendc:corrections:{entity}:{id}:{type} → ascendc:corrections:detail:{entity}:{id}:{type}
    correction_keys = redis._client.keys("ascendc:corrections:*:*:*")
    for old_key in correction_keys:
        # 跳过已迁移的
        if "ascendc:corrections:detail:" in old_key or "ascendc:corrections:reports:" in old_key:
            continue

        parts = old_key.split(':')
        # 格式: ascendc:corrections:{entity}:{id}:{type}
        if len(parts) == 5 and parts[0] == 'ascendc' and parts[1] == 'corrections':
            new_key = f"ascendc:corrections:detail:{parts[2]}:{parts[3]}:{parts[4]}"
            if dry_run:
                print(f"[DRY-RUN] 会将: {old_key}")
                print(f"          迁移到: {new_key}")
            else:
                value = redis._client.get(old_key)
                if value:
                    redis._client.set(new_key, value)
                    redis._client.delete(old_key)
                    migrated_count += 1
                    print(f"  迁移: {old_key} → {new_key}")

    # 4. 迁移 correction_reports 键 (list 类型)
    # ascendc:correction_reports:{entity}:{id} → ascendc:corrections:reports:{entity}:{id}
    correction_reports_keys = redis._client.keys("ascendc:correction_reports:*")
    for old_key in correction_reports_keys:
        # 跳过索引键（单独处理）
        if old_key.endswith(":index"):
            continue

        if "ascendc:corrections:reports:" in old_key:
            continue

        new_key = old_key.replace("ascendc:correction_reports:", "ascendc:corrections:reports:")

        if dry_run:
            print(f"[DRY-RUN] 会将: {old_key}")
            print(f"          迁移到: {new_key}")
        else:
            key_type = redis._client.type(old_key)
            if key_type == 'list':
                data = redis._client.lrange(old_key, 0, -1)
                if data:
                    redis._client.rpush(new_key, *data)
                    redis._client.delete(old_key)
                    migrated_count += 1
                    print(f"  迁移: {old_key} → {new_key} ({len(data)} items)")

    # 5. 迁移 correction_reports 索引
    old_index = "ascendc:correction_reports:index"
    new_index = "ascendc:corrections:index"

    if redis._client.exists(old_index):
        if dry_run:
            print(f"[DRY-RUN] 会将: {old_index}")
            print(f"          迁移到: {new_index}")
        else:
            members = redis._client.zrange(old_index, 0, -1, withscores=True)
            if members:
                redis._client.zadd(new_index, dict(members))
                redis._client.delete(old_index)
                migrated_count += 1
                print(f"  迁移: {old_index} → {new_index} ({len(members)} entries)")

    if dry_run:
        print(f"\n[DRY-RUN] 共发现 {migrated_count} 个键需要迁移")
        print("          使用 --execute 执行实际迁移")
    else:
        print(f"\n✅ 迁移完成: {migrated_count} 个键已迁移, {deleted_count} 个键已删除")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Redis 键前缀迁移脚本')
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='仅显示，不执行')
    parser.add_argument('--execute', action='store_true',
                        help='执行迁移')

    args = parser.parse_args()

    print("=" * 60)
    print("Redis 键前缀统一迁移")
    print("=" * 60)

    # 初始化 Redis
    redis = RedisClient(mock=False)

    # 显示当前键情况
    print("\n当前 Redis 键前缀分布:")
    all_keys = redis._client.keys("ascendc:*")
    prefixes = {}
    for key in all_keys:
        prefix = ':'.join(key.split(':')[:3]) if ':' in key else key
        prefixes[prefix] = prefixes.get(prefix, 0) + 1

    for prefix, count in sorted(prefixes.items()):
        print(f"  {prefix}*: {count} 个键")

    print()
    migrate_keys(redis, dry_run=not args.execute)


if __name__ == '__main__':
    main()
