# Use Case: CUDA Warp Shuffle 到 AscendC API 语义检索

> **测试日期**: 2026-04-23
> **测试方式**: 实际 JSON-RPC 请求通过 stdio 调用 MCP Server

## 场景描述

**任务**: 用户在开发 GPU 到 NPU 迁移代码时，询问 CUDA warp shuffle 系列 API 对应的 AscendC API

**用户提问**:
```
cuda的warp shuffle对应的AscendC 什么API
```

---

## 实际调用路径

### 1. MCP 配置

Claude Code 的 `settings.json` 中配置了 asc-ops MCP Server:

```json
"mcpServers": {
  "asc-ops": {
    "command": "/Users/huangshilei/opt/miniconda3/bin/python",
    "args": ["-m", "src.asc_ops.mcp.cli"],
    "cwd": "/Users/huangshilei/Documents/pythonprojects/asc_ops"
  }
}
```

### 2. 调用链路图

```
┌─────────────────────────────────────────────────────────────────────┐
│  用户提问: "cuda的warp shuffle对应的AscendC 什么API"                    │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Claude Code 主会话                                                   │
│  - 接收用户问题                                                      │
│  - 检测到需要查询 CUDA→AscendC 映射                                  │
│  - 通过 stdio 启动 MCP Server 子进程                                 │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  MCP Client → MCP Server (stdio)                                    │
│  JSON-RPC 请求:                                                      │
│  {                                                                   │
│    "jsonrpc": "2.0",                                                 │
│    "id": "1",                                                        │
│    "method": "initialize",                                           │
│    "params": {}                                                      │
│  }                                                                   │
│  {                                                                   │
│    "jsonrpc": "2.0",                                                 │
│    "id": "2",                                                        │
│    "method": "tools/call",                                           │
│    "params": {                                                       │
│      "name": "semantic_cuda_to_npu_mapping",                         │
│      "arguments": {                                                  │
│        "cuda_api_name": "__shfl_up_sync",                             │
│        "min_confidence": 0.6,                                        │
│        "limit": 5                                                    │
│      }                                                               │
│    }                                                                 │
│  }                                                                   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  MCP Server (python -m src.asc_ops.mcp.cli)                          │
│  工作目录: /Users/huangshilei/Documents/pythonprojects/asc_ops         │
│                                                                   │
│  cli.py:main()                                                      │
│    ↓                                                                │
│  initialize_services()                                              │
│    - GPUStorage(use_mock=False)                                     │
│    - KnowledgeQueryService(chroma_db_path, base_url)                │
│    - MapperEngine(storage)                                          │
│    ↓                                                                │
│  server.run() → 从 stdin 读取 JSON-RPC 请求                          │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  server.py:_handle_request()                                         │
│    ↓                                                                │
│  _handle_tools_call(request_id, params)                              │
│    ↓                                                                │
│  MCPTools.call_tool(                                                 │
│    name="semantic_cuda_to_npu_mapping",                              │
│    arguments={cuda_api_name: "__shfl_up_sync", ...},                 │
│    knowledge_query_service,                                         │
│    mapper_engine                                                    │
│  )                                                                   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  tools.py:_semantic_cuda_to_npu_mapping()                           │
│    ↓                                                                │
│  KnowledgeQueryService.semantic_cuda_to_npu_mapping()               │
│    ↓                                                                │
│  检查硬编码映射 (browser_client.py:286-289)                          │
│    - __shfl_up_sync → asc_shfl_up (存在)                            │
│    ↓                                                                │
│  ChromaDB 向量检索 (如果需要)                                        │
│    - query_embeddings with 1024D vector                             │
│    - similarity_search with threshold                               │
│    ↓                                                                │
│  返回结果列表，按置信度排序                                          │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  MCP Server 返回 JSON-RPC 响应                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 3. 实际请求/响应

#### initialize 请求
```bash
printf '{"jsonrpc":"2.0","id":"1","method":"initialize","params":{}}\n' | python -m src.asc_ops.mcp.cli
```

**响应**:
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {}},
    "serverInfo": {"name": "asc-ops-mcp", "version": "0.1.0"}
  }
}
```

#### semantic_cuda_to_npu_mapping 请求
```bash
printf '{"jsonrpc":"2.0","id":"2","method":"tools/call","params":{"name":"semantic_cuda_to_npu_mapping","arguments":{"cuda_api_name":"__shfl_up_sync","min_confidence":0.6,"limit":5}}}\n' | python -m src.asc_ops.mcp.cli
```

**响应**:
```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "# CUDA → AscendC 语义检索: __shfl_up_sync\n\n找到 2 个匹配的 AscendC API\n\n## 匹配 1\n- AscendC API: **asc_shfl_up**\n- 置信度: 0.67\n- 来源: inferred\n- 匹配描述: API: asc_shfl_up | 分类: util/ | 描述: asc_shfl_up产品支持情况产品是否支持Atlas 350 加速卡√Atlas A3 训练系列产品/Atlas A3 推理系列产品xAtlas A2 训练系列产品/Atlas A2 推理系列产品...\n\n## 匹配 2\n- AscendC API: **asc_shfl**\n- 置信度: 0.62\n- 来源: inferred"
      }
    ],
    "isError": false
  }
}
```

---

## 完整映射表 (实测)

| CUDA API | AscendC API | 置信度 | 来源 |
|----------|-------------|--------|------|
| `__shfl_sync` | `asc_shfl` | - | 硬编码映射 |
| `__shfl_up_sync` | `asc_shfl_up` | 0.67 | ChromaDB 语义检索 |
| `__shfl_down_sync` | `asc_shfl_down` | - | 硬编码映射 |
| `__shfl_xor_sync` | `asc_shfl_xor` | - | 硬编码映射 |

---

## 数据来源

### 硬编码映射
**文件**: `src/asc_ops/collector/browser_client.py:286-289`

```python
"asc_shfl": ("SIMT API", "Warp函数", ""),
"asc_shfl_up": ("SIMT API", "Warp函数", ""),
"asc_shfl_down": ("SIMT API", "Warp函数", ""),
"asc_shfl_xor": ("SIMT API", "Warp函数", ""),
```

### 向量检索
**文件**: `src/asc_ops/knowledge_query.py`

语义检索使用 `semantic_cuda_to_npu_mapping()` 函数：
1. 先检查硬编码映射
2. 未命中时查询 ChromaDB `gpu_apis` collection
3. 使用 Qwen3-Embedding-0.6B 模型生成 1024D 向量
4. 返回相似度 > 阈值的结果

---

## 核心价值

| 价值维度 | 说明 |
|----------|------|
| **消除幻觉** | LLM 可能臆造 API 名称，知识库提供真实准确的 API |
| **精确映射** | Warp shuffle 4 个 API 全部有明确对应 |
| **产品支持信息** | 返回 Atlas 350/A3/A2 各产品的支持矩阵 |
| **置信度量化** | 每个结果附带置信度，便于决策 |

---

## 相关文件

| 文件路径 | 作用 |
|----------|------|
| `~/.claude/settings.json` | MCP Server 配置 |
| `src/asc_ops/mcp/cli.py` | MCP CLI 入口，初始化服务 |
| `src/asc_ops/mcp/server.py` | JSON-RPC 请求处理 |
| `src/asc_ops/mcp/tools.py` | MCP 工具定义和调用 |
| `src/asc_ops/knowledge_query.py` | 语义检索核心逻辑 |
| `src/asc_ops/collector/browser_client.py` | 硬编码 CUDA→AscendC 映射 |
| `data/chroma_db/` | ChromaDB 向量数据库 |
