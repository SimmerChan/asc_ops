# 文档目录

本文档目录涵盖AscendC算子知识库的全部文档。

---

## 快速入门

| 文档 | 说明 |
|------|------|
| [安装指南](getting-started/installation.md) | 详细的安装步骤和环境配置 |
| [快速入门](getting-started/quickstart.md) | 5分钟快速体验 |
| [首次查询](getting-started/first-query.md) | 详细查询示例 |

## 部署指南

| 文档 | 说明 |
|------|------|
| [Docker部署](deployment/docker.md) | Docker和Docker Compose部署 |

## API文档

| 文档 | 说明 |
|------|------|
| [API参考](api/reference.md) | 完整REST API定义 |

## 设计文档

| 文档 | 说明 |
|------|------|
| [总体架构设计](../design/2026-04-09-ascendc-api-knowledge-base-design.md) | API知识库架构设计 |
| [GPU-NPU跨平台设计](../design/2026-04-09-gpu-npu-cross-platform-knowledge-base-design.md) | GPU到NPU适配知识设计 |
| [Bug优化知识设计](../design/2026-04-10-npu-bug-optimization-knowledge-design.md) | Bug修复与优化知识设计 |

## 实施路径

| 文档 | 说明 |
|------|------|
| [Roadmap](../roadmap/2026-04-09-ascendc-knowledge-base-implementation-roadmap.md) | 完整实施计划和里程碑 |
| [PR采样分析](../analysis/pr_sampling_report.md) | 6个昇腾算子仓的采样分析报告 |

---

## 实施阶段

| Phase | 内容 | 状态 | 完成日期 |
|-------|------|------|----------|
| Phase 1 | P1双存储架构 (ChromaDB + Redis) | ✅ 完成 | 2026-04-10 |
| Phase 2 | MCP Server + GPU采集 + CLI同步 + 端到端测试 | ✅ 完成 | 2026-04-11 |
| Phase 3 | 置信度感知排序层 (Authority/Recency/Accuracy) | ✅ 完成 | 2026-04-11 |
| Phase 4 | 知识质量评分体系 (CitationTracker + FeedbackAPI) | ✅ 完成 | 2026-04-11 |
| Phase 5 | Bug/优化知识设计 (BugFix + Optimization Knowledge) | ✅ 完成 | 2026-04-11 |

### 今日完成 (2026-04-11)

1. **P1知识存储pipeline修复** - 修复async/await、导入路径问题，端到端验证成功
2. **GitCode PR批量采集** - 配置6个仓库，修复分页bug，实现分页支持
3. **冷启动知识库填充** - 从6个本地Git仓库导入125条知识 (115 bug fixes + 10 optimizations)
4. **P2置信度排序系统** - 置信度分数现在显示复合分数0.680
5. **P2质量反馈循环** - CitationTracker + FeedbackAPI 端到端验证完成

### 待处理事项

1. **告警机制增强** - 当前仅日志记录，需要实现真正的告警集成
2. **修正报告查询端点** - `/api/v1/quality/correction/reports`
3. **Redis键前缀统一** - CitationTracker (`citations:*`) vs Ranker (`stats:*`)

---

## 文档更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-04-10 | 补充README、快速入门、部署、API文档 |
| 2026-04-11 | 更新MVP完成状态，Phase 1-5 全部完成 |
| 2026-04-11 | 更新今日完成工作，待处理事项 |
