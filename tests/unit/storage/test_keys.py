# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Redis Key 命名空间管理单元测试
"""

import pytest

from asc_ops.storage.keys import (
    KeyNamespace,
    KeyPattern,
    build_key,
    parse_key,
    api_key,
    operator_key,
    pr_key,
    progress_key,
    sync_lock_key,
    sync_status_key,
)


class TestKeyNamespace:
    """KeyNamespace 枚举测试"""

    def test_all_namespaces(self):
        """测试所有命名空间定义"""
        assert KeyNamespace.API.value == "api"
        assert KeyNamespace.OPERATOR.value == "operator"
        assert KeyNamespace.PR.value == "pr"
        assert KeyNamespace.SYNC.value == "sync"
        assert KeyNamespace.PROGRESS.value == "progress"
        assert KeyNamespace.CONFIG.value == "config"
        assert KeyNamespace.TEMP.value == "temp"


class TestKeyPattern:
    """KeyPattern 测试"""

    def test_patterns(self):
        """测试 key 模式定义"""
        assert KeyPattern.API_INDEX == "api:{api_id}"
        assert KeyPattern.OPERATOR_INDEX == "operator:{operator_id}"
        assert KeyPattern.PR_META == "pr:{repo}:{pr_number}"
        assert KeyPattern.SYNC_STATUS == "sync:status"
        assert KeyPattern.PROGRESS_API == "progress:api_collection"


class TestBuildKey:
    """build_key 函数测试"""

    def test_build_api_key(self):
        """测试构建 API key"""
        key = build_key(KeyPattern.API_INDEX, api_id="Exp")
        assert key == "api:Exp"

    def test_build_operator_key(self):
        """测试构建算子 key"""
        key = build_key(KeyPattern.OPERATOR_INDEX, operator_id="Matmul")
        assert key == "operator:Matmul"

    def test_build_pr_key(self):
        """测试构建 PR key"""
        key = build_key(KeyPattern.PR_META, repo="ops-nn", pr_number="123")
        assert key == "pr:ops-nn:123"

    def test_build_key_with_special_chars(self):
        """测试构建带特殊字符的 key"""
        key = build_key(KeyPattern.API_INDEX, api_id="Vec_Add_128")
        assert key == "api:Vec_Add_128"


class TestParseKey:
    """parse_key 函数测试"""

    def test_parse_api_key(self):
        """测试解析 API key"""
        params = parse_key("api:Exp", KeyPattern.API_INDEX)
        assert params == {"api_id": "Exp"}

    def test_parse_operator_key(self):
        """测试解析算子 key"""
        params = parse_key("operator:Matmul", KeyPattern.OPERATOR_INDEX)
        assert params == {"operator_id": "Matmul"}

    def test_parse_pr_key(self):
        """测试解析 PR key"""
        params = parse_key("pr:ops-nn:123", KeyPattern.PR_META)
        assert params == {"repo": "ops-nn", "pr_number": "123"}

    def test_parse_invalid_key(self):
        """测试解析无效的 key"""
        params = parse_key("invalid:key", KeyPattern.API_INDEX)
        assert params is None

    def test_parse_simple_pattern_match(self):
        """测试解析简单模式匹配"""
        params = parse_key("sync:status", "sync:status")
        assert params == {}


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_api_key(self):
        """测试 api_key 函数"""
        assert api_key("Exp") == "api:Exp"

    def test_operator_key(self):
        """测试 operator_key 函数"""
        assert operator_key("Matmul") == "operator:Matmul"

    def test_pr_key(self):
        """测试 pr_key 函数"""
        assert pr_key("ops-nn", "123") == "pr:ops-nn:123"

    def test_progress_key(self):
        """测试 progress_key 函数"""
        assert progress_key("api_collection") == "progress:api_collection"

    def test_sync_lock_key(self):
        """测试 sync_lock_key 函数"""
        assert sync_lock_key() == "sync:lock"

    def test_sync_status_key(self):
        """测试 sync_status_key 函数"""
        assert sync_status_key() == "sync:status"
