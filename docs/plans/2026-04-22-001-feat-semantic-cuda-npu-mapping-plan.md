# CUDA API → AscendC API 语义检索实现

**文档版本**: v1.1
**创建日期**: 2026-04-22
**状态**: active
**origin**: docs/brainstorms/2026-04-22-cuda-ascendc-semantic-mapping-requirements.md

---

## Overview

实现"给定任意 CUDA API，语义检索返回最相似的 AscendC API 及置信度"的能力。

**核心原则：LLM 分析在数据准备阶段离线完成，查询阶段只有 ChromaDB 向量检索，MCP 工具零 LLM 调用。**

---

## Problem Frame

用户查询"某个 CUDA API 对应的 AscendC API 是什么"时，当前知识库无法回答。`cross_platform_mappings` 只有 57 条映射，覆盖极少。需要实现语义检索能力。

---

## Requirements Trace

- **R1**: GPU API 知识采集 — 全量 CUDA API 采集 + LLM 语义分析 + 入库
- **R2**: 双向语义检索 — 查询阶段零 LLM，基于 gpu_apis description embedding 检索 ascend_apis
- **R3**: 混合结果返回 — 精确映射优先，语义检索置信度 ≥0.75
- **R4**: MCP 工具扩展 — `semantic_cuda_to_npu_mapping` 工具

---

## Scope Boundaries

**In Scope:**
- 全量 CUDA API 采集（1000+ API）
- LLM 分批处理语义分析（离线数据准备）
- gpu_apis collection 构建（带 embedding 向量）
- MCP 工具语义检索（查询阶段零 LLM）

**Out of Scope:**
- 自动代码转换
- 在线 LLM 推理（MCP 查询路径）

---

## Key Technical Decisions

- **统一抽象存储与检索**: gpu_apis 和 ascend_apis 共用 BaseSemanticStore 和 BaseSemanticSearcher，简化架构
- **gpu_apis collection 带 embedding**：GPU API 信息存入会同时生成 embedding 向量，支持向量检索
- **精确匹配优先**：先查 cross_platform_mappings，未命中再走语义检索
- **置信度阈值 0.75**：distance < 0.25 → confidence ≥ 0.75

---

## Architecture

### 数据流

```
离线数据准备（一次性）：
    NVIDIA CUDA 文档
         │
         ▼
    doc_scraper.py (浏览器自动化/文档解析)
         │
         ▼
    CUDA API 列表 (名称、签名、分类)
         │
         ▼
    LLM 分批分析语义（每批 50-100 个 API）
         │
         ▼
    QwenEmbedder.encode() → 生成向量
         │
         ▼
    GPUStorage.store_api_with_embedding() → 存入 gpu_apis collection
    ──────────────────────
    {
      id: "cuda-api-xxx",
      api_name: "cudaMalloc",
      full_signature: "cudaError_t cudaMalloc(void** devPtr, size_t size)",
      category: "memory-management",
      description: "Allocate device memory on GPU, equivalent to device-side malloc",
      embedding: [0.123, ...],  ← 1024 维
      metadata: {...}
    }

在线 MCP 查询：
    用户: "cudaMalloc 对应 AscendC 什么 API"
         │
         ▼
    Step 1: 精确匹配 cross_platform_mappings
         │  → 命中？返回精确映射
         │
         ▼ (未命中)
    Step 2: 查 gpu_apis 获取 description
         │  api_name = "cudaMalloc"
         │  → 返回 GPUAPIInfo (含 description + embedding)
         │
         ▼
    Step 3: 用 gpu_apis 的 description embedding 查 ascend_apis
         │  → 返回 Top-N NPU API + cosine distance
         │
         ▼
    Step 4: 置信度过滤
         │  distance < 0.25 → confidence ≥ 0.75 → 返回
         │  distance ≥ 0.25 → 返回空
         │
         ▼
    返回结果 (npu_api, confidence, matched_description)
```

### Distance → Confidence 转换公式

```
confidence = max(0, 1 - distance / 0.25)
```

- distance = 0.0 → confidence = 1.0
- distance = 0.25 → confidence = 0.75
- distance ≥ 0.25 → confidence < 0.75 → 视为"未找到"

---

## Implementation Units

- [ ] **Unit 1: gpu_apis Collection 构建与存储**

**Goal:** 构建带 embedding 向量的 gpu_apis collection

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `src/asc_ops/gpu_collector/storage.py` — 新增 `store_api_with_embedding()` 和 `get_api_by_name()` 方法
- Modify: `src/asc_ops/gpu_collector/models.py` — GPUAPIInfo 新增 `description_embedding` 字段
- Modify: `src/asc_ops/storage/collections.py` — 新增 `GPU_APIS` collection 类型
- Test: `tests/unit/gpu_collector/test_cuda_api_store.py`

