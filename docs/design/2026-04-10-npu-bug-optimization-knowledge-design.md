# NPU算子Bug修复与优化知识设计方案

**文档版本**: v1.0
**创建日期**: 2026-04-10
**作者**: 首席架构师
**状态**: 正式版

---

## 1. 背景与目标

### 1.1 问题背景

当前昇腾AscendC算子知识库设计存在以下缺失：

| 缺失项 | 影响 |
|--------|------|
| Bug修复知识未建模 | Agent无法利用历史bug修复经验 |
| PR中bugfix内容如何提取未定义 | 知识采集流程不完整 |
| 优化点缺少量化指标 | 优化效果无法评估 |
| Agent使用知识的场景未细化 | 查询接口设计缺乏依据 |

### 1.2 设计目标

```
┌─────────────────────────────────────────────────────────────────────┐
│                         设计目标                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  目标1: 建立Bug修复知识的结构化表示                                     │
│  目标2: 建立优化知识的轻量级表示（量化可选）                           │
│  目标3: 设计完整的知识抽取流程                                        │
│  目标4: 支持Agent主动开发参考 + 被动问题排查                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 核心设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| NPU Bug知识来源 | **先采样后建模** | PR信息量未知，需先分析再定义抽取逻辑 |
| Bug知识场景 | **主动+被动双模式** | 开发参考 + 遇到问题时的解决方案搜索 |
| 优化点量化 | **可选字段，非强制** | 有则记录，无则跳过 |
| GPU Bug知识 | **暂不采集** | 聚焦NPU侧 |
| PR采样范围 | **6个昇腾仓全部采样** | 全面了解PR结构 |

---

## 2. Bug修复知识建模

### 2.1 数据模型

```python
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class BugSeverity(Enum):
    CRITICAL = "critical"   # 导致crash/数据错误
    MAJOR = "major"         # 功能正确但结果偏差
    MINOR = "minor"         # 性能/精度轻微影响

class BugCategory(Enum):
    CORRECTNESS = "correctness"      # 正确性问题
    PERFORMANCE = "performance"       # 性能问题
    NUMERICAL = "numerical"          # 数值精度问题
    MEMORY = "memory"                # 内存问题
    SYNC = "sync"                    # 同步问题

@dataclass
class BugFixKnowledge:
    """NPU算子Bug修复知识"""

    # ========== 基础标识 ==========
    bug_id: str                       # 唯一标识，如 "fbgemm_matmul_precision_001"
    operator_id: str                  # 关联算子，如 "matmul"
    source_repo: str                  # 来源仓，如 "fbgemm-ascend"
    source_pr: str                    # 来源PR号，如 "PR #234"

    # ========== Bug描述 ==========
    bug_title: str                    # Bug简短描述
    symptom: str                      # 表现：什么现象
    severity: BugSeverity             # 严重程度
    category: BugCategory             # Bug类别

    # ========== 根因与触发 ==========
    root_cause: Optional[str]         # 根因（如果能从PR中提取）
    trigger_conditions: List[str]     # 触发条件列表

    # ========== 修复方案 ==========
    fix_pattern: str                  # 修复模式/方案描述
    fix_code_hints: List[str]         # 修复代码提示（如改了什么API调用）
    workarounds: List[str]            # 临时规避方案（如有）

    # ========== 关联信息 ==========
    related_apis: List[str]           # 涉及的API
    related_bugs: List[str]           # 关联的其他bug（如有类似问题）
    affected_versions: List[str]      # 受影响版本

    # ========== 元数据 ==========
    confidence: float                 # 置信度 (0-1)
    extraction_method: str           # 抽取方式：llm/manual/pattern
    review_status: str                # 审核状态：pending/approved/rejected

    # ========== 向量嵌入 ==========
    embedding: List[float]

    # ========== 时间戳 ==========
    created_at: datetime
    updated_at: datetime
