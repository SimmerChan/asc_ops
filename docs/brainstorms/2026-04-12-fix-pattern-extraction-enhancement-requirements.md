# Fix Pattern 抽取增强 - 代码 Diff 上下文

## Problem Frame

**问题**: 当前 LLM 抽取管道从 PR body 文本中提取 fix_pattern，但 80% 的 PR 缺乏修复方案的技术细节文本，导致 fix_pattern 填充率仅 20.5%。

**根因**: 原始 commit/PR 只有简短描述（如 "fix memory leak"），但代码 diff 本身包含完整修复方案。

**目标**: 利用代码 diff 作为 LLM 抽取的主要分析对象，提升 fix_pattern 填充率至 ≥70%。

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

- fix_pattern 填充率从 21% 提升至 **≥70%**
- root_cause 填充率保持 ≥70%
- 新增 diff 上下文不引入新的抽取失败

---

## Scope Boundaries

**在范围内**:
- 本地 Git 仓库 diff 获取 ✓ (已完成)
- GitCode API diff 获取 ✓ (已完成)
- BugExtractor 的 diff 上下文支持 ✓ (已完成)
- BatchBugExtractor 集成 ✓ (已完成)
- **Diff 代码变更模式结构化提取** ← 新增

**不在范围内**:
- 人工标注流程

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

---

## Diff 代码变更模式提取设计

### 问题分析

当前 prompt 存在指令冲突:
- 第 42 行: "Only extract information that is explicitly stated" (只提取明确说明的信息)
- 第 68 行: "Use the code diff to infer root_cause and fix_pattern" (从 diff 推断)

LLM 在冲突指令间趋向保守，导致 fix_pattern 填充率仅 21%。

### Prompt 设计改进 (v2)

**改进要点:**
1. 移除 "Only extract explicitly stated" 冲突指令
2. 移除 change_type 分类（容易误判 "放开限制" 为 feature_addition）
3. 改为 `has_code_fix: true/false` 二值判断
4. 添加 "Key Insight: Relaxing Constraints IS a Bug Fix" 指导
5. 强调 "When in doubt, extract fix_pattern"

**验证结果 (2026-04-12):**
- ops-nn-941 (代码修复): Current=解析失败, New v2=**成功提取** ✓
- ops-nn-777 (新增功能): Current=解析失败, New v2=正确返回 null ✓
- ops-transformer-942 (文档更新): Current=不准确, New v2=正确返回 null ✓

### 设计原则

1. **Diff 作为主要分析对象**，而非背景上下文
2. **多层级代码变更分析**: 语句级、函数级、架构级
3. **分类输出**: 不同变更类型映射到不同字段

### Diff 变更类型 → 字段映射

| diff 变更类型 | 分析维度 | 输出字段 | 示例 |
|--------------|---------|---------|------|
| 代码语句添加 | **语句级** | fix_pattern | "Added null check before pointer dereference" |
| 代码语句删除 | 语句级 (隐式) | root_cause | "Removed incorrect bounds check" |
| 条件判断变更 | 触发条件 | trigger_conditions | "Changed condition from > to >= (off-by-one)" |
| 函数/方法变更 | API 关联 | related_apis | "Added new parameter to Matmul::compute()" |
| 错误处理添加 | 修复方案 | fix_pattern | "Added retry logic with exponential backoff" |
| 算法重构 | 修复方案 | fix_pattern | "Replaced O(n²) loop with hashmap for O(1)" |

### 期望的 fix_pattern 示例

| 级别 | fix_pattern 示例 |
|------|-----------------|
| 语句级 | "Added if (ptr != nullptr) check before dereference" |
| 语句级 | "Added bounds check: if (idx < size) before array access" |
| 函数级 | "Added validate_tensor() function called at entry of process()" |
| 架构级 | "Added error handling layer with try-catch wrapper" |
| 算法级 | "Replaced linear search with binary search (O(n) → O(log n))" |

---

## Outstanding Questions

### Resolve Before Planning
- [R1][User] fix_pattern 目标填充率应该是多少？→ **≥70%** ✓ 已确认

### Deferred to Planning
- [R2][Technical] 如何处理超长 diff 的截断策略？
- [R3][Needs research] 是否需要为 root_cause 和 fix_pattern 使用不同的 prompt 模板？
- [R4][Technical] 如何验证 fix_pattern 质量（不仅仅是填充率，还有语义正确性）？

---

## Next Steps

→ `/ce:plan` 进行结构化实施规划
