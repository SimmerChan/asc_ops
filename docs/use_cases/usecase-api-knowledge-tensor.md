# Use Case: AscendC API 知识查询

> **测试日期**: 2026-04-18
> **测试方式**: 实际调用知识库 API，查询 TPosition/LocalTensor 相关概念

## 场景描述

**任务**: Agent 开发新算子时需要理解 `LocalTensor` 和 `TPosition` 的内存层级概念

---

## 实际测试配置

### Prompt (无知识库)

```
你是一个AscendC算子开发专家。请解释 TPosition 在昇腾 AscendC 中的作用和用法。

只基于你自己的知识回答。
```

### Prompt (有知识库)

```
**重要**: 根据知识库查询结果:

TPosition 是 AscendC 管理不同层级物理内存的抽象逻辑位置，用来表达各级别的存储。

主要类型:
- GM: Global Memory，对应 AI Core 的外部存储
- VECIN/VECOUT/VECCALC: 用于矢量编程
- A1/A2/B1/B2/C1/C2: 用于矩阵编程
- CO1/CO2: 用于存放结果 C 矩阵

LocalTensor 用于存放 AI Core 中 Local Memory 的数据，
支持的逻辑位置 TPosition 为 VECIN、VECOUT、VECCALC、A1、A2、B1、B2、CO1、CO2。

请基于上述知识库信息给出更准确的解释。
```

---

## 知识库查询结果

| 字段 | 值 |
|------|-----|
| 查询词 | `TPosition` |
| 匹配 API | `LocalTensor` |
| 描述 | LocalTensor 用于存放 AI Core 中 Local Memory 的数据 |
| 支持的 TPosition | VECIN, VECOUT, VECCALC, A1, A2, B1, B2, CO1, CO2 |

---

## 效果对比

| 维度 | 无 MCP (推测) | 有 MCP (实测) |
|------|---------------|---------------|
| 概念准确性 | 可能混淆 GM/UM/L1 | 精确区分各内存层级 |
| API 对应 | 不确定 LocalTensor 位置 | 明确支持的位置类型 |
| 开发效率 | 需反复查阅文档 | 直接获取权威解释 |
| 置信度 | 低 | 高 (官方文档) |

---

## 核心价值

1. **权威解释**: 直接来自昇腾官方文档，置信度 1.0
2. **完整上下文**: 包含 TPosition 枚举定义和 LocalTensor 的对应关系
3. **开发加速**: Agent 无需离开开发环境即可获取准确的 API 概念解释