```

### 2.2 数据示例

```python
# 真实示例：Matmul精度问题
bug_fix_example = BugFixKnowledge(
    bug_id="fbgemm_matmul_numerical_001",
    operator_id="matmul",
    source_repo="fbgemm-ascend",
    source_pr="PR #234",

    bug_title="Matmul FP16计算结果精度偏差",
    symptom="FP16模式下Matmul输出与参考实现有0.1%误差",
    severity=BugSeverity.MAJOR,
    category=BugCategory.NUMERICAL,

    root_cause="FP16累加过程中溢出风险，累加顺序导致精度损失",

    trigger_conditions=[
        "输入数据值域较大（如激活值>100）",
        "矩阵维度K较大（K>1024）",
        "使用FP16精度"
    ],

    fix_pattern="启用Tensor Accumulator的relaxed rounding模式",
    fix_code_hints=[
        "在Mmad调用前设置config.relaxed_rounding=true",
        "或使用TF32精度替代FP16"
    ],
    workarounds=[
        "临时降低batch size以减小中间值",
        "切换到FP32精度"
    ],

    related_apis=["Mmad", "TensorDesc"],
    related_bugs=[],

    confidence=0.85,
    extraction_method="llm",
    review_status="approved",

    embedding=[...],  # 向量嵌入

    created_at=datetime(2026, 3, 15),
    updated_at=datetime(2026, 3, 15)
)
```

---

## 3. 优化知识建模

### 3.1 数据模型

```python
@dataclass
class OptimizationKnowledge:
    """NPU算子优化知识（轻量级）"""

    # ========== 基础标识 ==========
    opt_id: str                        # 唯一标识
    operator_id: str                   # 关联算子
    source_repo: str                    # 来源仓
    source_pr: str                      # 来源PR

    # ========== 优化描述 ==========
    opt_title: str                     # 优化简短描述
    optimization_type: List[str]       # 优化类型：["分块", "流水", "向量化"]
    target: str                        # 优化目标：性能/内存/精度

    # ========== 优化详情 ==========
    optimization_description: str       # 优化方案描述
    optimization_context: str           # 上下文：什么场景下有效

    # ========== 量化指标（可选） ==========
    improvement_ratio: Optional[float]  # 提升比例，如 0.15 表示15%提升
    before_metrics: Optional[dict]       # 优化前指标
    after_metrics: Optional[dict]        # 优化后指标
    measurement_conditions: Optional[str]  # 测量条件

    # ========== 关联信息 ==========
    related_apis: List[str]            # 涉及的API
    applicable_hw: List[str]            # 适用硬件（可选）
    applicable_data_scale: Optional[str]  # 适用数据规模（可选）

    # ========== 元数据 ==========
    confidence: float
    extraction_method: str
    review_status: str

    # ========== 向量嵌入 ==========
    embedding: List[float]

    created_at: datetime
    updated_at: datetime
```

### 3.2 数据示例

```python
# 真实示例：Matmul分块优化
opt_example = OptimizationKnowledge(
    opt_id="ops_nn_matmul_blocking_001",
    operator_id="matmul",
    source_repo="ops-nn",
    source_pr="PR #156",

    opt_title="Matmul大矩阵分块优化",
    optimization_type=["分块", "内存优化"],
    target="性能",

    optimization_description="""
    将大矩阵乘法拆分为16x16的小块进行计算，
    利用Tensor Core的WMMA指令加速，
    通过shared memory缓存中间结果减少全局内存访问
    """,
    optimization_context="适用于矩阵维度大于128的场景",

    improvement_ratio=0.35,  # 35%性能提升
    before_metrics={
        "throughput": "850 GFLOPS",
        "latency": "12ms"
    },
    after_metrics={
        "throughput": "1148 GFLOPS",
        "latency": "8.9ms"
    },
    measurement_conditions="A100, 1024x1024x1024, FP16",

    related_apis=["Mmad", "DataCopy", "TensorDesc"],
    applicable_hw=["Ascend 910B", "A100"],
    applicable_data_scale="大矩阵（>128维度）",

    confidence=0.9,
    extraction_method="llm",
    review_status="approved",

    embedding=[...],

    created_at=datetime(2026, 2, 20),
    updated_at=datetime(2026, 2, 20)
)
```

---

## 4. PR采样分析

### 4.1 采样目标

| 目标 | 说明 |
|------|------|
| 了解PR结构 | 标题/描述/代码/评论的完整度 |
| Bugfix PR占比 | 不同仓的bugfix比例 |
| 信息完整度 | 根因/触发条件/修复方案的覆盖情况 |

### 4.2 采样范围

```
┌─────────────────────────────────────────────────────────────────┐
│                    采样仓库列表                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Ascend组织                                                      │
│  ├─ HierarchicalKV-ascend                                       │
│  └─ fbgemm-ascend                                                │
│                                                                  │
│  cann组织                                                        │
│  ├─ ops-math                                                     │
│  ├─ ops-nn                                                       │
│  ├─ ops-transformer                                              │
│  └─ ops-cv                                                       │
│                                                                  │
│  采样数量：每个仓100个PR（按需调整）                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 采样分析脚本

