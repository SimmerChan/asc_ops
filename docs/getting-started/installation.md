# 安装指南

本文档详细介绍AscendC算子知识库的安装步骤。

---

## 环境要求

| 组件 | 最低版本 | 推荐版本 | 说明 |
|------|----------|----------|------|
| Python | 3.10 | 3.11 | 必须 |
| Redis | 6.0 | 7.0 | **MCP 工具必需** |
| Git | 2.30 | 最新 | 必须 |
| pip | 21.0 | 最新 | 包管理 |

### 必需组件

| 组件 | 用途 | 安装方式 |
|------|------|----------|
| Redis | MCP 工具引用追踪和置信度排序 | Docker 或 apt |
| Docker | 容器化部署 | 官方安装 |
| Docker Compose | 多容器编排 | 官方安装 |

---

## 安装步骤

### 方式一：pip安装（推荐用于开发）

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 方式二：从源码安装

```bash
# 克隆仓库
git clone https://github.com/your-org/asc_ops.git
cd asc_ops

# 安装为开发模式
pip install -e .

# 安装开发依赖
pip install -r requirements-dev.txt
```

### 方式三：Docker部署（推荐用于生产）

见 [部署指南](deployment/docker.md)

---

## 依赖说明

### 核心依赖

```
# requirements.txt
chromadb>=0.4.0          # 向量数据库
redis>=5.0.0             # KV存储
pydantic>=2.0            # 数据验证
httpx>=0.25.0            # HTTP客户端
```

### 可选依赖

```bash
# 向量化模型（用于语义嵌入）
pip install sentence-transformers>=2.2.0

# LLM支持（用于知识抽取）
pip install anthropic>=0.18.0  # 或 openai>=1.0
```

---

## 环境配置

### 1. 复制环境变量模板

```bash
cp .env.example .env
```

### 2. 编辑.env文件

```bash
# .env 文件示例

# === ChromaDB配置 ===
CHROMA_DB_PATH=./data/chroma_db

# === Redis配置（MCP 工具必需）===
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=  # 如需要

# === LLM配置（用于知识抽取）===
# 选择其中一种
ANTHROPIC_API_KEY=sk-xxx  # 或
OPENAI_API_KEY=sk-xxx

# === 向量化模型 ===
EMBEDDING_MODEL=all-MiniLM-L6-v2

# === 服务配置 ===
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
LOG_LEVEL=INFO
```

### 3. 配置说明

| 变量名 | 必填 | 说明 |
|--------|------|------|
| CHROMA_DB_PATH | 是 | ChromaDB数据目录 |
| REDIS_HOST/PORT | **是** | MCP 工具必需 |
| REDIS_DB | 否 | 默认0 |
| REDIS_PASSWORD | 否 | 无密码则留空 |
| ANTHROPIC_API_KEY | 推荐 | 用于LLM知识抽取 |
| OPENAI_API_KEY | 推荐 | 替代Anthropic的LLM选项 |
| EMBEDDING_MODEL | 是 | 向量化模型名称 |
| SERVER_PORT | 否 | 默认8000 |

> **注意**: Redis 是 MCP 工具正常运行的必要依赖，用于引用计数追踪和置信度感知排序。缺少 Redis 时部分 MCP 工具将无法正常工作。

---

## 验证安装

### 1. 验证Python依赖

```bash
python -c "import chromadb; import redis; import pydantic; print('依赖检查通过')"
```

### 2. 验证服务启动

```bash
python -m asc_ops.server --help
```

预期输出：
```
usage: __main__.py [-h] [--host HOST] [--port PORT] [--reload]
```

### 3. 运行测试

```bash
# 运行单元测试
pytest tests/unit/ -v

# 运行集成测试（需要Redis）
pytest tests/integration/ -v
```

---

## 常见问题

### Q1: ChromaDB启动失败

**症状**: `ImportError: Cannot find ChromaDB`

**解决**:
```bash
pip install chromadb==0.4.22
```

### Q2: Redis连接失败

**症状**: `ConnectionError: Error connecting to Redis` 或 `failed to initialize redis client`

**解决**:
```bash
# 方式1: 启动Redis服务
redis-server

# 方式2: 使用docker启动Redis
docker run -d -p 6379:6379 redis:7-alpine

# 验证Redis是否正常运行
redis-cli ping
# 预期输出: PONG
```

> **重要**: Redis 是 MCP 工具的必需依赖，无法禁用。请确保 Redis 服务正常运行后再使用 MCP 工具。

### Q3: 向量化模型下载失败

**症状**: `OSError: Cannot find embedding model`

**解决**:
```bash
# 手动下载模型
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Q4: Python版本不兼容

**症状**: `SyntaxError` 或 `ModuleNotFoundError`

**解决**: 确保使用Python 3.10+

```bash
python --version  # 确认版本
# 如果是3.9或更低，需要升级Python
```

---

## 下一步

- [快速入门](quickstart.md) - 5分钟快速体验
- [首次查询](first-query.md) - 运行第一个查询
- [API参考](../api/reference.md) - 完整接口文档
