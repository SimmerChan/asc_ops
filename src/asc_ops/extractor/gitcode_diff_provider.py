# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
GitCode Diff 提供器

从 GitCode API 获取 PR 的代码 diff，作为 LLM 抽取的补充上下文
"""

import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Diff 最大字符数
MAX_DIFF_LENGTH = 4000


class GitCodeDiffProvider:
    """
    GitCode Diff 提供器

    通过 GitCode API 获取 PR 的代码变更
    """

    # Bug ID 格式: BUG-{repo}-{pr_number}
    # repo 格式: cann/ops-nn, cann/ops-math 等
    BUG_ID_PATTERN_GITCODE = "BUG-cann/"

    def __init__(
        self,
        token: Optional[str] = None,
        max_diff_length: int = MAX_DIFF_LENGTH,
    ):
        """
        初始化 GitCodeDiffProvider

        Args:
            token: GitCode Access Token
            max_diff_length: Diff 最大字符数
        """
        self._token = token
        self._max_diff_length = max_diff_length
        self._session = None

    def _get_session(self):
        """获取或创建 HTTP Session"""
        if self._session is None:
            import os
            from dotenv import load_dotenv

            # 尝试加载 .env 文件
            env_path = None
            try:
                from pathlib import Path
                env_path = Path(__file__).parent.parent.parent.parent / ".env"
                if env_path.exists():
                    load_dotenv(env_path)
            except ImportError:
                pass

            self._token = self._token or os.environ.get("GITCODE_TOKEN", "")

            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "Accept": "application/json",
                "User-Agent": "asc_ops/1.0",
            })
            if self._token:
                self._session.headers["PRIVATE-TOKEN"] = self._token

        return self._session

    def parse_bug_id(self, bug_id: str) -> Optional[tuple]:
        """
        解析 bug_id 获取 repo 名和 PR 编号

        Args:
            bug_id: bug ID，格式 BUG-{repo_prefix}/{short_repo}-{pr_number}
                   例如: BUG-cann/ops-nn-1244 -> (cann/ops-nn, 1244)
                   例如: BUG-ops-nn-1244 -> (cann/ops-nn, 1244)  (旧格式，自动转换)

        Returns:
            (repo, pr_number) 或 None
        """
        # 新格式: BUG-cann/ops-nn-1244
        if bug_id.startswith("BUG-cann/"):
            suffix = bug_id[len("BUG-cann/"):]

            # PR 编号是纯数字在最后
            for i in range(len(suffix) - 1, -1, -1):
                if suffix[i] == "-":
                    remaining = suffix[i+1:]
                    try:
                        pr_number = int(remaining)
                        repo = "cann/" + suffix[:i]
                        # 确保 repo 名不为空
                        if repo and repo != "cann/":
                            return (repo, pr_number)
                    except ValueError:
                        continue

        # 旧格式: BUG-ops-nn-1244 -> 转换为 cann/ops-nn
        elif bug_id.startswith("BUG-"):
            return self._parse_legacy(bug_id)

        return None

    def get_diff(self, bug_id: str) -> Optional[str]:
        """
        获取指定 bug 对应 PR 的 diff

        Args:
            bug_id: bug ID，格式 BUG-cann/{repo}-{pr_number}

        Returns:
            diff 字符串 或 None
        """
        parsed = self.parse_bug_id(bug_id)
        if not parsed:
            # 尝试原始格式兼容
            return self._get_diff_legacy(bug_id)

        repo, pr_number = parsed

        try:
            diff = self._fetch_pr_diff(repo, pr_number)
            if diff is None:
                return None

            # 截断过长的 diff
            if len(diff) > self._max_diff_length:
                diff = diff[:self._max_diff_length] + f"\n... (diff truncated, total {len(diff)} chars)"

            logger.info(f"Got diff for {bug_id}: {len(diff)} chars from {repo} PR #{pr_number}")
            return diff

        except Exception as e:
            logger.error(f"Failed to get diff for {bug_id}: {e}")
            return None

    def _get_diff_legacy(self, bug_id: str) -> Optional[str]:
        """
        处理旧格式 bug_id (如 BUG-ops-nn-1234)

        Args:
            bug_id: 旧格式 bug ID

        Returns:
            diff 字符串 或 None
        """
        # 尝试解析旧格式: BUG-ops-nn-1234 -> cann/ops-nn, 1234
        if bug_id.startswith("BUG-"):
            parts = bug_id[4:].rsplit("-", 1)
            if len(parts) == 2:
                repo_short = parts[0]  # ops-nn
                try:
                    pr_number = int(parts[1])
                    # 转换为完整 repo 名
                    repo = f"cann/{repo_short}"
                    return self.get_diff(f"BUG-{repo}-{pr_number}")
                except ValueError:
                    pass
        return None

    def _fetch_pr_diff(self, repo: str, pr_number: int) -> Optional[str]:
        """
        通过 GitCode API 获取 PR 的代码 diff

        Args:
            repo: 仓库名 (如 cann/ops-nn)
            pr_number: PR 编号

        Returns:
            合并的 diff 字符串 或 None
        """
        session = self._get_session()

        url = f"https://api.gitcode.com/api/v5/repos/{repo}/pulls/{pr_number}/files"

        try:
            resp = session.get(url)
            if resp.status_code != 200:
                logger.warning(f"GitCode API error for {repo} PR #{pr_number}: {resp.status_code}")
                return None

            data = resp.json()
            if isinstance(data, dict) and data.get("error_code"):
                logger.warning(f"GitCode API error: {data.get('error_message')}")
                return None

            if not isinstance(data, list):
                logger.warning(f"Unexpected GitCode API response type for {repo} PR #{pr_number}")
                return None

            # 合并所有文件的 diff
            return self._merge_diffs(data)

        except Exception as e:
            logger.error(f"Failed to fetch PR diff from GitCode: {e}")
            return None

    def _merge_diffs(self, files: List[Dict[str, Any]]) -> str:
        """
        合并多个文件的 diff

        Args:
            files: GitCode API 返回的文件列表

        Returns:
            合并后的 diff 字符串
        """
        diff_parts = []

        for file_info in files:
            filename = file_info.get("filename", "unknown")
            patch = file_info.get("patch", {})

            if isinstance(patch, dict):
                diff = patch.get("diff", "")
            elif isinstance(patch, str):
                diff = patch
            else:
                diff = ""

            if diff:
                diff_parts.append(f"=== {filename} ===\n{diff}")

        return "\n\n".join(diff_parts) if diff_parts else ""

    def get_diff_with_context(
        self,
        bug_id: str,
        include_files: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        获取 diff 及相关上下文

        Args:
            bug_id: bug ID
            include_files: 是否包含文件列表

        Returns:
            包含 diff 和上下文的字典 或 None
        """
        parsed = self.parse_bug_id(bug_id)
        if not parsed:
            # 尝试旧格式
            parsed_old = self._parse_legacy(bug_id)
            if not parsed_old:
                return None
            repo, pr_number = parsed_old
        else:
            repo, pr_number = parsed

        session = self._get_session()

        # 获取 PR 信息
        pr_url = f"https://api.gitcode.com/api/v5/repos/{repo}/pulls/{pr_number}"
        try:
            pr_resp = session.get(pr_url)
            if pr_resp.status_code != 200:
                return None
            pr_data = pr_resp.json()
        except Exception:
            return None

        # 获取文件列表
        files_url = f"https://api.gitcode.com/api/v5/repos/{repo}/pulls/{pr_number}/files"
        try:
            files_resp = session.get(files_url)
            if files_resp.status_code != 200:
                return None
            files_data = files_resp.json()
        except Exception:
            return None

        result = {
            "pr_title": pr_data.get("title", ""),
            "pr_body": pr_data.get("body", ""),
            "diff": self._merge_diffs(files_data) if isinstance(files_data, list) else "",
            "files": [],
        }

        if include_files and isinstance(files_data, list):
            result["files"] = [
                {
                    "filename": f.get("filename", ""),
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                }
                for f in files_data
            ]

        return result

    def _parse_legacy(self, bug_id: str) -> Optional[tuple]:
        """解析旧格式 bug_id"""
        if bug_id.startswith("BUG-"):
            parts = bug_id[4:].rsplit("-", 1)
            if len(parts) == 2:
                repo_short = parts[0]
                try:
                    pr_number = int(parts[1])
                    return (f"cann/{repo_short}", pr_number)
                except ValueError:
                    pass
        return None
