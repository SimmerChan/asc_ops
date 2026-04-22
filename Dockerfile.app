# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
AscendC Operator Knowledge Base - 多阶段构建

阶段1: 开发镜像 - 包含测试工具
阶段2: 生产镜像 - 最小化
"""

# ===== 阶段1: 开发镜像 =====
FROM python:3.11-slim AS development

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装开发依赖
RUN pip install --no-cache-dir pytest pytest-cov pytest-asyncio httpx

# 下载 embedding 模型
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('Qwen/Qwen3-Embedding-0.6B')"

# Copy application code
COPY . .

# 创建数据目录
RUN mkdir -p /data/chroma_db /data/redis

# 暴露端口
EXPOSE 8000

# 开发模式启动 (带热重载)
CMD ["python", "-m", "asc_ops.server"]


# ===== 阶段2: 生产镜像 =====
FROM python:3.11-slim AS production

WORKDIR /app

# 安装系统依赖 (最小化)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (生产环境不需要测试工具)
RUN pip install --no-cache-dir -r requirements.txt

# 下载 embedding 模型
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('Qwen/Qwen3-Embedding-0.6B')"

# Copy application code
COPY . .

# 创建非 root 用户运行
RUN useradd -m -u 1000 appuser && \
    mkdir -p /data/chroma_db /data/redis && \
    chown -R appuser:appuser /app

USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 生产模式启动
CMD ["python", "-m", "asc_ops.server"]
