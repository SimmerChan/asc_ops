# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Collections 配置单元测试
"""

import pytest

from asc_ops.storage.collections import (
    CollectionType,
    COLLECTION_CONFIGS,
    get_collection_config,
    get_collection_name,
    get_all_collection_names,
    ensure_collection_exists,
)
from asc_ops.storage.chroma_client import ChromaDBClient


class TestCollectionType:
    """CollectionType 枚举测试"""

    def test_collection_types(self):
        """测试 collection 类型定义"""
        assert CollectionType.ASCEND_APIS.value == "ascend_apis"
        assert CollectionType.BUG_FIXES.value == "bug_fixes"
        assert CollectionType.OPTIMIZATIONS.value == "optimizations"

    def test_all_collection_types_have_config(self):
        """测试所有 collection 类型都有配置"""
        for collection_type in CollectionType:
            assert collection_type in COLLECTION_CONFIGS
            config = COLLECTION_CONFIGS[collection_type]
            assert "name" in config
            assert "metadata" in config
            assert "index_params" in config


class TestCollectionConfigs:
    """Collection 配置测试"""

    def test_ascend_apis_config(self):
        """测试 ASCEND_APIS 配置"""
        config = COLLECTION_CONFIGS[CollectionType.ASCEND_APIS]
        assert config["name"] == "ascend_apis"
        assert config["metadata"]["knowledge_type"] == "api"

    def test_bug_fixes_config(self):
        """测试 BUG_FIXES 配置"""
        config = COLLECTION_CONFIGS[CollectionType.BUG_FIXES]
        assert config["name"] == "bug_fixes"
        assert config["metadata"]["knowledge_type"] == "bug_fix"

    def test_optimizations_config(self):
        """测试 OPTIMIZATIONS 配置"""
        config = COLLECTION_CONFIGS[CollectionType.OPTIMIZATIONS]
        assert config["name"] == "optimizations"
        assert config["metadata"]["knowledge_type"] == "optimization"


class TestCollectionHelperFunctions:
    """Collection 辅助函数测试"""

    def test_get_collection_config(self):
        """测试获取 collection 配置"""
        config = get_collection_config(CollectionType.ASCEND_APIS)
        assert config["name"] == "ascend_apis"
        assert "metadata" in config

    def test_get_collection_name(self):
        """测试获取 collection 名称"""
        name = get_collection_name(CollectionType.BUG_FIXES)
        assert name == "bug_fixes"

    def test_get_all_collection_names(self):
        """测试获取所有 collection 名称"""
        names = get_all_collection_names()
        assert "ascend_apis" in names
        assert "bug_fixes" in names
        assert "optimizations" in names
        assert "cross_platform_mappings" in names
        assert len(names) == 4


class TestEnsureCollectionExists:
    """ensure_collection_exists 函数测试"""

    @pytest.fixture
    def client(self, tmp_path):
        """创建临时 ChromaDB 客户端"""
        return ChromaDBClient(persist_directory=str(tmp_path))

    def test_creates_collection_if_not_exists(self, client):
        """测试创建不存在的 collection"""
        # 确保不存在
        from chromadb.errors import NotFoundError

        with pytest.raises(NotFoundError):
            client.get_collection("ascend_apis")

        # 创建
        collection = ensure_collection_exists(client, CollectionType.ASCEND_APIS)
        assert collection is not None
        assert collection.name == "ascend_apis"

    def test_returns_existing_collection(self, client):
        """测试返回已存在的 collection"""
        # 先创建
        ensure_collection_exists(client, CollectionType.ASCEND_APIS)

        # 再获取
        collection = ensure_collection_exists(client, CollectionType.ASCEND_APIS)
        assert collection.name == "ascend_apis"

    def test_creates_all_collections(self, client):
        """测试创建所有 collections"""
        for collection_type in CollectionType:
            collection = ensure_collection_exists(client, collection_type)
            assert collection.name == collection_type.value
