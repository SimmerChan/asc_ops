# CUDA API → AscendC API 语义检索能力

**文档版本**: v1.0
**创建日期**: 2026-04-22
**状态**: 规划中

---

## Problem Frame

用户查询"某个 CUDA API 对应的 AscendC API 是什么"时，当前知识库无法回答。原因：
1. `cross_platform_mappings` collection 只有 57 条映射，覆盖极少
2. `gpu_apis` / `gpu_kernels` collection 为空
3. 无自动映射生成能力

需要实现：**给定任意 CUDA API，语义检索返回最相似的 AscendC API 及置信度**。

---

## Requirements

### R1. GPU API 知识采集
- 从 CUDA Toolkit 官方文档抓取 API 定义（名称、签名、参数、返回值、语义描述）
- 使用**浏览器自动化**抓取官方文档（通过 MCP Chrome DevTools 访问 `https://docs.nvidia.com/cuda/cuda-c-programming-guide/`）
- 采集范围 MVP：**warp shuffle 系列**（`__shfl_sync`、`__shfl_up_sync`、`__shfl_down_sync`、`__shfl_xor_sync`）和其他核心同步/内存原语
- **已验证可用**：
  - warp shuffle 文档页面可正常访问，函数签名和语义描述已确认
  - Mock 存储验证通过：4 个 warp shuffle API 成功入库并可检索
- 采集到的 GPU API 存入 `gpu_apis` collection（embedding 后向量检索用）

### R2. 双向语义检索
- 用户输入 CUDA API 名称
- LLM 先分析该 API 的功能、输入输出参数、数据类型、语义
- **复用现有 Qwen3-Embedding-0.6B** 进行 embedding，不单独训练
- 基于分析结果构造语义描述，embedding 后同时检索：
  - `gpu_apis` collection（确认 GPU API 存在）
  - `ascend_apis` collection（寻找语义相似的 NPU API）
- 返回最相似的 AscendC API、置信度、语义匹配说明

### R3. 混合结果返回
- 若知识库已有显式映射（`cross_platform_mappings`），优先返回精确映射
- 若无精确映射但语义检索有高置信度结果（**≥0.75**），返回语义匹配结果 + 标注为"推断"
- 若无结果，返回"未找到对应 API，建议查阅 CANN 文档"

### R4. MCP 工具扩展
- 复用现有 MCP 工具框架（`KnowledgeQueryService`）
- 新增一个工具：`semantic_mapping_query(cuda_api_name: str) -> MappingResult`

---

## Success Criteria

- [ ] 输入 `__shfl_up_sync`，返回 warp shuffle 对应的 AscendC API（如 `WarpShift` 或 `WarpUnpack`）及置信度
- [ ] 输入任意 CUDA API（如 `cudaMalloc`），能返回语义相似的 AscendC API 或"未找到"
- [ ] 语义检索流程在 3 步内完成（MCP 工具调用）

---

## Scope Boundaries

**In Scope:**
- Warp shuffle 系列 API 的采集 + 检索 MVP
- 复用现有 embedding 模型和 ChromaDB 架构
- MCP 工具扩展

**Out of Scope:**
- 批量 GPU API 采集（完整 CUDA API 覆盖）
- 自动代码转换
- 离线预生成全部映射对

---

## Key Decisions

- **双向语义检索**而非预定义映射：利用现有 ascend_apis (1102 条) 作为 NPU 语义库，无需为每个 GPU API 建立显式映射
- **MVP 先验证**：先采集 10+ 个核心 warp shuffle API 入库，验证语义检索可行性
- **混合返回**：精确映射优先，查不到再用语义推断，不强行假设

---

## Dependencies / Assumptions

- 依赖现有 ChromaDB collections 结构
- 依赖现有 `APIEmbedder` embedding 能力（复用 Qwen3-Embedding-0.6B）
- 依赖 MCP Chrome DevTools 浏览器自动化抓取 CUDA 官方文档
- 假设 LLM 能有效分析 CUDA API 语义并构造检索描述
- 假设 `ascend_apis` (1102 条) 覆盖了足够多样的 NPU API 语义

---

## Outstanding Questions

### Resolve Before Planning
*(已解决)* [R1] ~~**CUDA 文档页面**~~ → 已确认通过浏览器可访问 NVIDIA 文档，warp shuffle API 信息可抓取

### Deferred to Planning
- [R2] **LLM Prompt 设计**：如何构造 prompt 使 LLM 输出稳定的 CUDA API 语义描述？
- [R3] **置信度阈值**：0.75 作为边界是否合理？

---

## Next Steps
→ `/ce:plan` for structured implementation planning
