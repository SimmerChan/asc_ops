# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
CLI 算子知识同步模块

从 GitHub 仓库同步昇腾算子 bug/优化知识
"""

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


# 昇腾算子仓库列表
ASCEND_REPOS = [
    "ascend/cann-ann",       # 算子仓库 A
    "ascend/cann-b",         # 算子仓库 B
    # 可以继续添加更多仓库
]


@dataclass
class OperatorPR:
    """算子 PR 信息"""
    pr_number: int
    title: str
    body: str
    state: str
    merged_at: Optional[datetime]
    author: str
    labels: List[str]
    repo: str

    @property
    def is_merged(self) -> bool:
        return self.state == "closed" and self.merged_at is not None


@dataclass
class OperatorSyncResult:
    """算子同步结果"""
    total_prs: int = 0
    bug_prs: int = 0
    optimization_prs: int = 0
    bug_knowledge_count: int = 0
    optimization_knowledge_count: int = 0
    errors: List[str] = field(default_factory=list)


class OperatorSync:
    """
    算子知识同步器

    从昇腾 GitHub 仓库拉取 PR 列表，
    分类并抽取 bug/优化知识
    """

    def __init__(
        self,
        since_date: Optional[datetime] = None,
        repo_filter: Optional[List[str]] = None,
    ):
        """
        初始化同步器

        Args:
            since_date: 只同步此日期之后的 PR
            repo_filter: 只同步指定的仓库列表
        """
        self._since_date = since_date
        self._repo_filter = repo_filter or ASCEND_REPOS
        self._classifier = None
        self._bug_extractor = None
        self._opt_extractor = None

    def _init_extractors(self):
        """初始化抽取器"""
        try:
            from ..extractor import PRClassifier, BugExtractor, OptimizationExtractor
            self._classifier = PRClassifier()
            self._bug_extractor = BugExtractor()
            self._opt_extractor = OptimizationExtractor()
        except ImportError as e:
            logger.warning(f"抽取器不可用: {e}")

    async def sync_all(self) -> OperatorSyncResult:
        """
        同步所有配置的仓库

        Returns:
            同步结果统计
        """
        self._init_extractors()

        result = OperatorSyncResult()

        for repo in self._repo_filter:
            try:
                repo_result = await self.sync_repository(repo)
                result.total_prs += repo_result.total_prs
                result.bug_prs += repo_result.bug_prs
                result.optimization_prs += repo_result.optimization_prs
                result.bug_knowledge_count += repo_result.bug_knowledge_count
                result.optimization_knowledge_count += repo_result.optimization_knowledge_count
            except Exception as e:
                logger.error(f"同步仓库 {repo} 失败: {e}")
                result.errors.append(f"{repo}: {str(e)}")

        return result

    async def sync_repository(self, repo: str) -> OperatorSyncResult:
        """
        同步指定仓库

        Args:
            repo: 仓库名称 (owner/repo)

        Returns:
            同步结果统计
        """
        logger.info(f"开始同步仓库: {repo}")

        result = OperatorSyncResult()

        # 拉取 PR 列表
        prs = await self._fetch_prs(repo)
        result.total_prs = len(prs)

        logger.info(f"  发现 {len(prs)} 个 PR")

        # 分类 PR
        for pr in prs:
            try:
                pr_result = await self._process_pr(pr)
                if pr_result["is_bug"]:
                    result.bug_prs += 1
                    result.bug_knowledge_count += pr_result["bug_count"]
                if pr_result["is_optimization"]:
                    result.optimization_prs += 1
                    result.optimization_knowledge_count += pr_result["opt_count"]
            except Exception as e:
                logger.error(f"  处理 PR #{pr.pr_number} 失败: {e}")
                result.errors.append(f"{repo}#{pr.pr_number}: {str(e)}")

        return result

    async def _fetch_prs(self, repo: str) -> List[OperatorPR]:
        """
        获取仓库的 PR 列表

        Args:
            repo: 仓库名称

        Returns:
            PR 列表
        """
        # TODO: 接入 GitHub API
        # 目前返回模拟数据
        logger.info(f"  获取 PR 列表 (模拟)...")

        # 模拟一些 PR
        mock_prs = [
            OperatorPR(
                pr_number=1,
                title="fix: Matmul kernel crash on large input",
                body="Fix a crash issue when input size exceeds 2GB",
                state="closed",
                merged_at=datetime.now(),
                author="contributor1",
                labels=["bug", "matmul"],
                repo=repo,
            ),
            OperatorPR(
                pr_number=2,
                title="perf: Optimize VecReduce by 30%",
                body="Improve VecReduce performance through pipelining",
                state="closed",
                merged_at=datetime.now(),
                author="contributor2",
                labels=["enhancement", "optimization"],
                repo=repo,
            ),
        ]

        return mock_prs

    async def _process_pr(self, pr: OperatorPR) -> Dict[str, Any]:
        """
        处理单个 PR

        Args:
            pr: PR 信息

        Returns:
            处理结果
        """
        result = {
            "is_bug": False,
            "is_optimization": False,
            "bug_count": 0,
            "opt_count": 0,
        }

        # 检查是否为 bug 或 optimization PR
        label_names = [l.lower() for l in pr.labels]

        is_bug = (
            "bug" in label_names or
            "fix" in label_names or
            any("crash" in l or "fail" in l for l in label_names)
        )

        is_optimization = (
            "optimization" in label_names or
            "enhancement" in label_names or
            "perf" in label_names or
            "performance" in label_names
        )

        result["is_bug"] = is_bug
        result["is_optimization"] = is_optimization

        # 使用分类器进行细分类
        if self._classifier and (is_bug or is_optimization):
            try:
                classification = self._classifier.classify(pr.title, pr.body)
                if classification.pr_type.value in ["bugfix", "both"]:
                    result["is_bug"] = True
                if classification.pr_type.value in ["optimization", "both"]:
                    result["is_optimization"] = True
            except Exception as e:
                logger.warning(f"  PR #{pr.pr_number} 分类失败: {e}")

        # 抽取知识
        if result["is_bug"] and self._bug_extractor:
            try:
                bug_result = await self._bug_extractor.extract(pr.title, pr.body)
                if bug_result:
                    result["bug_count"] = 1
                    # 存储知识
                    # await self._store_bug_knowledge(bug_result)
            except Exception as e:
                logger.warning(f"  PR #{pr.pr_number} Bug 抽取失败: {e}")

        if result["is_optimization"] and self._opt_extractor:
            try:
                opt_result = await self._opt_extractor.extract(pr.title, pr.body)
                if opt_result:
                    result["opt_count"] = 1
                    # 存储知识
                    # await self._store_optimization_knowledge(opt_result)
            except Exception as e:
                logger.warning(f"  PR #{pr.pr_number} Optimization 抽取失败: {e}")

        return result


def add_operator_sync_parser(subparsers) -> argparse.ArgumentParser:
    """添加 operator-sync 子命令解析器"""
    parser = subparsers.add_parser(
        "operator-sync",
        help="从 GitHub 同步算子知识",
        description="从昇腾算子仓库拉取 PR，抽取 bug 和优化知识",
    )

    parser.add_argument(
        "--repo",
        type=str,
        help="指定仓库 (默认同步所有配置的仓库)",
    )

    parser.add_argument(
        "--since",
        type=str,
        help="只同步此日期之后的 PR (格式: YYYY-MM-DD)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示将要同步的内容，不实际同步",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出",
    )

    return parser


async def run_operator_sync(args) -> int:
    """
    执行算子同步

    Args:
        args: 解析后的命令行参数

    Returns:
        0 成功, 1 失败
    """
    # 设置日志
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # 解析日期
    since_date = None
    if args.since:
        try:
            since_date = datetime.strptime(args.since, "%Y-%m-%d")
        except ValueError:
            print(f"无效的日期格式: {args.since}")
            return 1

    # 确定仓库列表
    repos = [args.repo] if args.repo else ASCEND_REPOS

    # 创建同步器
    sync = OperatorSync(since_date=since_date, repo_filter=repos)

    print("\n" + "=" * 50)
    print("  AscendC Operator Knowledge Sync")
    print("=" * 50)
    print(f"\n同步仓库: {', '.join(repos)}")
    if since_date:
        print(f"起始日期: {since_date.strftime('%Y-%m-%d')}")
    if args.dry_run:
        print("模式: Dry Run (不实际同步)")
    print()

    if args.dry_run:
        # 只显示将要同步的内容
        print("将同步以下 PR:")
        for repo in repos:
            print(f"  - {repo}")
        return 0

    # 执行同步
    result = await sync.sync_all()

    # 显示结果
    print("\n" + "=" * 50)
    print("  同步结果")
    print("=" * 50)
    print(f"\n总计 PR: {result.total_prs}")
    print(f"Bug PR: {result.bug_prs} (抽取知识: {result.bug_knowledge_count})")
    print(f"优化 PR: {result.optimization_prs} (抽取知识: {result.optimization_knowledge_count})")

    if result.errors:
        print(f"\n错误: {len(result.errors)}")
        for error in result.errors[:5]:
            print(f"  - {error}")

    print("\n" + "=" * 50)

    return 0 if not result.errors else 1
