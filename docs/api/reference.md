# API参考文档

本文档提供AscendC算子知识库的完整API接口定义。

---

## 基础信息

| 项目 | 值 |
|------|-----|
| 基础URL | `http://localhost:8000` |
| API版本 | v1 |
| 文档地址 | `/docs` (Swagger UI) |
| 健康检查 | `/health` |

---

## 认证

当前版本不需要认证。生产环境部署时应通过API Gateway或Nginx添加认证。

---

## 错误响应

所有API错误返回统一格式：

```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "operator_name不能为空",
    "details": {}
  }
}
```

错误码列表：

| HTTP状态码 | error.code | 说明 |
|------------|------------|------|
| 400 | INVALID_PARAMETER | 参数错误 |
| 404 | NOT_FOUND | 资源不存在 |
| 422 | VALIDATION_ERROR | 数据验证失败 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |

---

## 知识查询API

### 1. 开发参考查询

查询指定算子的开发知识（Bug修复、优化方案）。

**请求**

```http
POST /api/v1/query/development
Content-Type: application/json

{
  "operator_name": "Matmul",
  "query_type": "all",        // "bug" | "optimization" | "all"
  "api_filter": [],           // 可选，API过滤
  "severity_filter": [],      // 可选，严重程度过滤
  "min_confidence": 0.5,      // 可选，最低置信度
  "limit": 10                 // 可选，返回数量，默认10
}
```

**响应**

```json
{
  "operator_name": "Matmul",
  "query_type": "all",
  "total_count": 5,
  "bug_fixes": [
    {
      "bug_id": "bug_ops_nn_abc123",
      "bug_title": "非对齐数据导致地址越界",
      "symptom": "处理非对齐数据时crash",
      "root_cause": "未检查地址对齐",
      "severity": "major",
      "trigger_conditions": ["数据地址不是16倍数"],
      "fix_pattern": "添加地址对齐检查",
      "confidence": 0.85,
      "source_repo": "ops-nn",
      "source_pr": "PR #123"
    }
  ],
  "optimizations": [
    {
      "opt_id": "opt_ops_nn_def456",
      "opt_title": "分块计算减少内存访问",
      "optimization_type": ["memory", "tiling"],
      "improvement_ratio": 0.15,
      "confidence": 0.72,
      "source_repo": "ops-nn"
    }
  ]
}
```

---

### 2. 问题排查查询

根据症状搜索相似Bug和解决方案。

**请求**

```http
POST /api/v1/query/troubleshooting
Content-Type: application/json

{
  "symptom": "Matmul算子crash",
  "operator_name": "Matmul",      // 可选
  "error_message": "address error", // 可选
  "used_apis": ["Mmad", "TensorDesc"], // 可选
  "include_related": true,          // 可选
  "include_api_details": false,      // 可选
  "limit": 5
}
```

**响应**

```json
{
  "symptom": "Matmul算子crash",
  "possible_causes": [
    {
      "bug_id": "bug_ops_nn_abc123",
      "description": "非对齐数据导致地址越界",
      "confidence": 0.85,
      "root_cause": "未检查地址对齐",
      "trigger_conditions": ["数据地址不是16倍数"],
      "suggested_fix": "添加地址对齐检查",
      "suggested_checks": [
        "检查输入数据地址对齐",
        "使用assert验证对齐"
      ]
    }
  ],
  "related_knowledge": [...],
  "related_apis": [...]
}
```

---

### 3. API查询

查询AscendC API的定义和使用方法。

**请求**

```http
GET /api/v1/api/{api_name}
```

**响应**

