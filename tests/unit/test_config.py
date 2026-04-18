# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
配置管理单元测试
"""

import pytest
import os
from pathlib import Path
from unittest.mock import patch

from asc_ops.config import (
    ChromaDBConfig,
    RedisConfig,
    LLMConfig,
    EmbeddingConfig,
    ServerConfig,
    AppConfig,
    get_config,
    reload_config,
    reset_config,
)


class TestChromaDBConfig:
    """ChromaDB 配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = ChromaDBConfig()
        assert config.db_path == "./data/chroma_db"

    def test_env_override(self):
        """测试环境变量覆盖"""
        with patch.dict(os.environ, {"CHROMA_DB_PATH": "/custom/path"}):
            config = ChromaDBConfig()
            assert config.db_path == "/custom/path"


class TestRedisConfig:
    """Redis 配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = RedisConfig()
        # 注意：当 REDIS_PASSWORD="" 在 .env 中时，pydantic 读取为空字符串而非 None
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.max_connections == 10

    def test_password_empty_string(self):
        """测试空密码字符串"""
        config = RedisConfig()
        # pydantic 读取空字符串环境变量为 ""
        assert config.password == ""

    def test_env_override(self):
        """测试环境变量覆盖"""
        with patch.dict(
            os.environ,
            {
                "REDIS_HOST": "redis.example.com",
                "REDIS_PORT": "6380",
                "REDIS_DB": "5",
            },
        ):
            config = RedisConfig()
            assert config.host == "redis.example.com"
            assert config.port == 6380
            assert config.db == 5


class TestLLMConfig:
    """LLM 配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = LLMConfig()
        # 注意：当环境变量已设置时，pydantic 会使用环境变量值
        # 这里只测试必定有值的字段
        assert config.default_provider == "anthropic"
        assert isinstance(config.anthropic_api_key, str)
        assert config.anthropic_api_base is not None

    def test_env_override(self):
        """测试环境变量覆盖"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            config = LLMConfig()
            assert config.anthropic_api_key == "sk-ant-test"


class TestEmbeddingConfig:
    """Embedding 配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = EmbeddingConfig()
        # 注意：当环境变量已设置时，pydantic 会使用环境变量值
        # 这里只测试必定有值的字段
        assert config.embedder_type is not None
        assert config.model_name is not None
        assert config.batch_size > 0

    def test_env_override(self):
        """测试环境变量覆盖"""
        with patch.dict(
            os.environ,
            {
                "EMBEDDING_MODEL_NAME": "BAAI/bge-large-zh",
                "EMBEDDING_BATCH_SIZE": "64",
            },
        ):
            config = EmbeddingConfig()
            assert config.model_name == "BAAI/bge-large-zh"
            assert config.batch_size == 64


class TestServerConfig:
    """服务配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = ServerConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.debug is False
        assert config.log_level == "INFO"

    def test_env_override(self):
        """测试环境变量覆盖"""
        with patch.dict(
            os.environ,
            {"SERVER_PORT": "9000", "SERVER_DEBUG": "true", "SERVER_LOG_LEVEL": "DEBUG"},
        ):
            config = ServerConfig()
            assert config.port == 9000
            assert config.debug is True
            assert config.log_level == "DEBUG"


class TestAppConfig:
    """应用主配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = AppConfig()
        assert config.use_mock_storage is False
        assert isinstance(config.chroma, ChromaDBConfig)
        assert isinstance(config.redis, RedisConfig)
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.embedding, EmbeddingConfig)
        assert isinstance(config.server, ServerConfig)

    def test_data_dir_creation(self, tmp_path):
        """测试数据目录自动创建"""
        data_dir = tmp_path / "test_data"
        config = AppConfig(data_dir=data_dir)
        assert config.data_dir.exists()

    def test_sub_configs_inherited(self):
        """测试子配置能够被正确继承"""
        with patch.dict(
            os.environ,
            {
                "CHROMA_DB_PATH": "/chroma",
                "REDIS_HOST": "redis",
                "EMBEDDING_MODEL_NAME": "my-model",
            },
        ):
            config = AppConfig()
            assert config.chroma.db_path == "/chroma"
            assert config.redis.host == "redis"
            assert config.embedding.model_name == "my-model"


class TestConfigSingleton:
    """配置单例测试"""

    def setup_method(self):
        """每个测试前重置配置"""
        reset_config()

    def test_get_config_returns_singleton(self):
        """测试 get_config 返回单例"""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reload_config_creates_new_instance(self):
        """测试 reload_config 创建新实例"""
        config1 = get_config()
        config2 = reload_config()
        assert config1 is not config2

    def test_reset_config_clears_singleton(self):
        """测试 reset_config 清除单例"""
        config1 = get_config()
        reset_config()
        config2 = get_config()
        assert config1 is not config2
