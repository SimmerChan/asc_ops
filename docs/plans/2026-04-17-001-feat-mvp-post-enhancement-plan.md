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
| R1: 告警机制 | ❌ 未实现 | 仅日志记录，无真正告警 |
| R2: 修正报告查询 | ✅ 已完成 | 已实现 `/api/v1/quality/correction/reports` |
| R3: Redis键前缀统一 | ❌ 未完成 | `ascendc:citations:*` vs `ascendc:stats:*` |

## Requirements Trace

- R1: 告警机制增强 - 支持飞书/钉钉 Webhook 通知
- R3: Redis 键前缀统一 - 统一为 `ascendc:stats:*`

## Scope Boundaries

**在范围内:**
- 飞书 Webhook 告警集成
- Redis 键前缀统一

**不在范围内:**
- Web UI 管理界面
- 钉钉 Webhook（飞书优先）
- 自动化修正流程

## Key Technical Decisions

- **Decision**: 优先实现飞书 Webhook 告警
  - **Rationale**: 飞书是团队主要沟通平台，实现价值最大
  - **Alternatives considered**: 钉钉、Webhook 接口抽象（过度设计）

- **Decision**: 统一键前缀为 `ascendc:stats:*`
  - **Rationale**: CitationTracker 已有少量数据，修改成本低
  - **Alternatives considered**: 保持现状（不统一）

## Implementation Units

- [ ] **Unit 1: 飞书 Webhook 告警集成**

**Goal:** 实现飞书告警，当纠错次数超过阈值时发送通知

**Requirements:** R1

**Dependencies:** 无

**Files:**
- Create: `src/asc_ops/integrations/feishu_webhook.py`
- Modify: `src/asc_ops/quality/feedback.py`
- Test: `tests/unit/quality/test_feishu_webhook.py`

**Approach:**
1. 创建 `FeishuWebhook` 类封装飞书自定义机器人 API
2. 在 `FeedbackAPI.report_correction()` 中调用告警
3. 支持富文本消息格式

**Patterns to follow:**
- 参考 `scripts/llm_retry_batch.py` 的 HTTP 请求模式

**Test scenarios:**
- 纠错次数超过阈值时发送告警
- 告警消息包含实体信息和纠错描述
- 网络失败时优雅降级（仅日志）

**Verification:**
- 模拟触发阈值后，飞书群收到消息

---

- [ ] **Unit 2: Redis 键前缀统一**

**Goal:** 统一所有 Redis 键前缀为 `ascendc:stats:*`

**Requirements:** R3

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
- **告警渠道**: 飞书Webhook（用户偏好）
- **键前缀**: 统一为 `ascendc:stats:*`

### Deferred to Implementation
- **告警阈值配置化**: 硬编码5次是否需要改为配置？

## System-Wide Impact

- **Feedback API**: 新增飞书告警调用
- **Redis**: 键名前缀变更（需验证无数据丢失）

## Risks & Dependencies

- 飞书 Webhook URL 需要配置在环境变量
- 键前缀变更可能影响历史数据查询（影响小）
