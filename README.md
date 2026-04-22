# AscendC Operator Knowledge Base

**昇腾AscendC算子知识库** - 为Coding Agent提供昇腾NPU算子开发知识支持

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

---

## 项目概述

AscendC Operator Knowledge Base (asc_ops) 是一个面向Coding Agent的昇腾AscendC算子知识检索系统。

### 核心价值

- **开发参考**: Agent开发新昇腾算子时，可查询API使用案例、优化方案、历史bug修复经验
- **问题排查**: Agent遇到昇腾算子问题时，可搜索相似问题的解决方案
- **跨平台适配**: Agent可将GPU算子实现迁移到昇腾NPU时，参考GPU实现知识和API映射

### 核心功能

| 功能 | 说明 |
|------|------|
| **AscendC API知识库** | 1120 官方API，100% nav_path覆盖，覆盖Vec/Matmul/Tensor等核心接口 |
| **NPU算子知识** | 1203+ Bug修复经验 + 13+ 优化方案 |
| **GPU→NPU适配** | 57+ 跨平台API映射 (CUDA/CUB/CUTLASS → AscendC) |
| **MCP接口** | 支持Claude Code/CoPilot/Cursor等MCP兼容Agent |

### 支持的Coding Agent

- Claude Code (通过MCP)
- GitHub CoPilot (通过MCP)
- Cursor (通过MCP)
- 通义灵码 (通过MCP)
- 其他MCP兼容Agent

---

## 与AscendC开发Skill的对比

### 核心定位差异

| 维度 | AscendC开发Skill | asc_ops MCP知识库 |
|------|------------------|-------------------|
| **本质** | 单点工具/指令集 | **知识检索系统** |
| **交互方式** | 被动响应指令 | **主动检索** |
| **知识规模** | Skill本身的指令容量 | **2400+条知识** (1120 API + 1203 Bug + 57映射) |
| **检索能力** | 固定指令路径 | **混合检索** (向量+BM25+置信度) |

### asc_ops的独特/不可替代优势

#### 1. 动态知识库 vs 静态Skill
```
Skill: 编译时固定的指令集 → 知识上限受限于代码量
MCP知识库: 运行时可扩展 → 持续吸收新经验
```

#### 2. 置信度感知排序层
三权重融合: **向量 0.6 + BM25 0.3 + 置信度 0.1**

效果：返回结果按置信度排序，**避免低质量知识误导Agent决策**

#### 3. GPU→NPU跨平台映射
Skill只能教你"**怎么写AscendC**"，asc_ops教你"**GPU代码怎么改写成NPU代码**"。

| 场景 | 无MCP | 有MCP |
|------|-------|-------|
| CUB BlockScan | 需试错 | `aclnnAsynchronousCompleteCumsum` (0.95) |
| Gather API | `aclnnGather` (猜测) | `aclnnInvertPermute` (0.98, exact) |

#### 4. 历史Bug推理能力
```python
# 根据症状搜索可能原因
symptom: "Matmul crash"
→ 返回 Bug ID + 置信度 + 根因 + 建议修复 + 检查项
```

这不是文档查询，而是**从历史Bug知识中推理可能原因**。

### 什么场景下Skill仍有价值？

| 场景 | 说明 |
|------|------|
| 简单指令执行 | 如"帮我生成Matmul核函数模板" |
| 官方文档查询 | 昇腾官方API签名的精确参考 |
| 实时编码辅助 | IDE内联补全 |

### 总结

asc_ops的核心不可替代性：

| 优势 | 说明 |
|------|------|
| **跨平台迁移** | GPU CUDA/CUB→NPU AscendC的完整映射知识 |
| **历史Bug推理** | 1200+真实Bug的根因分析 |
| **置信度排序** | 避免低质量知识误导Agent决策 |
| **持续扩展** | 可接入新仓库、新经验 |

> **一句话总结**：Skill教你"怎么用API"，asc_ops教你"别人踩过什么坑"和"GPU代码怎么改写成NPU代码"。两者是互补关系，但知识库的**推理能力**和**跨平台映射**是Skill无法替代的。

