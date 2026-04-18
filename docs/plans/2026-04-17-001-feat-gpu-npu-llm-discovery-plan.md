# GPU→NPU 算子等价分析与知识迁移实施计划

---
title: feat: GPU-NPU LLM Discovery
type: feat
status: completed
date: 2026-04-17
completed: 2026-04-18
origin: docs/brainstorms/2026-04-17-gpu-npu-llm-discovery-requirements.md
deepened: 2026-04-17
---

## Overview

引入 LLM 自动分析能力，从 GPU 算子仓和 NPU 算子仓中发现实现级等价关系，提取可迁移的优化知识，并持久化到向量库。已删除 `predefined_mappings.py` 的静态依赖，所有映射通过 LLM 分析获取。

## Problem Frame

当前预定义映射表依赖人工维护，仅覆盖 45+ 基础 API。用户需要：
1. 自动发现 GPU→NPU 映射关系
2. 提取可迁移的优化知识（数据分块、shared memory、Tensor Core 利用率等）

## Requirements Trace

- **R1**: 对等仓库配置管理（仓路径 + 平台类型 + 用户指定分析范围）
- **R2**: LLM 驱动算子等价分析（算子级 + 实现级）
- **R3**: 可迁移优化知识提取
- **R4**: 纯向量库持久化（全部存入 ChromaDB + Redis，高置信度标记为可直接使用）
- **R5**: 手动触发 + dry-run

## Scope Boundaries

**In Scope:**
- 算子级和实现级等价分析 ✅
- 原子级 API 等价分析 ✅
- 简单配置（仓路径 + 平台类型） ✅
- 手动触发 + dry-run 预览 ✅
- 新增独立 ChromaDB collection (`cross_platform_mappings`) ✅
- Redis 元数据存储 ✅
- 删除 `predefined_mappings.py` 静态映射依赖 ✅ 已完成

**Out of Scope:**
- Webhook 自动触发
- 定期全量分析
- 自动代码转换

## Key Technical Decisions

- **纯向量库存储**: 所有映射均来自代码仓 LLM 分析，存入 ChromaDB + Redis，不再依赖 `predefined_mappings.py` ✅ 已完成
- **置信度分流**: 分析结果按置信度分流存储，全部写入向量库，≥0.8 标记为高置信度供主查询使用
- **复用现有组件**: 扩展 `GPUStorage`、`MapperEngine`，而非新建平行模块

  **理由**:
  1. 避免存储碎片化: `GPUStorage` 已实现 ChromaDB + Redis 双存储，并原生支持 `CrossPlatformMapping` 模型
  2. 复用 LLM 调用模式: `MapperEngine._generate_llm_mapping()` 已封装完整 LLM 调用流程，新分析引擎只需替换 prompt 模板
  3. 接口继承清晰: `GPUNPUAnalysisEngine` 专注 LLM 分析，`GPUStorage` 专注持久化，两者通过 `CrossPlatformMapping` dataclass 解耦

- **用户指定范围**: 配置中指定分析路径，LLM 只分析指定文件

## Implementation Units

- [x] **Unit 1: 存储层扩展** ✅

**Goal:** 扩展 ChromaDB collection 和 Redis keys 支持跨平台映射

**Requirements:** R4

**Dependencies:** None

**Files:**
- Modify: `src/asc_ops/storage/collections.py` — 新增 `CROSS_PLATFORM_MAPPINGS` collection
- Modify: `src/asc_ops/storage/keys.py` — 新增映射相关 key patterns
- Modify: `src/asc_ops/gpu_collector/storage.py` — 扩展 `GPUStorage` 支持双写 (ChromaDB + Redis)

**Approach:**
- 在 `CollectionType` 枚举新增 `CROSS_PLATFORM_MAPPINGS = "cross_platform_mappings"`
- 在 `KeyPattern` 新增 `MAPPING_INDEX = "mapping:{mapping_id}"`、`MAPPING_LIST = "mapping:list"`、`MAPPING_SOURCE = "mapping:{mapping_id}:source"`
- 扩展 `GPUStorage` 支持同时写入 ChromaDB (向量) 和 Redis (元数据)，而非仅 Redis

**Patterns to follow:**
- `GPUStorage` 现有存储模式
- `CollectionType` 现有枚举模式

**Test scenarios:**
- 新增 collection 配置正确 ✅
- 映射存储和查询正确 ✅

**Verification:**
- `GPUStorage` 能存储和查询 `CrossPlatformMapping` ✅
- ChromaDB collection 存在且可写入 ✅

---

- [x] **Unit 2: 配置层扩展** ✅

**Goal:** 支持对等仓库配置

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `src/asc_ops/config.py` — 新增 `PeerRepoConfig` 和相关配置
- Modify: `peer_repos.yaml` — 对等仓库配置示例

