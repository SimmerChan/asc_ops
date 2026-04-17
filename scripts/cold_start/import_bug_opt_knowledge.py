#!/usr/bin/env python3
# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Bug/优化知识批量导入脚本

从昇腾算子仓的本地 git 仓库导入 Bug/优化知识。
使用规则抽取器（无 LLM），所有 commits 都存储（包括 extraction_success=False 的）。

Usage:
    python scripts/cold_start/import_bug_opt_knowledge.py [--repo REPO] [--limit N] [--dry-run]

Environment:
    REPOS_YAML_PATH: repos.yaml 配置文件路径 (默认: ./repos.yaml)
    CHROMA_DB_PATH: ChromaDB 路径 (默认: ./data/chroma_db)
    REDIS_HOST: Redis 主机 (默认: localhost)
    REDIS_PORT: Redis 端口 (默认: 6379)

Config (repos.yaml):
    每个仓库可配置 local_path 指定本地路径，优先于默认的克隆路径。
"""

import argparse
import logging
import os
import subprocess
import sys
import yaml
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from asc_ops.extractor.bug_extractor import BugExtractor, BugExtractionResult
from asc_ops.extractor.opt_extractor import OptimizationExtractor, OptimizationExtractionResult
from asc_ops.extractor.knowledge_storage import KnowledgeStorage
from asc_ops.extractor.classifier import PRClassifier, PRType
from asc_ops.storage.redis_client import RedisClient
from asc_ops.storage.chroma_client import ChromaDBClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# 仓库列表
ASCEND_REPOS = [
    "HierarchicalKV-ascend",
    "fbgemm-ascend",
    "ops-nn",
    "ops-math",
    "ops-transformer",
    "ops-cv",
]


def get_repos_config() -> Dict[str, dict]:
    """
    从 repos.yaml 加载仓库配置

    Returns:
        Dict[str, dict]: {仓库名: {platform, local_path, ...}}
    """
    config_path = Path(os.environ.get("REPOS_YAML_PATH", "./repos.yaml"))
    if not config_path.exists():
        logger.warning(f"repos.yaml not found: {config_path}")
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    repos = config.get("repos", []) if config else []
    return {repo["name"]: repo for repo in repos}


def get_repo_path(repo_name: str) -> Path:
    """
    获取单个仓库的路径

    优先从 repos.yaml 的 local_path 配置获取，
    其次使用仓库根目录下的子目录。

    Args:
        repo_name: 仓库名称 (如 "CANN/ops-nn" 或 "ops-nn")

    Returns:
        Path: 仓库路径
    """
    repos_config = get_repos_config()

    # 支持简短名称匹配 (如 "ops-nn" 匹配 "CANN/ops-nn")
    full_name = None
    short_name = None
    for name in repos_config:
        if name.endswith(f"/{repo_name}"):
            full_name = name
            short_name = name.split("/")[-1]
            break
        if name == repo_name:
            full_name = name
            short_name = repo_name
            break

    # 优先使用 repos.yaml 中的 local_path
    if full_name and full_name in repos_config:
        local_path = repos_config[full_name].get("local_path")
        if local_path:
            path = Path(local_path)
            if path.exists():
                logger.info(f"使用 repos.yaml 配置路径 for {repo_name}: {path}")
                return path
            else:
                logger.warning(f"repos.yaml 配置路径不存在: {path}, fallback to default")

    # 其次使用默认仓库根目录
    base_path = Path(os.environ.get("ASCEND_REPO_BASE_PATH", "/tmp/ascend_repos"))
    return base_path / repo_name


@dataclass
class CommitInfo:
    """Commit 信息"""
    repo: str
    commit_hash: str
    message: str
    author: str
    date: str


@dataclass
class ImportStats:
    """导入统计"""
    total_commits: int = 0
    bugfix_commits: int = 0
    optimization_commits: int = 0
    bug_stored: int = 0
    bug_failed: int = 0
    opt_stored: int = 0
    opt_failed: int = 0
    skipped: int = 0


def classify_commit(message: str) -> PRType:
    """
    使用 PRClassifier 对 commit message 进行分类

    Args:
        message: commit message

    Returns:
        PRType: 分类结果
    """
    classifier = PRClassifier()
    return classifier.classify(message, "").pr_type


def get_commits(repo_path: Path, max_count: Optional[int] = None) -> List[CommitInfo]:
    """
    获取仓库的 commit 信息

    Args:
        repo_path: 仓库路径
        max_count: 最大获取数量

    Returns:
        CommitInfo 列表
    """
    cmd = [
        "git", "-C", str(repo_path), "log",
        "--format=%H|%s|%an|%ad",
        "--date=short",
    ]
    if max_count:
        cmd.append(f"--max-count={max_count}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) >= 4:
                commits.append(CommitInfo(
                    repo=repo_path.name,
                    commit_hash=parts[0],
                    message=parts[1],
                    author=parts[2],
                    date=parts[3],
                ))
        return commits
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get commits from {repo_path}: {e}")
        return []


def create_storage(mock_redis: bool = False) -> KnowledgeStorage:
    """创建知识存储实例

    直接使用默认配置，避免通过 AppConfig 的环境变量解析问题

    Args:
        mock_redis: 是否使用 mock Redis (用于测试)
    """
    # 使用默认值创建客户端
    redis_client = RedisClient(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        db=int(os.environ.get("REDIS_DB", "0")),
        password=os.environ.get("REDIS_PASSWORD"),
        mock=mock_redis,
    )
    chroma_client = ChromaDBClient(
        persist_directory=os.environ.get("CHROMA_DB_PATH", "./data/chroma_db"),
    )

    return KnowledgeStorage(
        chroma_client=chroma_client,
        redis_client=redis_client,
    )


def import_from_repository(
    repo_name: str,
    storage: KnowledgeStorage,
    bug_extractor: BugExtractor,
    opt_extractor: OptimizationExtractor,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> ImportStats:
    """
    从单个仓库导入知识

    Args:
        repo_name: 仓库名称
        storage: 知识存储实例
        bug_extractor: Bug 抽取器
        opt_extractor: Optimization 抽取器
        limit: 最大 commit 数量
        dry_run: 是否只打印不存储

    Returns:
        ImportStats: 导入统计
    """
    stats = ImportStats()

    repo_path = get_repo_path(repo_name)
    if not repo_path.exists():
        logger.warning(f"Repository not found: {repo_path}")
        return stats

    logger.info(f"Fetching commits from {repo_name}...")
    commits = get_commits(repo_path, max_count=limit)
    stats.total_commits = len(commits)

    if stats.total_commits == 0:
        logger.warning(f"No commits found in {repo_name}")
        return stats

    logger.info(f"Processing {stats.total_commits} commits from {repo_name}")

    for commit in commits:
        try:
            # 分类
            pr_type = classify_commit(commit.message)

            if pr_type == PRType.BUGFIX:
                stats.bugfix_commits += 1
                result = bug_extractor.extract(
                    pr_title=commit.message,
                    pr_body="",  # commit 没有 body
                    source_repo=commit.repo,
                    source_pr=commit.commit_hash,
                )

                if dry_run:
                    logger.info(f"  [DRY RUN] BugFix: {commit.commit_hash[:8]} - {commit.message[:50]}...")
                    stats.bug_stored += 1
                else:
                    # 关键：使用 store_failed=True 存储所有结果（包括 extraction_success=False）
                    success = storage.store_bugfix(result, store_failed=True)
                    if success:
                        stats.bug_stored += 1
                    else:
                        stats.bug_failed += 1

            elif pr_type == PRType.OPTIMIZATION:
                stats.optimization_commits += 1
                result = opt_extractor.extract(
                    pr_title=commit.message,
                    pr_body="",
                    source_repo=commit.repo,
                    source_pr=commit.commit_hash,
                )

                if dry_run:
                    logger.info(f"  [DRY RUN] Optimization: {commit.commit_hash[:8]} - {commit.message[:50]}...")
                    stats.opt_stored += 1
                else:
                    success = storage.store_optimization(result, store_failed=True)
                    if success:
                        stats.opt_stored += 1
                    else:
                        stats.opt_failed += 1

            else:
                stats.skipped += 1

        except Exception as e:
            logger.error(f"  Error processing commit {commit.commit_hash[:8]}: {e}")
            stats.bug_failed += 1

    return stats


def print_stats(stats: ImportStats, repo_name: str):
    """打印统计信息"""
    print(f"\n{'='*60}")
    print(f"仓库: {repo_name}")
    print(f"{'='*60}")
    print(f"总 commits: {stats.total_commits}")
    print(f"  - Bugfix: {stats.bugfix_commits}")
    print(f"  - Optimization: {stats.optimization_commits}")
    print(f"  - Skipped (feature/other): {stats.skipped}")
    print(f"\n存储结果:")
    print(f"  - BugFix stored: {stats.bug_stored} (failed: {stats.bug_failed})")
    print(f"  - Optimization stored: {stats.opt_stored} (failed: {stats.opt_failed})")


def main():
    parser = argparse.ArgumentParser(
        description="从昇腾算子仓导入 Bug/优化知识",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 导入所有仓库
  python scripts/cold_start/import_bug_opt_knowledge.py

  # 只导入 ops-nn
  python scripts/cold_start/import_bug_opt_knowledge.py --repo ops-nn

  # 只导入前 100 条 commits
  python scripts/cold_start/import_bug_opt_knowledge.py --limit 100

  # Dry run (不实际存储)
  python scripts/cold_start/import_bug_opt_knowledge.py --dry-run
        """,
    )

    parser.add_argument(
        "--repo",
        type=str,
        choices=ASCEND_REPOS,
        help="指定仓库 (默认导入所有)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="每个仓库最多导入的 commit 数量",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印不存储",
    )
    parser.add_argument(
        "--mock-redis",
        action="store_true",
        help="使用 mock Redis (用于测试)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    repos = [args.repo] if args.repo else ASCEND_REPOS

    print("\n" + "="*60)
    print("  Bug/优化知识批量导入")
    print("="*60)
    print(f"\n仓库: {', '.join(repos)}")
    if args.limit:
        print(f"限制: 每次仓库最多 {args.limit} commits")
    if args.dry_run:
        print("模式: DRY RUN (不实际存储)")
    print()

    # 初始化组件
    storage = create_storage(mock_redis=args.mock_redis)
    bug_extractor = BugExtractor()
    opt_extractor = OptimizationExtractor()

    # 总统计
    total_stats = ImportStats()

    # 导入每个仓库
    for repo in repos:
        repo_path = get_repo_path(repo)
        if not repo_path.exists():
            logger.warning(f"跳过 {repo} (路径不存在: {repo_path})")
            continue

        stats = import_from_repository(
            repo_name=repo,
            storage=storage,
            bug_extractor=bug_extractor,
            opt_extractor=opt_extractor,
            limit=args.limit,
            dry_run=args.dry_run,
        )

        print_stats(stats, repo)

        # 累加
        total_stats.total_commits += stats.total_commits
        total_stats.bugfix_commits += stats.bugfix_commits
        total_stats.optimization_commits += stats.optimization_commits
        total_stats.bug_stored += stats.bug_stored
        total_stats.bug_failed += stats.bug_failed
        total_stats.opt_stored += stats.opt_stored
        total_stats.opt_failed += stats.opt_failed
        total_stats.skipped += stats.skipped

    # 打印总统计
    print(f"\n{'='*60}")
    print("  总计")
    print(f"{'='*60}")
    print(f"总 commits: {total_stats.total_commits}")
    print(f"  - Bugfix: {total_stats.bugfix_commits}")
    print(f"  - Optimization: {total_stats.optimization_commits}")
    print(f"  - Skipped: {total_stats.skipped}")
    print(f"\n存储结果:")
    print(f"  - BugFix stored: {total_stats.bug_stored} (failed: {total_stats.bug_failed})")
    print(f"  - Optimization stored: {total_stats.opt_stored} (failed: {total_stats.opt_failed})")

    # 计算 extraction_success 比例
    if total_stats.bug_stored > 0:
        # 注意: stored 数量包括 extraction_success=True 和 False 的
        # 实际 extraction_success=True 的数量需要从 Redis 获取
        pass

    print(f"\n{'='*60}")
    if args.dry_run:
        print("DRY RUN 完成 - 无数据实际存储")
    else:
        print("导入完成")
    print("="*60)

    # 关闭存储连接
    storage._redis.close() if storage._redis else None

    return 0


if __name__ == "__main__":
    sys.exit(main())
