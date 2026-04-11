# Fix Pattern 抽取增强 - 代码 Diff 上下文

## Problem Frame

**问题**: 当前 LLM 抽取管道从 PR body 文本中提取 fix_pattern，但 80% 的 PR 缺乏修复方案的技术细节文本，导致 fix_pattern 填充率仅 20.5%。

**根因**: 原始 commit/PR 只有简短描述（如 "fix memory leak"），但代码 diff 本身包含完整修复方案。

**目标**: 利用代码 diff 作为 LLM 抽取的补充上下文，提升 fix_pattern 填充率至 ≥50%。

---

## Requirements

### R1: 代码 Diff 获取

- R1.1: 从本地 Git 仓库获取指定 commit 的 diff
- R1.2: 支持 `BUG-{repo}-{commit_hash}` 格式的 bug_id 解析
- R1.3: Diff 获取失败时降级为仅使用 pr_body（保持向后兼容）

### R2: BugExtractor 增强

- R2.1: `BugExtractor.extract()` 新增 `pr_diff` 参数
- R2.2: LLM prompt 增强: 当提供 diff 时，引导 LLM 从 diff 中分析修复方案
- R2.3: Diff 过长时进行截断（保留关键变更部分）

### R3: BatchBugExtractor 增强

- R3.1: 抽取前自动获取对应 commit 的 diff
- R3.2: 将 diff 传递给 BugExtractor
- R3.3: 保持现有优先级队列逻辑不变

### R4: 质量验证

- R4.1: 对比增强前后的 fix_pattern 填充率
- R4.2: 验证 root_cause 填充率不下降

---

## Success Criteria

- fix_pattern 填充率从 20.5% 提升至 ≥50%
- root_cause 填充率保持 ≥70%
- 新增 diff 上下文不引入新的抽取失败

---

## Scope Boundaries

**在范围内**:
- 本地 Git 仓库 diff 获取
- BugExtractor 的 diff 上下文支持
- BatchBugExtractor 集成

**不在范围内**:
- GitHub/GitCode API 获取 diff（R3 延期）
- 人工标注流程
- Diff 的结构化解析（让 LLM 自己分析）

---

## Key Decisions

- **Diff 来源**: 本地 Git 仓库 (`/tmp/ascend_repos/{repo}`)
- **Bug ID 格式**: `BUG-{repo}-{commit_hash}`，其中 repo 对应本地仓库目录名
- **Diff 传递方式**: 作为独立参数传入 BugExtractor，由 prompt 处理

---

## Dependencies / Assumptions

- 本地 Git 仓库路径 `/tmp/ascend_repos/` 存在且包含所需的 commit
- 冷启动导入的 bug 记录中 `source_repo` 和 `source_pr` (commit_hash) 字段已正确填充

---

## Next Steps

→ `/ce:plan` 进行结构化实施规划