**Approach:**
1. 在 `GPUAPIInfo` 新增 `description_embedding: Optional[List[float]]` 字段
2. 在 `CollectionType` 新增 `GPU_APIS = "gpu_apis"`
3. 在 `GPUStorage` 新增 `store_api_with_embedding(api: GPUAPIInfo, embedder)` 方法
4. 在 `GPUStorage` 新增 `get_api_by_name(api_name: str)` 方法用于精确查找
5. 调用 `embedder.encode(description)` 生成向量（如果没有 embedding）
6. ChromaDB upsert 支持传入 embeddings 参数
7. 验证入库后可通过 `get_api_by_name()` 精确查到

**Patterns to follow:**
- `KnowledgeQueryService._query_api_semantic()` — embedding 生成逻辑
- `APIStorage.store_api()` — GPUAPIInfo 存储逻辑

**Test scenarios:**
- warp shuffle API 入库后能通过 `get_api_by_name()` 精确查到
- 入库 API 的 embedding 向量维度正确（1024）

**Verification:**
- `python -c "from asc_ops.gpu_collector.storage import GPUStorage; ..."` 验证存储

---

- [ ] **Unit 2: CUDA API 数据采集与语义分析入库流程**

**Goal:** 完成全量 CUDA API 的采集 + LLM 分析 + 入库

**Requirements:** R1

**Dependencies:** Unit 1

**Files:**
- Create: `src/asc_ops/gpu_collector/doc_scraper.py` — CUDA API 文档采集
- Create: `src/asc_ops/gpu_collector/llm_semantic_analyzer.py` — LLM 语义分析
- Create: `scripts/batch_import_cuda_apis.py` — 批量入库脚本
- Test: `tests/unit/gpu_collector/test_doc_scraper.py`

**Approach:**
1. **doc_scraper.py**：从 NVIDIA 文档（CUDA C++ Programming Guide、CUDA Runtime API 等）抓取 API 定义
   - 使用浏览器自动化或离线文档解析
   - 输出：List[GPUAPIInfo]
2. **llm_semantic_analyzer.py**：LLM 分批分析语义
   - 每批 50-100 个 API
   - Prompt 模板化输出
   - 输出：description 字段填充
3. **batch_import_cuda_apis.py**：批量入库
   - 调用 `GPUStorage.store_api_with_embedding()`
   - 支持断点续传

**Patterns to follow:**
- `GPUCollector` 已有采集器模式
- `LLMAnalyzer` 已有 LLM 调用模式

**Test scenarios:**
- cudaMalloc 采集后 description 正确
- 分批处理后数据一致性

**Verification:**
- ChromaDB `gpu_apis` collection 条目数 > 0
- 抽样验证 description 非空

---

- [ ] **Unit 3: KnowledgeQueryService 语义映射查询方法**

**Goal:** 实现查询阶段零 LLM 调用的语义检索

**Requirements:** R2, R3

**Dependencies:** None

**Files:**
- Modify: `src/asc_ops/knowledge_query.py`
- Test: `tests/unit/test_knowledge_query.py`

**Approach:**
```python
async def semantic_cuda_to_npu_mapping(
    self,
    cuda_api_name: str,
    min_confidence: float = 0.75,
    limit: int = 5,
) -> List[MappingResult]:
    # Step 1: 精确匹配 cross_platform_mappings
    exact_match = self._mapper_engine.find_mapping(cuda_api_name)
    if exact_match:
        return [MappingResult.from_cross_platform_mapping(exact_match)]

    # Step 2: 查 gpu_apis 获取 description 和 embedding
    gpu_api = self._gpu_storage.get_api_by_name(cuda_api_name)
    if not gpu_api:
        return []

    # Step 3: 用 gpu_apis 的 description embedding 查 ascend_apis
    # description_embedding 已在 Step 2 从 ChromaDB 获取
    results = self._chroma.query(
        collection_name="ascend_apis",
        query_embeddings=[gpu_api.description_embedding],
        n_results=limit,
    )

    # Step 4: 置信度过滤
    mapping_results = []
    for i, distance in enumerate(results["distances"][0]):
        confidence = max(0, 1 - distance / 0.25)
        if confidence >= min_confidence:
            mapping_results.append(MappingResult(
                npu_api=results["metadatas"][0][i]["api_name"],
                confidence=confidence,
                matched_description=results["documents"][0][i],
                source="inferred",  # 区分精确映射和语义推断
            ))
    return mapping_results
```

