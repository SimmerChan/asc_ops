# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
AscendC知识库数据模型
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class BugSeverity(Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class BugCategory(Enum):
    CORRECTNESS = "correctness"
    PERFORMANCE = "performance"
    NUMERICAL = "numerical"
    MEMORY = "memory"
    SYNC = "sync"


class ExtractionMethod(Enum):
    LLM = "llm"
    MANUAL = "manual"
    PATTERN = "pattern"


@dataclass
class BugFixKnowledge:
    """NPU算子Bug修复知识"""
    bug_id: str
    operator_id: str
    source_repo: str
    source_pr: str

    bug_title: str
    symptom: str
    severity: BugSeverity
    category: BugCategory

    root_cause: Optional[str] = None
    trigger_conditions: List[str] = field(default_factory=list)
    fix_pattern: str = ""
    fix_code_hints: List[str] = field(default_factory=list)
    workarounds: List[str] = field(default_factory=list)

    related_apis: List[str] = field(default_factory=list)
    confidence: float = 0.5
    extraction_method: ExtractionMethod = ExtractionMethod.LLM
    review_status: str = "pending"

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class OptimizationKnowledge:
    """NPU算子优化知识"""
    opt_id: str
    operator_id: str
    source_repo: str
    source_pr: str

    opt_title: str
    optimization_type: List[str]  # 分块/流水/向量化/内存优化等
    optimization_description: str = ""
    optimization_context: str = ""

    improvement_ratio: Optional[float] = None  # 性能提升比例
    before_metrics: Optional[dict] = None
    after_metrics: Optional[dict] = None

    related_apis: List[str] = field(default_factory=list)
    confidence: float = 0.5
    extraction_method: ExtractionMethod = ExtractionMethod.LLM
    review_status: str = "pending"

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class APISourceInfo:
    """API来源信息"""
    source_type: str  # "official" | "community"
    source_url: str
    authority_weight: float = 1.0


@dataclass
class APIParameter:
    """API参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[str] = None


@dataclass
class APIReturnValue:
    """API返回值定义"""
    type: str
    description: str


@dataclass
class UsageExample:
    """API使用示例"""
    scenario: str
    code: str
    注意事项: Optional[str] = None


@dataclass
class AscendCAPIDefinition:
    """AscendC API定义"""
    api_id: str
    canonical_name: str
    full_signature: str

    category: str  # memory/compute/sync/tensor/util
    subcategory: str

    description: str
    parameters: List[APIParameter]
    return_value: APIReturnValue

    version_info: str = ""
    usage_examples: List[UsageExample] = field(default_factory=list)
    注意事项: List[str] = field(default_factory=list)
    禁忌: List[str] = field(default_factory=list)

    source: APISourceInfo = None
    confidence: float = 1.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class KnowledgeStats:
    """知识库统计信息"""
    api_count: int = 0
    operator_count: int = 0
    bug_fix_count: int = 0
    optimization_count: int = 0
    storage_size_mb: float = 0.0
    last_sync_time: Optional[datetime] = None
