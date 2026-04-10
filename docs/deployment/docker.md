# Docker部署指南

本文档介绍如何使用Docker部署AscendC算子知识库。

---

## 部署架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   asc_ops   │  │   redis     │  │  (可选)     │          │
│  │   server    │  │   7-alpine  │  │  redis-ui   │          │
│  │             │  │             │  │             │          │
│  │  Port:8000  │◄─┤  Port:6379  │  │  Port:8080  │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              持久化存储                              │   │
│  │  ./data/chroma_db ← ChromaDB数据                    │   │
│  │  ./data/redis    ← Redis数据 (可选)                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 前置条件

- Docker 20.10+
- Docker Compose 2.0+

```bash
# 验证安装
docker --version
docker compose version
```

---

## 快速部署

### 1. 克隆项目

```bash
git clone https://github.com/your-org/asc_ops.git
cd asc_ops
```

### 2. 配置环境变量

```bash
# 创建.env文件
cp .env.example .env

# 编辑必要的配置
nano .env
```

关键配置项：

```bash
# .env
CHROMA_DB_PATH=/data/chroma_db
REDIS_HOST=redis
REDIS_PORT=6379
ANTHROPIC_API_KEY=sk-xxx  # 必填，用于知识抽取
EMBEDDING_MODEL=all-MiniLM-L6-v2
SERVER_PORT=8000
```

### 3. 启动服务

```bash
# 构建并启动所有服务
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f asc_ops
```

### 4. 验证服务

```bash
# 检查API文档
curl http://localhost:8000/docs

# 检查健康状态
curl http://localhost:8000/health
```

预期响应：

```json
{"status": "healthy", "version": "0.1.0"}
```

---

## Docker Compose配置

### 基本配置 (docker-compose.yml)

```yaml
version: '3.8'

services:
  asc_ops:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: asc_ops
    ports:
      - "8000:8000"
    environment:
      - CHROMA_DB_PATH=/data/chroma_db
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - EMBEDDING_MODEL=all-MiniLM-L6-v2
    volumes:
      - ./data/chroma_db:/data/chroma_db
      - ./data/redis:/data/redis
    depends_on:
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    container_name: asc_ops_redis
    ports:
      - "6379:6379"
    volumes:
      - ./data/redis:/data
    command: redis-server --appendonly yes
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  # 可选：Redis管理界面
  redisinsight:
    image: redis/redisinsight:latest
    container_name: asc_ops_redis_ui
    ports:
      - "8080:8000"
    depends_on:
      - redis
    restart: unless-stopped
```

### 生产配置 (docker-compose.prod.yml)

```yaml
version: '3.8'

services:
  asc_ops:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        - DEBUG=false
    environment:
      - CHROMA_DB_PATH=/data/chroma_db
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - EMBEDDING_MODEL=all-MiniLM-L6-v2
      - LOG_LEVEL=WARNING
    volumes:
      - /opt/asc_ops/chroma_db:/data/chroma_db
      - /opt/asc_ops/redis:/data/redis
    depends_on:
      redis:
        condition: service_healthy
    restart: always
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G

  redis:
    image: redis:7-alpine
    volumes:
      - /opt/asc_ops/redis:/data
    command: redis-server --appendonly yes --maxmemory 1gb --maxmemory-policy allkeys-lru
    restart: always
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
```

---

## 数据管理

### 数据目录结构

```bash
./data/
├── chroma_db/          # ChromaDB数据
│   ├── index/          # 向量索引
│   └── metadata/       # 元数据
└── redis/              # Redis持久化
    ├── appendonly.aof  # AOF日志
    └── dump.rdb        # RDB快照
```

### 备份

```bash
# 备份数据目录
tar -czf asc_ops_backup_$(date +%Y%m%d).tar.gz data/

# 备份到远程存储
rsync -avz ./data/ user@backup-server:/path/to/backup/
```

### 恢复

```bash
# 停止服务
docker compose down

# 恢复数据
tar -xzf asc_ops_backup_20260410.tar.gz

# 重启服务
docker compose up -d
```

---

## 扩缩容

### 水平扩展（多实例）

```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  asc_ops:
    # ... 其他配置 ...
    deploy:
      replicas: 3
    depends_on:
      - redis

  redis:
    # ... 其他配置 ...
    # Redis单实例，ChromaDB为嵌入式
```

```bash
docker compose -f docker-compose.scale.yml up -d --scale asc_ops=3
```

### 资源调整

```bash
# 查看资源使用
docker stats

# 调整内存限制
docker compose up -d --scale asc_ops=1 -m 2g
```

---

## 监控

### 健康检查

```bash
# 检查所有服务健康状态
curl http://localhost:8000/health
curl http://localhost:6379/ping  # Redis

# Docker健康检查
docker inspect --format='{{.State.Health.Status}}' asc_ops
```

### 日志管理

```bash
# 查看实时日志
docker compose logs -f

# 查看最近100行
docker compose logs --tail=100

# 日志轮转配置 (docker-compose.yml)
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### 监控指标

```bash
# Prometheus格式指标
curl http://localhost:8000/metrics
```

---

## 常见问题

### Q1: 容器无法启动

**症状**: `docker compose up` 失败

**排查步骤**:
```bash
# 1. 检查端口占用
lsof -i :8000
lsof -i :6379

# 2. 查看详细日志
docker compose up --verbose

# 3. 检查Docker资源
docker system df
```

### Q2: ChromaDB数据丢失

**症状**: 重启后知识库为空

**解决**:
```bash
# 确保volume挂载正确
docker compose down
docker volume rm asc_ops_chroma_db  # 危险：会删除数据
docker compose up -d
```

### Q3: Redis连接失败

**症状**: `ConnectionError: Cannot connect to Redis`

**排查**:
```bash
# 1. 检查Redis是否运行
docker compose ps redis

# 2. 检查Redis日志
docker compose logs redis

# 3. 手动测试连接
docker exec -it asc_ops_redis redis-cli ping
```

---

## 下一步

- [快速入门](../getting-started/quickstart.md) - 使用知识库
- [API参考](../api/reference.md) - 接口文档
- [配置参考](./config.md) - 完整配置项
