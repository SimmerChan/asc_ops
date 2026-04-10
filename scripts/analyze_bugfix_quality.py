#!/usr/bin/env python3
"""
深入分析Bugfix Commit的质量
评估能否提取：根因、触发条件、修复方案
"""

import os
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path

@dataclass
class BugfixDetail:
    commit_hash: str
    message: str
    full_message: str  # 包括body

    # 评估指标
    has_root_cause: bool
    has_trigger_condition: bool
    has_fix_description: bool
    has_operator_name: bool
    has_api_mentioned: bool

    quality_score: float  # 0-1


def get_full_commit_message(repo_path: str, commit_hash: str) -> str:
    """获取完整的commit消息（包括body）"""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "-1", "--format=%B", commit_hash],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except:
        return ""


def analyze_bugfix_detail(repo_path: str, commit_hash: str, message: str) -> BugfixDetail:
    """分析单个bugfix commit的质量"""

    full_msg = get_full_commit_message(repo_path, commit_hash)
    all_text = message + " " + full_msg

    # 检测特征
    has_root_cause = any(kw in all_text.lower() for kw in [
        "原因", "root cause", "因为", "由于", "导致",
        "因为xxx导致", "的问题在于", "的问题是"
    ])

    has_trigger = any(kw in all_text.lower() for kw in [
        "当", "when", "在xxx时", "场景", "条件",
        "触发", "遇到", "输入为", "大于", "小于"
    ])

    has_fix_description = any(kw in all_text.lower() for kw in [
        "修复", "修改", "改为", "调整", "fix", "change to",
        "改为", "修复为", "通过", "使用"
    ])

    # 检测算子名（简化版）
    import re
    operator_patterns = [
        r'[A-Z][a-z]+(?:[A-Z][a-z]+)+',  #驼峰命名 如MatMul, BatchMatmul
        r'(?:op|operator|算子)[_\s]+(\w+)',  #op_xxx
    ]
    has_operator = any(re.search(p, all_text) for p in operator_patterns)

    # 检测API提及
    api_patterns = [
        r'aclnn\w+',  #aclnn开头的API
        r'Mmad', r'Vec', r'Tensor',
        r'gmma', r'wmma',  # MMA相关
    ]
    has_api = any(re.search(p, all_text, re.IGNORECASE) for p in api_patterns)

    # 质量评分
    score = 0.0
    if has_root_cause: score += 0.25
    if has_trigger: score += 0.2
    if has_fix_description: score += 0.2
    if has_operator: score += 0.15
    if has_api: score += 0.1
    if len(full_msg) > 50: score += 0.1  # 有body加分

    return BugfixDetail(
        commit_hash=commit_hash,
        message=message,
        full_message=full_msg,
        has_root_cause=has_root_cause,
        has_trigger_condition=has_trigger,
        has_fix_description=has_fix_description,
        has_operator_name=has_operator,
        has_api_mentioned=has_api,
        quality_score=min(score, 1.0)
    )


def classify_and_score(repo_path: str, max_count: int = 100) -> Dict:
    """分析仓库的所有commits并评分"""

    # 获取bugfix commits
    result = subprocess.run(
        ["git", "-C", repo_path, "log", f"--max-count={max_count}", "--format=%H|%s"],
        capture_output=True, text=True, check=True
    )

    bugfix_details = []
    opt_details = []

    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        parts = line.split('|', 1)
        if len(parts) < 2:
            continue
        commit_hash, message = parts
        msg_lower = message.lower()

        # 简单分类
        if any(kw in msg_lower for kw in ["fix", "bug", "修复", "解决", "修复"]):
            detail = analyze_bugfix_detail(repo_path, commit_hash, message)
            bugfix_details.append(detail)
        elif any(kw in msg_lower for kw in ["optimize", "perf", "优化", "提升", "加速"]):
            opt_details.append(message)

    return {
        "bugfix": bugfix_details,
        "optimization": opt_details,
    }


