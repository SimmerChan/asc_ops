# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Git Diff 提供器

从本地 Git 仓库获取 commit 的代码 diff，作为 LLM 抽取的补充上下文
"""

import logging
import re
import subprocess
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# 本地 Git 仓库根路径
GIT_REPO_BASE_PATH = "/tmp/ascend_repos"

# Diff 最大字符数（保留关键变更）
MAX_DIFF_LENGTH = 4000


class GitDiffProvider:
    """
    Git Diff 提供器

    从本地 Git 仓库获取 commit 的代码变更
    """

    # Bug ID 格式: BUG-{repo}-{commit_hash}
    BUG_ID_PATTERN = re.compile(r"^BUG-(.+)-([a-f0-9]+)$")

    def __init__(self, repo_base_path: str = GIT_REPO_BASE_PATH):
        """
        初始化 GitDiffProvider

        Args:
            repo_base_path: 本地 Git 仓库根路径
        """
        self._repo_base_path = repo_base_path

    def parse_bug_id(self, bug_id: str) -> Optional[Tuple[str, str]]:
        """
        解析 bug_id 获取 repo 名和 commit hash

        Args:
            bug_id: bug ID，格式 BUG-{repo}-{commit_hash}

        Returns:
            (repo, commit_hash) 或 None（解析失败）
        """
        match = self.BUG_ID_PATTERN.match(bug_id)
        if not match:
            logger.warning(f"Invalid bug_id format: {bug_id}")
            return None

        repo = match.group(1)
        commit_hash = match.group(2)

        return (repo, commit_hash)

    def get_diff(self, bug_id: str) -> Optional[str]:
        """
        获取指定 bug 对应 commit 的 diff

        Args:
            bug_id: bug ID，格式 BUG-{repo}-{commit_hash}

        Returns:
            diff 字符串 或 None（获取失败）
        """
        parsed = self.parse_bug_id(bug_id)
        if not parsed:
            return None

        repo, commit_hash = parsed
        repo_path = f"{self._repo_base_path}/{repo}"

        # 检查仓库路径是否存在
        import os
        if not os.path.isdir(repo_path):
            logger.warning(f"Repository not found: {repo_path}")
            return None

        try:
            # 获取 commit 的 diff
            # 使用 commit^..commit 获取该 commit 的变更
            diff = self._get_git_diff(repo_path, commit_hash)

            if diff is None:
                return None

            # 截断过长的 diff
            if len(diff) > MAX_DIFF_LENGTH:
                diff = diff[:MAX_DIFF_LENGTH] + "\n... (diff truncated)"

            logger.info(f"Got diff for {bug_id}: {len(diff)} chars")
            return diff

        except Exception as e:
            logger.error(f"Failed to get diff for {bug_id}: {e}")
            return None

    def _get_git_diff(self, repo_path: str, commit_hash: str) -> Optional[str]:
        """
        执行 git diff 命令获取 commit 的变更

        Args:
            repo_path: 仓库路径
            commit_hash: commit hash

        Returns:
            diff 字符串 或 None
        """
        # 先检查 commit 是否存在
        check_cmd = ["git", "-C", repo_path, "rev-parse", "--verify", commit_hash]
        try:
            result = subprocess.run(
                check_cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            if not result.stdout.strip():
                logger.warning(f"Commit not found: {commit_hash} in {repo_path}")
                return None
        except subprocess.CalledProcessError:
            logger.warning(f"Commit not found: {commit_hash} in {repo_path}")
            return None

        # 获取 diff
        # 使用 commit^..commit 获取该 commit 相对于父提交的变更
        diff_cmd = ["git", "-C", repo_path, "diff", f"{commit_hash}^..{commit_hash}"]

        try:
            result = subprocess.run(
                diff_cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout

        except subprocess.CalledProcessError as e:
            logger.error(f"Git diff failed: {e}")
            return None
