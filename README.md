# AscendC Operator Knowledge Base

**昇腾AscendC算子知识库** - 为Coding Agent提供昇腾NPU算子开发知识支持

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
| **AscendC API知识库** | 1786+官方API，覆盖Vec/Matmul/Tensor等核心接口 |
| **NPU算子知识** | 从6个昇腾算子仓采集的优化措施、bug修复方案 |
| **GPU→NPU适配** | CUDA算子知识采集 + 跨平台API映射 |
| **Agent集成** | MCP接口，支持Claude Code/CoPilot/Cursor等Agent框架 |

### 支持的Coding Agent

- Claude Code
- GitHub CoPilot
- Cursor
- 通义灵码
- 其他MCP兼容Agent

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Coding Agent                                  │
│  (Claude Code / CoPilot / Cursor / 通义灵码)                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │ MCP协议
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    知识查询服务 (asc_ops)                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────────┐      ┌───────────────────┐               │
│  │   ChromaDB        │      │   Redis           │               │
│  │   (向量存储)       │      │   (KV存储)        │               │
│  │                   │      │                   │               │
│  │  • API语义向量     │      │  • 算子属性       │               │
│  │  • 算子知识向量    │      │  • PR元数据       │               │
│  │  • Bug知识向量     │      │  • 质量评分       │               │
│  └───────────────────┘      └───────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 环境要求

- Python 3.10+
- Redis 6.0+ (可选，本地开发可用模拟)
- Git

### 安装

```bash
# 克隆项目
git clone https://github.com/your-org/asc_ops.git
cd asc_ops

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑.env填入必要配置
```

### 启动服务

```bash
# 方式1: 直接运行（使用ChromaDB嵌入式模式）
python -m asc_ops.server

# 方式2: Docker部署（见 docs/deployment/docker.md）
```

### 首次查询

```python
from asc_ops import KnowledgeQueryService

# 初始化服务
service = KnowledgeQueryService()

# 查询Matmul算子的bug修复经验
result = await service.query_for_troubleshooting(
    symptom="Matmul算子处理非对齐数据时crash",
    operator_name="Matmul"
)

print(result.possible_causes)
```

更多示例见 [docs/getting-started/first-query.md](docs/getting-started/first-query.md)

---

## 数据规模

| 知识类型 | 数量 | 来源 |
|----------|------|------|
| AscendC API | 1786+ | 昇腾官方文档 |
| NPU Bug修复 | 126+ (持续增长) | ops-nn, ops-math等6仓 |
| NPU优化方案 | 26+ (持续增长) | ops-nn, ops-math等6仓 |
| GPU算子知识 | 规划中 | cuBLAS, CUTLASS等 |

---

## 项目结构

```
asc_ops/
├── README.md                    # 本文件
├── docs/                        # 文档目录
│   ├── getting-started/         # 快速入门
│   ├── deployment/             # 部署指南
│   ├── api/                    # API参考
│   ├── design/                 # 设计文档
│   ├── roadmap/                # 实施路径
│   └── analysis/               # 分析报告
├── scripts/                    # 分析脚本
├── src/                        # 源代码
│   └── asc_ops/               # 主包
└── tests/                      # 测试
```

---

## 相关文档

- [快速入门](docs/getting-started/quickstart.md) - 5分钟快速上手
- [安装指南](docs/getting-started/installation.md) - 详细安装步骤
- [Coding Agent使用案例](docs/getting-started/coding-agent-usecases.md) - Agent开发调试完整案例
- [API参考](docs/api/reference.md) - 接口文档
- [设计文档](docs/design/) - 架构设计详情
- [Roadmap](docs/roadmap/) - 实施计划

---

## 贡献指南

欢迎提交Issue和Pull Request！

---

**License**: Apache 2.0
**Author**: SimmerChan
**Version**: 1.0.0 (MVP完成)

---

## 开发状态

### MVP完成状态 ✅

| 阶段 | 状态 | 完成日期 |
|------|------|----------|
| Phase 1: 双存储架构 | ✅ 已完成 | 2026-04-10 |
| Phase 2: 原子化知识图谱 | ✅ 已完成 | 2026-04-10 |
| Phase 3: 置信度感知排序层 | ✅ 已完成 | 2026-04-10 |
| Phase 4: 知识质量评分体系 | ✅ 已完成 | 2026-04-10 |
| Phase 5: Bug/优化知识设计 | ✅ 已完成 | 2026-04-11 |

### 测试覆盖

- **单元测试**: 563+ 测试用例
- **集成测试**: 端到端测试覆盖
- **总测试数**: 580 个测试

### 核心模块

| 模块 | 路径 | 说明 |
|------|------|------|
| 知识存储 | `src/asc_ops/storage/` | ChromaDB + Redis 双存储 |
| 知识抽取 | `src/asc_ops/extractor/` | API/Bug/优化知识抽取 |
| 置信度排序 | `src/asc_ops/ranker/` | Authority × Recency × Accuracy |
| 质量评分 | `src/asc_ops/quality/` | 引用追踪与反馈闭环 |
| 查询服务 | `src/asc_ops/knowledge_query.py` | 统一查询接口 |