def main():
    base_path = Path("/tmp/ascend_repos")
    repos = [
        ("HierarchicalKV-ascend", "HierarchicalKV-ascend"),
        ("fbgemm-ascend", "fbgemm-ascend"),
        ("ops-nn", "ops-nn"),
        ("ops-math", "ops-math"),
        ("ops-transformer", "ops-transformer"),
        ("ops-cv", "ops-cv"),
    ]

    all_bugfix = []
    all_optimization = []

    for repo_id, repo_name in repos:
        repo_path = base_path / repo_id
        if not repo_path.exists():
            continue

        print(f"\n分析 {repo_name}...")

        result = classify_and_score(repo_path)
        all_bugfix.extend([(repo_name, d) for d in result["bugfix"]])
        all_optimization.extend([(repo_name, m) for m in result["optimization"]])

    # 汇总分析
    print("\n" + "="*70)
    print("Bugfix Commit质量分析汇总")
    print("="*70)

    total_bugfix = len(all_bugfix)
    if total_bugfix > 0:
        avg_score = sum(d.quality_score for _, d in all_bugfix) / total_bugfix
        with_root_cause = sum(1 for _, d in all_bugfix if d.has_root_cause)
        with_trigger = sum(1 for _, d in all_bugfix if d.has_trigger_condition)
        with_fix_desc = sum(1 for _, d in all_bugfix if d.has_fix_description)
        with_operator = sum(1 for _, d in all_bugfix if d.has_operator_name)
        with_api = sum(1 for _, d in all_bugfix if d.has_api_mentioned)

        print(f"\n总Bugfix Commits: {total_bugfix}")
        print(f"平均质量分: {avg_score:.2f}/1.0")
        print(f"\n信息完整度:")
        print(f"  - 有根因描述: {with_root_cause} ({with_root_cause/total_bugfix*100:.1f}%)")
        print(f"  - 有触发条件: {with_trigger} ({with_trigger/total_bugfix*100:.1f}%)")
        print(f"  - 有修复描述: {with_fix_desc} ({with_fix_desc/total_bugfix*100:.1f}%)")
        print(f"  - 提及算子名: {with_operator} ({with_operator/total_bugfix*100:.1f}%)")
        print(f"  - 提及API: {with_api} ({with_api/total_bugfix*100:.1f}%)")

        # 按质量分类
        high_quality = [(r, d) for r, d in all_bugfix if d.quality_score >= 0.6]
        medium_quality = [(r, d) for r, d in all_bugfix if 0.3 <= d.quality_score < 0.6]
        low_quality = [(r, d) for r, d in all_bugfix if d.quality_score < 0.3]

        print(f"\n质量分布:")
        print(f"  - 高质量(≥0.6): {len(high_quality)} ({len(high_quality)/total_bugfix*100:.1f}%)")
        print(f"  - 中等(0.3-0.6): {len(medium_quality)} ({len(medium_quality)/total_bugfix*100:.1f}%)")
        print(f"  - 低质量(<0.3): {len(low_quality)} ({len(low_quality)/total_bugfix*100:.1f}%)")

        # 高质量示例
        print(f"\n高质量Bugfix示例 (质量分≥0.6):")
        for repo, detail in sorted(high_quality, key=lambda x: x[1].quality_score, reverse=True)[:5]:
            print(f"\n  [{repo}] 评分:{detail.quality_score:.2f}")
            print(f"    {detail.message[:60]}...")
            if detail.has_root_cause:
                print(f"    [有根因]")
            if detail.has_trigger_condition:
                print(f"    [有触发条件]")

        # 低质量示例
        print(f"\n低质量Bugfix示例 (质量分<0.3):")
        for repo, detail in sorted(low_quality, key=lambda x: x[1].quality_score)[:5]:
            print(f"\n  [{repo}] 评分:{detail.quality_score:.2f}")
            print(f"    {detail.message[:60]}...")

    print(f"\n\nOptimization Commits: {len(all_optimization)}")
    if all_optimization:
        print("示例:")
        for repo, msg in all_optimization[:5]:
            print(f"  [{repo}] {msg[:60]}...")


if __name__ == "__main__":
    main()
