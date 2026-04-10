# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Redis 客户端单元测试
"""

import pytest

from asc_ops.storage.redis_client import RedisClient


class TestRedisClientMockMode:
    """Redis 客户端 Mock 模式测试"""

    @pytest.fixture
    def client(self):
        """创建 mock 模式客户端"""
        return RedisClient(mock=True)

    # ==================== 基本操作测试 ====================

    def test_set_and_get(self, client):
        """测试基本 set/get 操作"""
        client.set("key1", "value1")
        assert client.get("key1") == "value1"

    def test_get_nonexistent_key(self, client):
        """测试获取不存在的 key"""
        assert client.get("nonexistent") is None

    def test_delete(self, client):
        """测试删除操作"""
        client.set("key1", "value1")
        assert client.delete("key1") == 1
        assert client.get("key1") is None

    def test_delete_nonexistent(self, client):
        """测试删除不存在的 key"""
        assert client.delete("nonexistent") == 0

    def test_exists(self, client):
        """测试 exists 操作"""
        client.set("key1", "value1")
        assert client.exists("key1") is True
        assert client.exists("nonexistent") is False

    def test_expire(self, client):
        """测试 expire 操作"""
        client.set("key1", "value1")
        assert client.expire("key1", 100) is True

    def test_ttl(self, client):
        """测试 ttl 操作"""
        client.set("key1", "value1")
        # Mock 模式下 ttl 返回 -1
        assert client.ttl("key1") == -1

    def test_set_with_ex(self, client):
        """测试带过期时间的 set"""
        result = client.set("key1", "value1", ex=100)
        assert result is True

    def test_set_nx(self, client):
        """测试 nx 选项"""
        client.set("key1", "value1")
        # key 已存在，nx 应该失败
        assert client.set("key1", "value2", nx=True) is False
        # key 不存在，nx 应该成功
        assert client.set("key2", "value2", nx=True) is True

    # ==================== Hash 操作测试 ====================

    def test_hset_and_hget(self, client):
        """测试 hset/hget 操作"""
        client.hset("hash1", "field1", "value1")
        assert client.hget("hash1", "field1") == "value1"

    def test_hset_with_mapping(self, client):
        """测试 hset 带 mapping"""
        client.hset("hash1", mapping={"f1": "v1", "f2": "v2"})
        assert client.hget("hash1", "f1") == "v1"
        assert client.hget("hash1", "f2") == "v2"

    def test_hgetall(self, client):
        """测试 hgetall 操作"""
        client.hset("hash1", mapping={"f1": "v1", "f2": "v2"})
        result = client.hgetall("hash1")
        assert result == {"f1": "v1", "f2": "v2"}

    def test_hdel(self, client):
        """测试 hdel 操作"""
        client.hset("hash1", mapping={"f1": "v1", "f2": "v2"})
        assert client.hdel("hash1", "f1") == 1
        assert client.hget("hash1", "f1") is None
        assert client.hget("hash1", "f2") == "v2"

    def test_hexists(self, client):
        """测试 hexists 操作"""
        client.hset("hash1", "f1", "v1")
        assert client.hexists("hash1", "f1") is True
        assert client.hexists("hash1", "f2") is False

    def test_hlen(self, client):
        """测试 hlen 操作"""
        client.hset("hash1", mapping={"f1": "v1", "f2": "v2"})
        assert client.hlen("hash1") == 2

    def test_hkeys(self, client):
        """测试 hkeys 操作"""
        client.hset("hash1", mapping={"f1": "v1", "f2": "v2"})
        keys = client.hkeys("hash1")
        assert set(keys) == {"f1", "f2"}

    def test_hvals(self, client):
        """测试 hvals 操作"""
        client.hset("hash1", mapping={"f1": "v1", "f2": "v2"})
        vals = client.hvals("hash1")
        assert set(vals) == {"v1", "v2"}

    # ==================== List 操作测试 ====================

    def test_lpush_and_lrange(self, client):
        """测试 lpush/lrange 操作"""
        client.lpush("list1", "a", "b", "c")
        result = client.lrange("list1", 0, -1)
        assert result == ["c", "b", "a"]

    def test_rpush_and_lrange(self, client):
        """测试 rpush/lrange 操作"""
        client.rpush("list1", "a", "b", "c")
        result = client.lrange("list1", 0, -1)
        assert result == ["a", "b", "c"]

    def test_llen(self, client):
        """测试 llen 操作"""
        client.rpush("list1", "a", "b", "c")
        assert client.llen("list1") == 3

    # ==================== Set 操作测试 ====================

    def test_sadd_and_smembers(self, client):
        """测试 sadd/smembers 操作"""
        client.sadd("set1", "a", "b", "c")
        members = client.smembers("set1")
        assert members == {"a", "b", "c"}

    def test_sismember(self, client):
        """测试 sismember 操作"""
        client.sadd("set1", "a", "b")
        assert client.sismember("set1", "a") is True
        assert client.sismember("set1", "c") is False

    def test_srem(self, client):
        """测试 srem 操作"""
        client.sadd("set1", "a", "b", "c")
        assert client.srem("set1", "b") == 1
        members = client.smembers("set1")
        assert members == {"a", "c"}

    # ==================== 连接管理测试 ====================

    def test_ping(self, client):
        """测试 ping 操作"""
        assert client.ping() is True

    def test_is_mock(self, client):
        """测试 is_mock 属性"""
        assert client.is_mock is True

    def test_close(self, client):
        """测试 close 操作"""
        client.close()  # 不应该抛出异常


class TestRedisClientRealMode:
    """Redis 客户端真实模式测试 (需要 Redis 服务器)"""

    @pytest.fixture
    def client(self):
        """创建真实模式客户端 (如果不可用则跳过)"""
        client = RedisClient(
            host="localhost",
            port=6379,
            db=15,  # 使用独立的 DB 避免污染
            mock=False,
        )
        if not client.ping():
            pytest.skip("Redis server not available")
        yield client
        # 清理
        client._client.flushdb()

    def test_real_set_and_get(self, client):
        """测试真实模式的 set/get"""
        client.set("test_key", "test_value")
        assert client.get("test_key") == "test_value"

    def test_real_hash_operations(self, client):
        """测试真实模式的 hash 操作"""
        client.hset("test_hash", mapping={"f1": "v1", "f2": "v2"})
        result = client.hgetall("test_hash")
        assert result["f1"] == "v1"
        assert result["f2"] == "v2"

    def test_connection_pool_reuse(self, client):
        """测试连接池复用"""
        # 执行多个操作
        for i in range(5):
            client.set(f"key_{i}", f"value_{i}")
        # 验证都能获取
        for i in range(5):
            assert client.get(f"key_{i}") == f"value_{i}"
