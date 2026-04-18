# Use Case: Matmul 算子 Bug 知识查询

> **测试日期**: 2026-04-18
> **测试方式**: 实际调用知识库 API，查询 Matmul 相关 Bug

## 场景描述

**任务**: Agent 开发 Matmul 算子时遇到 `SocVersion` 相关问题

**症状**: Matmul 实现使用了过时的 SocVersion 架构枚举 (Ascend910B, Ascend950)，需要迁移到新的 NpuArch 接口

---

## 实际测试配置

### Prompt (无知识库)

```
你是一个AscendC算子开发专家。开发者在使用 Matmul 算子时遇到以下问题:

症状: Matmul 实现使用了过时的 SocVersion 架构枚举

请问:
1. 这可能是什么原因?
2. 如何解决这个问题?

只基于你自己的知识回答。
```

### Prompt (有知识库)

```
**重要**: 根据知识库查询结果，这个问题有已知的根因和解决方案:

根因:
Matmul 实现使用了过时的 SocVersion-based 架构枚举
(Ascend910B, Ascend950)，需要迁移到新的 DAV2201/DAV3510 架构标识。

触发条件:
在需要新 DAV2201/DAV3510 架构标识的硬件上运行 Matmul 操作。

相关 API:
- Tile::TileCopy<Arch::Ascend910B/Ascend950>
- Tile::TileCopy<Arch::DAV2201/DAV3510>

请基于上述知识库信息给出解决方案。
```

---

## 知识库查询结果

| 字段 | 值 |
|------|-----|
| Operator | `Matmul` |
| Bug 数量 | 5 条相关 |
| 示例 Bug | `Matmul使用的SocVerison整改为NpuArch新接口` |
| 严重性 | `minor` |
| 根因 | 过时的 SocVersion 架构枚举需要迁移到 NpuArch |
| 触发条件 | 在 DAV2201/DAV3510 架构硬件上运行 |

---

## 效果对比

| 维度 | 无 MCP (推测) | 有 MCP (实测) |
|------|---------------|---------------|
| 问题定位 | 需猜测可能原因 | 精确定位到 SocVersion 过时 |
| 解决方案 | 需搜索文档 | 直接提供迁移路径 |
| 相关 API | 未知 | 明确列出新旧 API 对应 |
| 触发条件 | 不确定 | 明确告知硬件要求 |

---

## 核心价值

1. **快速定位根因**: 知识库直接指出是 SocVersion vs NpuArch 的问题
2. **提供修复路径**: 明确新旧 API 对应关系 (`Tile::TileCopy<Arch::Ascend910B>` → `Tile::TileCopy<Arch::DAV2201>`)
3. **避免踩坑**: 知道在哪些硬件配置下会触发此问题
