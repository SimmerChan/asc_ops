# Fix Pattern 抽取增强 - 代码 Diff 上下文

## Overview

对 LLM 抽取管道增强，从本地 Git 仓库获取代码 diff 作为补充上下文，提升 fix_pattern 填充率至 ≥50%。

## Problem Frame

当前 LLM 抽取管道从 PR body 文本中提取 fix_pattern，但 80% 的 PR 缺乏修复方案的技术细节（PR body 只有简短描述如 "fix memory leak"），导致 fix_pattern 填充率仅 20.5%。

实际验证发现：Top 10 高优先级记录 10 条中 8 条因"不是 bugfix"被跳过，2 条成功但仅有 root_cause 无 fix_pattern。代码 diff 包含完整修复方案但未被利用。

## Requirements Trace

- **R1**: 代码 Diff 获取 — 从本地 Git 仓库获取 commit diff
- **R2**: BugExtractor 增强 — 支持 diff 上下文，引导 LLM 从 diff 分析修复方案
- **R3**: BatchBugExtractor 集成 — 抽取前自动获取 diff
- **R4**: 质量验证 — 对比增强前后填充率

## Scope Boundaries

**在范围内**:
- 本地 Git 仓库 diff 获取
- BugExtractor 的 diff 上下文支持
- BatchBugExtractor 集成

**不在范围内**:
- GitHub/GitCode API 获取 diff
- 人工标注流程
- Diff 的结构化解析（让 LLM 自己分析）

## Key Technical Decisions

- **Diff 来源**: 本地 Git 仓库 (`/tmp/ascend_repos/{repo}`)
- **Bug ID 格式**: `BUG-{repo}-{commit_hash}` → repo 对应 `/tmp/ascend_repos/{repo}`
- **Diff 传递方式**: 作为 `pr_diff` 参数传入 `BugExtractor.extract_async()`
- **Prompt 增强**: 当 `pr_diff` 存在时，追加 `Code Diff:` 部分到 prompt

## Implementation Units

- [ ] **Unit 1: GitDiffProvider 工具类**

**Goal:** 提供从本地 Git 仓库获取 commit diff 的统一接口

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `src/asc_ops/extractor/git_diff_provider.py`
- Test: `tests/unit/extractor/test_git_diff_provider.py`

**Approach:**
- 解析 bug_id 格式 `BUG-{repo}-{commit_hash}` 获取 repo 名和 commit hash
- 使用 `git diff {commit}^..{commit}` 获取变更
- Diff 过长时截断（保留前 4000 字符，确保包含关键变更）
- 获取失败时返回 None，由调用方决定降级策略

**Patterns to follow:**
- `scripts/cold_start/import_bug_opt_knowledge.py` — git subprocess 调用模式

**Test scenarios:**
- 有效 bug_id 正确解析出 repo 和 commit hash
- git 命令成功时返回完整 diff
- git 命令失败时返回 None（降级）
- diff 过长时正确截断

**Verification:**
- 单元测试通过
- 手动验证: `GitDiffProvider.get_diff("BUG-ops-math-4b6c97c0")` 返回有效 diff

---

- [ ] **Unit 2: BugExtractor diff 支持**

**Goal:** BugExtractor 支持 pr_diff 参数，增强 LLM prompt 引导分析

**Requirements:** R2

**Dependencies:** Unit 1

**Files:**
- Modify: `src/asc_ops/extractor/bug_extractor.py`
- Test: `tests/unit/extractor/test_bug_extractor.py` (新增测试)

**Approach:**
- `extract_async()` 新增 `pr_diff: Optional[str] = None` 参数
- `_llm_extract()` 新增 `pr_diff` 参数并合并到 prompt
- `BUG_EXTRACTION_PROMPT` 增强：当提供 diff 时追加 `Code Diff:` 部分
- 保持现有逻辑不变，diff 仅作为补充上下文

**Technical design:**
```
BUG_EXTRACTION_PROMPT 增强:
...
{pr_body}

{如果 pr_diff 存在:
Code Diff:
```diff
{pr_diff}
```
分析此代码变更，给出 root_cause 和 fix_pattern。}
```

