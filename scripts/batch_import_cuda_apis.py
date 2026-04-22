#!/usr/bin/env python3
# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
批量导入 CUDA API 到知识库

用法:
    python scripts/batch_import_cuda_apis.py --collect
    python scripts/batch_import_cuda_apis.py --analyze
    python scripts/batch_import_cuda_apis.py --import
    python scripts/batch_import_cuda_apis.py --all
    python scripts/batch_import_cuda_apis.py --all --resume
"""

import argparse
import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from asc_ops.gpu_collector.doc_scraper import (
    CUDADocScraper,
    CUDAAPIScrapedData,
    WARP_SHUFFLE_APIS,
    WARP_VOTE_APIS,
    WARP_REDUCE_APIS,
    MEMORY_APIS,
    THREAD_SYNC_APIS,
    MEMORY_FENCE_APIS,
    STREAM_APIS,
    EVENT_APIS,
)
from asc_ops.gpu_collector.llm_semantic_analyzer import (
    CUDASemanticAnalyzer,
    SemanticAnalysisResult,
    BatchAnalysisResult,
)
from asc_ops.gpu_collector.models import GPUAPIInfo, GPUPlatform
from asc_ops.gpu_collector.storage import GPUStorage
from asc_ops.llm import UnifiedLLMClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 检查点文件
CHECKPOINT_DIR = Path(__file__).parent.parent / "data" / "checkpoints"
CHECKPOINT_FILE = CHECKPOINT_DIR / "cuda_apis_import.json"


def load_checkpoint() -> Dict[str, Any]:
    """加载检查点"""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"stage": "init", "processed_apis": [], "errors": []}


def save_checkpoint(data: Dict[str, Any]):
    """保存检查点"""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def collect_cuda_apis(
    headless: bool = True,
) -> List[CUDAAPIScrapedData]:
    """
    采集 CUDA API

    Args:
        headless: 是否使用无头模式

    Returns:
        CUDAAPIScrapedData 列表
    """
    logger.info("Starting CUDA API collection...")

    async with CUDADocScraper(headless=headless) as scraper:
        all_apis = []

        # 采集 Warp Shuffle/Vote/Reduce APIs (所有 warp-level APIs)
        logger.info(f"Collecting {len(WARP_SHUFFLE_APIS) + len(WARP_VOTE_APIS) + len(WARP_REDUCE_APIS)} warp-level APIs...")
        warp_apis = await scraper.scrape_warp_shuffle_apis()
        all_apis.extend(warp_apis)
        logger.info(f"Collected {len(warp_apis)} warp-level APIs")

        # 采集 Memory APIs
        logger.info(f"Collecting {len(MEMORY_APIS)} memory APIs...")
        memory_apis = await scraper.scrape_memory_apis()
        all_apis.extend(memory_apis)
        logger.info(f"Collected {len(memory_apis)} memory APIs")

        # 采集 Thread Synchronization APIs
        logger.info(f"Collecting {len(THREAD_SYNC_APIS)} thread sync APIs...")
        thread_sync_apis = await scraper.scrape_thread_sync_apis()
        all_apis.extend(thread_sync_apis)
        logger.info(f"Collected {len(thread_sync_apis)} thread sync APIs")

        # 采集 Memory Fence APIs
        logger.info(f"Collecting {len(MEMORY_FENCE_APIS)} memory fence APIs...")
        memory_fence_apis = await scraper.scrape_memory_fence_apis()
        all_apis.extend(memory_fence_apis)
        logger.info(f"Collected {len(memory_fence_apis)} memory fence APIs")

        # 采集 Stream APIs
        logger.info(f"Collecting {len(STREAM_APIS)} stream APIs...")
        stream_apis = await scraper.scrape_stream_apis()
        all_apis.extend(stream_apis)
        logger.info(f"Collected {len(stream_apis)} stream APIs")

        # 采集 Event APIs
        logger.info(f"Collecting {len(EVENT_APIS)} event APIs...")
        event_apis = await scraper.scrape_event_apis()
        all_apis.extend(event_apis)
        logger.info(f"Collected {len(event_apis)} event APIs")

        logger.info(f"Total collected: {len(all_apis)} APIs")
        return all_apis


async def analyze_apis_with_llm(
    apis: List[CUDAAPIScrapedData],
    llm_client: Optional[UnifiedLLMClient] = None,
    batch_size: int = 50,
) -> BatchAnalysisResult:
    """
    使用 LLM 分析 API

    Args:
        apis: API 列表
        llm_client: LLM 客户端
        batch_size: 批大小

    Returns:
        BatchAnalysisResult
    """
    logger.info(f"Starting LLM semantic analysis for {len(apis)} APIs...")

    analyzer = CUDASemanticAnalyzer(
        llm_client=llm_client,
        batch_size=batch_size,
    )

    def progress_callback(completed: int, total: int):
        logger.info(f"Progress: {completed}/{total} ({100 * completed / total:.1f}%)")

    result = await analyzer.analyze_batch(apis, progress_callback)

    logger.info(f"LLM analysis complete: {result.successful} successful, {result.failed} failed")
    return result


def import_apis_to_storage(
    apis: List[CUDAAPIScrapedData],
    analyses: List[SemanticAnalysisResult],
    storage: GPUStorage,
    embedder=None,
    resume: bool = False,
) -> tuple[int, int]:
    """
    导入 APIs 到存储

    Args:
        apis: API 数据列表
        analyses: 语义分析结果列表
        storage: GPU 存储实例
        embedder: Embedder 实例
        resume: 是否从检查点恢复

    Returns:
        (成功数, 失败数)
    """
    logger.info(f"Importing {len(apis)} APIs to storage...")

    # 构建分析结果映射
    analysis_map = {a.api_name: a for a in analyses}

    successful = 0
    failed = 0
    checkpoint = load_checkpoint()
    processed = set(checkpoint.get("processed_apis", []))

    for api_data in apis:
        # 检查是否已处理（resume 模式）
        if resume and api_data.api_name in processed:
            logger.debug(f"Skipping already processed: {api_data.api_name}")
            continue

        try:
            # 获取语义分析结果
            analysis = analysis_map.get(api_data.api_name)

            # 构建 GPUAPIInfo
            api = GPUAPIInfo(
                api_id=f"cuda-api-{uuid.uuid4().hex[:8]}",
                api_name=api_data.api_name,
                platform=GPUPlatform.CUDA,
                full_signature=api_data.full_signature,
                description=analysis.semantic_description if analysis else api_data.description,
                parameters=api_data.parameters,
                return_type=api_data.return_type,
                category=api_data.category,
                subcategory=api_data.subcategory,
                documentation_url=api_data.documentation_url,
            )

            # 生成 embedding
            if embedder and api.description:
                api.description_embedding = embedder.encode_api(api.description)

            # 存储
            if embedder:
                storage.store_api_with_embedding(api, embedder)
            else:
                storage.store_api(api)

            successful += 1
            processed.add(api_data.api_name)

            # 更新检查点
            checkpoint["processed_apis"] = list(processed)
            save_checkpoint(checkpoint)

            logger.info(f"Imported: {api_data.api_name}")

        except Exception as e:
            failed += 1
            checkpoint["errors"].append({
                "api_name": api_data.api_name,
                "error": str(e),
            })
            save_checkpoint(checkpoint)
            logger.error(f"Failed to import {api_data.api_name}: {e}")

    logger.info(f"Import complete: {successful} successful, {failed} failed")
    return successful, failed


def save_collected_apis(apis: List[CUDAAPIScrapedData], filepath: Path):
    """保存采集的 API 数据"""
    data = {
        "collected_at": datetime.now().isoformat(),
        "total": len(apis),
        "apis": [
            {
                "api_name": a.api_name,
                "full_signature": a.full_signature,
                "description": a.description,
                "category": a.category,
                "subcategory": a.subcategory,
                "parameters": a.parameters,
                "return_type": a.return_type,
                "documentation_url": a.documentation_url,
            }
            for a in apis
        ],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved collected APIs to {filepath}")


def load_collected_apis(filepath: Path) -> List[CUDAAPIScrapedData]:
    """加载采集的 API 数据"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [
        CUDAAPIScrapedData(
            api_name=a["api_name"],
            full_signature=a["full_signature"],
            description=a["description"],
            category=a["category"],
            subcategory=a["subcategory"],
            parameters=a["parameters"],
            return_type=a["return_type"],
            documentation_url=a["documentation_url"],
        )
        for a in data["apis"]
    ]


