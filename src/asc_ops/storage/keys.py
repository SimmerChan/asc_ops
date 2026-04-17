# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Redis Key 命名空间管理

统一定义和管理 Redis key 的命名空间，避免 key 冲突
"""

from enum import Enum
from typing import Optional


class KeyNamespace(Enum):
    """Redis Key 命名空间"""

    # API 相关
    API = "api"
    # 算子相关
    OPERATOR = "operator"
    # PR 相关
    PR = "pr"
    # 同步状态
    SYNC = "sync"
    # 采集进度
    PROGRESS = "progress"
    # 配置
    CONFIG = "config"
    # 临时数据
    TEMP = "temp"
    # 跨平台映射
    MAPPING = "mapping"


# Key 模式定义
class KeyPattern:
    """Redis Key 模式"""

    # API 相关 Keys
    API_INDEX = "api:{api_id}"  # API 索引信息
    API_LIST = "api:list"  # API ID 列表
    API_CATEGORY = "api:category:{category}"  # 按类别组织的 API

    # 算子相关 Keys
    OPERATOR_INDEX = "operator:{operator_id}"  # 算子索引信息
    OPERATOR_BUGS = "operator:{operator_id}:bugs"  # 算子的 Bug 列表
    OPERATOR_OPTS = "operator:{operator_id}:opts"  # 算子的优化列表
    OPERATOR_LIST = "operator:list"  # 算子 ID 列表

    # PR 相关 Keys
    PR_META = "pr:{repo}:{pr_number}"  # PR 元数据

    # 同步相关 Keys
    SYNC_STATUS = "sync:status"  # 同步状态
    SYNC_LOCK = "sync:lock"  # 同步锁

    # 采集进度 Keys
    PROGRESS_API = "progress:api_collection"  # API 采集进度
    PROGRESS_BUG = "progress:bug_extraction"  # Bug 知识采集进度
    PROGRESS_OPT = "progress:opt_extraction"  # 优化知识采集进度

    # 配置 Keys
    CONFIG_LAST_SYNC = "config:last_sync"  # 上次同步时间

    # 跨平台映射 Keys
    MAPPING_INDEX = "mapping:{mapping_id}"  # 映射索引信息
    MAPPING_LIST = "mapping:list"  # 映射 ID 列表
    MAPPING_SOURCE = "mapping:{mapping_id}:source"  # 映射来源 (llm_high_conf/llm_suggested)
    MAPPING_GPU_API = "mapping:gpu:{gpu_api}"  # 按 GPU API 索引的映射


def build_key(pattern: str, **kwargs: str) -> str:
    """
    根据模式构建 Redis key

    Args:
        pattern: Key 模式
        **kwargs: 模式参数

    Returns:
        完整的 Redis key

    Example:
        >>> build_key(KeyPattern.API_INDEX, api_id="Exp")
        'api:Exp'
    """
    return pattern.format(**kwargs)


def parse_key(key: str, pattern: str) -> Optional[dict]:
    """
    解析 Redis key，提取模式参数

    Args:
        key: 完整的 Redis key
        pattern: Key 模式

    Returns:
        模式参数字典，如果解析失败则返回 None

    Example:
        >>> parse_key('api:Exp', KeyPattern.API_INDEX)
        {'api_id': 'Exp'}
    """
    try:
        # 将模式转换为正则表达式
        import re

        regex_pattern = pattern.replace("{", "(?P<").replace(
            "}", ">[^:]+)"
        )
        # 处理没有参数的简单模式
        if "{" not in pattern:
            if key == pattern:
                return {}
            return None

        match = re.match(f"^{regex_pattern}$", key)
        if match:
            return match.groupdict()
        return None
    except Exception:
        return None


# 便捷函数
def api_key(api_id: str) -> str:
    """构建 API key"""
    return build_key(KeyPattern.API_INDEX, api_id=api_id)


def operator_key(operator_id: str) -> str:
    """构建算子 key"""
    return build_key(KeyPattern.OPERATOR_INDEX, operator_id=operator_id)


def pr_key(repo: str, pr_number: str) -> str:
    """构建 PR key"""
    return build_key(KeyPattern.PR_META, repo=repo, pr_number=pr_number)


def progress_key(progress_type: str) -> str:
    """构建采集进度 key"""
    return f"progress:{progress_type}"


def sync_lock_key() -> str:
    """获取同步锁 key"""
    return KeyPattern.SYNC_LOCK


def sync_status_key() -> str:
    """获取同步状态 key"""
    return KeyPattern.SYNC_STATUS
