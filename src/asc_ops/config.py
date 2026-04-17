# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
AscendC 知识库配置管理

使用 pydantic-settings 管理配置，支持环境变量和 .env 文件
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from pathlib import Path
from dataclasses import dataclass, field


class ChromaDBConfig(BaseSettings):
    """ChromaDB 配置"""

    model_config = SettingsConfigDict(
        env_prefix="CHROMA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: str = "./data/chroma_db"


class RedisConfig(BaseSettings):
    """Redis 配置"""

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    max_connections: int = 10


class LLMConfig(BaseSettings):
    """LLM 配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider 选择
    default_provider: str = "anthropic"

    # Anthropic 配置
    anthropic_api_key: Optional[str] = None
    anthropic_api_base: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # OpenAI 配置
    openai_api_key: Optional[str] = None
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    # Zhipu 配置
    zhipu_api_key: Optional[str] = None
    zhipu_api_base: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_model: str = "glm-4"

    # MiniMax 配置
    minimax_api_key: Optional[str] = None
    minimax_api_base: str = "https://api.minimax.chat/v1"
    minimax_group_id: Optional[str] = None
    minimax_model: str = "MiniMax-Text-01"


class EmbeddingConfig(BaseSettings):
    """Embedding 模型配置"""

    model_config = SettingsConfigDict(
        env_prefix="EMBEDDING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Embedder 类型: "sentence_transformers" | "qwen" | "mock"
    embedder_type: str = "sentence_transformers"
    # 模型名称
    model_name: str = "all-MiniLM-L6-v2"
    # 模型路径 (如果使用本地模型)
    model_path: Optional[str] = None
    # 向量维度 (某些模型可配置)
    embedding_dim: Optional[int] = None
    # 批处理大小
    batch_size: int = 32
    # 设备: "cpu" | "cuda"
    device: str = "cpu"


class ServerConfig(BaseSettings):
    """服务配置"""

    model_config = SettingsConfigDict(
        env_prefix="SERVER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: str = "INFO"


@dataclass
class PeerRepoConfig:
    """
    对等仓库配置

    用于配置 GPU 仓和 NPU 仓的对等关系，支持 LLM 分析
    """
    name: str
    gpu_repo_path: str  # GPU 仓本地路径
    npu_repo_path: str  # NPU 仓本地路径
    gpu_platform: str = "cuda"  # GPU 平台: cuda/cutlass/cublas/cudnn
    analysis_paths: List[str] = field(default_factory=list)  # 用户指定要分析的子目录或文件路径


class AppConfig(BaseSettings):
    """应用主配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 各子配置 - 使用 Field(default_factory=) 确保环境变量正确传递
    chroma: Optional[ChromaDBConfig] = None
    redis: Optional[RedisConfig] = None
    llm: Optional[LLMConfig] = None
    embedding: Optional[EmbeddingConfig] = None
    server: Optional[ServerConfig] = None

    # 数据源配置
    data_dir: Path = Path("./data")
    # 是否使用 mock 存储 (用于测试)
    use_mock_storage: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # 延迟初始化子配置，确保环境变量正确传递
        if self.chroma is None:
            self.chroma = ChromaDBConfig()
        if self.redis is None:
            self.redis = RedisConfig()
        if self.llm is None:
            self.llm = LLMConfig()
        if self.embedding is None:
            self.embedding = EmbeddingConfig()
        if self.server is None:
            self.server = ServerConfig()


# 全局配置实例
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """
    获取全局配置实例 (单例模式)

    Returns:
        AppConfig 实例
    """
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def reload_config() -> AppConfig:
    """
    重新加载配置

    Returns:
        重新加载后的 AppConfig 实例
    """
    global _config
    _config = AppConfig()
    return _config


def reset_config() -> None:
    """重置配置 (主要用于测试)"""
    global _config
    _config = None


def load_peer_repos_config(config_path: str = "peer_repos.yaml") -> List[PeerRepoConfig]:
    """
    加载对等仓库配置

    Args:
        config_path: 配置文件路径

    Returns:
        PeerRepoConfig 列表
    """
    import yaml

    path = Path(config_path)
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "peer_repos" not in data:
        return []

    configs = []
    for repo_data in data["peer_repos"]:
        config = PeerRepoConfig(
            name=repo_data.get("name", ""),
            gpu_repo_path=repo_data.get("gpu_repo_path", ""),
            npu_repo_path=repo_data.get("npu_repo_path", ""),
            gpu_platform=repo_data.get("gpu_platform", "cuda"),
            analysis_paths=repo_data.get("analysis_paths", []),
        )
        configs.append(config)

    return configs