def save_analysis_results(
    analyses: List[SemanticAnalysisResult],
    filepath: Path,
):
    """保存分析结果"""
    data = {
        "analyzed_at": datetime.now().isoformat(),
        "total": len(analyses),
        "results": [a.to_dict() for a in analyses],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved analysis results to {filepath}")


def load_analysis_results(filepath: Path) -> List[SemanticAnalysisResult]:
    """加载分析结果"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [
        SemanticAnalysisResult(
            api_name=r["api_name"],
            semantic_description=r["semantic_description"],
            keywords=r["keywords"],
            operation_type=r["operation_type"],
            complexity_hint=r["complexity_hint"],
        )
        for r in data["results"]
    ]


async def run_full_pipeline(
    headless: bool = True,
    batch_size: int = 50,
    resume: bool = False,
):
    """
    运行完整流程

    Args:
        headless: 是否使用无头模式
        batch_size: 批大小
        resume: 是否恢复
    """
    # 数据文件路径
    data_dir = Path(__file__).parent.parent / "data"
    collected_file = data_dir / "cuda_apis_collected.json"
    analyzed_file = data_dir / "cuda_apis_analyzed.json"

    # 初始化存储
    storage = GPUStorage(use_mock=False)

    # 初始化 LLM 客户端
    llm_client = None
    try:
        llm_client = UnifiedLLMClient.from_env()
        logger.info("LLM client initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize LLM client: {e}")
        logger.warning("Will use fallback semantic analysis")

    # 步骤 1: 采集
    if resume and collected_file.exists():
        logger.info("Resuming from collected APIs...")
        apis = load_collected_apis(collected_file)
    else:
        apis = await collect_cuda_apis(headless=headless)
        save_collected_apis(apis, collected_file)

    # 步骤 2: LLM 分析
    if resume and analyzed_file.exists():
        logger.info("Resuming from analyzed results...")
        analyses = load_analysis_results(analyzed_file)
    else:
        analyses_result = await analyze_apis_with_llm(apis, llm_client, batch_size)
        analyses = analyses_result.results
        save_analysis_results(analyses, analyzed_file)

    # 步骤 3: 导入到存储
    # 注意：需要 embedder 来生成向量
    # 如果没有 embedder，导入将只存储文本描述
    embedder = None
    try:
        from asc_ops.collector.embedder import QwenEmbedder
        embedder = QwenEmbedder(
            model_name="Qwen/Qwen3-Embedding-0.6B",
            embedding_dim=1024,
            batch_size=8,
            device="mps",  # Apple Silicon
        )
        logger.info("Embedder initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize embedder: {e}")

    successful, failed = import_apis_to_storage(
        apis, analyses, storage, embedder, resume
    )

    logger.info(f"\n{'=' * 50}")
    logger.info(f"Pipeline complete!")
    logger.info(f"  Total APIs: {len(apis)}")
    logger.info(f"  Successful imports: {successful}")
    logger.info(f"  Failed imports: {failed}")
    logger.info(f"{'=' * 50}")


def main():
    parser = argparse.ArgumentParser(description="Batch import CUDA APIs to knowledge base")
    parser.add_argument("--collect", action="store_true", help="Only collect APIs")
    parser.add_argument("--analyze", action="store_true", help="Only analyze collected APIs")
    parser.add_argument("--import-only", action="store_true", help="Only import (requires collected and analyzed data)")
    parser.add_argument("--all", action="store_true", help="Run full pipeline")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for LLM analysis")
    parser.add_argument("--data-dir", type=Path, default=None, help="Data directory")

    args = parser.parse_args()

    if args.all:
        asyncio.run(run_full_pipeline(
            headless=args.headless,
            batch_size=args.batch_size,
            resume=args.resume,
        ))
    elif args.collect:
        apis = asyncio.run(collect_cuda_apis(headless=args.headless))
        print(f"\nCollected {len(apis)} APIs:")
        for api in apis:
            print(f"  - {api.api_name}: {api.category}")
    elif args.analyze:
        data_dir = args.data_dir or Path(__file__).parent.parent / "data"
        collected_file = data_dir / "cuda_apis_collected.json"
        if not collected_file.exists():
            logger.error(f"Collected data not found: {collected_file}")
            sys.exit(1)
        apis = load_collected_apis(collected_file)
        analyses = asyncio.run(analyze_apis_with_llm(apis, batch_size=args.batch_size))
        print(f"\nAnalyzed {len(apis)} APIs:")
        print(f"  Successful: {analyses.successful}")
        print(f"  Failed: {analyses.failed}")
    elif args.import_only:
        storage = GPUStorage(use_mock=False)
        data_dir = args.data_dir or Path(__file__).parent.parent / "data"
        apis = load_collected_apis(data_dir / "cuda_apis_collected.json")
        analyses = load_analysis_results(data_dir / "cuda_apis_analyzed.json")
        successful, failed = import_apis_to_storage(apis, analyses, storage, resume=args.resume)
        print(f"\nImported: {successful} successful, {failed} failed")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