**Patterns to follow:**
- `bug_extractor.py` 现有 `_llm_extract()` 模式
- 现有 `BUG_EXTRACTION_PROMPT` 结构

**Test scenarios:**
- pr_diff=None 时行为与现有逻辑完全一致
- pr_diff 有值时 prompt 包含 diff 内容
- _llm_extract 正确传递 pr_diff 参数

**Verification:**
- 现有测试全部通过
- 新增 diff 相关测试通过

---

- [ ] **Unit 3: BatchBugExtractor diff 集成**

**Goal:** 批量抽取前自动获取 diff 并传递给 BugExtractor

**Requirements:** R3

**Dependencies:** Unit 1, Unit 2

**Files:**
- Modify: `src/asc_ops/extractor/batch_extractor.py`
- Test: `tests/unit/extractor/test_batch_extractor.py` (新增测试)

**Approach:**
- `BatchBugExtractor` 持有 `GitDiffProvider` 实例
- `process_bug()` 内部调用 `GitDiffProvider.get_diff(bug.bug_id)` 获取 diff
- 将 diff 传递给 `bug_extractor.extract_async(..., pr_diff=diff)`
- 保持并发控制和错误处理逻辑不变

**Patterns to follow:**
- `batch_extractor.py` 现有 `process_bug()` 模式
- `GitDiffProvider` 接口（Unit 1 定义）

**Test scenarios:**
- diff 获取成功时正确传递给 BugExtractor
- diff 获取失败时降级传递 None（不中断抽取）
- diff 内容过长时正确截断

**Verification:**
- 单元测试通过
- 手动验证: `python scripts/llm_retry_batch.py --limit 3` 能正确获取并使用 diff

---

- [ ] **Unit 4: 端到端质量验证**

**Goal:** 对比增强前后的 fix_pattern 填充率

**Requirements:** R4

**Dependencies:** Units 1-3

**Files:**
- None (验证任务)

**Approach:**
- 执行 `python scripts/llm_retry_batch.py --report-only` 获取基线
- 执行 `python scripts/llm_retry_batch.py --limit 50` 进行增强抽取
- 再次执行 `--report-only` 对比填充率变化
- 验证 root_cause 填充率不下降

**Success Criteria:**
- fix_pattern 填充率: 20.5% → ≥50%
- root_cause 填充率: ≥70% (不下降)

**Verification:**
- 填充率对比达标

## System-Wide Impact

- **BatchBugExtractor**: 新增 GitDiffProvider 依赖
- **CLI 脚本**: 无需修改，逻辑在 BatchBugExtractor 内部处理
- **向后兼容**: pr_diff=None 时行为完全不变

## Risks & Dependencies

| 风险 | 影响 | 缓解 |
|------|------|------|
| 本地 git 仓库不存在 | diff 获取失败 | 降级传递 None，依赖现有 pr_body |
| diff 过长导致 prompt 超限 | LLM 处理失败 | 截断至 4000 字符 |
| git 命令执行慢 | 抽取延迟增加 | 并发获取 diff（可选优化） |

## Open Questions

### Resolved During Planning

- **Diff 获取时机**: 在 BatchBugExtractor.process_bug() 内部串行获取
- **Diff 截断策略**: 前 4000 字符，保留关键变更

### Deferred to Implementation

- **并发获取 diff 优化**: 当前串行获取，可作为后续优化项
- **GitHub/GitCode API fallback**: 当本地仓库缺失时从远程 API 获取

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-12-fix-pattern-extraction-enhancement-requirements.md](../brainstorms/2026-04-12-fix-pattern-extraction-enhancement-requirements.md)
- Related code: `src/asc_ops/extractor/bug_extractor.py`, `src/asc_ops/extractor/batch_extractor.py`
- Related pattern: `scripts/cold_start/import_bug_opt_knowledge.py` — git subprocess 调用
- PR #3: `feat(extractor): 实现LLM冷启动补充抽取管道`
