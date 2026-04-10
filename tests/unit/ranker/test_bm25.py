# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
BM25 模块测试
"""

import pytest

from src.asc_ops.ranker.bm25 import BM25Document, BM25Index


class TestBM25Document:
    """BM25Document 测试"""

    def test_create_document(self):
        """测试创建文档"""
        doc = BM25Document(
            id="test1",
            terms=["hello", "world", "test"],
        )

        assert doc.id == "test1"
        assert len(doc.terms) == 3
        assert doc.metadata == {}


class TestBM25Index:
    """BM25Index 测试"""

    def test_add_single_document(self):
        """测试添加单个文档"""
        index = BM25Index()

        doc = BM25Document(
            id="doc1",
            terms=["matmul", "optimization", "performance"],
        )

        index.add_document(doc)

        assert index.num_docs == 1
        assert "doc1" in index.documents
        assert index.avg_doc_len == 3.0

    def test_add_multiple_documents(self):
        """测试添加多个文档"""
        index = BM25Index()

        docs = [
            BM25Document(id="doc1", terms=["matmul", "cpu"]),
            BM25Document(id="doc2", terms=["matmul", "npu"]),
            BM25Document(id="doc3", terms=["vecmul", "npu"]),
        ]

        index.add_documents(docs)

        assert index.num_docs == 3

    def test_inverted_index(self):
        """测试倒排索引"""
        index = BM25Index()

        doc = BM25Document(
            id="doc1",
            terms=["matmul", "matmul", "npu"],
        )

        index.add_document(doc)

        assert "matmul" in index.inverted_index
        assert "npu" in index.inverted_index
        assert index.inverted_index["matmul"]["doc1"] == 2  # 出现2次

    def test_search_single_term(self):
        """测试单 term 搜索"""
        index = BM25Index()

        docs = [
            BM25Document(id="doc1", terms=["matmul", "optimization"]),
            BM25Document(id="doc2", terms=["vecmul", "npu"]),
            BM25Document(id="doc3", terms=["matmul", "npu"]),
        ]

        index.add_documents(docs)

        results = index.search("matmul", top_k=10)

        assert len(results) == 2
        result_ids = [r[0].id for r in results]
        assert "doc1" in result_ids
        assert "doc3" in result_ids

    def test_search_multiple_terms(self):
        """测试多 term 搜索"""
        index = BM25Index()

        docs = [
            BM25Document(id="doc1", terms=["matmul", "npu", "optimization"]),
            BM25Document(id="doc2", terms=["vecmul", "npu"]),
            BM25Document(id="doc3", terms=["matmul", "cpu"]),
        ]

        index.add_documents(docs)

        # 搜索 "matmul npu"
        results = index.search("matmul npu", top_k=10)

        # doc1 包含两者, doc2 包含 npu, doc3 包含 matmul
        # doc1 排在最前因为同时匹配两个词
        assert len(results) == 3
        assert results[0][0].id == "doc1"

    def test_search_top_k(self):
        """测试 top_k 限制"""
        index = BM25Index()

        docs = [
            BM25Document(id="doc1", terms=["matmul", "test"]),
            BM25Document(id="doc2", terms=["matmul", "test"]),
            BM25Document(id="doc3", terms=["matmul", "test"]),
            BM25Document(id="doc4", terms=["matmul", "test"]),
            BM25Document(id="doc5", terms=["matmul", "test"]),
        ]

        index.add_documents(docs)

        results = index.search("test", top_k=3)

        assert len(results) == 3
        # 结果应该都是 tuple
        assert all(isinstance(r, tuple) for r in results)

    def test_search_with_scores(self):
        """测试带分数搜索"""
        index = BM25Index()

        docs = [
            BM25Document(id="doc1", terms=["matmul", "matmul", "npu"]),
            BM25Document(id="doc2", terms=["matmul", "npu"]),
        ]

        index.add_documents(docs)

        results = index.search_with_scores("matmul", top_k=10)

        assert len(results) == 2
        # 返回的是 tuple (doc, score)
        assert isinstance(results[0], tuple)
        assert results[0][1] >= results[1][1]  # 分数递减

    def test_search_no_results(self):
        """测试无结果"""
        index = BM25Index()

        doc = BM25Document(id="doc1", terms=["matmul"])
        index.add_document(doc)

        results = index.search("nonexistent", top_k=10)

        assert len(results) == 0

    def test_remove_document(self):
        """测试移除文档"""
        index = BM25Index()

        doc = BM25Document(id="doc1", terms=["matmul", "npu"])
        index.add_document(doc)

        assert index.num_docs == 1

        success = index.remove_document("doc1")

        assert success is True
        assert index.num_docs == 0
        assert "doc1" not in index.documents
        # 倒排索引中的 term 可能仍有键但 doc 列表为空
        assert "doc1" not in index.inverted_index.get("matmul", {})

    def test_remove_nonexistent(self):
        """测试移除不存在的文档"""
        index = BM25Index()

        success = index.remove_document("nonexistent")

        assert success is False

    def test_clear_index(self):
        """测试清空索引"""
        index = BM25Index()

        docs = [
            BM25Document(id="doc1", terms=["matmul"]),
            BM25Document(id="doc2", terms=["npu"]),
        ]

        index.add_documents(docs)

        index.clear()

        assert index.num_docs == 0
        assert len(index.documents) == 0
        assert len(index.inverted_index) == 0

    def test_idf_calculation(self):
        """测试 IDF 计算"""
        index = BM25Index()

        # 添加10个文档，其中3个包含"matmul"
        for i in range(10):
            terms = ["matmul"] if i < 3 else ["other"]
            doc = BM25Document(id=f"doc{i}", terms=terms)
            index.add_document(doc)

        idf = index._calculate_idf("matmul")

        # IDF 应该 > 0
        assert idf > 0

    def test_bm25_score_calculation(self):
        """测试 BM25 分数计算"""
        index = BM25Index(k1=1.5, b=0.75)

        # 添加文档
        doc = BM25Document(id="doc1", terms=["matmul", "npu"])
        index.add_document(doc)

        # 计算单个词的 BM25 分数
        tf = 1
        doc_len = 2
        idf = index._calculate_idf("matmul")

        score = index._calculate_bm25(tf, doc_len, idf)

        # 分数应该 > 0
        assert score > 0

    def test_tokenize(self):
        """测试分词"""
        index = BM25Index()

        terms = index._tokenize("Hello World Test")

        assert "hello" in terms
        assert "world" in terms
        assert "test" in terms
        # 短词应该被过滤
        assert len([t for t in terms if len(t) < 2]) == 0