```json
{
  "api_id": "ascendc_vec_reduce_max",
  "canonical_name": "VecReduceMax",
  "full_signature": "void VecReduceMax(LocalTensor<T>& out, LocalTensor<In>& in, int32_t dim)",
  "category": "compute",
  "subcategory": "reduction",
  "description": "向量归约取最大值",
  "parameters": [
    {
      "name": "out",
      "type": "LocalTensor<T>&",
      "description": "输出张量",
      "required": true,
      "default": null
    },
    {
      "name": "in",
      "type": "LocalTensor<In>&",
      "description": "输入张量",
      "required": true,
      "default": null
    },
    {
      "name": "dim",
      "type": "int32_t",
      "description": "归约维度",
      "required": true,
      "default": null
    }
  ],
  "return_value": {
    "type": "void",
    "description": "无返回值，结果写入out张量"
  },
  "usage_examples": [
    {
      "scenario": "二维张量按行取最大值",
      "code": "VecReduceMax(out, in, 1);",
      "注意事项": ["dim必须有效", "out大小需匹配"]
    }
  ],
  "注意事项": ["输入输出张量不能重叠"],
  "confidence": 1.0
}
```

---

### 4. 语义搜索

通过自然语言搜索知识。

**请求**

```http
POST /api/v1/search
Content-Type: application/json

{
  "query": "矩阵乘法的性能优化方法",
  "search_type": "all",     // "knowledge" | "api" | "all"
  "limit": 10,
  "min_score": 0.5
}
```

**响应**

```json
{
  "query": "矩阵乘法的性能优化方法",
  "results": [
    {
      "type": "optimization",
      "id": "opt_ops_math_xyz789",
      "title": "Matmul分块tiling优化",
      "snippet": "通过分块计算减少...的访存",
      "score": 0.92
    },
    {
      "type": "api",
      "id": "ascendc_matmul",
      "title": "Matmul API",
      "snippet": "矩阵乘法核心接口，支持...",
      "score": 0.85
    }
  ]
}
```

---

## 管理API

### 5. 知识库统计

获取知识库统计信息。

**请求**

```http
GET /api/v1/stats
```

**响应**

```json
{
  "api_count": 1786,
  "operator_count": 156,
  "bug_fix_count": 126,
  "optimization_count": 26,
  "last_sync_time": "2026-04-10T12:00:00Z",
  "storage_size_mb": 245.6
}
```

---

### 6. 知识追溯

查询特定知识的来源信息。

**请求**

```http
GET /api/v1/knowledge/{knowledge_id}/source
```

**响应**

```json
{
  "knowledge_id": "bug_ops_nn_abc123",
  "source_type": "pr",
  "source_repo": "ops-nn",
  "source_url": "https://gitcode.com/cann/ops-nn/pulls/123",
  "author": "developer@huawei.com",
  "created_at": "2026-03-15T10:30:00Z",
  "updated_at": "2026-03-15T14:20:00Z",
  "review_status": "approved"
}
```

---

### 7. Webhook配置

配置知识同步Webhook。

**请求**

```http
POST /api/v1/webhook
Content-Type: application/json

{
  "repo": "cann/ops-nn",
  "events": ["pull_request.merged", "push"],
  "url": "https://your-server.com/webhook",
  "secret": "your-webhook-secret"
}
```

**响应**

```json
{
  "webhook_id": "wh_abc123",
  "status": "active",
  "repo": "cann/ops-nn",
  "events": ["pull_request.merged", "push"],
  "created_at": "2026-04-10T12:00:00Z"
}
```

---

## SDK接口

### Python SDK

```python
from asc_ops import KnowledgeQueryService

# 初始化
service = KnowledgeQueryService(
    base_url="http://localhost:8000"  # 可选，默认本地
)

# 查询
result = await service.query_for_development(
    operator_name="Matmul",
    query_type="all"
)
```

### TypeScript SDK

```typescript
import { AscOpsClient } from '@asc-ops/client';

// 初始化
const client = new AscOpsClient({
  baseUrl: 'http://localhost:8000'
});

// 查询
const result = await client.query.development({
  operatorName: 'Matmul',
  queryType: 'all'
});
```

---

## OpenAPI规范

完整的OpenAPI 3.0规范可从以下地址获取：

```
http://localhost:8000/openapi.json
```

---

## 下一步

- [快速入门](../getting-started/quickstart.md) - 使用示例
- [部署指南](../deployment/docker.md) - 生产部署
