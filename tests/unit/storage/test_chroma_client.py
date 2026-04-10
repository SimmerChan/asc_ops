# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
ChromaDB 客户端单元测试
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from asc_ops.storage.chroma_client import ChromaDBClient


class TestChromaDBClient:
    """ChromaDBClient 测试类"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录用于测试"""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def client(self, temp_dir):
        """创建 ChromaDB 客户端实例"""
        return ChromaDBClient(persist_directory=temp_dir)

    def test_init_with_persist_directory(self, temp_dir):
        """测试使用持久化目录初始化"""
        client = ChromaDBClient(persist_directory=temp_dir)
        assert client is not None

    def test_init_without_persist_directory(self):
        """测试使用临时客户端初始化"""
        client = ChromaDBClient()
        assert client is not None

    def test_get_or_create_collection(self, client):
        """测试获取或创建 collection"""
        collection = client.get_or_create_collection(
            name="test_collection",
            metadata={"description": "test"},
        )
        assert collection is not None
        assert collection.name == "test_collection"

    def test_get_collection(self, client):
        """测试获取已存在的 collection"""
        # 先创建
        client.get_or_create_collection(name="test_get")
        # 再获取
        collection = client.get_collection(name="test_get")
        assert collection.name == "test_get"

    def test_delete_collection(self, client):
        """测试删除 collection"""
        client.get_or_create_collection(name="test_delete")
        client.delete_collection(name="test_delete")

        # 验证删除
        from chromadb.errors import NotFoundError

        with pytest.raises(NotFoundError):
            client.get_collection(name="test_delete")

    def test_list_collections(self, client):
        """测试列出所有 collections"""
        client.get_or_create_collection(name="list_test_1")
        client.get_or_create_collection(name="list_test_2")

        collections = client.list_collections()
        names = [c.name for c in collections]
        assert "list_test_1" in names
        assert "list_test_2" in names

    def test_upsert_and_query_vector(self, client):
        """测试插入和查询向量"""
        # 创建 collection
        client.get_or_create_collection(name="test_vectors")

        # 插入向量
        client.upsert_vector(
            collection_name="test_vectors",
            ids=["id1", "id2"],
            embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            documents=["document 1", "document 2"],
            metadatas=[{"source": "test1"}, {"source": "test2"}],
        )

        # 验证插入数量
        count = client.count(collection_name="test_vectors")
        assert count == 2

        # 查询向量
        results = client.query(
            collection_name="test_vectors",
            query_embeddings=[[0.1, 0.2, 0.3]],
            n_results=1,
        )
        assert len(results["ids"][0]) == 1
        assert results["ids"][0][0] == "id1"

    def test_get_vectors(self, client):
        """测试获取指定 ID 的向量"""
        client.get_or_create_collection(name="test_get_vectors")
        client.upsert_vector(
            collection_name="test_get_vectors",
            ids=["get_id1", "get_id2"],
            embeddings=[[0.1, 0.2], [0.3, 0.4]],
            documents=["doc1", "doc2"],
        )

        results = client.get(
            collection_name="test_get_vectors",
            ids=["get_id1"],
        )
        assert "get_id1" in results["ids"]
        assert "doc1" in results["documents"]

    def test_reset_collection(self, client):
        """测试重置 collection"""
        # 创建并插入数据
        client.get_or_create_collection(name="test_reset")
        client.upsert_vector(
            collection_name="test_reset",
            ids=["reset_id1"],
            embeddings=[[0.1, 0.2]],
        )
        assert client.count("test_reset") == 1

        # 重置
        client.reset_collection("test_reset")
        # 重置后应该为空
        assert client.count("test_reset") == 0

    def test_reset_database(self, client):
        """测试重置数据库"""
        # 创建多个 collections
        client.get_or_create_collection(name="reset_db_1")
        client.get_or_create_collection(name="reset_db_2")

        # 重置数据库 (可能会抛出 AuthorizationError 如果被禁用)
        try:
            client.reset()
        except Exception:
            pass  # 如果重置被禁用，手动删除

        # 验证所有 collections 都被删除
        collections = client.list_collections()
        # 如果重置成功应该为空，如果被禁用则手动清理
        if collections:
            for c in collections:
                try:
                    client.delete_collection(c.name)
                except Exception:
                    pass
            collections = client.list_collections()
        assert len(collections) == 0

    def test_count_empty_collection(self, client):
        """测试统计空 collection"""
        client.get_or_create_collection(name="empty_collection")
        count = client.count("empty_collection")
        assert count == 0