```python
# scripts/sample_pr_analysis.py
"""
昇腾仓PR采样分析脚本
"""

import asyncio
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class PRSampleResult:
    repo: str
    total_prs: int
    bugfix_prs: int
    optimization_prs: int
    feature_prs: int

    # Bugfix信息完整度
    bugfix_with_root_cause: float  # 百分比
    bugfix_with_trigger: float
    bugfix_with_fix_detail: float

    # 平均描述长度
    avg_title_length: float
    avg_description_length: float

    # 推荐
    recommendations: List[str]


async def sample_analyze_prs(repo_url: str, sample_size: int = 100) -> PRSampleResult:
    """采样分析昇腾仓PR"""

    # 1. 获取PR列表
    prs = await github.get_prs(
        repo_url,
        state="all",
        sort="updated",
        direction="desc",
        per_page=100
    )

    # 2. 取样
    sampled_prs = random.sample(prs, min(sample_size, len(prs)))

    # 3. 分类统计
    classifier = PRClassifier()
    analysis = {
        "bugfix": [],
        "optimization": [],
        "feature": []
    }

    for pr in sampled_prs:
        pr_type = classifier.classify(pr.title, pr.description)
        analysis[pr_type].append(pr)

    # 4. Bugfix信息完整度分析
    bugfix_info = analyze_bugfix_completeness(analysis["bugfix"])

    # 5. 生成推荐
    recommendations = generate_recommendations(bugfix_info)

    return PRSampleResult(
        repo=repo_url,
        total_prs=len(sampled_prs),
        bugfix_prs=len(analysis["bugfix"]),
        optimization_prs=len(analysis["optimization"]),
        feature_prs=len(analysis["feature"]),
        bugfix_with_root_cause=bugfix_info["root_cause_rate"],
        bugfix_with_trigger=bugfix_info["trigger_rate"],
        bugfix_with_fix_detail=bugfix_info["fix_detail_rate"],
        avg_title_length=sum(len(p.title) for p in sampled_prs) / len(sampled_prs),
        avg_description_length=sum(len(p.description or "") for p in sampled_prs) / len(sampled_prs),
        recommendations=recommendations
    )


async def main():
    repos = [
        "NVIDIA/HierarchicalKV",
        "NVIDIA/fbgemm",
        # Ascend/cann组织下的仓
    ]

    results = []
    for repo in repos:
        result = await sample_analyze_prs(repo)
        results.append(result)

    # 生成汇总报告
    summary = generate_summary_report(results)

    # 存储到 docs/analysis/pr_sampling_report.md
    save_report(summary)


if __name__ == "__main__":
    asyncio.run(main())
```

### 4.4 PR分类器

```python
class PRClassifier:
    """PR类型分类器"""

    BUG_KEYWORDS = [
        "fix", "bug", "修复", "解决", "hotfix", "patch",
        "crash", "error", "incorrect", "wrong", "精度",
        "regression", "issue", "问题"
    ]

    OPTIMIZATION_KEYWORDS = [
        "optimize", "perf", "performance", "优化", "加速",
        "improve", "enhance", "提升", "speedup",
        "efficiency", "throughput", "latency"
    ]

    def classify(self, title: str, description: str) -> str:
        """
        分类PR类型：bugfix / optimization / feature
        返回: bugfix | optimization | feature
        """
        text = (title + " " + (description or "")).lower()

        bug_score = sum(1 for kw in self.BUG_KEYWORDS if kw in text)
        opt_score = sum(1 for kw in self.OPTIMIZATION_KEYWORDS if kw in text)

        if bug_score >= 2 or (bug_score >= 1 and opt_score == 0):
            return "bugfix"
        elif opt_score >= 2 or (opt_score >= 1 and bug_score == 0):
            return "optimization"
        else:
            return "feature"

    def extract_bug_keywords(self, text: str) -> List[str]:
        """提取文本中包含的bug相关关键词"""
        text = text.lower()
        return [kw for kw in self.BUG_KEYWORDS if kw in text]
```

---

## 5. 知识抽取流程

