# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
CLI 采集命令

提供命令行接口采集 AscendC API 文档
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime

from ..collector.api_collector import APICollector

logger = logging.getLogger(__name__)


def add_collect_parser(subparsers) -> argparse.ArgumentParser:
    """添加 collect 子命令解析器"""
    parser = subparsers.add_parser(
        "collect",
        help="采集 AscendC API 文档",
        description="从昇腾官方文档采集 API 知识",
    )

    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="限制采集数量 (默认: 全量)",
    )

    parser.add_argument(
        "--resume/--no-resume",
        default=True,
        help="是否从断点继续 (默认: True)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出",
    )

    return parser


async def run_collect(args) -> int:
    """
    执行采集

    Args:
        args: 解析后的命令行参数

    Returns:
        0 成功, 1 失败
    """
    # 设置日志级别
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    try:
        collector = APICollector()

        print("\n" + "=" * 50)
        print("  AscendC API 采集工具")
        print("=" * 50)

        print(f"\n采集配置:")
        print(f"  - 限制数量: {args.limit or '全量'}")
        print(f"  - 断点续采: {'是' if args.resume else '否'}")

        # 获取当前进度
        progress = collector.get_progress()
        if progress["total"] > 0:
            print(f"\n当前进度:")
            print(f"  - 已完成: {progress['completed']}/{progress['total']}")
            print(f"  - 失败: {progress['failed']}")
            print(f"  - 进度: {progress['progress']:.1f}%")

        print(f"\n开始采集...")

        # 执行采集
        result = await collector.run_full_collection(
            limit=args.limit,
            resume=args.resume,
        )

        # 显示结果
        print(f"\n采集结果:")
        print(f"  - 总数: {result['total']}")
        print(f"  - 成功: {result['success']}")
        print(f"  - 失败: {result['failed']}")
        print(f"  - 耗时: {result['duration_seconds']:.2f}s")

        print("\n" + "=" * 50)

        if result["failed"] > 0:
            print(f"\n警告: 有 {result['failed']} 个 API 采集失败")
            print("使用 --resume 重新运行以重试失败的 API")

        return 0 if result["failed"] == 0 else 1

    except Exception as e:
        logger.error(f"采集失败: {e}")
        return 1


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        prog="asc_kb",
        description="AscendC 知识库命令行工具",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 添加 collect 子命令
    add_collect_parser(subparsers)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    # 执行对应的子命令
    if args.command == "collect":
        return asyncio.run(run_collect(args))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