### 效果验证

实际测试表明：使用 MCP 知识库查询 vs 无知识库搜索，LLM 回答质量差异显著：

| 场景 | 无 MCP | 有 MCP |
|------|--------|--------|
| GPU→NPU 映射 | `aclnnGather` (猜测) | `aclnnInvertPermute` (0.98, exact) |
| CUB BlockScan | 需试错 | `aclnnAsynchronousCompleteCumsum` (0.95) |
| Bug 根因 | 猜测可能原因 | 精确定位 SocVersion→NpuArch |
| API 概念 | 可能混淆 | 权威解释 TPosition/LocalTensor |

详见 [使用案例](docs/use_cases/):
- [Sparse Ops 迁移](docs/use_cases/case-study-gpu-to-npu-migration.md)
- [CUB BlockScan 迁移](docs/use_cases/usecase-gpu-npu-block-scan-migration.md)
- [Matmul Bug 查询](docs/use_cases/usecase-bug-knowledge-matmul.md)
- [API 知识查询](docs/use_cases/usecase-api-knowledge-tensor.md)
- [AtomicMax API 查询](docs/use_cases/usecase-atomicmax-api-query.md)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Coding Agent                                  │
│  (Claude Code / CoPilot / Cursor / 通义灵码)                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │ MCP协议 (stdio)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Server (asc_ops)                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────────┐      ┌───────────────────┐               │
│  │   ChromaDB        │      │   Redis           │               │
│  │   (向量存储)       │      │   (KV存储)        │               │
│  │                   │      │                   │               │
│  │  • API语义向量     │      │  • 算子属性       │               │
│  │  • Bug知识向量     │      │  • PR元数据       │               │
│  │  • GPU-NPU映射    │      │  • 质量评分       │               │
│  └───────────────────┘      └───────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 安装部署

### 环境要求

- Python 3.9+
- Redis 6.0+ (开发模式可用mock)
- ChromaDB (本地向量存储)
- Git

### 步骤 1: 克隆项目

```bash
git clone https://github.com/SimmerChan/asc_ops.git
cd asc_ops
```

### 步骤 2: 安装依赖

```bash
# 创建虚拟环境 (推荐)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 步骤 3: 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 填入必要配置
nano .env  # 或使用你喜欢的编辑器
```

**关键配置项**:

```env
# ChromaDB配置
CHROMA_DB_PATH=./data/chroma_db

# Redis配置 (开发模式可留空)
REDIS_HOST=localhost
REDIS_PORT=6379

# LLM配置 (用于知识抽取)
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_API_BASE=https://api.anthropic.com
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# 向量化模型
EMBEDDING_MODEL_PATH=/path/to/Qwen3-Embedding-0.6B
EMBEDDING_DEVICE=mps  # 或 cuda
```

### 步骤 4: 初始化数据 (可选)

项目已包含预采集的数据在 `data/` 目录：

```bash
# 数据目录结构
data/
├── chroma_db/           # 向量数据库
│   ├── cross_platform_mappings  # 57条 GPU-NPU映射
│   ├── ascend_apis            # 1120个 API (100% nav_path)
│   ├── bug_fixes              # 1203个 Bug知识
│   └── optimizations         # 13个 优化知识
└── checkpoints/             # 同步检查点
```

如需重新采集数据，参考 [docs/getting-started/collect-data.md](docs/getting-started/collect-data.md)。

### 步骤 5: 启动服务

**方式1: 启动MCP Server (推荐用于Coding Agent)**

```bash
python -m src.asc_ops.mcp.cli
```

MCP Server使用stdio协议，可直接与Claude Code等Agent集成。

**方式2: 启动FastAPI服务**

```bash
python -m src.asc_ops.server
```

服务将在 `http://localhost:8000` 启动，API文档: `http://localhost:8000/docs`

---

## 快速使用

### MCP Server 使用

启动MCP Server后，在Claude Code中配置MCP工具即可使用。