### 5.1 整体Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    知识抽取Pipeline                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   PR事件触发                               │  │
│  │                   (Webhook)                               │  │
│  └────────────────────────┬─────────────────────────────────┘  │
│                           │                                      │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              PR分类 (PRClassifier)                        │  │
│  │  bugfix ──► Bug知识抽取                                  │  │
│  │  optimization ──► 优化知识抽取                           │  │
│  │  feature ──► 跳过（除非包含相关知识）                     │  │
│  └────────────────────────┬─────────────────────────────────┘  │
│                           │                                      │
│          ┌────────────────┴────────────────┐                     │
│          ▼                                 ▼                     │
│  ┌──────────────────┐          ┌──────────────────┐            │
│  │  Bug知识抽取      │          │  优化知识抽取     │            │
│  │                  │          │                  │            │
│  │  1. LLM语义抽取  │          │  1. LLM语义抽取  │            │
│  │  2. 信息补全     │          │  2. 指标提取     │            │
│  │  3. 置信度评估   │          │  3. 置信度评估  │            │
│  │  4. 去重检查     │          │  4. 去重检查     │            │
│  │  5. 存储         │          │  5. 存储         │            │
│  └──────────────────┘          └──────────────────┘            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Bug知识抽取详细流程

```python
async def extract_bug_knowledge(pr: PullRequest) -> Optional[BugFixKnowledge]:
    """从BugFix PR中抽取Bug知识"""

    # 1. PR信息准备
    pr_content = {
        "title": pr.title,
        "description": pr.description or "",
        "diff": pr.get_diff(),
        "comments": pr.get_comments(),
        "files_changed": pr.get_changed_files()
    }

    # 2. LLM语义抽取
    extraction = await llm.extract_bug_knowledge(
        prompt=f"""
从以下BugFix PR中抽取结构化知识：

标题: {pr_content['title']}
描述: {pr_content['description']}
代码变更: {pr_content['diff']}

请提取以下信息（无法提取的字段填空字符串）：
- bug_title: Bug简短描述
- symptom: Bug表现（什么现象）
- root_cause: 根因（如果能从描述/diff中推断）
- trigger_conditions: 触发条件列表
- fix_pattern: 修复方案描述
- related_apis: 涉及的API（从代码中识别AscendC API调用）
- severity: 严重程度 (critical/major/minor)
- category: Bug类别 (correctness/performance/numerical/memory/sync)

输出格式: JSON
"""
    )

    # 3. 信息补全（如果根因为空，尝试从diff分析）
    if not extraction.root_cause:
        extraction.root_cause = await analyze_code_change_for_root_cause(
            pr_content['diff']
        )

    # 4. 关联算子识别
    operator_id = extract_operator_id_from_pr(pr_content)

    # 5. 置信度评估
    confidence = evaluate_confidence(extraction, pr_content)

    # 6. 去重检查
    is_duplicate = await check_duplicate_bug(
        operator_id,
        extraction.symptom,
        extraction.fix_pattern
    )

    if is_duplicate:
        return None  # 跳过重复

    # 7. 构建知识
    bug_knowledge = BugFixKnowledge(
        bug_id=f"bug_{pr.repo}_{pr.pr_number}",
        operator_id=operator_id,
        source_repo=pr.repo,
        source_pr=f"PR #{pr.pr_number}",
        bug_title=extraction.bug_title or pr.title,
        symptom=extraction.symptom,
        severity=extraction.severity or BugSeverity.MAJOR,
        category=extraction.category or BugCategory.CORRECTNESS,
        root_cause=extraction.root_cause,
        trigger_conditions=extraction.trigger_conditions or [],
        fix_pattern=extraction.fix_pattern,
        fix_code_hints=extraction.fix_code_hints or [],
        related_apis=extraction.related_apis or [],
        confidence=confidence,
        extraction_method="llm",
        review_status="pending" if confidence < 0.7 else "approved",
        embedding=await generate_embedding(extraction),
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    return bug_knowledge


def evaluate_confidence(extraction, pr_content) -> float:
    """评估抽取置信度"""

    score = 0.5  # 基础分

    # 根因信息
    if extraction.root_cause:
        score += 0.2
    else:
        # 尝试从diff分析
        score += 0.05

    # 触发条件
    if extraction.trigger_conditions:
        score += 0.1

    # 修复方案
    if extraction.fix_pattern:
        score += 0.15

    # API关联
    if extraction.related_apis:
        score += 0.05

    # 描述完整度加成
    desc_len = len(pr_content.get('description', '') or '')
    if desc_len > 200:
        score += 0.05

    return min(score, 1.0)  # 最高1.0
```

