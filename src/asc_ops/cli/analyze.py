# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
CLI GPU-NPU 等价分析命令

分析 GPU 算子仓和 NPU 算子仓的代码对，发现等价关系
"""

import argparse
import asyncio
import logging
import sys
import json
from pathlib import Path
from typing import List, Tuple

from ..mapper.llm_analyzer import GPUNPUAnalysisEngine
from ..gpu_collector.storage import GPUStorage
from ..gpu_collector.models import GPUPlatform
from ..llm.client import UnifiedLLMClient
from ..config import load_peer_repos_config, PeerRepoConfig

logger = logging.getLogger(__name__)


def add_analyze_parser(subparsers) -> argparse.ArgumentParser:
    """添加 analyze-mapping 子命令解析器"""
    parser = subparsers.add_parser(
        "analyze-mapping",
        help="分析 GPU-NPU 代码对的等价关系",
        description="使用 LLM 分析 GPU 算子仓和 NPU 算子仓的代码对，发现等价关系",
    )

    parser.add_argument(
        "--gpu-repo",
        type=str,
        required=True,
        help="GPU 仓本地路径",
    )

    parser.add_argument(
        "--npu-repo",
        type=str,
        required=True,
        help="NPU 仓本地路径",
    )

    parser.add_argument(
        "--gpu-platform",
        type=str,
        default="cuda",
        choices=["cuda", "cutlass", "cublas", "cudnn"],
        help="GPU 平台类型 (默认: cuda)",
    )

    parser.add_argument(
        "--analysis-paths",
        type=str,
        nargs="+",
        default=[],
        help="要分析的子目录或文件路径（相对于仓根目录）",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="dry-run 模式：只输出分析结果，不持久化",
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出结果到指定文件 (JSON 格式)",
    )

    parser.add_argument(
        "--config",
        type=str,
        default="peer_repos.yaml",
        help="对等仓库配置文件 (默认: peer_repos.yaml)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出",
    )

    return parser


def discover_file_pairs(
    gpu_repo: Path,
    npu_repo: Path,
    analysis_paths: List[str],
) -> List[Tuple[Path, Path]]:
    """
    发现要分析的文件对

    Args:
        gpu_repo: GPU 仓根目录
        npu_repo: NPU 仓根目录
        analysis_paths: 要分析的路径列表（为空时扫描整个仓库）

    Returns:
        [(gpu_file, npu_file), ...] 列表
    """
    pairs = []

    # 如果没有指定路径，扫描整个仓库
    if not analysis_paths:
        pairs.extend(_discover_pairs_in_dir(gpu_repo, npu_repo))
    else:
        for path in analysis_paths:
            gpu_path = gpu_repo / path
            npu_path = npu_repo / path

            # 如果是文件，直接配对
            if gpu_path.is_file() and npu_path.is_file():
                pairs.append((gpu_path, npu_path))
            # 如果是目录，递归查找配对的源文件
            elif gpu_path.is_dir() and npu_path.is_dir():
                pairs.extend(_discover_pairs_in_dir(gpu_path, npu_path))

    return pairs


def _discover_pairs_in_dir(gpu_dir: Path, npu_dir: Path) -> List[Tuple[Path, Path]]:
    """递归发现文件对"""
    pairs = []
    # 使用 stem (不含扩展名) 作为 key 以匹配 .cu 和 .cpp 文件
    gpu_files = {f.stem: f for f in gpu_dir.rglob("*.cu") if f.is_file()}
    npu_files = {f.stem: f for f in npu_dir.rglob("*.cpp") if f.is_file()}

    # 配对相同文件名的文件
    for name in gpu_files:
        if name in npu_files:
            pairs.append((gpu_files[name], npu_files[name]))

    return pairs


async def run_analyze_mapping(args) -> int:
    """
    执行 GPU-NPU 等价分析

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
        gpu_repo = Path(args.gpu_repo)
        npu_repo = Path(args.npu_repo)

        # 验证路径
        if not gpu_repo.exists():
            print(f"错误: GPU 仓路径不存在: {gpu_repo}")
            return 1
        if not npu_repo.exists():
            print(f"错误: NPU 仓路径不存在: {npu_repo}")
            return 1

        # 确定 GPU 平台
        gpu_platform_map = {
            "cuda": GPUPlatform.CUDA,
            "cutlass": GPUPlatform.CUTLASS,
            "cublas": GPUPlatform.CUBLAS,
            "cudnn": GPUPlatform.CUDNN,
        }
        gpu_platform = gpu_platform_map.get(args.gpu_platform, GPUPlatform.CUDA)

        # 发现文件对
        print("\n" + "=" * 50)
        print("  GPU-NPU 等价分析工具")
        print("=" * 50)

        print(f"\n分析配置:")
        print(f"  - GPU 仓: {gpu_repo}")
        print(f"  - NPU 仓: {npu_repo}")
        print(f"  - GPU 平台: {args.gpu_platform}")
        print(f"  - 分析路径: {args.analysis_paths or '全部'}")
        print(f"  - 模式: {'dry-run' if args.dry_run else '持久化'}")

        # 发现文件对
        file_pairs = discover_file_pairs(
            gpu_repo,
            npu_repo,
            args.analysis_paths,
        )

        if not file_pairs:
            print("\n警告: 未发现可分析的文件对")
            return 1

        print(f"\n发现 {len(file_pairs)} 对文件待分析")

        # 初始化 LLM 客户端和存储
        llm_client = UnifiedLLMClient()
        storage = GPUStorage(use_mock=True)  # TODO: 使用实际存储

        # 创建分析引擎
        engine = GPUNPUAnalysisEngine(
            llm_client=llm_client,
            storage=storage,
        )

        # 执行分析
        print("\n开始分析...")
        results = []
        for i, (gpu_file, npu_file) in enumerate(file_pairs):
            print(f"  [{i+1}/{len(file_pairs)}] 分析: {gpu_file.name} <-> {npu_file.name}")

            if args.dry_run:
                # dry-run 模式：跳过 LLM 调用，只显示会分析哪些文件对
                from ..mapper.llm_analyzer import FilePairAnalysis, AnalysisResult
                from ..gpu_collector.models import MappingEquivalenceLevel

                gpu_api = gpu_file.stem.upper()
                if gpu_api.endswith("_KERNEL"):
                    gpu_api = gpu_api.replace("_KERNEL", "")
                if gpu_api.endswith("_OP"):
                    gpu_api = gpu_api.replace("_OP", "")

                analysis = FilePairAnalysis(
                    gpu_file=str(gpu_file),
                    npu_file=str(npu_file),
                    gpu_api=gpu_api,
                    gpu_platform=gpu_platform,
                    result=AnalysisResult(
                        is_equivalent=False,
                        npu_equivalent="N/A",
                        equivalence_level=MappingEquivalenceLevel.CONCEPTUAL_ONLY,
                        confidence=0.0,
                        adaptation_notes="dry-run mode",
                        optimization_hints="none",
                    ),
                    parsing_failed=False,
                )
                print(f"    [dry-run] GPU API: {gpu_api}")
            else:
                analysis = await engine.analyze_file_pair(
                    gpu_file=gpu_file,
                    npu_file=npu_file,
                    gpu_platform=gpu_platform,
                )
                print(f"    -> {analysis.gpu_api} -> {analysis.result.npu_equivalent} "
                      f"(置信度: {analysis.result.confidence:.2f})")

            results.append(analysis)

        # 统计结果
        total = len(results)
        equivalent = sum(1 for r in results if r.result.is_equivalent)
        high_conf = sum(1 for r in results if r.result.confidence >= 0.8)
        parsing_failed = sum(1 for r in results if r.parsing_failed)

        print(f"\n分析完成!")
        print(f"  - 总计: {total}")
        print(f"  - 等价: {equivalent}")
        print(f"  - 高置信度 (≥0.8): {high_conf}")
        print(f"  - 解析失败: {parsing_failed}")

        # 输出到文件
        if args.output:
            output_data = [
                {
                    "gpu_file": r.gpu_file,
                    "npu_file": r.npu_file,
                    "gpu_api": r.gpu_api,
                    "is_equivalent": r.result.is_equivalent,
                    "npu_equivalent": r.result.npu_equivalent,
                    "confidence": r.result.confidence,
                    "equivalence_level": r.result.equivalence_level.value,
                    "adaptation_notes": r.result.adaptation_notes,
                    "optimization_hints": r.result.optimization_hints,
                    "parsing_failed": r.parsing_failed,
                }
                for r in results
            ]
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"\n结果已输出到: {args.output}")

        # 非 dry-run 时存储结果
        if not args.dry_run:
            print("\n存储结果...")
            stored = 0
            for analysis in results:
                if engine.store_analysis_result(analysis, dry_run=False):
                    stored += 1
            print(f"已存储 {stored} 条映射")

        return 0

    except Exception as e:
        logger.exception(f"分析失败: {e}")
        print(f"\n错误: {e}")
        return 1


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        prog="asc-ops analyze",
        description="AscendC 知识库 CLI 工具",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 添加 analyze-mapping 子命令
    add_analyze_parser(subparsers)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    # 执行对应的子命令
    if args.command == "analyze-mapping":
        return asyncio.run(run_analyze_mapping(args))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
