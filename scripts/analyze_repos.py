#!/usr/bin/env python3
"""
昇腾仓PR/Commit采样分析脚本
分析commit消息，分类为bugfix/optimization/feature
"""

import os
import re
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path

@dataclass
class CommitInfo:
    repo: str
    commit_hash: str
    message: str
    author: str
    date: str

@dataclass
class AnalysisResult:
    repo: str
    total_commits: int
    bugfix_commits: int
    optimization_commits: int
    feature_commits: int

    # Bugfix信息完整度
    bugfix_with_issue_ref: float  # 有issue引用
    bugfix_with_description: float  # 有描述

    # 平均消息长度
    avg_message_length: float

    # 示例
    bugfix_examples: List[str]
    optimization_examples: List[str]

# PR分类关键词
BUG_KEYWORDS = [
    "fix", "bug", "fix", "修复", "解决", "hotfix", "patch",
    "crash", "error", "incorrect", "wrong", "精度", "regression",
    "issue", "问题", "bugfix", "bump", "patch"
]

OPTIMIZATION_KEYWORDS = [
    "optimize", "optimise", "perf", "performance", "优化", "加速",
    "improve", "enhance", "提升", "speedup", "efficiency",
    "throughput", "latency", "speed", "faster"
]


def classify_commit(message: str) -> str:
    """分类commit类型：bugfix / optimization / feature"""
    msg_lower = message.lower()

    bug_score = sum(1 for kw in BUG_KEYWORDS if kw in msg_lower)
    opt_score = sum(1 for kw in OPTIMIZATION_KEYWORDS if kw in msg_lower)

    # 特殊规则
    if "merge" in msg_lower:
        return "merge"

    if bug_score >= 1 and opt_score == 0:
        return "bugfix"
    elif opt_score >= 1 and bug_score == 0:
        return "optimization"
    elif bug_score >= 1 and opt_score >= 1:
        # 两者都有，看哪个分数高
        if bug_score >= opt_score:
            return "bugfix"
        else:
            return "optimization"
    else:
        return "feature"


def get_commits(repo_path: str, max_count: int = 100) -> List[CommitInfo]:
    """获取仓库的commit信息"""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", f"--max-count={max_count}",
             "--format=%H|%s|%an|%ad", "--date=short"],
            capture_output=True,
            text=True,
            check=True
        )
        commits = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|', 3)
            if len(parts) >= 4:
                commits.append(CommitInfo(
                    repo=os.path.basename(repo_path),
                    commit_hash=parts[0],
                    message=parts[1],
                    author=parts[2],
                    date=parts[3]
                ))
        return commits
    except subprocess.CalledProcessError as e:
        print(f"Error getting commits from {repo_path}: {e}")
        return []


def analyze_repo(repo_path: str, repo_name: str = None) -> AnalysisResult:
    """分析单个仓库"""
    if repo_name is None:
        repo_name = os.path.basename(repo_path)

    commits = get_commits(repo_path)

    bugfix_commits = []
    optimization_commits = []
    feature_commits = []

    for commit in commits:
        commit_type = classify_commit(commit.message)
        if commit_type == "bugfix":
            bugfix_commits.append(commit)
        elif commit_type == "optimization":
            optimization_commits.append(commit)
        elif commit_type == "feature":
            feature_commits.append(commit)

    # Bugfix信息分析
    bugfix_with_issue = 0
    bugfix_with_desc = 0

    for commit in bugfix_commits:
        msg = commit.message.lower()
        if "#" in msg or "issue" in msg or "#" in msg:
            bugfix_with_issue += 1
        if len(commit.message) > 20:
            bugfix_with_desc += 1

    bugfix_count = len(bugfix_commits)
    bugfix_with_issue_rate = bugfix_with_issue / bugfix_count if bugfix_count > 0 else 0
    bugfix_with_desc_rate = bugfix_with_desc / bugfix_count if bugfix_count > 0 else 0

    return AnalysisResult(
        repo=repo_name,
        total_commits=len(commits),
        bugfix_commits=bugfix_count,
        optimization_commits=len(optimization_commits),
        feature_commits=len(feature_commits),
        bugfix_with_issue_ref=bugfix_with_issue_rate,
        bugfix_with_description=bugfix_with_desc_rate,
        avg_message_length=sum(len(c.message) for c in commits) / len(commits) if commits else 0,
        bugfix_examples=[c.message for c in bugfix_commits[:3]],
        optimization_examples=[c.message for c in optimization_commits[:3]]
    )


