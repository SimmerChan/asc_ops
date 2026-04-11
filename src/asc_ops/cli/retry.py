# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
CLI 重试命令

使用 LLM 重新抽取失败的 BugFix/Optimization
"""

import argparse
import asyncio
import logging
import sys

from ..config import get_config
from ..extractor.retry import create_retry_instance

logger = logging.getLogger(__name__)


def add_retry_parser(subparsers) -> argparse.ArgumentParser:
    """添加 retry 子命令解析器"""
    parser = subparsers.add_parser(
        "retry",
        help="使用 LLM 重试抽取失败的知识点",
        description="从存储层获取抽取失败的记录，使用 LLM 重新抽取",
    )

    parser.add_argument(
        "--type",
        choices=["bugfix", "optimization", "all"],
        default="all",
        help="重试类型 (默认: all)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="最大重试数量 (默认: 100)",
    )

    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai", "zhipu", "minimax"],
        default="minimax",
        help="LLM Provider (默认: minimax)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出",
    )

    return parser


async def run_retry(args) -> int:
    """
    执行重试

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

    print("\n" + "=" * 50)
    print("  LLM Retry - 知识抽取重试")
    print("=" * 50)

    try:
        # 创建重试实例
        retry = await create_retry_instance(provider=args.provider)

        try:
            # 确定重试类型
            retry_bugfix = args.type in ("bugfix", "all")
            retry_optimization = args.type in ("optimization", "all")

            print(f"\n配置:")
            print(f"  - 重试类型: {args.type}")
            print(f"  - 最大数量: {args.limit}")
            print(f"  - LLM Provider: {args.provider}")
            print()

            # 执行重试
            results = await retry.retry_all(
                limit=args.limit,
                bugfix=retry_bugfix,
                optimization=retry_optimization,
            )

            # 显示结果
            print("\n" + "=" * 50)
            print("  重试结果")
            print("=" * 50)

            total_success = 0
            total_failed = 0
            total_skipped = 0

            for knowledge_type, stats in results.items():
                print(f"\n{knowledge_type.upper()}:")
                print(f"  总数: {stats.total}")
                print(f"  成功: {stats.success}")
                print(f"  失败: {stats.failed}")
                print(f"  跳过: {stats.skipped}")
                total_success += stats.success
                total_failed += stats.failed
                total_skipped += stats.skipped

            print("\n" + "=" * 50)
            print(f"总计: 成功 {total_success}, 失败 {total_failed}, 跳过 {total_skipped}")
            print("=" * 50)

            return 0 if total_failed == 0 else 1

        finally:
            await retry.close()

    except Exception as e:
        logger.error(f"重试失败: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
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

    # 添加 sync 子命令
    from .sync import add_sync_parser
    add_sync_parser(subparsers)

    # 添加 retry 子命令
    add_retry_parser(subparsers)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    # 执行对应的子命令
    if args.command == "sync":
        from .sync import run_sync
        return asyncio.run(run_sync(args))
    elif args.command == "retry":
        return asyncio.run(run_retry(args))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