**Patterns to follow:**
- `KnowledgeQueryService.query_api()` — ChromaDB 查询模式
- `MapperEngine.find_mapping()` — 精确匹配模式

**Test scenarios:**
- cudaMalloc 查询返回 AscendC 内存分配相关 API
- 不存在的 API 返回空列表

**Verification:**
- `python -c "from asc_ops.knowledge_query import KnowledgeQueryService; ..."` 能正常调用

---

- [ ] **Unit 4: MCP 工具 semantic_cuda_to_npu_mapping**

**Goal:** 注册新 MCP 工具供 Agent 调用

**Requirements:** R4

**Dependencies:** Unit 3

**Files:**
- Modify: `src/asc_ops/mcp/tools.py`
- Test: `tests/unit/test_mcp_tools.py`

**Approach:**
- 在 `MCPTools` 添加 `_semantic_cuda_to_npu_mapping()` 方法
- 在 `call_tool()` 添加 `semantic_cuda_to_npu_mapping` 分支
- 输入：`cuda_api_name: str`；输出：`MappingResult` 列表

**Patterns to follow:**
- `MCPTools._query_cross_platform()` — 工具注册模式

**Test scenarios:**
- MCP 工具调用 `semantic_cuda_to_npu_mapping` 参数正确返回结果

**Verification:**
- MCP 服务器能正确响应工具调用请求

---

- [ ] **Unit 5: 集成测试与端到端验证**

**Goal:** 验证完整的语义检索流程

**Requirements:** Success Criteria 全量

**Dependencies:** Unit 1, Unit 2, Unit 3, Unit 4

**Files:**
- Create: `tests/integration/test_semantic_mapping.py`

**Approach:**
- 端到端测试：从 MCP 工具调用 → KnowledgeQueryService → ChromaDB 查询 → 返回结果
- 验证 warp shuffle API 能返回合理的 AscendC API 映射

**Test scenarios:**
- `semantic_cuda_to_npu_mapping("__shfl_up_sync")` 返回 `WarpShift` 或类似 API
- `semantic_cuda_to_npu_mapping("cudaMalloc")` 返回 AscendC 内存分配 API
- `semantic_cuda_to_npu_mapping("__inexistent_api__")` 返回空

**Verification:**
- `pytest tests/integration/test_semantic_mapping.py -v` 通过

---

## System-Wide Impact

- **MCP 工具新增**: `MCPTools` 新增工具暴露，Agent 调用方式不变
- **KnowledgeQueryService**: 新增方法不影响现有 `query_api()` 等方法
- **ChromaDB**: 新增 `gpu_apis` collection，带 embedding 索引
- **GPUStorage**: 新增 `store_api_with_embedding()` 方法

---

## Data Model

### GPUAPIInfo (已有，新增字段)

```python
@dataclass
class GPUAPIInfo:
    api_id: str
    api_name: str
    platform: GPUPlatform
    full_signature: str = ""
    description: str = ""           # LLM 分析后填充
    description_embedding: List[float] = None  # 新增：语义描述向量
    parameters: List[str] = field(default_factory=list)
    return_type: str = ""
    category: str = ""
    subcategory: str = ""
```

### MappingResult (新增)

```python
@dataclass
class MappingResult:
    npu_api: str
    confidence: float
    matched_description: str
    source: str = "exact"  # "exact" | "inferred"
```

---

## Batch Import 流程

```
1. doc_scraper.py 采集 CUDA API 列表
   └── 输出: List[GPUAPIInfo] (description 待填充)

2. llm_semantic_analyzer.py 分批处理
   └── 每批 50-100 个 API
   └── Prompt: "为以下 CUDA API 生成语义描述，用于检索对应的 NPU AscendC API..."
   └── 输出: description 填充后的 GPUAPIInfo

3. batch_import_cuda_apis.py 入库
   └── 调用 GPUStorage.store_api_with_embedding()
   └── 支持 --resume 断点续传
   └── 支持 --batch-size 控制每批大小
```

---

## Risks & Dependencies

- **风险**: ascend_apis (1102 条) 可能没有覆盖足够的 NPU API → 需要验证检索结果覆盖率
- **依赖**: doc_scraper 能稳定抓取 CUDA 文档 → NVIDIA 文档 URL 结构需验证
- **依赖**: LLM 语义分析质量 → Prompt 模板需精心设计

---

## Documentation / Operational Notes

- 更新 `docs/getting-started/installation.md` 说明新的 MCP 工具
- 更新 `docs/plans/2026-04-10-001-feat-ascendc-knowledge-base-implementation-plan.md` 记录新增能力
- 批量入库脚本使用文档

---

## Next Steps

- `/ce:work` 开始实现 Unit 1-5
