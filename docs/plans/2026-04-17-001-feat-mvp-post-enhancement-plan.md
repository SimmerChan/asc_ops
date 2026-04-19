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
| R2: Redis键前缀统一 | ✅ 已完成 | 统一为 `ascendc:stats:*` 和 `ascendc:corrections:*` |

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

- [x] **Unit 1: Redis 键前缀统一** ✅

**Status:** ✅ 已完成 (2026-04-19)

**迁移结果:**
- CitationTracker: `ascendc:citations:*` → `ascendc:stats:citation:*`
- CitationTracker: `ascendc:corrections:*` → `ascendc:stats:correction:*`
- CitationTracker: `ascendc:last_cited:*` → `ascendc:stats:last_cited:*`
- CitationTracker: `ascendc:last_corrected:*` → `ascendc:stats:last_corrected:*`
- FeedbackAPI: `ascendc:corrections:{entity}:{id}:{type}` → `ascendc:corrections:detail:{entity}:{id}:{type}`
- FeedbackAPI: `ascendc:correction_reports:*` → `ascendc:corrections:reports:*`

**数据迁移:** 43 个键已迁移，0 个键丢失

**Files Modified:**
- `src/asc_ops/quality/citation_tracker.py` - 更新键前缀定义
- `src/asc_ops/quality/feedback.py` - 更新键前缀定义
- `src/asc_ops/storage/redis_client.py` - 修复 mock 模式初始化
- `tests/unit/quality/test_feedback.py` - 更新测试中的硬编码键
- `scripts/migrate_redis_keys.py` - 新增迁移脚本

## Open Questions

### Resolved During Planning
- **键前缀**: 统一为 `ascendc:stats:*`

## System-Wide Impact

- **Redis**: 键名前缀变更（需验证无数据丢失）

## Risks & Dependencies

- 键前缀变更可能影响历史数据查询（影响小）
