# GPU→NPU 算子等价分析与知识迁移

**文档版本**: v1.0
**创建日期**: 2026-04-17
**状态**: 待规划

---

## Problem Frame

当前预定义映射表（`predefined_mappings.py`）依赖人工维护，仅覆盖 45+ 基础 API 映射。已改用 LLM 自动分析能力，从 GPU 算子仓（如 cuBLAS、CUTLASS）和 NPU 算子仓（AscendC）中发现**实现级等价关系**，并提取可迁移的优化知识。所有映射通过 LLM 分析获取，不再依赖预定义静态映射。

这解决了两个核心问题：
1. **映射发现问题**：GPU 上这个算子在 NPU 上对应哪个 API？
2. **迁移知识提取**：GPU 上的优化模式（如 tiling、fusion）在 NPU 上如何实现？

---

## Requirements

### R1. 对等仓库配置管理
- 用户可在配置文件中设置 GPU 仓和 NPU 仓的对等关系
- 配置项：仓路径、本地路径、平台类型（CUDA/CUTLASS/cuBLAS ↔ AscendC）
- 支持多组对等仓配置
- **用户指定分析范围**：在配置中指定要分析的子目录或文件路径

### R2. LLM 驱动的算子等价分析
- 给定一组对等仓，LLM 自动分析并发现：
  - 算子级等价：`cublasSgemm` ↔ `Matmul`
  - 实现级等价：具体 kernel 的数据分块策略、shared memory 使用、寄存器分配模式
- 输出：包含等价级别（EXACT/SIMILAR）、适配备注、置信度的映射关系

### R3. 可迁移优化知识提取
- 分析 GPU kernel 的优化模式：
  - 内存访问模式（coalesced、tiled、strided）
  - 计算分块策略（block size、warp tiling）
  - 异步流水线（overlap IO and compute）
  - Tensor Core 利用率
- 输出：在 NPU 上的等效实现建议

### R4. 分析结果持久化
- **向量数据库**：分析结果存入 ChromaDB + Redis，支持语义检索
- **置信度分流**：≥0.8 标记为 `llm_high_conf`，<0.8 标记为 `llm_suggested`
- ~~**预定义映射表**：分析结果追加到 `predefined_mappings.py`，覆盖或补充人工定义**~~ ✅ 已删除预定义映射

### R5. 手动触发机制
- 用户显式触发分析任务
- 命令行接口：`asc-ops analyze-mapping --gpu-repo <path> --npu-repo <path>`
- 支持 dry-run 预览模式

---

## Success Criteria

- [ ] 给定一组对等仓（CUDA 仓 ↔ AscendC 仓），系统能自动输出 80%+ 覆盖率的算子映射
- [ ] 映射包含等价级别和适配备注，可直接用于迁移辅助
- [ ] 分析结果同时持久化到预定义映射表和向量库
- [ ] 命令行触发机制可用，用户可指定仓路径并获得分析报告

---

## Scope Boundaries

**In Scope:**
- 算子级和实现级等价分析
- 简单配置（仓路径 + 平台类型）
- 手动触发 + dry-run 预览

**Out of Scope:**
- Webhook 自动触发（后续迭代）
- 定期全量分析（后续迭代）
- 细粒度文件过滤配置（后续迭代）
- 自动代码转换或生成（作为独立功能）

---

## Key Decisions

- **简单配置优先**：不做过度的配置复杂度，LLM 应能自动推断分析范围
- **手动触发**：不引入 Webhook 等自动机制，降低系统耦合
- **双存储 + 置信度过滤**：预定义映射表作为权威来源（代码化），向量库支持语义检索；置信度 ≥ 0.8 写入预定义表，< 0.8 仅存入向量库供人工审核

---

## Dependencies / Assumptions

- 依赖现有 `gpu_collector` 模块的数据模型（`GPUKernelKnowledge`、`CrossPlatformMapping`）
- 依赖现有 `GPUStorage` 的 ChromaDB + Redis 双写存储
- 假设 LLM 能有效理解 GPU 和 NPU 的代码语义差异

---

## Outstanding Questions

### Resolve Before Planning
- [R2/R3] **分析深度**：~~LLM 分析单个 kernel 需要消耗的 token 成本是否可接受？~~ → **用户指定**：用户在配置中指定要分析的子目录或文件路径
- [R4] **置信度阈值**：~~分析结果的置信度低于多少时不应写入预定义映射表？~~ → **≥ 0.8 写入预定义表，< 0.8 仅存向量库**

### Deferred to Planning
- [R2] **LLM Prompt 设计**：具体如何构造 prompt 让 LLM 输出一致性强的结构化映射？
- [R4] **冲突处理**：如果 LLM 分析结果与现有预定义映射矛盾，如何处理？
- [R5] **CLI 界面**：具体命令行参数和输出格式设计

---

## Next Steps
→ Resume `/ce:brainstorm` to resolve blocking questions before planning