### 5.3 优化知识抽取

```python
async def extract_optimization_knowledge(
    pr: PullRequest
) -> Optional[OptimizationKnowledge]:
    """从优化PR中抽取优化知识"""

    # 1. PR信息准备
    pr_content = {
        "title": pr.title,
        "description": pr.description or "",
        "diff": pr.get_diff()
    }

    # 2. LLM语义抽取
    extraction = await llm.extract_optimization_knowledge(
        prompt=f"""
从以下优化PR中抽取结构化知识：

标题: {pr_content['title']}
描述: {pr_content['description']}
代码变更: {pr_content['diff']}

请提取以下信息：
- opt_title: 优化简短描述
- optimization_type: 优化类型列表（分块/流水/向量化/内存优化/精度优化等）
- optimization_description: 详细优化方案
- optimization_context: 优化适用场景/上下文
- improvement_ratio: 性能提升比例（如0.15表示15%，如无则填null）
- before_metrics: 优化前指标（如无则填null）
- after_metrics: 优化后指标（如无则填null）
- related_apis: 涉及的API

输出格式: JSON
"""
    )

    # 3. 关联算子识别
    operator_id = extract_operator_id_from_pr(pr_content)

    # 4. 量化指标解析
    improvement_ratio = parse_improvement_ratio(extraction.improvement_ratio)

    # 5. 构建知识
    opt_knowledge = OptimizationKnowledge(
        opt_id=f"opt_{pr.repo}_{pr.pr_number}",
        operator_id=operator_id,
        source_repo=pr.repo,
        source_pr=f"PR #{pr.pr_number}",
        opt_title=extraction.opt_title or pr.title,
        optimization_type=extraction.optimization_type or [],
        target="性能",  # 默认性能优化
        optimization_description=extraction.optimization_description,
        optimization_context=extraction.optimization_context,
        improvement_ratio=improvement_ratio,
        before_metrics=extraction.before_metrics,
        after_metrics=extraction.after_metrics,
        related_apis=extraction.related_apis or [],
        confidence=0.8 if improvement_ratio else 0.6,
        extraction_method="llm",
        review_status="pending",
        embedding=await generate_embedding(extraction),
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    return opt_knowledge
```

---

## 6. Agent查询场景

### 6.1 主动查询（开发参考）

```
Agent开发新算子前，查询常见问题：

┌─────────────────────────────────────────────────────────────────┐
│ Query: "开发Matmul算子需要注意哪些常见问题？"                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 查询Bug知识                                                  │
│     ─────────────────                                             │
│     ChromaDB语义检索:                                            │
│     - query: "Matmul bug fix"                                   │
│     - filter: operator_id = "matmul"                            │
│     - n_results: 5                                              │
│                                                                  │
│  2. 查询优化知识                                                 │
│     ─────────────────                                            │
│     ChromaDB语义检索:                                            │
│     - query: "Matmul optimization"                              │
│     - filter: operator_id = "matmul"                            │
│     - n_results: 5                                              │
│                                                                  │
│  3. 合并返回开发参考清单                                          │
│     ─────────────────────                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 被动查询（问题排查）

```
Agent遇到bug时，搜索解决方案：

┌─────────────────────────────────────────────────────────────────┐
│ Query: "Matmul算子在处理非对齐数据时crash"                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 意图识别                                                     │
│     ───────                                                     │
│     - symptom: "crash 非对齐 Matmul"                             │
│     - query_type: bug_fixing                                    │
│                                                                  │
│  2. 多路搜索                                                     │
│     ────────                                                    │
│                                                                  │
│     路径A: symptom语义搜索                                       │
│     ├─ ChromaDB: npu_bug_knowledge                              │
│     └─ query: "crash 非对齐 Matmul"                             │
│                                                                  │
│     路径B: operator搜索                                          │
│     ├─ ChromaDB: npu_bug_knowledge                              │
│     └─ filter: operator_id = "matmul"                          │
│                                                                  │
│     路径C: API关联搜索                                           │
│     ├─ 已知使用API: ["Mmad", "TensorDesc"]                      │
│     ├─ Redis: bug:api:Mmad                                      │
│     └─ Redis: bug:api:TensorDesc                                │
│                                                                  │
│  3. 结果融合                                                     │
│     ────────                                                    │
│     合并多路结果                                                  │
│     按: 相关性×0.6 + 置信度×0.4 排序                              │
│                                                                  │
│  4. 返回格式                                                     │
│     ────────                                                    │
│     {                                                            │
│       "possible_causes": [                                      │
│         {                                                        │
│           "bug_id": "...",                                       │
│           "description": "...",                                 │
│           "confidence": 0.85,                                   │
│           "suggested_checks": [...]                             │
│         }                                                        │
│       ],                                                        │
│       "related_knowledge": [...]                                 │
│     }                                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 查询接口定义

