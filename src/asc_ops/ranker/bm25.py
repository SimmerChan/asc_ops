# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
BM25 关键词检索模块

提供基于 BM25 的关键词检索能力
"""

import logging
import math
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class BM25Document:
    """BM25 文档"""
    id: str
    terms: List[str]
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BM25Index:
    """
    BM25 索引

    实现 BM25 算法的倒排索引
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        avg_doc_len: float = None,
    ):
        """
        初始化 BM25 索引

        Args:
            k1: BM25 k1 参数 (控制词频饱和)
            b: BM25 b 参数 (文档长度归一化)
            avg_doc_len: 平均文档长度 (自动计算或手动指定)
        """
        self.k1 = k1
        self.b = b
        self.avg_doc_len: float = avg_doc_len or 0.0

        # 文档集合
        self.documents: dict[str, BM25Document] = {}
        self.doc_lengths: dict[str, int] = {}

        # 倒排索引: term -> {doc_id: tf}
        self.inverted_index: dict[str, dict[str, int]] = {}

        # 文档频率: term -> df
        self.doc_freq: dict[str, int] = {}

        # 文档总数
        self.num_docs: int = 0

        logger.info(f"BM25Index initialized: k1={k1}, b={b}")

    def add_document(self, doc: BM25Document) -> None:
        """
        添加文档到索引

        Args:
            doc: BM25 文档
        """
        self.documents[doc.id] = doc
        self.num_docs += 1

        # 计算文档长度
        doc_len = len(doc.terms)
        self.doc_lengths[doc.id] = doc_len

        # 更新平均长度
        self.avg_doc_len = (
            (self.avg_doc_len * (self.num_docs - 1) + doc_len)
            / self.num_docs
        )

        # 更新倒排索引
        term_freqs = Counter(doc.terms)
        for term, tf in term_freqs.items():
            if term not in self.inverted_index:
                self.inverted_index[term] = {}
                self.doc_freq[term] = 0

            self.inverted_index[term][doc.id] = tf
            self.doc_freq[term] += 1

        logger.debug(f"Added document {doc.id}: {doc_len} terms")

    def add_documents(self, docs: List[BM25Document]) -> None:
        """
        批量添加文档

        Args:
            docs: 文档列表
        """
        for doc in docs:
            self.add_document(doc)

    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> List[tuple["BM25Document", float]]:
        """
        搜索文档

        Args:
            query: 查询字符串
            top_k: 返回前 k 个结果
            min_score: 最低分数阈值

        Returns:
            List[tuple[BM25Document, float]]: 按 BM25 分数排序的 (文档, 分数) 列表
        """
        # 解析查询词
        query_terms = self._tokenize(query)

        if not query_terms:
            return []

        # 计算每个文档的 BM25 分数
        scores: dict[str, float] = {}

        for term in query_terms:
            if term not in self.inverted_index:
                continue

            # IDF
            idf = self._calculate_idf(term)

            # 对每个包含该词的文档计算分数
            for doc_id, tf in self.inverted_index[term].items():
                doc_len = self.doc_lengths[doc_id]
                score = self._calculate_bm25(tf, doc_len, idf)

                if doc_id not in scores:
                    scores[doc_id] = 0.0
                scores[doc_id] += score

        # 排序
        sorted_docs = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # 构建结果
        results = []
        for doc_id, score in sorted_docs:
            if score < min_score:
                break
            if len(results) >= top_k:
                break
            results.append((self.documents[doc_id], score))

        logger.debug(
            f"BM25 search for '{query}': "
            f"{len(query_terms)} terms, {len(results)} results"
        )

        return results

    def search_with_scores(
        self,
        query: str,
        top_k: int = 10,
    ) -> List[tuple[BM25Document, float]]:
        """
        搜索文档并返回分数

        Args:
            query: 查询字符串
            top_k: 返回前 k 个结果

        Returns:
            List[tuple[BM25Document, float]]: (文档, 分数) 列表
        """
        return self.search(query, top_k, min_score=0.0)

    def _calculate_idf(self, term: str) -> float:
        """
        计算 IDF (逆文档频率)

        Args:
            term: 词项

        Returns:
            float: IDF 值
        """
        if term not in self.doc_freq:
            return 0.0

        df = self.doc_freq[term]

        # 平滑的 IDF 计算
        # log((N - df + 0.5) / (df + 0.5))
        return math.log(
            (self.num_docs - df + 0.5) / (df + 0.5) + 1.0
        )

    def _calculate_bm25(
        self,
        tf: int,
        doc_len: int,
        idf: float,
    ) -> float:
        """
        计算 BM25 分数

        Args:
            tf: 词频
            doc_len: 文档长度
            idf: 逆文档频率

        Returns:
            float: BM25 分数
        """
        # BM25 公式: IDF * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_doc_len))
        numerator = tf * (self.k1 + 1)
        denominator = tf + self.k1 * (
            1 - self.b + self.b * doc_len / self.avg_doc_len
        )

        return idf * numerator / denominator

    def _tokenize(self, text: str) -> List[str]:
        """
        分词

        Args:
            text: 输入文本

        Returns:
            List[str]: 词项列表
        """
        # 简单分词: 转小写, 按空白字符分割, 过滤短词
        terms = text.lower().split()
        return [t for t in terms if len(t) >= 2]

    def get_document(self, doc_id: str) -> Optional[BM25Document]:
        """
        获取文档

        Args:
            doc_id: 文档 ID

        Returns:
            Optional[BM25Document]: 文档对象
        """
        return self.documents.get(doc_id)

    def remove_document(self, doc_id: str) -> bool:
        """
        从索引中移除文档

        Args:
            doc_id: 文档 ID

        Returns:
            bool: 是否成功移除
        """
        if doc_id not in self.documents:
            return False

        doc = self.documents[doc_id]

        # 从倒排索引中移除
        for term in doc.terms:
            if term in self.inverted_index:
                if doc_id in self.inverted_index[term]:
                    del self.inverted_index[term][doc_id]
                    self.doc_freq[term] -= 1

        # 更新状态
        del self.documents[doc_id]
        del self.doc_lengths[doc_id]
        self.num_docs -= 1

        # 重新计算平均长度
        if self.num_docs > 0:
            self.avg_doc_len = sum(self.doc_lengths.values()) / self.num_docs
        else:
            self.avg_doc_len = 0.0

        logger.debug(f"Removed document {doc_id}")
        return True

    def clear(self) -> None:
        """清空索引"""
        self.documents.clear()
        self.doc_lengths.clear()
        self.inverted_index.clear()
        self.doc_freq.clear()
        self.num_docs = 0
        self.avg_doc_len = 0.0
        logger.info("BM25 index cleared")
