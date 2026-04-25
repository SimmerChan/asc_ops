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
            model_name: 模型名称 (默认 Qwen/Qwen3-Embedding-0.6B)
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


class QwenEmbedder:
    """
    Qwen3-Embedding 向量化器

    使用 transformers 直接加载 Qwen3-Embedding 模型
    支持 MRL (Matryoshka Representation Learning) 输出可变维度
    支持 Apple Silicon MPS / CUDA / CPU
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Embedding-0.6B",
        model_path: Optional[str] = None,
        embedding_dim: int = 1024,
        batch_size: int = 8,
        device: str = "mps",
    ):
        """
        初始化 Qwen 向量化器

        Args:
            model_name: 模型名称
            model_path: 本地模型路径 (可选)
            embedding_dim: 输出向量维度 (MRL支持, 0.6B支持32-1024)
            batch_size: 批处理大小
            device: 设备 "mps"(Apple Silicon) / "cuda" / "cpu"
        """
        self.model_name = model_name
        self.embedding_dim = embedding_dim
        self.batch_size = batch_size

        # 确定模型路径: 本地路径优先，否则使用 HuggingFace 模型名
        import os
        if model_path and os.path.isdir(model_path):
            # 本地路径直接使用
            model_to_load = model_path
            logger.info(f"Loading Qwen3-Embedding from local path: {model_path}")
        else:
            # 使用 HuggingFace 模型名
            model_to_load = model_name
            logger.info(f"Loading Qwen3-Embedding model: {model_name}, dim={embedding_dim}")

        from transformers import AutoTokenizer, AutoModel

        self._tokenizer = AutoTokenizer.from_pretrained(
            model_to_load,
            trust_remote_code=True,
        )

        # 设备选择: mps (Apple Silicon) > cuda > cpu
        import torch
        if device == "mps" and torch.backends.mps.is_available():
            # MPS 需要 bfloat16 才能正常工作
            self._model = AutoModel.from_pretrained(
                model_to_load,
                trust_remote_code=True,
                dtype=torch.bfloat16,
            )
            self._model = self._model.to("mps")
            self._device = "mps"
        elif device == "cuda" and torch.cuda.is_available():
            self._model = AutoModel.from_pretrained(
                model_to_load,
                trust_remote_code=True,
            )
            self._model = self._model.cuda()
            self._device = "cuda"
        else:
            self._model = AutoModel.from_pretrained(
                model_to_load,
                trust_remote_code=True,
            )
            self._model.eval()
            self._device = "cpu"

        logger.info(f"QwenEmbedder initialized on {self._device}")

    def _mean_pooling(self, last_hidden_state: "torch.Tensor", attention_mask: "torch.Tensor") -> "torch.Tensor":
        """Mean pooling - 平均池化"""
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
        return torch.sum(last_hidden_state * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    def _last_token_pool(self, last_hidden_state: "torch.Tensor", attention_mask: "torch.Tensor") -> "torch.Tensor":
        """Last token pooling - Qwen3-Embedding 推荐的方式"""
        import torch
        left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
        if left_padding:
            return last_hidden_state[:, -1]
        else:
            sequence_lengths = attention_mask.sum(dim=1) - 1
            batch_size = last_hidden_state.shape[0]
            return last_hidden_state[torch.arange(batch_size, device=last_hidden_state.device), sequence_lengths]

    def _normalize(self, embeddings: "torch.Tensor") -> "torch.Tensor":
        """L2 归一化"""
        import torch
        norms = torch.norm(embeddings, p=2, dim=1, keepdim=True)
        return embeddings / norms

    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        批量编码文本为向量

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        import torch

        if not texts:
            return []

        all_embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]

            # Tokenize
            inputs = self._tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=8192,  # Qwen3-Embedding 支持 32K
                return_tensors="pt",
            )

            # 移动到设备
            if self._device in ("cuda", "mps"):
                inputs = {k: v.to(self._device) for k, v in inputs.items()}

            # 前向传播
            with torch.no_grad():
                outputs = self._model(**inputs)
                last_hidden_state = outputs.last_hidden_state

                # Last token pooling
                embeddings = self._last_token_pool(last_hidden_state, inputs["attention_mask"])

                # MRL: 如果 embedding_dim < 2560，取前 dim 维
                if self.embedding_dim < 2560:
                    embeddings = embeddings[:, :self.embedding_dim]

                # L2 归一化
                embeddings = self._normalize(embeddings)

            # 转换为 list
            all_embeddings.extend(embeddings.float().cpu().numpy().tolist())

        return all_embeddings

    def encode_api(self, api_text: str) -> List[float]:
        """
        编码单个 API 文本

        Args:
            api_text: API 文本

        Returns:
            向量
        """
        result = self.encode([api_text])
        return result[0] if result else []

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

        # API 名称
        if api_name:
            parts.append(f"API名称: {api_name}")

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
            apis: API 信息列表

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
                embedding=embeddings[i] if i < len(embeddings) else [],
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


# 全局 Embedder 单例
_embedder_instance: Optional["EmbedderInterface"] = None


def get_embedder() -> "EmbedderInterface":
    """
    获取全局 Embedder 实例（单例）

    统一从 .env 配置读取 EMBEDDING_* 环境变量创建 Embedder
    优先使用 QwenEmbedder，其次 sentence_transformers，最后 MockEmbedder
    带有 fallback 逻辑：某类 embedder 初始化失败时自动降级

    Returns:
        EmbedderInterface 实例
    """
    global _embedder_instance
    if _embedder_instance is None:
        from ..config import get_config
        config = get_config().embedding

        embedder_type = config.embedder_type.lower()

        if embedder_type == "qwen":
            try:
                _embedder_instance = QwenEmbedder(
                    model_name=config.model_name,
                    model_path=config.model_path,
                    embedding_dim=config.embedding_dim or 1024,
                    batch_size=config.batch_size,
                    device=config.device,
                )
                logger.info("Global embedder initialized: QwenEmbedder")
            except Exception as e:
                logger.warning(f"QwenEmbedder failed: {e}, falling back to MockEmbedder")
                _embedder_instance = MockEmbedder(embedding_dim=384)

        elif embedder_type == "sentence_transformers":
            try:
                _embedder_instance = APIEmbedder(
                    model_name=config.model_name,
                    model_path=config.model_path,
                    embedding_dim=config.embedding_dim,
                    batch_size=config.batch_size,
                )
                logger.info("Global embedder initialized: APIEmbedder (sentence_transformers)")
            except ImportError:
                logger.warning("sentence_transformers not available, using MockEmbedder")
                _embedder_instance = MockEmbedder(embedding_dim=config.embedding_dim or 384)
            except Exception as e:
                logger.warning(f"APIEmbedder failed: {e}, falling back to MockEmbedder")
                _embedder_instance = MockEmbedder(embedding_dim=config.embedding_dim or 384)

        else:
            if embedder_type != "mock":
                logger.warning(f"Unknown embedder type '{embedder_type}', using MockEmbedder")
            _embedder_instance = MockEmbedder(embedding_dim=config.embedding_dim or 384)
            logger.warning("Global embedder initialized: MockEmbedder (not suitable for production)")

    return _embedder_instance


def reset_embedder() -> None:
    """重置 Embedder（主要用于测试）"""
    global _embedder_instance
    _embedder_instance = None
    logger.debug("Embedder singleton reset")