```python
class KnowledgeQueryService:
    """知识查询服务"""

    async def query_for_development(
        self,
        operator_name: str,
        query_type: str = "all"
    ) -> DevelopmentQueryResult:
        """
        主动开发查询

        Args:
            operator_name: 算子名称
            query_type: "bug" | "optimization" | "all"

        Returns:
            DevelopmentQueryResult: 开发参考结果
        """

    async def query_for_troubleshooting(
        self,
        symptom: str,
        operator_name: Optional[str] = None,
        error_message: Optional[str] = None,
        used_apis: Optional[List[str]] = None
    ) -> TroubleshootingResult:
        """
        被动问题排查查询

        Args:
            symptom: 异常表现描述
            operator_name: 涉及的算子（可选）
            error_message: 错误信息（可选）
            used_apis: 使用的API列表（可选）

        Returns:
            TroubleshootingResult: 问题排查结果
        """
```

---

## 7. 存储结构

### 7.1 ChromaDB Collections

```
┌─────────────────────────────────────────────────────────────────┐
│ ChromaDB Collections                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ Collection: npu_bug_knowledge                                    │
│ ├─ fields:                                                       │
│ │   - bug_id (str, primary key)                                 │
│ │   - operator_id (str, indexed)                                │
│ │   - embedding (numpy.array[1024])                             │
│ │   - symptom_text (str)                                        │
│ │   - root_cause_text (str)                                     │
│ │   - fix_pattern_text (str)                                    │
│ │   - severity (str)                                            │
│ │   - confidence (float)                                        │
│ │   - source_repo (str)                                         │
│ └─ metadata:                                                     │
│     - index: operator_id, severity, source_repo                 │
│                                                                  │
│ Collection: npu_optimization_knowledge                            │
│ ├─ fields:                                                       │
│ │   - opt_id (str, primary key)                                 │
│ │   - operator_id (str, indexed)                                │
│ │   - embedding (numpy.array[1024])                             │
│ │   - opt_title_text (str)                                     │
│ │   - optimization_description (str)                            │
│ │   - optimization_type (list[str])                             │
│ │   - improvement_ratio (float, nullable)                      │
│ │   - confidence (float)                                        │
│ │   - source_repo (str)                                         │
│ └─ metadata:                                                     │
│     - index: operator_id, optimization_type                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Redis Key Patterns

```
┌─────────────────────────────────────────────────────────────────┐
│ Redis Key Patterns                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ # Bug知识索引                                                     │
│ bug:operator:{operator_id}     → SET of bug_id                 │
│ bug:api:{api_id}               → SET of bug_id                 │
│ bug:repo:{repo}                → SET of bug_id                 │
│ bug:severity:{severity}         → SET of bug_id                 │
│                                                                  │
│ # Bug详情存储                                                    │
│ bug:detail:{bug_id}            → HASH of BugFixKnowledge       │
│                                                                  │
│ # 优化知识索引                                                    │
│ opt:operator:{operator_id}     → SET of opt_id                 │
│ opt:api:{api_id}               → SET of opt_id                 │
│ opt:repo:{repo}                → SET of opt_id                 │
│                                                                  │
│ # 优化详情存储                                                    │
│ opt:detail:{opt_id}            → HASH of OptimizationKnowledge │
│                                                                  │
│ # 待审核队列                                                     │
│ bug:pending_review             → LIST of bug_id                │
│ opt:pending_review             → LIST of opt_id                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. 实施计划

### 8.1 Phase划分

| Phase | 内容 | 工作量 | 前置条件 |
|-------|------|--------|----------|
| **Phase 0** | PR采样分析 | 1-2天 | 无 |
| **Phase 1** | Bug知识模型 + 基础抽取 | 3-5天 | Phase 0结论 |
| **Phase 2** | 优化知识模型 + 抽取 | 2-3天 | Phase 1 |
| **Phase 3** | 主动查询接口 | 2-3天 | Phase 1, 2 |
| **Phase 4** | 被动查询接口 | 2-3天 | Phase 3 |

