# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
抽取质量评估报告模块

生成抽取质量报告，量化管道效果
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..storage.chroma_client import ChromaDBClient
from ..storage.redis_client import RedisClient

logger = logging.getLogger(__name__)


@dataclass
class QualityReportStats:
    """质量报告统计"""
    total_bugs: int = 0
    bugs_with_root_cause: int = 0
    bugs_with_fix_pattern: int = 0
    bugs_with_both: int = 0
    bugs_with_neither: int = 0

    @property
    def root_cause_fill_rate(self) -> float:
        if self.total_bugs == 0:
            return 0.0
        return self.bugs_with_root_cause / self.total_bugs

    @property
    def fix_pattern_fill_rate(self) -> float:
        if self.total_bugs == 0:
            return 0.0
        return self.bugs_with_fix_pattern / self.total_bugs

    @property
    def both_fill_rate(self) -> float:
        if self.total_bugs == 0:
            return 0.0
        return self.bugs_with_both / self.total_bugs

    def to_dict(self) -> dict:
        return {
            "total_bugs": self.total_bugs,
            "bugs_with_root_cause": self.bugs_with_root_cause,
            "bugs_with_fix_pattern": self.bugs_with_fix_pattern,
            "bugs_with_both": self.bugs_with_both,
            "bugs_with_neither": self.bugs_with_neither,
            "root_cause_fill_rate": f"{self.root_cause_fill_rate * 100:.1f}%",
            "fix_pattern_fill_rate": f"{self.fix_pattern_fill_rate * 100:.1f}%",
            "both_fill_rate": f"{self.both_fill_rate * 100:.1f}%",
        }


@dataclass
class ProblemBug:
    """问题记录"""
    bug_id: str
    operator_id: str
    source_repo: str
    source_pr: str
    bug_title: str
    missing_fields: List[str]


