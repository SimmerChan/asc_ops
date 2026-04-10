# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
结果融合模块测试
"""

import pytest

from src.asc_ops.ranker.fusion import (
    FusionConfig,
    QueryType,
    Ranker,
    ResultFusion,
    ScoredResult,
    IntentRouter,
)


class TestFusionConfig:
    """FusionConfig 测试"""

    def test_default_weights(self):
        """测试默认权重"""
        config = FusionConfig()

        assert config.vector_weight == 0.6
        assert config.bm25_weight == 0.3
        assert config.confidence_weight == 0.1

    def test_weight_normalization(self):
        """测试权重归一化"""
        # 非归一化权重应该被归一化
        config = FusionConfig(
            vector_weight=0.6,
            bm25_weight=0.3,
            confidence_weight=0.2,
        )

        # 总和应该归一化到 1.0
        total = config.vector_weight + config.bm25_weight + config.confidence_weight
        assert abs(total - 1.0) < 0.01


class TestScoredResult:
    """ScoredResult 测试"""

    def test_score_clamping(self):
        """测试分数钳制"""
        result = ScoredResult(id="test", score=1.5)
        assert result.score == 1.0

        result = ScoredResult(id="test", score=-0.5)
        assert result.score == 0.0

    def test_default_query_type(self):
        """测试默认查询类型"""
        result = ScoredResult(id="test", score=0.5)
        assert result.query_type == QueryType.SEMANTIC


class TestResultFusion:
    """ResultFusion 测试"""

    def test_fuse_with_vector_only(self):
        """测试仅向量结果"""
        fusion = ResultFusion()

        vector_results = [
            ScoredResult(id="1", score=0.9, vector_score=0.9),
            ScoredResult(id="2", score=0.8, vector_score=0.8),
        ]

        confidence_scores = {
            "1": 0.9,
            "2": 0.7,
        }

        fused = fusion.fuse(vector_results, [], confidence_scores)

        assert len(fused) == 2
        assert fused[0].id == "1"
        assert fused[0].confidence_score == 0.9

    def test_fuse_with_bm25(self):
        """测试 BM25 融合"""
        fusion = ResultFusion()

        vector_results = [
            ScoredResult(id="1", score=0.9, vector_score=0.9),
            ScoredResult(id="2", score=0.7, vector_score=0.7),
        ]

        bm25_results = [
            ScoredResult(id="1", score=0.85, bm25_score=0.85),
            ScoredResult(id="3", score=0.8, bm25_score=0.8),
        ]

        fused = fusion.fuse(vector_results, bm25_results, {})

        # doc 1 应该有融合分数
        doc1 = next(r for r in fused if r.id == "1")
        assert doc1.vector_score == 0.9
        assert doc1.bm25_score == 0.85

        # doc 3 只在 BM25 中
        doc3 = next(r for r in fused if r.id == "3")
        assert doc3.vector_score is None
        assert doc3.bm25_score == 0.8

    def test_min_score_threshold(self):
        """测试最低分数阈值"""
        config = FusionConfig(min_score_threshold=0.5)
        fusion = ResultFusion(config)

        vector_results = [
            ScoredResult(id="1", score=0.4, vector_score=0.4),
            ScoredResult(id="2", score=0.9, vector_score=0.9),
        ]

        fused = fusion.fuse(vector_results, [], {})

        # 只返回分数 >= 0.5 的
        assert len(fused) == 1
        assert fused[0].id == "2"

    def test_rerank(self):
        """测试重排序"""
        fusion = ResultFusion()

        results = [
            ScoredResult(id="1", score=0.5, vector_score=0.5),
            ScoredResult(id="2", score=0.8, vector_score=0.8),
            ScoredResult(id="3", score=0.6, vector_score=0.6),
        ]

        reranked = fusion.rerank(results, top_k=2)

        assert len(reranked) == 2
        assert reranked[0].id == "2"
        assert reranked[1].id == "3"


class TestIntentRouter:
    """IntentRouter 测试"""

    def test_classify_semantic(self):
        """测试语义查询分类"""
        router = IntentRouter()

        queries = [
            "how to optimize performance",
            "what is the difference",
            "explain the memory layout",
            "similar to VecReduce",
        ]

        for query in queries:
            assert router.classify(query) == QueryType.SEMANTIC

    def test_classify_exact(self):
        """测试精确查询分类"""
        router = IntentRouter()

        queries = [
            "API function",
            "exact method",
            "specific class",
        ]

        for query in queries:
            assert router.classify(query) == QueryType.EXACT

    def test_classify_default(self):
        """测试默认分类"""
        router = IntentRouter()

        # 没有关键词的查询默认混合
        assert router.classify("random query") == QueryType.HYBRID

    def test_should_use_bm25(self):
        """测试 BM25 使用判断"""
        router = IntentRouter()

        # EXACT 和 HYBRID 查询使用 BM25
        assert router.should_use_bm25("API function") is True  # EXACT
        assert router.should_use_bm25("random query") is True  # HYBRID
        # SEMANTIC 查询不使用 BM25
        assert router.should_use_bm25("how to use this") is False  # SEMANTIC

    def test_should_use_vector(self):
        """测试向量检索使用判断"""
        router = IntentRouter()

        # SEMANTIC 和 HYBRID 查询使用向量检索
        assert router.should_use_vector("how to optimize") is True  # SEMANTIC
        assert router.should_use_vector("random query") is True  # HYBRID
        # EXACT 查询不使用向量检索
        assert router.should_use_vector("API function") is False  # EXACT


class TestRanker:
    """Ranker 测试"""

    def test_rank_with_vector_only(self):
        """测试仅向量结果排序"""
        ranker = Ranker()

        vector_results = [
            ScoredResult(id="1", score=0.6, vector_score=0.6),
            ScoredResult(id="2", score=0.8, vector_score=0.8),
        ]

        confidence_scores = {
            "1": 0.9,
            "2": 0.5,
        }

        ranked = ranker.rank_results(
            "how to use Matmul",
            vector_results,
            confidence_scores=confidence_scores,
        )

        assert len(ranked) == 2
        # doc 2 有更高的向量分数，应该排前
        # (虽然 doc 1 置信度更高，但向量权重更大)
        assert ranked[0].id == "2"

    def test_rank_with_bm25(self):
        """测试混合排序"""
        ranker = Ranker()

        vector_results = [
            ScoredResult(id="1", score=0.9, vector_score=0.9),
        ]

        bm25_results = [
            ScoredResult(id="1", score=0.8, bm25_score=0.8),
            ScoredResult(id="2", score=0.7, bm25_score=0.7),
        ]

        ranked = ranker.rank_results(
            "Matmul API",
            vector_results,
            bm25_results,
        )

        assert len(ranked) == 2

    def test_rank_top_k(self):
        """测试 top_k 限制"""
        ranker = Ranker()

        vector_results = [
            ScoredResult(id=str(i), score=1.0 - i * 0.1, vector_score=1.0 - i * 0.1)
            for i in range(10)
        ]

        ranked = ranker.rank_results(
            "query",
            vector_results,
            top_k=3,
        )

        assert len(ranked) == 3
        assert ranked[0].id == "0"