### 8.2 Phase 0: 采样分析详细计划

```python
# 采样分析任务清单
SAMPLE_TASKS = [
    {
        "repo": "HierarchicalKV-ascend",
        "url": "https://github.com/ascend-provider/HierarchicalKV",
        "sample_size": 100,
        "priority": 1
    },
    {
        "repo": "fbgemm-ascend",
        "url": "https://github.com/ascend-provider/fbgemm",
        "sample_size": 100,
        "priority": 1
    },
    {
        "repo": "ops-math",
        "url": "https://github.com/ascend-cann/ops-math",
        "sample_size": 100,
        "priority": 2
    },
    {
        "repo": "ops-nn",
        "url": "https://github.com/ascend-cann/ops-nn",
        "sample_size": 100,
        "priority": 2
    },
    {
        "repo": "ops-transformer",
        "url": "https://github.com/ascend-cann/ops-transformer",
        "sample_size": 80,
        "priority": 3
    },
    {
        "repo": "ops-cv",
        "url": "https://github.com/ascend-cann/ops-cv",
        "sample_size": 80,
        "priority": 3
    }
]

# 分析指标
ANALYSIS_METRICS = [
    "bugfix_pr_ratio",           # Bugfix PR占比
    "avg_description_length",    # 平均描述长度
    "root_cause_mention_rate",   # 根因提及率
    "trigger_mention_rate",      # 触发条件提及率
    "fix_detail_mention_rate",   # 修复详情提及率
    "pr_merge_time",             # PR平均处理时间
]
```

---

## 9. 与其他模块的关系

```
┌─────────────────────────────────────────────────────────────────┐
│                      模块依赖关系图                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              采集稳定性设计 (已设计)                      │    │
│  │              R1-R6: 重试/限速/断点续采                    │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │ PR事件触发                            │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              PR分类器 (PRClassifier)                     │    │
│  │              bugfix / optimization / feature            │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │                                      │
│         ┌─────────────────┴─────────────────┐                    │
│         ▼                                   ▼                    │
│  ┌──────────────────┐             ┌──────────────────┐          │
│  │  Bug知识抽取      │             │  优化知识抽取     │          │
│  │  (本设计 - Phase1)│            │  (本设计 - Phase2)│          │
│  └────────┬─────────┘             └────────┬─────────┘          │
│           │                                  │                    │
│           └──────────────┬───────────────────┘                    │
│                          ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │         ChromaDB + Redis存储                            │    │
│  │         npu_bug_knowledge + npu_optimization_knowledge   │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │                                      │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │         Agent查询接口                                    │    │
│  │         主动查询 + 被动问题排查                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| PR信息量不足，抽取质量差 | 中 | 高 | Phase 0采样后调整抽取策略 |
| Bug和优化PR分类错误 | 中 | 中 | 多级分类器 + 人工审核 |
| 重复Bug知识堆积 | 低 | 低 | 去重检查机制 |
| 向量检索召回率低 | 中 | 中 | 混合检索（语义+关键词） |

---

## 11. 成功标准

### 11.1 采集阶段

| 指标 | 目标 |
|------|------|
| Bug知识覆盖率 | 6个仓Bugfix PR覆盖率 ≥ 80% |
| 优化知识覆盖率 | 6个仓优化PR覆盖率 ≥ 70% |
| 置信度分布 | 高置信度(≥0.8)占比 ≥ 50% |

### 11.2 查询阶段

| 指标 | 目标 |
|------|------|
| 主动查询召回率 | Top5结果中相关 ≥ 80% |
| 被动查询准确率 | 首个推荐结果准确 ≥ 70% |
| 查询响应时间 | P95 < 500ms |

---

## 12. 未来扩展

### 12.1 GPU Bug知识（后续Phase）

```
当需要GPU Bug知识时，可复用本设计方案：

GPU Bug知识模型 = BugFixKnowledge + GPU特定字段
- platform: "cuda"
- sm_architecture: "sm_80/sm_90"
- cuda_api_used: List[str]
```

### 12.2 知识图谱增强

```
未来可构建"问题模式→修复方案"的知识图谱：

Node: BugPattern
Edge: "solved_by" → BugFixKnowledge

实现更智能的问题诊断
```

---

**文档结束**

*本文档使用中文编写，采用mermaid图表格式*
