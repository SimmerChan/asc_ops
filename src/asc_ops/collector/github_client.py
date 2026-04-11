# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GitHub API 客户端

从 GitHub 仓库获取 PR 信息（标题、描述、标签等）
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from github import Github
from github.PullRequest import PullRequest

logger = logging.getLogger(__name__)


@dataclass
class GitHubPR:
    """GitHub PR 信息"""
    repo_name: str
    pr_number: int
    title: str
    body: str
    state: str
    merged_at: Optional[datetime]
    author: str
    labels: List[str]
    html_url: str

    @property
    def is_merged(self) -> bool:
        return self.state == "closed" and self.merged_at is not None


class GitHubCollector:
    """
    GitHub PR 采集器

    使用 PyGithub 从 GitHub 仓库获取 PR 信息
    """

    # 昇腾算子仓库列表
    DEFAULT_REPOS = [
        "ascend-community/HierarchicalKV-ascend",
        "ascend-community/fbgemm-ascend",
        "ascend-community/ops-nn",
        "ascend-community/ops-math",
        "ascend-community/ops-transformer",
        "ascend-community/ops-cv",
    ]

    def __init__(self, token: Optional[str] = None):
        """
        初始化 GitHub 采集器

        Args:
            token: GitHub Personal Access Token (可选，无 token 限流 60 req/hr)
        """
        self._token = token
        self._github: Optional[Github] = None

    def _get_client(self) -> Github:
        """获取 GitHub 客户端"""
        if self._github is None:
            token = self._token or os.environ.get("GITHUB_TOKEN", "")
            if token:
                self._github = Github(
                    login_or_token=token,
                    per_page=100,
                )
            else:
                logger.warning("未设置 GITHUB_TOKEN，将使用未认证访问（限流 60 req/hr）")
                self._github = Github(per_page=100)
        return self._github

    def fetch_prs(
        self,
        repo: str,
        since_date: Optional[datetime] = None,
        state: str = "closed",
        max_count: Optional[int] = None,
    ) -> List[GitHubPR]:
        """
        获取仓库的 PR 列表

        Args:
            repo: 仓库名称 (owner/repo)
            since_date: 只获取此日期之后的 PR
            state: PR 状态 (open, closed, all)
            max_count: 最大获取数量

        Returns:
            GitHubPR 列表
        """
        try:
            client = self._get_client()
            repo_obj = client.get_repo(repo)

            # 获取 PRs
            pulls = repo_obj.get_pulls(state=state, sort="updated", direction="desc")

            prs = []
            for pr in pulls:
                # 过滤已合并的 PR
                if not pr.merged:
                    continue

                # 过滤日期
                if since_date and pr.merged_at and pr.merged_at < since_date:
                    break

                prs.append(GitHubPR(
                    repo_name=repo,
                    pr_number=pr.number,
                    title=pr.title,
                    body=pr.body or "",
                    state=pr.state,
                    merged_at=pr.merged_at,
                    author=pr.user.login,
                    labels=[label.name for label in pr.labels],
                    html_url=pr.html_url,
                ))

                if max_count and len(prs) >= max_count:
                    break

            logger.info(f"Fetched {len(prs)} PRs from {repo}")
            return prs

        except Exception as e:
            import traceback
            logger.error(f"Failed to fetch PRs from {repo}: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            # 检查常见错误
            error_msg = str(e)
            if "Bad credentials" in error_msg or "401" in error_msg:
                logger.error("GitHub token 无效或已过期，请检查 GITHUB_TOKEN 环境变量")
            elif "rate limit" in error_msg.lower() or "403" in error_msg:
                logger.error("GitHub API 限流，请设置 GITHUB_TOKEN 或稍后重试")
            elif "Not Found" in error_msg or "404" in error_msg:
                logger.error(f"仓库 {repo} 不存在或无法访问")
            return []

    def fetch_all_prs(
        self,
        repos: Optional[List[str]] = None,
        since_date: Optional[datetime] = None,
        max_per_repo: Optional[int] = None,
    ) -> List[GitHubPR]:
        """
        获取多个仓库的 PR

        Args:
            repos: 仓库列表 (默认使用 DEFAULT_REPOS)
            since_date: 只获取此日期之后的 PR
            max_per_repo: 每个仓库最大 PR 数量

        Returns:
            所有仓库的 PR 列表
        """
        repos = repos or self.DEFAULT_REPOS
        all_prs = []

        for repo in repos:
            prs = self.fetch_prs(
                repo=repo,
                since_date=since_date,
                state="closed",
                max_count=max_per_repo,
            )
            all_prs.extend(prs)

        logger.info(f"Total PRs fetched: {len(all_prs)} from {len(repos)} repos")
        return all_prs

    def get_pr_detail(self, repo: str, pr_number: int) -> Optional[GitHubPR]:
        """
        获取单个 PR 的详细信息

        Args:
            repo: 仓库名称
            pr_number: PR 编号

        Returns:
            GitHubPR 或 None
        """
        try:
            client = self._get_client()
            repo_obj = client.get_repo(repo)
            pr = repo_obj.get_pull(pr_number)

            return GitHubPR(
                repo_name=repo,
                pr_number=pr.number,
                title=pr.title,
                body=pr.body or "",
                state=pr.state,
                merged_at=pr.merged_at,
                author=pr.user.login,
                labels=[label.name for label in pr.labels],
                html_url=pr.html_url,
            )

        except Exception as e:
            logger.error(f"Failed to fetch PR #{pr_number} from {repo}: {e}")
            return None