**可用MCP工具**:

| 工具 | 用途 | 示例 |
|------|------|------|
| `query_for_development` | 查询算子的Bug和优化知识 | 查询Matmul开发注意事项 |
| `query_for_troubleshooting` | 根据症状搜索可能原因 | 搜索"Matmul crash" |
| `query_api` | 查询AscendC API定义 | 查询aclnnMatmul用法 |
| `query_cross_platform` | 查询GPU→NPU API映射 | 查询cub::BlockScan对应NPU API |

### Python API 使用

```python
import asyncio
from src.asc_ops.knowledge_query import KnowledgeQueryService

async def main():
    service = KnowledgeQueryService(chroma_db_path="./data/chroma_db")

    # 查询算子开发知识
    result = await service.query_for_development(
        operator_name="Matmul",
        query_type="bug",
        limit=5
    )
    print(f"找到 {len(result.bug_fixes)} 条Bug知识")

    # 查询GPU-NPU映射
    from src.asc_ops.mapper import MapperEngine
    from src.asc_ops.gpu_collector.storage import GPUStorage

    storage = GPUStorage(use_mock=False)
    mapper = MapperEngine(storage=storage)

    mapping = mapper.find_mapping("cub::DeviceScan", "cuda")
    print(f"GPU→NPU映射: {mapping.gpu_api} → {mapping.npu_api}")

asyncio.run(main())
```

### MCP 工具依赖说明

| 工具 | ChromaDB 依赖 | Redis 依赖 | Embedding 依赖 |
|------|-------------|-----------|---------------|
| `query_for_development` | ✅ 精确查询 | ✅ 引用追踪/置信度排序 | ❌ 不需要 |
| `query_for_troubleshooting` | ✅ 向量查询 | ✅ 引用追踪/置信度排序 | ✅ 需要 |
| `query_api` (精确) | ✅ 精确匹配 | ❌ 不需要 | ❌ 不需要 |
| `query_api` (语义) | ✅ 向量查询 | ❌ 不需要 | ✅ 需要 |
| `query_cross_platform` | ❌ SQLite | ❌ 不需要 | ❌ 不需要 |

**说明**：
- **ChromaDB**: 向量数据库，存储 API 知识库
- **Redis**: KV 存储，用于引用计数追踪和置信度感知排序
- **Embedding**: 向量化模型，用于语义搜索

**Embedding 模型配置**：

```env
# 方式1: Qwen3-Embedding (默认, Apple Silicon MPS)
EMBEDDING_EMBEDDER_TYPE=qwen
EMBEDDING_DEVICE=mps  # 或 cuda/cpu

# 方式2: Sentence Transformers
EMBEDDING_EMBEDDER_TYPE=sentence_transformers
EMBEDDING_MODEL_NAME=Qwen/Qwen3-Embedding-0.6B

# 方式3: Mock (仅精确查询, 无语义搜索)
EMBEDDING_EMBEDDER_TYPE=mock
```

**无 Embedding 模型时的行为**：
- 精确查询 (`api_name=`) 正常工作
- 语义搜索 (`semantic_query=`) 返回空结果 + 警告
- 建议 Agent 改用精确查询

### CLI 工具

```bash
# 分析GPU-NPU代码对
python -m src.asc_ops.cli.analyze analyze-mapping \
    --config peer_repos.yaml \
    --name fbgemm-sparse-ops \
    --atomic

# 同步算子数据
python -m src.asc_ops.cli.collect sync \
    --source github \
    --repos ops-nn,ops-math
```

---

## 数据规模

| 知识类型 | 数量 | 来源 | 状态 |
|----------|------|------|------|
| AscendC API | 1120 | 昇腾官方文档 | ✅ 100% nav_path |
| NPU Bug修复 | 1203+ | ops-nn, ops-math等6仓 | ✅ |
| NPU优化方案 | 13+ | ops-nn, ops-math等6仓 | ✅ |
| GPU→NPU映射 | 57+ | FBGEMM, cuBLAS, CUTLASS等 | ✅ |