**Approach:**
- 新增 `PeerRepoConfig` dataclass：`gpu_repo_path`、`npu_repo_path`、`gpu_platform`、`analysis_paths`（用户指定）
- 配置支持多组对等仓

**Patterns to follow:**
- `ChromaDBConfig` 等现有配置类的 Pydantic 模式

**Test scenarios:**
- 配置正确解析 ✅
- 多组配置支持 ✅

**Verification:**
- `PeerRepoConfig` 能正确加载 YAML 配置 ✅

---

- [x] **Unit 3: LLM 分析引擎** ✅

**Goal:** 实现 GPU→NPU 等价分析核心逻辑

**Requirements:** R2, R3

**Dependencies:** Unit 1, Unit 2

**Files:**
- Create: `src/asc_ops/mapper/llm_analyzer.py` — `GPUNPUAnalysisEngine` 类
- Create: `tests/unit/test_llm_analyzer.py` — 单元测试

**Approach:**
- 实现 `GPUNPUAnalysisEngine.analyze_file_pair(gpu_file, npu_file)` 方法
- LLM Prompt 采用"结构化角色 + 代码对 + JSON 输出"三段式：
  1. 角色定义: "You are an expert in GPU and Huawei Ascend NPU cross-platform optimization..."
  2. 输入区块: 分别以 ` ```cuda ` 和 ` ```cpp ` 标记 GPU/NPU 代码段，附带元数据如函数签名、shared memory 使用等
  3. 输出规格: JSON 字段 `equivalence_level` (exact/similar/conceptual)、`npu_equivalent`（函数名）、`confidence` (0.0-1.0)、`adaptation_notes`、`optimization_hints` (数据分块/shared memory/TensorCore/无)
- temperature=0.1，max_tokens=2048 (支持 MiniMax thinking blocks)
- **JSON 解析失败处理**: 重试3次 (exponential backoff 1s/2s/4s)，仍失败则 confidence=0.0，标记 `parsing_failed=true`，存入向量库供人工审核
- **Markdown JSON 提取**: LLM 可能返回 ```json ... ``` 格式，增加正则提取逻辑
- Token 预算控制: 单次调用最多 N 个文件对（默认50），每个文件对最多 M tokens（默认2000）

**Patterns to follow:**
- `MapperEngine._generate_llm_mapping` 的 LLM 调用封装模式（但需独立实现文件对分析）

**Test scenarios:**
- 给定 GPU/NPU 代码对，输出有效映射 ✅
- 空输入或无效输入正确处理 ✅

**Verification:**
- `GPUNPUAnalysisEngine` 能处理代码对并返回结构化结果 ✅

---

- [x] **Unit 4: CLI 集成** ✅

**Goal:** 提供命令行触发接口

**Requirements:** R5

**Dependencies:** Unit 1, Unit 2, Unit 3

**Files:**
- Create: `src/asc_ops/cli/analyze.py` — `analyze-mapping` 子命令
- Modify: `src/asc_ops/cli/__init__.py` — 注册子命令

**Approach:**
- `asc-ops analyze-mapping --config <yaml> --name <config_name>` 或 `--gpu-repo <path> --npu-repo <path>`
- `--dry-run` 模式：只输出分析结果，不持久化
- `--output <file>` 输出结果到 JSON 文件
- `--atomic` 原子级分析模式（见下方原子化扩展）
- 正常模式：按置信度分流存储

**Patterns to follow:**
- `sync.py`、`collect.py` 等现有 CLI 子命令模式

**Test scenarios:**
- 正确解析参数 ✅
- dry-run 模式输出结果但不写入 ✅
- 正常模式正确分流存储 ✅

**Verification:**
- CLI 命令可执行 ✅
- 参数验证正确 ✅

---

- [x] **Unit 5: 持久化逻辑** ✅

**Goal:** 实现纯向量库存储逻辑

**Requirements:** R4

**Dependencies:** Unit 1, Unit 3

**Files:**
- Modify: `src/asc_ops/mapper/llm_analyzer.py` — 扩展 `GPUNPUAnalysisEngine` 集成存储逻辑

**Approach:**
- 所有分析结果统一存入 ChromaDB (`cross_platform_mappings`) + Redis
- 高置信度 (≥0.8) 映射：source='llm_high_conf'，可直接用于主查询
- 低置信度 (<0.8) 映射：source='llm_suggested'，供人工审核后晋升
- 冲突策略：同一 `gpu_api` 保留多条映射（置信度不同），按置信度排序，审核后可覆盖
- **存储事务**: 先写 Redis 再写 ChromaDB，若 ChromaDB 写入失败则删除 Redis 条目作为补偿
- 已删除 `predefined_mappings.py` 中的静态映射（用户决定）✅ 已完成

**Patterns to follow:**
- 现有 `MapperEngine` 存储模式

**Test scenarios:**
- 高置信度映射正确写入向量库 (source='llm_high_conf') ✅
- 低置信度映射正确存入向量库 (source='llm_suggested') ✅
- 存储失败时 Redis 回滚正确执行 ✅

