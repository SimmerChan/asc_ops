---
title: Fix Pattern Prompt v2 集成
type: feat
status: completed
date: 2026-04-12
origin: docs/brainstorms/2026-04-12-fix-pattern-extraction-enhancement-requirements.md
---

# Fix Pattern Prompt v2 集成

## Overview

将验证过的 `BUG_EXTRACTION_PROMPT_WITH_DIFF` v2 版本集成到 BugExtractor，解决当前 prompt 指令冲突问题，提升 fix_pattern 填充率至 ≥70%。

## Problem Frame

当前 prompt 存在指令冲突：
- 规则 1: "Only extract information that is explicitly stated" (只提取明确说明的)
- 规则 2: "Use the code diff to infer root_cause and fix_pattern" (从 diff 推断)

LLM 在冲突指令间趋向保守，导致 fix_pattern 填充率仅 21%。

**验证结果 (2026-04-12):**
- ops-nn-941 (代码修复): Current=解析失败, New v2=**成功提取** ✓
- ops-nn-777 (新增功能): Current=解析失败, New v2=正确返回 null ✓
- ops-transformer-942 (文档更新): Current=不准确, New v2=正确返回 null ✓

## Requirements Trace

- R2.2: LLM prompt 增强 — 引导 LLM 从 diff 分析修复方案
- R4: 质量验证 — 对比增强前后填充率 (R4.1, R4.2)

## Scope Boundaries

**在范围内:**
- 更新 `BUG_EXTRACTION_PROMPT_WITH_DIFF` 为 v2 版本
- 更新单元测试 mock response (添加 `has_code_fix` 字段)

**不在范围内:**
- BatchBugExtractor 改动 (已支持 diff 参数)
- GitCodeDiffProvider 改动 (已实现)

## Key Technical Decisions

- **Prompt v2 核心改动:**
  1. 移除 "Only extract explicitly stated" 冲突指令
  2. 移除 change_type 分类（误判 "放开限制" 为 feature_addition）
  3. 改为 `has_code_fix: true/false` 二值判断
  4. 添加 "Key Insight: Relaxing Constraints IS a Bug Fix" 指导
  5. 强调 "When in doubt, extract fix_pattern"

## Implementation Units

- [ ] **Unit 1: 更新 BUG_EXTRACTION_PROMPT_WITH_DIFF 为 v2**

**Goal:** 替换 bug_extractor.py 中的 prompt 模板，解决指令冲突

**Requirements:** R2.2

**Dependencies:** None

**Files:**
- Modify: `src/asc_ops/extractor/bug_extractor.py` (第 45-70 行，替换为 prompt v2，参考 test_prompt_comparison.py lines 57-118)

**Approach:**
- 用 prompt v2 完整替换当前的 `BUG_EXTRACTION_PROMPT_WITH_DIFF`
- Prompt v2 内容: 见 test_prompt_comparison.py 中已验证的 `NEW_PROMPT`
- 保持 `BUG_EXTRACTION_PROMPT` (无 diff 版本) 不变

**Patterns to follow:**
- 现有 `bug_extractor.py` prompt 定义结构

**Test scenarios:**
- prompt 包含 "Key Insight: Relaxing Constraints IS a Bug Fix"
- prompt 不包含 "Only extract explicitly stated"
- prompt 不包含 change_type 分类
- mock response 包含 `has_code_fix` 字段

**Verification:**
- grep 'has_code_fix' src/asc_ops/extractor/bug_extractor.py
- grep 'Only extract' src/asc_ops/extractor/bug_extractor.py (应无结果)
- 单元测试全部通过

## Verification

**Goal:** 验证 prompt v2 确实提升 fix_pattern 填充率

**Owner:** Unit 1

**Approach:**
- 使用 `python scripts/llm_retry_batch.py --limit 20` 测试 20 条记录
- 对比增强前后的 fix_pattern 填充率

**Success Criteria:**
- fix_pattern 填充率: 21% → ≥70%
- root_cause 填充率保持 ≥70%

**Verification:**
- 质量报告 fix_pattern 填充率 ≥70%

## Open Questions

### Deferred to Implementation

- **超长 diff 截断策略**: 已在现有实现中处理 (4000 字符截断)
- **prompt 是否需要分离**: 当前保持单一 prompt，通过 diff 参数区分

## System-Wide Impact

- **BugExtractor**: prompt 改变可能影响抽取结果，需验证
- **向后兼容**: 已有数据的 fix_pattern 不会自动更新，需要重新抽取

## Risks & Dependencies

| 风险 | 影响 | 缓解 |
|------|------|------|
| prompt 改变影响现有抽取质量 | 可能下降 | 验证 root_cause 不下降 |
| LLM 行为随模型版本变化 | prompt 效果不稳定 | 定期验证填充率 |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-12-fix-pattern-extraction-enhancement-requirements.md](../brainstorms/2026-04-12-fix-pattern-extraction-enhancement-requirements.md)
- **验证脚本:** `test_prompt_comparison.py` (验证通过)
- Related code: `src/asc_ops/extractor/bug_extractor.py`