---

## 项目结构

```
asc_ops/
├── README.md                    # 本文件
├── requirements.txt              # Python依赖
├── .env.example                 # 环境变量模板
├── peer_repos.yaml              # GPU-NPU对等仓库配置
│
├── src/asc_ops/                 # 主包
│   ├── app.py                   # FastAPI应用入口
│   ├── server.py                # API服务器
│   ├── config.py                # 配置管理
│   │
│   ├── mcp/                     # MCP Server
│   │   ├── cli.py               # MCP CLI入口
│   │   ├── server.py            # MCP协议服务器
│   │   └── tools.py             # MCP工具定义
│   │
│   ├── storage/                 # 存储层
│   │   ├── chroma_client.py     # ChromaDB客户端
│   │   ├── redis_client.py      # Redis客户端
│   │   └── collections.py        # Collection定义
│   │
│   ├── knowledge_query.py        # 知识查询服务
│   ├── mapper/                  # GPU-NPU映射
│   │   ├── engine.py            # 映射引擎
│   │   ├── llm_analyzer.py      # LLM分析器
│   │   └── atomic_parser.py      # 原子API解析
│   │
│   ├── ranker/                  # 排序层
│   │   ├── fusion.py            # 结果融合
│   │   ├── confidence.py         # 置信度引擎
│   │   └── scoring/             # 评分模块
│   │
│   ├── extractor/               # 知识抽取
│   ├── collector/               # 数据采集
│   ├── gpu_collector/           # GPU知识采集
│   ├── quality/                 # 质量评分
│   └── llm/                     # LLM集成
│
├── tests/                       # 测试
│   ├── unit/                    # 单元测试
│   ├── integration/             # 集成测试
│   └── e2e/                    # 端到端测试
│
└── docs/                       # 文档
    ├── plans/                   # 开发计划
    ├── brainstorms/             # 需求文档
    └── use_cases/              # 使用案例
```

---

## 开发状态

### MVP完成状态 ✅

| 阶段 | 功能 | 状态 | 完成日期 |
|------|------|------|----------|
| Phase 1 | 双存储架构 (ChromaDB + Redis) | ✅ 已完成 | 2026-04-10 |
| Phase 2 | 原子化知识图谱 | ✅ 已完成 | 2026-04-10 |
| Phase 3 | 置信度感知排序层 | ✅ 已完成 | 2026-04-11 |
| Phase 4 | 知识质量评分体系 | ✅ 已完成 | 2026-04-11 |
| Phase 5 | Bug/优化知识抽取 | ✅ 已完成 | 2026-04-12 |
| GPU-NPU LLM Discovery | GPU→NPU自动映射分析 | ✅ 已完成 | 2026-04-18 |
| API nav_path | 342个API导航路径补全 | ✅ 已完成 | 2026-04-19 |

### 核心模块

| 模块 | 路径 | 说明 |
|------|------|------|
| MCP Server | `src/asc_ops/mcp/` | Agent集成接口 |
| 知识存储 | `src/asc_ops/storage/` | ChromaDB + Redis |
| 知识查询 | `src/asc_ops/knowledge_query.py` | 统一查询服务 |
| GPU-NPU映射 | `src/asc_ops/mapper/` | 跨平台映射 |
| 置信度排序 | `src/asc_ops/ranker/` | Authority × Recency × Accuracy |

### 测试覆盖

- **单元测试**: 600+ 测试用例
- **集成测试**: 端到端测试覆盖
- **MCP测试**: 40个测试

---

## 相关文档

- [开发计划](docs/plans/) - 详细实施计划
- [GPU-NPU映射分析](memory/fbgemm-sparse-ops-analysis.md) - FBGEMM稀疏算子映射
- [使用案例](docs/use_cases/) - MCP工具效果对比实测

---

## 贡献指南

欢迎提交Issue和Pull Request！

---

## License

Apache License 2.0

**Author**: SimmerChan
**Version**: 1.0.0 (MVP完成)