def print_result(result: AnalysisResult):
    """打印分析结果"""
    print(f"\n{'='*60}")
    print(f"仓库: {result.repo}")
    print(f"{'='*60}")
    print(f"总commits: {result.total_commits}")
    print(f"  - Bugfix: {result.bugfix_commits} ({result.bugfix_commits/result.total_commits*100:.1f}%)")
    print(f"  - Optimization: {result.optimization_commits} ({result.optimization_commits/result.total_commits*100:.1f}%)")
    print(f"  - Feature: {result.feature_commits} ({result.feature_commits/result.total_commits*100:.1f}%)")
    print(f"\nBugfix信息完整度:")
    print(f"  - 有issue引用: {result.bugfix_with_issue_ref*100:.1f}%")
    print(f"  - 有详细描述: {result.bugfix_with_description*100:.1f}%")
    print(f"平均消息长度: {result.avg_message_length:.1f}字符")

    if result.bugfix_examples:
        print(f"\nBugfix示例:")
        for ex in result.bugfix_examples:
            print(f"  - {ex[:60]}...")

    if result.optimization_examples:
        print(f"\nOptimization示例:")
        for ex in result.optimization_examples:
            print(f"  - {ex[:60]}...")


def main():
    base_path = Path("/tmp/ascend_repos")
    repos = [
        "HierarchicalKV-ascend",
        "fbgemm-ascend",
        "ops-nn",
        "ops-math",
        "ops-transformer",
        "ops-cv"
    ]

    results = []

    print("昇腾仓PR/Commit采样分析")
    print("="*60)

    for repo in repos:
        repo_path = base_path / repo
        if not repo_path.exists():
            print(f"\n跳过 {repo} (不存在)")
            continue

        result = analyze_repo(repo_path)
        results.append(result)
        print_result(result)

    # 汇总
    print("\n" + "="*60)
    print("汇总")
    print("="*60)

    total_commits = sum(r.total_commits for r in results)
    total_bugfix = sum(r.bugfix_commits for r in results)
    total_opt = sum(r.optimization_commits for r in results)

    print(f"分析仓库数: {len(results)}")
    print(f"总commits: {total_commits}")
    print(f"Bugfix占比: {total_bugfix/total_commits*100:.1f}%")
    print(f"Optimization占比: {total_opt/total_commits*100:.1f}%")

    # 写入报告
    report_path = Path("/Users/huangshilei/Documents/pythonprojects/asc_ops/docs/analysis/pr_sampling_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w") as f:
        f.write("# 昇腾仓PR/Commit采样分析报告\n\n")
        f.write(f"**分析日期**: 2026-04-10\n\n")
        f.write(f"**采样范围**: 6个昇腾算子仓\n\n")

        for result in results:
            f.write(f"\n## {result.repo}\n\n")
            f.write(f"| 指标 | 值 |\n")
            f.write(f"|------|-----|\n")
            f.write(f"| 总commits | {result.total_commits} |\n")
            f.write(f"| Bugfix | {result.bugfix_commits} ({result.bugfix_commits/result.total_commits*100:.1f}%) |\n")
            f.write(f"| Optimization | {result.optimization_commits} ({result.optimization_commits/result.total_commits*100:.1f}%) |\n")
            f.write(f"| Feature | {result.feature_commits} ({result.feature_commits/result.total_commits*100:.1f}%) |\n")
            f.write(f"| Bugfix有issue引用 | {result.bugfix_with_issue_ref*100:.1f}% |\n")
            f.write(f"| Bugfix有详细描述 | {result.bugfix_with_description*100:.1f}% |\n")
            f.write(f"| 平均消息长度 | {result.avg_message_length:.1f}字符 |\n")

            if result.bugfix_examples:
                f.write(f"\n### Bugfix示例\n\n")
                for ex in result.bugfix_examples:
                    f.write(f"- {ex}\n")

            if result.optimization_examples:
                f.write(f"\n### Optimization示例\n\n")
                for ex in result.optimization_examples:
                    f.write(f"- {ex}\n")

    print(f"\n报告已保存到: {report_path}")


if __name__ == "__main__":
    main()
