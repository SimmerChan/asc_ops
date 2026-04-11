# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
CLI 算子知识同步模块

从 GitHub/GitCode 仓库同步昇腾算子 bug/优化知识
"""

import argparse
import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from ..collector.github_client import GitHubCollector, GitHubPR
from ..collector.gitcode_client import GitCodeCollector, GitCodePR

logger = logging.getLogger(__name__)


# 平台类型
Platform = str  # "github" 或 "gitcode"


@dataclass
class RepoConfig:
    """仓库配置"""
    name: str
    platform: Platform = "github"  # 默认使用 GitHub

    @property
    def is_github(self) -> bool:
        return self.platform == "github"

    @property
    def is_gitcode(self) -> bool:
        return self.platform == "gitcode"


def load_repos_from_file(file_path: str, default_platform: Platform = "github") -> List[RepoConfig]:
    """
    从 YAML 文件加载仓库列表

    支持两种格式:
    1. 简单格式: repos: [owner/repo1, owner/repo2]
    2. 详细格式: repos: [{name: owner/repo1, platform: github}, ...]

    Args:
        file_path: 配置文件路径
        default_platform: 默认平台 (当未指定时使用)

    Returns:
        RepoConfig 列表
    """
    import yaml

    path = Path(file_path)
    if not path.exists():
        logger.warning(f"仓库配置文件不存在: {path}")
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config:
            return []

        repos_raw = config.get("repos", [])
        if not repos_raw:
            return []

        repos = []
        for item in repos_raw:
            if isinstance(item, str):
                # 简单格式: "owner/repo"
                repos.append(RepoConfig(name=item, platform=default_platform))
            elif isinstance(item, dict):
                # 详细格式: {name: owner/repo, platform: github}
                name = item.get("name", "")
                platform = item.get("platform", default_platform)
                if name:
                    repos.append(RepoConfig(name=name, platform=platform))
            elif item:
                # 其他非空值，尝试转为字符串
                repos.append(RepoConfig(name=str(item), platform=default_platform))

        logger.info(f"从 {path} 加载了 {len(repos)} 个仓库")
        for r in repos:
            logger.debug(f"  - {r.name} (platform={r.platform})")
        return repos

    except Exception as e:
        logger.error(f"加载仓库配置文件失败: {e}")
        return []


# 默认 GitHub 仓库列表
DEFAULT_GITHUB_REPOS = [
    "ascend-community/HierarchicalKV-ascend",
    "ascend-community/fbgemm-ascend",
    "ascend-community/ops-nn",
    "ascend-community/ops-math",
    "ascend-community/ops-transformer",
    "ascend-community/ops-cv",
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
    platform: Platform = "github"

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

    从昇腾 GitHub/GitCode 仓库拉取 PR 列表，
    分类并抽取 bug/优化知识
    """

    def __init__(
        self,
        since_date: Optional[datetime] = None,
        repo_filter: Optional[List[RepoConfig]] = None,
        default_platform: Platform = "github",
    ):
        """
        初始化同步器

        Args:
            since_date: 只同步此日期之后的 PR
            repo_filter: 只同步指定的仓库列表
            default_platform: 默认平台 (当 repo_filter 为字符串列表时使用)
        """
        self._since_date = since_date
        self._default_platform = default_platform

        # 如果传入的是字符串列表，转换为 RepoConfig
        if repo_filter:
            if repo_filter and isinstance(repo_filter[0], str):
                self._repo_filter = [RepoConfig(name=r, platform=default_platform) for r in repo_filter]
            else:
                self._repo_filter = repo_filter
        else:
            self._repo_filter = [RepoConfig(name=r, platform=default_platform) for r in DEFAULT_GITHUB_REPOS]

        self._classifier = None
        self._bug_extractor = None
        self._opt_extractor = None

        # 初始化 collectors
        self._github_collector = GitHubCollector()
        self._gitcode_collector = GitCodeCollector()

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

        for repo_config in self._repo_filter:
            try:
                repo_result = await self.sync_repository(repo_config)
                result.total_prs += repo_result.total_prs
                result.bug_prs += repo_result.bug_prs
                result.optimization_prs += repo_result.optimization_prs
                result.bug_knowledge_count += repo_result.bug_knowledge_count
                result.optimization_knowledge_count += repo_result.optimization_knowledge_count
            except Exception as e:
                logger.error(f"同步仓库 {repo_config.name} 失败: {e}")
                result.errors.append(f"{repo_config.name}: {str(e)}")

        return result

    async def sync_repository(self, repo_config: RepoConfig) -> OperatorSyncResult:
        """
        同步指定仓库

        Args:
            repo_config: 仓库配置

        Returns:
            同步结果统计
        """
        logger.info(f"开始同步仓库: {repo_config.name} (platform={repo_config.platform})")

        result = OperatorSyncResult()

        # 拉取 PR 列表 (在独立线程中执行同步 IO)
        prs = await asyncio.to_thread(self._fetch_prs, repo_config)
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
                result.errors.append(f"{repo_config.name}#{pr.pr_number}: {str(e)}")

        return result

    def _fetch_prs(self, repo_config: RepoConfig) -> List[OperatorPR]:
        """
        获取仓库的 PR 列表

        Args:
            repo_config: 仓库配置

        Returns:
            PR 列表
        """
        logger.info(f"  获取 PR 列表: {repo_config.name} (platform={repo_config.platform})")

        if repo_config.is_github:
            collector = self._github_collector
            external_prs = collector.fetch_prs(
                repo=repo_config.name,
                since_date=self._since_date,
                state="closed",
            )
            # 转换为 OperatorPR
            prs = []
            for gh_pr in external_prs:
                prs.append(OperatorPR(
                    pr_number=gh_pr.pr_number,
                    title=gh_pr.title,
                    body=gh_pr.body,
                    state=gh_pr.state,
                    merged_at=gh_pr.merged_at,
                    author=gh_pr.author,
                    labels=gh_pr.labels,
                    repo=repo_config.name,
                    platform="github",
                ))
        else:
            collector = self._gitcode_collector
            external_prs = collector.fetch_prs(
                repo=repo_config.name,
                since_date=self._since_date,
                state="closed",
            )
            # 转换为 OperatorPR
            prs = []
            for gc_pr in external_prs:
                prs.append(OperatorPR(
                    pr_number=gc_pr.pr_number,
                    title=gc_pr.title,
                    body=gc_pr.body,
                    state=gc_pr.state,
                    merged_at=gc_pr.merged_at,
                    author=gc_pr.author,
                    labels=gc_pr.labels,
                    repo=repo_config.name,
                    platform="gitcode",
                ))

        return prs

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
                bug_result = self._bug_extractor.extract(
                    pr_title=pr.title,
                    pr_body=pr.body,
                    source_repo=pr.repo,
                    source_pr=str(pr.pr_number),
                )
                if bug_result:
                    result["bug_count"] = 1
                    # 存储知识
                    # await self._store_bug_knowledge(bug_result)
            except Exception as e:
                logger.warning(f"  PR #{pr.pr_number} Bug 抽取失败: {e}")

        if result["is_optimization"] and self._opt_extractor:
            try:
                opt_result = self._opt_extractor.extract(
                    pr_title=pr.title,
                    pr_body=pr.body,
                    source_repo=pr.repo,
                    source_pr=str(pr.pr_number),
                )
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
        help="从 GitHub/GitCode 同步算子知识",
        description="从昇腾算子仓库拉取 PR，抽取 bug 和优化知识",
    )

    parser.add_argument(
        "--repo",
        type=str,
        help="指定单个仓库 (格式: owner/repo)",
    )

    parser.add_argument(
        "--platform",
        type=str,
        choices=["github", "gitcode"],
        default="github",
        help="仓库平台类型 (默认: github)",
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

    parser.add_argument(
        "--repos-file",
        type=str,
        help="仓库列表配置文件 (YAML格式)",
    )

    parser.add_argument(
        "--github-token",
        type=str,
        help="GitHub Token (也可通过 GITHUB_TOKEN 环境变量)",
    )

    parser.add_argument(
        "--gitcode-token",
        type=str,
        help="GitCode Token (也可通过 GITCODE_TOKEN 环境变量)",
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

    # 确定默认平台
    default_platform = getattr(args, 'platform', 'github')

    # 设置 Token (如果通过命令行提供)
    if getattr(args, 'github_token', None):
        os.environ["GITHUB_TOKEN"] = args.github_token
    if getattr(args, 'gitcode_token', None):
        os.environ["GITCODE_TOKEN"] = args.gitcode_token

    # 确定仓库列表
    if args.repo:
        # 单个仓库指定
        repo_config = RepoConfig(name=args.repo, platform=default_platform)
        repos = [repo_config]
    elif args.repos_file:
        # 从配置文件加载
        repos = load_repos_from_file(args.repos_file, default_platform=default_platform)
        if not repos:
            logger.error(f"无法从 {args.repos_file} 加载仓库列表")
            return 1
    else:
        # 默认使用 DEFAULT_GITHUB_REPOS
        repos = [RepoConfig(name=r, platform=default_platform) for r in DEFAULT_GITHUB_REPOS]

    # 创建同步器
    sync = OperatorSync(since_date=since_date, repo_filter=repos)

    print("\n" + "=" * 50)
    print("  AscendC Operator Knowledge Sync")
    print("=" * 50)
    print(f"\n同步仓库 ({len(repos)} 个):")
    for r in repos:
        print(f"  - {r.name} (platform={r.platform})")
    if since_date:
        print(f"起始日期: {since_date.strftime('%Y-%m-%d')}")
    if args.dry_run:
        print("模式: Dry Run (不实际同步)")
    print()

    if args.dry_run:
        # 只显示将要同步的内容
        print("将同步以下仓库:")
        for r in repos:
            print(f"  - {r.name} ({r.platform})")
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
