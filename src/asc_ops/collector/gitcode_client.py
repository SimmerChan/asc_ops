# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GitCode API 客户端

从 GitCode 仓库获取 PR 信息（标题、描述、标签等）

GitCode API 文档: https://gitcode.com/help/assets/develop/doc/api/open_api.html
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any

import requests

logger = logging.getLogger(__name__)

# GitCode API 基础 URL
GITCODE_API_BASE = "https://api.gitcode.com/api/v5"


@dataclass
class GitCodePR:
    """GitCode PR 信息"""
    repo_name: str
    pr_number: int
    title: str
    body: str
    state: str
    merged_at: Optional[datetime]
    author: str
    labels: List[str]
    html_url: str
    source: str = "gitcode"  # 标记数据来源

    @property
    def is_merged(self) -> bool:
        return self.state == "closed" and self.merged_at is not None


class GitCodeCollector:
    """
    GitCode PR 采集器

    使用 GitCode Open API v5 获取 PR 信息
    """

    # 默认仓库列表
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
        初始化 GitCode 采集器

        Args:
            token: GitCode Access Token (可选)
        """
        self._token = token or os.environ.get("GITCODE_TOKEN", "")
        self._session = requests.Session()

        # 设置默认 headers
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "asc_ops/1.0",
        })

        if self._token:
            self._session.headers.update({
                "PRIVATE-TOKEN": self._token
            })

    def _build_url(self, endpoint: str) -> str:
        """构建 API URL"""
        return f"{GITCODE_API_BASE}/{endpoint.lstrip('/')}"

    def fetch_prs(
        self,
        repo: str,
        since_date: Optional[datetime] = None,
        state: str = "closed",
        max_count: Optional[int] = None,
    ) -> List[GitCodePR]:
        """
        获取仓库的 PR 列表

        Args:
            repo: 仓库名称 (owner/repo)
            since_date: 只获取此日期之后的 PR
            state: PR 状态 (open, closed, all)
            max_count: 最大获取数量

        Returns:
            GitCodePR 列表
        """
        try:
            # 构建 API URL
            # GitCode API: GET /api/v5/repos/{owner}/{repo}/pulls
            url = self._build_url(f"/repos/{repo}/pulls")

            params = {
                "state": state,  # open, closed, all
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
            }

            logger.info(f"Fetching PRs from GitCode: {repo}")
            response = self._session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            if not isinstance(data, list):
                logger.warning(f"Unexpected response format from {repo}: {type(data)}")
                return []

            prs = []
            for pr_data in data:
                # 解析 PR 数据
                pr = self._parse_pr(pr_data, repo)

                # 过滤已合并的 PR (只有 merged=True 的才是合并的)
                if not pr_data.get("merged", False):
                    continue

                # 过滤日期
                if since_date and pr.merged_at and pr.merged_at < since_date:
                    break

                prs.append(pr)

                if max_count and len(prs) >= max_count:
                    break

            logger.info(f"Fetched {len(prs)} PRs from {repo}")
            return prs

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching PRs from {repo}")
            return []
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(f"仓库 {repo} 不存在或无法访问")
            elif e.response.status_code == 403:
                logger.error(f"GitCode API 限流，请稍后重试")
            else:
                logger.error(f"HTTP error fetching PRs from {repo}: {e}")
            return []
        except Exception as e:
            import traceback
            logger.error(f"Failed to fetch PRs from {repo}: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return []

    def _parse_pr(self, data: Dict[str, Any], repo: str) -> GitCodePR:
        """解析 PR 数据"""
        # GitCode API 返回的日期格式可能是 ISO 8601
        merged_at_str = data.get("merged_at")
        merged_at = None
        if merged_at_str:
            try:
                # 尝试解析 ISO 格式
                merged_at = datetime.fromisoformat(merged_at_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                try:
                    merged_at = datetime.strptime(merged_at_str, "%Y-%m-%dT%H:%M:%S%z")
                except (ValueError, TypeError):
                    merged_at = None

        # 解析 labels
        labels = []
        if data.get("labels"):
            labels = [label.get("name", "") if isinstance(label, dict) else str(label)
                      for label in data.get("labels", [])]

        return GitCodePR(
            repo_name=repo,
            pr_number=data.get("number", 0),
            title=data.get("title", ""),
            body=data.get("body", "") or "",
            state=data.get("state", ""),
            merged_at=merged_at,
            author=data.get("user", {}).get("login", "") if isinstance(data.get("user"), dict) else "",
            labels=labels,
            html_url=data.get("html_url", ""),
            source="gitcode",
        )

    def fetch_all_prs(
        self,
        repos: Optional[List[str]] = None,
        since_date: Optional[datetime] = None,
        max_per_repo: Optional[int] = None,
    ) -> List[GitCodePR]:
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

    def get_pr_detail(self, repo: str, pr_number: int) -> Optional[GitCodePR]:
        """
        获取单个 PR 的详细信息

        Args:
            repo: 仓库名称
            pr_number: PR 编号

        Returns:
            GitCodePR 或 None
        """
        try:
            url = self._build_url(f"/repos/{repo}/pulls/{pr_number}")
            response = self._session.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()
            return self._parse_pr(data, repo)

        except Exception as e:
            logger.error(f"Failed to fetch PR #{pr_number} from {repo}: {e}")
            return None