class ExtractionQualityReporter:
    """
    抽取质量报告器

    统计字段填充率，生成问题记录列表
    """

    def __init__(
        self,
        chroma_client: Optional[ChromaDBClient] = None,
        redis_client: Optional[RedisClient] = None,
        collection_name: str = "bug_fixes",
    ):
        """
        初始化质量报告器

        Args:
            chroma_client: ChromaDB 客户端
            redis_client: Redis 客户端
            collection_name: Collection 名称
        """
        self._chroma = chroma_client
        self._redis = redis_client
        self._collection_name = collection_name

    def generate_report(self) -> QualityReportStats:
        """
        生成质量报告统计

        Returns:
            QualityReportStats: 质量统计
        """
        stats = QualityReportStats()

        if not self._chroma:
            logger.warning("No ChromaDB client, cannot generate report")
            return stats

        try:
            collection = self._chroma.get_collection(self._collection_name)
            results = collection.get(limit=10000)

            if not results or not results.get("ids"):
                logger.warning(f"No bugs found in collection {self._collection_name}")
                return stats

            ids = results["ids"]
            metadatas = results.get("metadatas", [])

            stats.total_bugs = len(ids)

            for i, bug_id in enumerate(ids):
                metadata = metadatas[i] if i < len(metadatas) else {}

                has_root_cause = metadata.get("has_root_cause", False)
                has_fix_pattern = metadata.get("has_fix_pattern", False)

                if has_root_cause:
                    stats.bugs_with_root_cause += 1
                if has_fix_pattern:
                    stats.bugs_with_fix_pattern += 1
                if has_root_cause and has_fix_pattern:
                    stats.bugs_with_both += 1
                if not has_root_cause and not has_fix_pattern:
                    stats.bugs_with_neither += 1

            logger.info(f"Quality report: {stats.bugs_with_root_cause}/{stats.total_bugs} bugs have root_cause")

        except Exception as e:
            logger.error(f"Error generating quality report: {e}")

        return stats

    def get_problem_bugs(
        self,
        limit: int = 100,
        missing_both: bool = True,
    ) -> List[ProblemBug]:
        """
        获取问题记录列表

        Args:
            limit: 返回数量
            missing_both: 只返回两者都缺失的

        Returns:
            List[ProblemBug]: 问题记录列表
        """
        problems = []

        if not self._chroma:
            return problems

        try:
            collection = self._chroma.get_collection(self._collection_name)
            results = collection.get(limit=10000)

            if not results or not results.get("ids"):
                return problems

            ids = results["ids"]
            metadatas = results.get("metadatas", [])

            for i, bug_id in enumerate(ids):
                metadata = metadatas[i] if i < len(metadatas) else {}

                has_root_cause = metadata.get("has_root_cause", False)
                has_fix_pattern = metadata.get("has_fix_pattern", False)

                if missing_both:
                    if not has_root_cause and not has_fix_pattern:
                        missing = ["root_cause", "fix_pattern"]
                        problems.append(ProblemBug(
                            bug_id=bug_id,
                            operator_id=metadata.get("operator_id", "unknown"),
                            source_repo=metadata.get("source_repo", ""),
                            source_pr=metadata.get("source_pr", ""),
                            bug_title=metadata.get("bug_title", ""),
                            missing_fields=missing,
                        ))
                else:
                    if not has_root_cause or not has_fix_pattern:
                        missing = []
                        if not has_root_cause:
                            missing.append("root_cause")
                        if not has_fix_pattern:
                            missing.append("fix_pattern")
                        problems.append(ProblemBug(
                            bug_id=bug_id,
                            operator_id=metadata.get("operator_id", "unknown"),
                            source_repo=metadata.get("source_repo", ""),
                            source_pr=metadata.get("source_pr", ""),
                            bug_title=metadata.get("bug_title", ""),
                            missing_fields=missing,
                        ))

                if len(problems) >= limit:
                    break

        except Exception as e:
            logger.error(f"Error getting problem bugs: {e}")

        return problems

    def generate_markdown_report(
        self,
        output_path: Optional[str] = None,
        include_problems: bool = True,
        problem_limit: int = 50,
    ) -> str:
        """
        生成 Markdown 格式报告

        Args:
            output_path: 输出文件路径（可选）
            include_problems: 是否包含问题记录列表
            problem_limit: 问题记录数量限制

        Returns:
            str: Markdown 格式报告
        """
        stats = self.generate_report()
        problems = self.get_problem_bugs(limit=problem_limit) if include_problems else []

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            f"# Bug 知识抽取质量报告",
            f"",
            f"**生成时间**: {timestamp}",
            f"",
            f"## 总体统计",
            f"",
            f"| 指标 | 值 |",
            f"|------|-----|",
            f"| 总记录数 | {stats.total_bugs} |",
            f"| 有 root_cause | {stats.bugs_with_root_cause} ({stats.root_cause_fill_rate * 100:.1f}%) |",
            f"| 有 fix_pattern | {stats.bugs_with_fix_pattern} ({stats.fix_pattern_fill_rate * 100:.1f}%) |",
            f"| 两者都有 | {stats.bugs_with_both} ({stats.both_fill_rate * 100:.1f}%) |",
            f"| 两者都缺失 | {stats.bugs_with_neither} |",
            f"",
        ]

        if include_problems and problems:
            lines.extend([
                f"## 问题记录 (前 {len(problems)} 条)",
                f"",
                f"| Bug ID | 算子 | 仓库 | PR | 缺失字段 |",
                f"|--------|------|------|-----|----------|",
            ])

            for bug in problems:
                lines.append(
                    f"| {bug.bug_id} | {bug.operator_id} | {bug.source_repo} | "
                    f"{bug.source_pr} | {', '.join(bug.missing_fields)} |"
                )

            lines.append("")

        # 成功标准检查
        lines.extend([
            f"## 成功标准检查",
            f"",
            f"| 标准 | 当前值 | 目标 | 状态 |",
            f"|------|--------|------|------|",
        ])

        root_cause_ok = stats.root_cause_fill_rate >= 0.7
        fix_pattern_ok = stats.fix_pattern_fill_rate >= 0.5

        lines.append(
            f"| Top 100 root_cause 填充率 | "
            f"{stats.root_cause_fill_rate * 100:.1f}% | ≥70% | "
            f"{'✅' if root_cause_ok else '❌'} |"
        )
        lines.append(
            f"| Top 100 fix_pattern 填充率 | "
            f"{stats.fix_pattern_fill_rate * 100:.1f}% | ≥50% | "
            f"{'✅' if fix_pattern_ok else '❌'} |"
        )

        lines.append("")
        lines.append(f"*报告生成时间: {timestamp}*")

        markdown = "\n".join(lines)

        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(markdown, encoding="utf-8")
            logger.info(f"Report written to {output_path}")

        return markdown

    def print_summary(self) -> None:
        """打印质量摘要到控制台"""
        stats = self.generate_report()

        print("\n" + "=" * 50)
        print("Bug 知识抽取质量报告")
        print("=" * 50)
        print(f"总记录数: {stats.total_bugs}")
        print(f"有 root_cause: {stats.bugs_with_root_cause} ({stats.root_cause_fill_rate * 100:.1f}%)")
        print(f"有 fix_pattern: {stats.bugs_with_fix_pattern} ({stats.fix_pattern_fill_rate * 100:.1f}%)")
        print(f"两者都有: {stats.bugs_with_both} ({stats.both_fill_rate * 100:.1f}%)")
        print(f"两者都缺失: {stats.bugs_with_neither}")
        print("=" * 50 + "\n")
