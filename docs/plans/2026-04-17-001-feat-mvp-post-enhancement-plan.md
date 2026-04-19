---
title: 下一阶段开发 - MVP 后增强
type: feat
status: active
date: 2026-04-17
origin: docs/brainstorms/2026-04-11-next-phase-options-requirements.md
---

# 下一阶段开发 - MVP 后增强

## Problem Frame

MVP (Phase 1-5) 已完成，但存在以下待改进点：

| 需求 | 状态 | 说明 |
|------|------|------|
| R1: 修正报告查询 | ✅ 已完成 | 已实现 `/api/v1/quality/correction/reports` |
| R2: Redis键前缀统一 | ❌ 未完成 | `ascendc:citations:*` vs `ascendc:stats:*` |

## Requirements Trace

- R1: 修正报告查询 - 已完成
- R2: Redis 键前缀统一 - 统一为 `ascendc:stats:*`

## Scope Boundaries

**在范围内:**
- Redis 键前缀统一

**不在范围内:**
- Web UI 管理界面
- 飞书/钉钉 Webhook 告警
- 自动化修正流程

## Key Technical Decisions

- **Decision**: 统一键前缀为 `ascendc:stats:*`
  - **Rationale**: CitationTracker 已有少量数据，修改成本低
  - **Alternatives considered**: 保持现状（不统一）

## Implementation Units

- [ ] **Unit 1: Redis 键前缀统一**

**Goal:** 统一所有 Redis 键前缀为 `ascendc:stats:*`

**Requirements:** R2

**Dependencies:** 无

**Files:**
- Modify: `src/asc_ops/quality/citation_tracker.py`
- Modify: `src/asc_ops/ranker/integrated_ranker.py`
- Test: `tests/unit/quality/test_citation_tracker.py`

**Approach:**
1. 将 `ascendc:citations:*` 改为 `ascendc:stats:*`
2. 添加数据迁移脚本（可选）
3. 更新相关文档

**Patterns to follow:**
- 参考 `redis_client.py` 中的键名前缀模式

**Test scenarios:**
- 所有使用旧前缀的代码能正常工作
- 新增数据使用统一前缀

**Verification:**
- Redis 中只有 `ascendc:stats:*` 前缀的键

## Open Questions

### Resolved During Planning
- **键前缀**: 统一为 `ascendc:stats:*`

## System-Wide Impact

- **Redis**: 键名前缀变更（需验证无数据丢失）

## Risks & Dependencies

- 键前缀变更可能影响历史数据查询（影响小）
