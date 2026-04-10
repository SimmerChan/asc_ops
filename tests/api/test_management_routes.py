# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
管理 API 路由测试
"""

import pytest
from fastapi.testclient import TestClient

from src.asc_ops.app import app


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


class TestManagementRoutes:
    """管理路由测试"""

    def test_get_status(self, client):
        """获取状态"""
        response = client.get("/api/v1/status")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "running"
        assert "version" in data["data"]
        assert "uptime_seconds" in data["data"]
        assert "knowledge_stats" in data["data"]

    def test_health_check(self, client):
        """健康检查"""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_get_stats(self, client):
        """获取统计信息"""
        response = client.get("/api/v1/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "api_count" in data["data"]
        assert "bug_fix_count" in data["data"]
        assert "optimization_count" in data["data"]

    def test_sync_trigger(self, client):
        """触发同步"""
        response = client.post(
            "/api/v1/sync",
            json={"sync_type": "all", "force": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["sync_type"] == "all"
        assert data["data"]["status"] == "sync_triggered"

    def test_sync_api_only(self, client):
        """仅同步 API"""
        response = client.post(
            "/api/v1/sync",
            json={"sync_type": "api", "force": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["sync_type"] == "api"

    def test_sync_invalid_type(self, client):
        """同步 - 无效类型"""
        response = client.post(
            "/api/v1/sync",
            json={"sync_type": "invalid", "force": False},
        )

        assert response.status_code == 400
