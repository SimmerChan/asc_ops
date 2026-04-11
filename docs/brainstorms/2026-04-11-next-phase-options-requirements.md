---
date: 2026-04-11
topic: next-phase-options
status: draft
---

# 下一阶段开发方向

**文档版本**: v1.0
**创建日期**: 2026-04-11
**状态**: 待讨论

---

## 问题背景

MVP (Phase 1-5) 已全部完成。当前质量反馈循环系统存在以下待改进点：

1. **告警机制增强** - 当前仅日志记录，需要实现真正的告警集成
2. **修正报告查询端点** - 缺失 `/api/v1/quality/correction/reports` 端点
3. **Redis键前缀不统一** - CitationTracker (`ascendc:citations:*`) vs Ranker (`ascendc:stats:*`)

---

## 需求概述

### R1: 告警机制增强

**当前状态**: FeedbackAPI 在纠错超过阈值时仅记录日志

**目标状态**: 实现真正的告警集成，支持多渠道通知

**可选方案**:

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| A. 飞书Webhook | 集成飞书自定义机器人 | 实现简单，支持富文本 | 仅飞书平台 |
| B. 钉钉Webhook | 集成钉钉自定义机器人 | 实现简单，支持富文本 | 仅钉钉平台 |
| C. 统一告警接口 | 定义 AlertChannel 接口，支持多渠道 | 灵活可扩展 | 实现复杂度高 |
| D. 保持现状 | 继续使用日志记录 | 无额外工作 | 无法主动通知 |

**推荐**: 方案A (飞书Webhook)，快速实现价值

---

### R2: 修正报告查询端点

**当前状态**: `/api/v1/quality/correction/` 仅支持上报，不支持查询

**目标状态**: 新增 `/api/v1/quality/correction/reports` 查询修正报告

**功能需求**:
- R2.1: 按时间范围查询修正报告
- R2.2: 按实体类型过滤 (bug/optimization/api)
- R2.3: 按修正类型过滤 (wrong/incomplete/outdated/misleading)
- R2.4: 支持分页

**API设计**:

```
GET /api/v1/quality/correction/reports
Query Parameters:
  - entity_type: bug | optimization | api (可选)
  - correction_type: wrong | incomplete | outdated | misleading (可选)
  - start_date: ISO日期 (可选)
  - end_date: ISO日期 (可选)
  - page: int (默认1)
  - page_size: int (默认20)

Response:
{
  "total": 100,
  "page": 1,
  "page_size": 20,
  "reports": [
    {
      "report_id": "CRR-xxx",
      "entity_id": "BUG-ops-nn-1136",
      "entity_type": "bug",
      "correction_type": "wrong",
      "description": "...",
      "suggested_fix": "...",
      "reported_by": "user-xxx",
      "created_at": "2026-04-11T..."
    }
  ]
}
```

---

### R3: Redis键前缀统一

**当前状态**:
- CitationTracker 使用: `ascendc:citations:{entity_type}:{entity_id}`
- Ranker accuracy 使用: `ascendc:stats:{entity_type}:citation:{entity_id}`

**目标状态**: 统一键前缀，确保数据一致性

**决策点**:
1. 统一使用 `ascendc:stats:*` 前缀 (Ranker现有)
2. 统一使用 `ascendc:citations:*` 前缀 (CitationTracker现有)
3. 创建同步机制两者兼顾

**推荐**: 方案1，统一为 `ascendc:stats:*`，修改 CitationTracker

---

## 成功标准

- [ ] 告警可发送至飞书/钉钉（至少一个渠道）
- [ ] `/api/v1/quality/correction/reports` 端点可查询历史修正
- [ ] Redis键前缀全局统一

---

## 范围边界

**在范围内**:
- 告警渠道集成
- 修正报告查询API
- Redis键名前缀统一

**不在范围内**:
- Web UI 管理界面
- 告警历史持久化到数据库
- 自动化修正流程

---

## 依赖 / 假设

- 飞书/钉钉 Webhook URL 已配置在环境变量
- Redis 连接正常

---

## 待讨论问题

### 需用户决策

1. **告警渠道优先级**: 优先集成飞书还是钉钉？
2. **修正报告保留策略**: 纠错记录保留多长时间？（建议30天）

### 技术决策

3. **键名前缀统一方案**: 统一为哪个前缀？
4. **告警阈值配置化**: 纠错超过5次触发告警，是否需要支持配置？

---

## 下一步

建议优先实现 **R2 (修正报告查询)** + **R3 (键前缀统一)**，作为MVP后的快速增强。

告警增强 (R1) 需要确认具体渠道偏好后实施。

---

**文档状态**: 待用户选择方向后完善
