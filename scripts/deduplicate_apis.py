#!/usr/bin/env python3
# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
API去重脚本

处理ChromaDB中的重复API记录，保留最高置信度条目
"""

import sys
import argparse
from collections import defaultdict
from typing import List, Dict, Tuple

# 添加项目根目录到路径
sys.path.insert(0, 'src')

from asc_ops.storage import ChromaDBClient
from asc_ops.storage.collections import CollectionType
from asc_ops.config import get_config


def analyze_duplicates(client: ChromaDBClient, collection_name: str) -> Dict[str, List[dict]]:
    """
    分析重复记录

    Returns:
        {name: [api_records...]} - 按名称分组的重复记录
    """
    col = client.get_collection(collection_name)
    results = col.get(include=['metadatas', 'documents', 'embeddings'])

    # 按名称分组
    by_name = defaultdict(list)
    for i, api_id in enumerate(results['ids']):
        metadata = results['metadatas'][i]
        document = results['documents'][i] if results['documents'] else ""

        name = metadata.get('name', '')
        if name:
            by_name[name].append({
                'api_id': api_id,
                'metadata': metadata,
                'document': document,
                'confidence': float(metadata.get('confidence', 0)),
            })

    # 筛选重复的
    duplicates = {k: v for k, v in by_name.items() if len(v) > 1}

    return duplicates


def decide_what_to_delete(records: List[dict]) -> List[str]:
    """
    决定删除哪些记录

    策略:
    1. 优先保留置信度高的
    2. 置信度相同时，保留描述更完整的
    3. 描述也相同时，随机选择

    Returns:
        要删除的api_id列表
    """
    # 按置信度降序，描述长度降序排序
    sorted_records = sorted(
        records,
        key=lambda r: (r['confidence'], len(r.get('document', '') or '')),
        reverse=True
    )

    # 保留第一条，删除其余的
    keep = sorted_records[0]
    delete = sorted_records[1:]

    return [r['api_id'] for r in delete], keep['api_id']


def deduplicate_collection(
    client: ChromaDBClient,
    collection_name: str,
    dry_run: bool = True
) -> Tuple[int, int, List[dict]]:
    """
    执行去重

    Returns:
        (删除数量, 保留数量, 删除详情)
    """
    duplicates = analyze_duplicates(client, collection_name)

    if not duplicates:
        print("没有发现重复记录")
        return 0, 0, []

    print(f"发现 {len(duplicates)} 个重复名称\n")

    to_delete = []
    to_keep_info = []

    for name, records in sorted(duplicates.items()):
        delete_ids, keep_id = decide_what_to_delete(records)

        print(f"=== {name} ({len(records)}条) ===")
        print(f"  保留: {keep_id} (conf={next(r['confidence'] for r in records if r['api_id'] == keep_id):.1f})")

        for r in records:
            action = "保留" if r['api_id'] == keep_id else "删除"
            print(f"    [{action}] {r['api_id'][:16]} conf={r['confidence']:.1f}")

        to_delete.extend(delete_ids)
        to_keep_info.append({
            'name': name,
            'keep_id': keep_id,
            'delete_count': len(delete_ids)
        })

    print(f"\n总结: 保留 {len(to_keep_info)} 条，删除 {len(to_delete)} 条")

    if not dry_run:
        # 执行删除
        col = client.get_collection(collection_name)

        # 使用ChromaDB的delete方法按ID删除
        print(f"\n🗑️ 删除 {len(to_delete)} 条重复记录...")
        delete_result = col.delete(ids=to_delete)

        print(f"✅ 删除完成: {delete_result}")

        print("✅ 去重完成")

    return len(to_delete), len(to_keep_info), to_keep_info


def analyze_low_confidence(client: ChromaDBClient, collection_name: str) -> List[dict]:
    """分析低置信度API"""
    col = client.get_collection(collection_name)
    results = col.get(include=['metadatas'])

    low_conf = []
    for i, api_id in enumerate(results['ids']):
        metadata = results['metadatas'][i]
        confidence = float(metadata.get('confidence', 1.0))
        if confidence < 0.5:
            low_conf.append({
                'api_id': api_id,
                'name': metadata.get('name', ''),
                'confidence': confidence,
                'has_description': bool(metadata.get('description', '')),
                'category': metadata.get('category', ''),
            })

    return low_conf


def print_statistics(client: ChromaDBClient, collection_name: str):
    """打印统计信息"""
    col = client.get_collection(collection_name)
    results = col.get(include=['metadatas'])
    metadatas = results['metadatas']

    print(f"\n=== {collection_name} 统计 ===")
    print(f"总记录数: {len(metadatas)}")

    # 按名称统计
    names = [m.get('name', '') for m in metadatas]
    from collections import Counter
    name_counts = Counter(names)
    duplicates = {k: v for k, v in name_counts.items() if v > 1}

    print(f"唯一名称数: {len(name_counts)}")
    print(f"重复名称数: {len(duplicates)}")
    print(f"重复记录总数: {sum(v - 1 for v in duplicates.values())}")

    # 置信度分布
    confidences = [float(m.get('confidence', 0)) for m in metadatas]
    low_conf = sum(1 for c in confidences if c < 0.5)
    print(f"低置信度(<0.5): {low_conf}")
    print(f"正常置信度: {len(confidences) - low_conf}")


def main():
    parser = argparse.ArgumentParser(description='API去重工具')
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='仅分析，不执行删除')
    parser.add_argument('--execute', action='store_true',
                        help='执行去重删除')
    parser.add_argument('--check-only', action='store_true',
                        help='仅检查，不执行')
    parser.add_argument('--collection', default='ascend_apis',
                        help='Collection名称')

    args = parser.parse_args()

    # 初始化客户端
    config = get_config()
    client = ChromaDBClient(persist_directory=str(config.chroma.db_path))

    print("=" * 60)
    print("API去重工具")
    print("=" * 60)

    # 打印统计
    print_statistics(client, args.collection)

    if args.check_only:
        print("\n--check-only 模式，仅分析")
        duplicates = analyze_duplicates(client, args.collection)
        if duplicates:
            print(f"\n发现 {len(duplicates)} 个重复名称:")
            for name, records in list(duplicates.items())[:5]:
                print(f"  {name}: {len(records)}条")
        else:
            print("没有发现重复")
        return

    if args.execute:
        print("\n--execute 模式，将执行删除")
        deduplicate_collection(client, args.collection, dry_run=False)
    else:
        print("\n默认dry-run模式，使用 --execute 执行删除")
        deduplicate_collection(client, args.collection, dry_run=True)

    # 分析低置信度
    print("\n" + "=" * 60)
    low_conf = analyze_low_confidence(client, args.collection)
    if low_conf:
        print(f"\n发现 {len(low_conf)} 个低置信度API:")
        for api in low_conf:
            print(f"  {api['name']}: conf={api['confidence']}, desc={api['has_description']}")
    else:
        print("\n没有发现低置信度API")


if __name__ == '__main__':
    main()
