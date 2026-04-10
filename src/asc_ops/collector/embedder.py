# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
API 向量化器

使用 sentence-transformers 生成 API 的向量表示
"""

import logging
import hashlib
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _check_sentence_transformers():
    """检查 sentence_transformers 是否可用"""
    try:
        from sentence_transformers import SentenceTransformer
        return True
    except (ImportError, Exception):
        # 捕获更广泛的异常，包括 TypeError 等
        return False


SENTENCE_TRANSFORMERS_AVAILABLE = _check_sentence_transformers()


@dataclass
class EmbeddingResult:
    """向量化结果"""
    api_id: str
    embedding: List[float]
    text: str  # 用于生成向量的原始文本


class APIEmbedder:
    """
    API 向量化器

    将 API 信息转换为向量表示
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
        embedding_dim: Optional[int] = None,
        batch_size: int = 32,
    ):
        """
        初始化向量化器

        Args:
            model_name: 模型名称 (默认 all-MiniLM-L6-v2)
            model_path: 本地模型路径 (可选)
            embedding_dim: 向量维度 (可选，用于验证)
            batch_size: 批处理大小

        Raises:
            ImportError: 如果 sentence_transformers 不可用
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence_transformers is not available. "
                "Please install it: pip install sentence-transformers"
            )

        from sentence_transformers import SentenceTransformer
        from ..config import get_config

        config = get_config()

        self.model_name = model_name or config.embedding.model_name
        self.model_path = model_path or config.embedding.model_path
        self.embedding_dim = embedding_dim or config.embedding.embedding_dim
        self.batch_size = batch_size or config.embedding.batch_size

        logger.info(f"Loading embedding model: {self.model_name}")
        self._model = SentenceTransformer(
            self.model_name,
            cache_folder=self.model_path,
        )

        # 验证维度
        if self.embedding_dim:
            test_embedding = self._model.encode("test")
            actual_dim = len(test_embedding)
            if actual_dim != self.embedding_dim:
                logger.warning(
                    f"Embedding dimension mismatch: expected {self.embedding_dim}, "
                    f"got {actual_dim}"
                )

        logger.info(
            f"API Embedder initialized: model={self.model_name}, "
            f"batch_size={self.batch_size}"
        )

    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        批量编码文本为向量

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        if not texts:
            return []

        embeddings = self._model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=len(texts) > 10,
            convert_to_numpy=True,
        )

        return [emb.tolist() for emb in embeddings]

    def encode_api(self, api_text: str) -> List[float]:
        """
        编码单个 API 文本

        Args:
            api_text: API 文本

        Returns:
            向量
        """
        embedding = self._model.encode(api_text, convert_to_numpy=True)
        return embedding.tolist()

    def build_api_text(
        self,
        api_name: str,
        signature: str,
        description: str,
        parameters: List[dict],
        return_value: str,
        category: str = "",
    ) -> str:
        """
        构建 API 的文本表示

        Args:
            api_name: API 名称
            signature: 函数签名
            description: 描述
            parameters: 参数列表
            return_value: 返回值
            category: 分类

        Returns:
            用于向量化的文本
        """
        parts = []

        # 分类
        if category:
            parts.append(f"分类: {category}")

        # 函数签名
        if signature:
            parts.append(f"签名: {signature}")

        # 描述
        if description:
            parts.append(f"描述: {description}")

        # 参数
        if parameters:
            param_strs = []
            for p in parameters:
                param_strs.append(
                    f"{p.get('name', 'unknown')}: {p.get('type', 'unknown')} - {p.get('description', '')}"
                )
            parts.append(f"参数: {', '.join(param_strs)}")

        # 返回值
        if return_value:
            parts.append(f"返回值: {return_value}")

        return " | ".join(parts)

    def embed_api(
        self,
        api_id: str,
        api_name: str,
        signature: str,
        description: str,
        parameters: List[dict],
        return_value: str,
        category: str = "",
    ) -> EmbeddingResult:
        """
        向量化单个 API

        Args:
            api_id: API ID
            api_name: API 名称
            signature: 函数签名
            description: 描述
            parameters: 参数列表
            return_value: 返回值
            category: 分类

        Returns:
            EmbeddingResult
        """
        text = self.build_api_text(
            api_name=api_name,
            signature=signature,
            description=description,
            parameters=parameters,
            return_value=return_value,
            category=category,
        )

        embedding = self.encode_api(text)

        return EmbeddingResult(
            api_id=api_id,
            embedding=embedding,
            text=text,
        )

    def embed_apis_batch(
        self,
        apis: List[dict],
    ) -> List[EmbeddingResult]:
        """
        批量向量化 APIs

        Args:
            apis: API 信息列表，每项包含:
                - api_id
                - name
                - signature
                - description
                - parameters
                - return_value
                - category

        Returns:
            EmbeddingResult 列表
        """
        if not apis:
            return []

        # 构建文本
        texts = []
        for api in apis:
            text = self.build_api_text(
                api_name=api.get("name", ""),
                signature=api.get("signature", ""),
                description=api.get("description", ""),
                parameters=api.get("parameters", []),
                return_value=api.get("return_value", ""),
                category=api.get("category", ""),
            )
            texts.append(text)

        # 批量编码
        embeddings = self.encode(texts)

        # 构建结果
        results = []
        for i, api in enumerate(apis):
            results.append(EmbeddingResult(
                api_id=api.get("api_id", f"api_{i}"),
                embedding=embeddings[i],
                text=texts[i],
            ))

        return results


class MockEmbedder:
    """
    Mock 向量化器 (用于测试或 sentence_transformers 不可用时)

    使用简单的 hash 作为伪向量
    """

    def __init__(self, embedding_dim: int = 384):
        self.embedding_dim = embedding_dim
        logger.warning("Using MockEmbedder - not suitable for production")

    def encode(self, texts: List[str]) -> List[List[float]]:
        """生成伪向量"""
        return [self._text_to_fake_embedding(t) for t in texts]

    def encode_api(self, api_text: str) -> List[float]:
        """生成单个伪向量"""
        return self._text_to_fake_embedding(api_text)

    def _text_to_fake_embedding(self, text: str) -> List[float]:
        """将文本转换为伪向量"""
        # 使用 hash 生成确定性的伪随机向量
        embedding = []
        hash_input = text.encode("utf-8")
        for i in range(self.embedding_dim):
            h = hashlib.sha256(hash_input + str(i).encode()).digest()
            value = (h[0] + h[1] * 256) / 65535.0  # 归一化到 [0, 1]
            embedding.append(value)
        return embedding

    def build_api_text(self, **kwargs) -> str:
        """同 APIEmbedder"""
        parts = []
        if kwargs.get("category"):
            parts.append(f"分类: {kwargs['category']}")
        if kwargs.get("signature"):
            parts.append(f"签名: {kwargs['signature']}")
        if kwargs.get("description"):
            parts.append(f"描述: {kwargs['description']}")
        return " | ".join(parts)

    def embed_api(self, **kwargs) -> EmbeddingResult:
        """生成伪嵌入结果"""
        text = self.build_api_text(
            api_name=kwargs.get("api_name", ""),
            signature=kwargs.get("signature", ""),
            description=kwargs.get("description", ""),
            parameters=kwargs.get("parameters", []),
            return_value=kwargs.get("return_value", ""),
            category=kwargs.get("category", ""),
        )
        return EmbeddingResult(
            api_id=kwargs.get("api_id", ""),
            embedding=self.encode_api(text),
            text=text,
        )

    def embed_apis_batch(self, apis: List[dict]) -> List[EmbeddingResult]:
        """批量生成伪嵌入"""
        return [self.embed_api(**api) for api in apis]
