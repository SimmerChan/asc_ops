# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
API 知识采集模块

负责从昇腾官方文档发现 API 链接并解析详情
"""

from .link_discovery import LinkDiscoveryResult, APILink, discover_api_links
from .official_docs import OfficialDocsClient
from .parsers import (
    ParsingResult,
    parse_api_page,
    APIParserError,
    ParsingDegradedError,
)
from .section_parser import SectionParser
from .embedder import APIEmbedder, MockEmbedder, EmbeddingResult
from .api_storage import APIStorage, APIStorageError
from .retry import (
    RetryConfig,
    RetryContext,
    RetryStrategy,
    RetryState,
    RetryExhaustedError,
    retry_with_backoff,
)
from .checkpoint import (
    CollectionCheckpoint,
    CheckpointManager,
    FailedAPI,
)
from .rate_limiter import (
    RateLimitConfig,
    AdaptiveRateLimiter,
    ConcurrencyLimiter,
    QueueFullError,
)

__all__ = [
    # Link discovery
    "LinkDiscoveryResult",
    "APILink",
    "discover_api_links",
    # Official docs client
    "OfficialDocsClient",
    # Parsers
    "ParsingResult",
    "parse_api_page",
    "APIParserError",
    "ParsingDegradedError",
    "SectionParser",
    # Embedding
    "APIEmbedder",
    "MockEmbedder",
    "EmbeddingResult",
    # Storage
    "APIStorage",
    "APIStorageError",
    # Retry
    "RetryConfig",
    "RetryContext",
    "RetryStrategy",
    "RetryState",
    "RetryExhaustedError",
    "retry_with_backoff",
    # Checkpoint
    "CollectionCheckpoint",
    "CheckpointManager",
    "FailedAPI",
    # Rate limiting
    "RateLimitConfig",
    "AdaptiveRateLimiter",
    "ConcurrencyLimiter",
    "QueueFullError",
]