**Verification:**
- 存储后查询能返回结果 ✅

---

## 原子化映射扩展 ✅

**Goal:** 将分析粒度从文件级细化到原子 API 调用级

**Status:** ✅ 已完成 (2026-04-18)

**Problem:**
- 文件级分析只能发现"整个文件的等价"，无法发现文件内具体 CUDA/CUB 库函数的 NPU 等效
- Agent 搜索 GPU 迁移知识时，只能搜索到文件级映射，不能搜索到具体 API 映射

**Solution:**
从 GPU/NPU 代码文件中提取原子 API 调用，对每个 API pair 单独进行 GPU→NPU 映射分析。

**Files:**
- Create: `src/asc_ops/mapper/atomic_parser.py` — `AtomicCodeParser` 原子 API 提取器
- Modify: `src/asc_ops/mapper/llm_analyzer.py` — 新增 `analyze_file_pair_atomic()` 方法
- Modify: `src/asc_ops/cli/analyze.py` — 新增 `--atomic` CLI 参数

**GPU API 模式覆盖:**
- CUDA: `cudaMalloc`, `cudaMemcpy`, `cudaFree`, `cudaStreamSync`, `atomicAdd`
- CUB: `cub::BlockScan`, `cub::DeviceScan`, `cub::DeviceReduce`, `cub::DeviceRadixSort`
- CUTLASS: `cutlass::*`, `cutlass_gemm`
- WMMA: `wmma::load_matrix_sync`, `wmma::store_matrix_sync`, `wmma::mma_sync`

**NPU API 模式覆盖:**
- ACLNN: `aclnnMatmul`, `aclnnConv2d`, `aclnnAdd`, `aclnnRelu`, `aclnnSoftmax`
- AscendC: `Load2D`, `Store2D`, `Matmul`, `SyncAll`, `LocalTensor`
- 异步: `EXEC_NPU_CMD(aclnn...)`

**原子分析 Prompt:**
```
分析以下原子 API 对的等价关系：
GPU API: cub::BlockScan
NPU API: asynchronous_complete_cumsum_npu
代码片段: [提取的代码上下文]

输出 JSON: {"is_equivalent": true/false, "npu_equivalent": "API名",
 "equivalence_level": "exact/similar/conceptual", "confidence": 0.0-1.0,
 "adaptation_notes": "..."}
```

**Example 映射结果:**
- `cub::BlockScan` → `async_cumsum_npu`
- `atomicAdd` → `atomic_add`
- `__syncthreads` → `SyncAll`
- `wmma::mma_sync` → `Matmul` (Tensor Core)

**验证:**
- MCP 工具 `query_cross_platform` 可查询原子映射 ✅
- E2E 测试验证 `__syncthreads` → `SyncAll` 映射查询 ✅

---

## System-Wide Impact

- **Interaction graph**: 新增 `analyze-mapping` CLI 命令；`MapperEngine` 已扩展支持查询 `cross_platform_mappings` collection；`predefined_mappings.py` 已删除
- **Error propagation**: LLM 调用失败应降级并报告错误（写入 stderr），不阻塞主流程；存储层失败应回滚并抛出异常
- **Integration coverage**: CLI → GPUNPUAnalysisEngine → GPUStorage 的完整链路需端到端测试

## Risks & Dependencies

- **LLM 成本**: 分析大量文件 token 消耗高
  - **缓解**: 用户在配置中指定分析路径；单次调用最多50个文件对；每个文件对最多2000 tokens
- **Prompt 调优**: 初期可能需要多次迭代
  - **缓解**: Unit 3 已提供初始 prompt 设计方向，后续在 Unit 5 测试阶段迭代优化
- **JSON 解析失败**: LLM 输出可能包含非标准 JSON
  - **缓解**: 重试3次 (exponential backoff 1s/2s/4s)，仍失败则 confidence=0.0 存入向量库
- **存储回滚**: ChromaDB + Redis 双存储可能失败
  - **缓解**: 先写 Redis 再写 ChromaDB，失败时删除 Redis 条目作为补偿
- **与现有 MapperEngine 的迁移**: predefined_mappings.py 已删除，MapperEngine 已改用 cross_platform_mappings
  - **缓解**: 已完成迁移验证

## Documentation / Operational Notes

- 更新相关文档说明新功能使用方法

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-17-gpu-npu-llm-discovery-requirements.md](docs/brainstorms/2026-04-17-gpu-npu-llm-discovery-requirements.md)
- Related code: `src/asc_ops/mapper/engine.py`, `src/asc_ops/gpu_collector/storage.py`, `src/asc_ops/storage/collections.py`
- **重大变更**: 用户决策 - 删除 `predefined_mappings.py` 依赖，所有映射从代码仓 LLM 分析获取 ✅ 已完成
