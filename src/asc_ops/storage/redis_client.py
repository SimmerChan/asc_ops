# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
Redis 客户端封装

提供 KV 存储的 CRUD 操作接口，支持连接池和 mock 模式
"""

import redis
from redis.connection import ConnectionPool
from typing import Optional, Any, Union, Iterator
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis 客户端封装类，支持连接池管理和 mock 模式"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = True,
        max_connections: int = 10,
        mock: bool = False,
    ):
        """
        初始化 Redis 客户端

        Args:
            host: Redis 主机地址
            port: Redis 端口
            db: 数据库编号
            password: 密码 (可选)
            decode_responses: 是否自动解码响应
            max_connections: 最大连接数
            mock: 是否使用 mock 模式 (用于测试)
        """
        self._mock = mock
        self._mock_data: dict = {}

        if not mock:
            self._pool = ConnectionPool(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=decode_responses,
                max_connections=max_connections,
            )
            self._client = redis.Redis(connection_pool=self._pool)
        else:
            self._pool = None
            self._client = None
            logger.info("Redis client initialized in mock mode")

        logger.info(f"Redis client initialized (host={host}, port={port}, db={db})")

    # ==================== 基本操作 ====================

    def get(self, key: str) -> Optional[str]:
        """获取指定 key 的值"""
        if self._mock:
            return self._mock_data.get(key)
        return self._client.get(key)

    def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """
        设置指定 key 的值

        Args:
            key: 键
            value: 值
            ex: 过期时间 (秒)
            px: 过期时间 (毫秒)
            nx: 仅在 key 不存在时设置
            xx: 仅在 key 存在时设置
        """
        if self._mock:
            if nx and key in self._mock_data:
                return False
            if xx and key not in self._mock_data:
                return False
            self._mock_data[key] = value
            return True
        return self._client.set(
            key, value, ex=ex, px=px, nx=nx, xx=xx
        )

    def delete(self, *keys: str) -> int:
        """删除指定的 key(s)"""
        if self._mock:
            deleted = sum(1 for k in keys if k in self._mock_data)
            for k in keys:
                self._mock_data.pop(k, None)
            return deleted
        return self._client.delete(*keys)

    def exists(self, key: str) -> bool:
        """检查 key 是否存在"""
        if self._mock:
            return key in self._mock_data
        return self._client.exists(key) > 0

    def expire(self, key: str, seconds: int) -> bool:
        """设置 key 的过期时间"""
        if self._mock:
            if key not in self._mock_data:
                return False
            return True
        return self._client.expire(key, seconds)

    def ttl(self, key: str) -> int:
        """获取 key 的剩余生存时间"""
        if self._mock:
            return -1
        return self._client.ttl(key)

    # ==================== Hash 操作 ====================

    def hget(self, key: str, field: str) -> Optional[str]:
        """获取 hash 中指定 field 的值"""
        if self._mock:
            data = self._mock_data.get(key, {})
            return data.get(field) if isinstance(data, dict) else None
        return self._client.hget(key, field)

    def hset(
        self,
        key: str,
        field: Optional[str] = None,
        value: Optional[str] = None,
        mapping: Optional[dict] = None,
    ) -> int:
        """
        设置 hash 中指定 field 的值

        Args:
            key: hash 键
            field: field 名 (如果为 None，则 value 应该是 dict)
            value: field 值
            mapping: 批量设置 dict
        """
        if self._mock:
            if key not in self._mock_data:
                self._mock_data[key] = {}
            if mapping:
                self._mock_data[key].update(mapping)
                return len(mapping)
            if field is None and isinstance(value, dict):
                self._mock_data[key].update(value)
                return len(value)
            self._mock_data[key][field] = value
            return 1
        if mapping:
            return self._client.hset(key, mapping=mapping)
        if field is None and isinstance(value, dict):
            return self._client.hset(key, mapping=value)
        return self._client.hset(key, field, value)

    def hgetall(self, key: str) -> dict:
        """获取 hash 中所有的 field-value 对"""
        if self._mock:
            data = self._mock_data.get(key, {})
            return data if isinstance(data, dict) else {}
        return self._client.hgetall(key)

    def hdel(self, key: str, *fields: str) -> int:
        """删除 hash 中指定的 field(s)"""
        if self._mock:
            if key not in self._mock_data:
                return 0
            data = self._mock_data[key]
            if not isinstance(data, dict):
                return 0
            deleted = sum(1 for f in fields if f in data)
            for f in fields:
                data.pop(f, None)
            return deleted
        return self._client.hdel(key, *fields)

    def hexists(self, key: str, field: str) -> bool:
        """检查 hash 中指定 field 是否存在"""
        if self._mock:
            data = self._mock_data.get(key, {})
            return field in data if isinstance(data, dict) else False
        return self._client.hexists(key, field)

    def hlen(self, key: str) -> int:
        """获取 hash 中 field 的数量"""
        if self._mock:
            data = self._mock_data.get(key, {})
            return len(data) if isinstance(data, dict) else 0
        return self._client.hlen(key)

    def hkeys(self, key: str) -> list:
        """获取 hash 中所有的 field 名"""
        if self._mock:
            data = self._mock_data.get(key, {})
            return list(data.keys()) if isinstance(data, dict) else []
        return self._client.hkeys(key)

    def hvals(self, key: str) -> list:
        """获取 hash 中所有的 value"""
        if self._mock:
            data = self._mock_data.get(key, {})
            return list(data.values()) if isinstance(data, dict) else []
        return self._client.hvals(key)

    # ==================== List 操作 ====================

    def lpush(self, key: str, *values: str) -> int:
        """将一个或多个值插入到列表左侧"""
        if self._mock:
            if key not in self._mock_data:
                self._mock_data[key] = []
            # Redis lpush adds elements to the head, so reversed order
            self._mock_data[key] = list(reversed(values)) + self._mock_data[key]
            return len(self._mock_data[key])
        return self._client.lpush(key, *values)

    def rpush(self, key: str, *values: str) -> int:
        """将一个或多个值插入到列表右侧"""
        if self._mock:
            if key not in self._mock_data:
                self._mock_data[key] = []
            self._mock_data[key] = self._mock_data[key] + list(values)
            return len(self._mock_data[key])
        return self._client.rpush(key, *values)

    def lrange(self, key: str, start: int, end: int) -> list:
        """获取列表中指定范围内的元素"""
        if self._mock:
            data = self._mock_data.get(key, [])
            if not isinstance(data, list):
                return []
            if end == -1:
                return data[start:]
            return data[start:end + 1]
        return self._client.lrange(key, start, end)

    def llen(self, key: str) -> int:
        """获取列表的长度"""
        if self._mock:
            data = self._mock_data.get(key, [])
            return len(data) if isinstance(data, list) else 0
        return self._client.llen(key)

    # ==================== Set 操作 ====================

    def sadd(self, key: str, *values: str) -> int:
        """向集合添加一个或多个成员"""
        if self._mock:
            if key not in self._mock_data:
                self._mock_data[key] = set()
            self._mock_data[key].update(values)
            return len(values)
        return self._client.sadd(key, *values)

    def smembers(self, key: str) -> set:
        """获取集合中所有的成员"""
        if self._mock:
            data = self._mock_data.get(key, set())
            return data if isinstance(data, set) else set()
        return self._client.smembers(key)

    def sismember(self, key: str, value: str) -> bool:
        """检查成员是否是集合的成员"""
        if self._mock:
            data = self._mock_data.get(key, set())
            return value in data if isinstance(data, set) else False
        return self._client.sismember(key, value) > 0

    def srem(self, key: str, *values: str) -> int:
        """从集合移除一个或多个成员"""
        if self._mock:
            if key not in self._mock_data:
                return 0
            data = self._mock_data[key]
            if not isinstance(data, set):
                return 0
            removed = sum(1 for v in values if v in data)
            data.difference_update(values)
            return removed
        return self._client.srem(key, *values)

    def zadd(self, key: str, mapping: dict) -> int:
        """
        向有序集合添加成员

        Args:
            key: 键
            mapping: 成员到分数的映射 {member: score, ...}

        Returns:
            添加的成员数量
        """
        if self._mock:
            if "ascendc:correction_reports:index" not in self._mock_data:
                self._mock_data["ascendc:correction_reports:index"] = {}
            data = self._mock_data["ascendc:correction_reports:index"]
            if not isinstance(data, dict):
                data = {}
                self._mock_data["ascendc:correction_reports:index"] = data
            for member, score in mapping.items():
                data[member] = score
            return len(mapping)
        return self._client.zadd(key, mapping)

    def zrangebyscore(
        self,
        key: str,
        min: Union[float, str],
        max: Union[float, str],
        withscores: bool = False,
    ) -> list:
        """
        按分数范围查询有序集合

        Args:
            key: 键
            min: 最小分数
            max: 最大分数
            withscores: 是否返回分数

        Returns:
            成员列表或 (成员, 分数) 列表
        """
        if self._mock:
            data = self._mock_data.get(key, {})
            if not isinstance(data, dict):
                return []
            result = []
            min_score = float(min) if isinstance(min, (int, float, str)) else 0
            max_score = float(max) if isinstance(max, (int, float, str)) else float("inf")
            if max == "+inf":
                max_score = float("inf")
            for member, score in data.items():
                if min_score <= score <= max_score:
                    if withscores:
                        result.append((member, score))
                    else:
                        result.append(member)
            return result
        return self._client.zrangebyscore(key, min, max, withscores=withscores)

    def scan_iter(self, match: Optional[str] = None) -> Iterator[str]:
        """
        遍历所有匹配模式的键

        Args:
            match: 键名模式 (支持 * 和 ? 通配符)

        Returns:
            匹配键的迭代器
        """
        if self._mock:
            if not match:
                return iter(list(self._mock_data.keys()))
            # 简单实现：支持 * 通配符
            import fnmatch
            pattern = match.replace("*", ".*").replace("?", ".")
            result = [k for k in self._mock_data.keys() if fnmatch.fnmatch(k, match)]
            return iter(result)
        # Real Redis client
        return self._client.scan_iter(match)

    # ==================== 连接管理 ====================

    def ping(self) -> bool:
        """检查连接是否正常"""
        if self._mock:
            return True
        try:
            return self._client.ping()
        except redis.ConnectionError:
            return False

    def close(self) -> None:
        """关闭连接"""
        if not self._mock and self._client:
            self._client.close()
        logger.info("Redis connection closed")

    @property
    def is_mock(self) -> bool:
        """是否处于 mock 模式"""
        return self._mock
