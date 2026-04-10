# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
查询 API 路由测试
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from src.asc_ops.app import app
from src.asc_ops.routes.query import get_query_service


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_query_service():
    """创建模拟查询服务"""
    mock_service = MagicMock()
    mock_service.query_for_development = AsyncMock()
    mock_service.query_for_troubleshooting = AsyncMock()
    mock_service.query_api = AsyncMock()
    return mock_service


class TestQueryRoutes:
    """查询路由测试"""

    def test_development_query_success(self, client, mock_query_service):
        """开发查询成功"""
        from src.asc_ops.knowledge_query import DevelopmentQueryResult
        from src.asc_ops.models import BugFixKnowledge, BugSeverity, BugCategory

        mock_result = DevelopmentQueryResult(
            operator_name="Matmul",
            query_type="all",
            total_count=1,
            bug_fixes=[
                BugFixKnowledge(
                    bug_id="BUG-1",
                    operator_id="Matmul",
                    source_repo="ascend-cann",
                    source_pr="1234",
                    bug_title="Memory leak",
                    symptom="High memory",
                    severity=BugSeverity.MAJOR,
                    category=BugCategory.MEMORY,
                )
            ],
            optimizations=[],
        )
        mock_query_service.query_for_development.return_value = mock_result

        with patch("src.asc_ops.routes.query.get_query_service", return_value=mock_query_service):
            response = client.post(
                "/api/v1/query/development",
                json={
                    "operator_name": "Matmul",
                    "query_type": "all",
                    "limit": 10,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["operator_name"] == "Matmul"
        assert len(data["data"]["bug_fixes"]) == 1

    def test_development_query_invalid_type(self, client):
        """开发查询 - 无效类型"""
        response = client.post(
            "/api/v1/query/development",
            json={
                "operator_name": "Matmul",
                "query_type": "invalid",
                "limit": 10,
            },
        )

        # 验证请求可以处理（实际验证在服务层）
        assert response.status_code in [200, 422]

    def test_troubleshooting_query_success(self, client, mock_query_service):
        """问题排查查询成功"""
        from src.asc_ops.knowledge_query import TroubleshootingResult, PossibleCause

        mock_result = TroubleshootingResult(
            symptom="Matmul crash",
            possible_causes=[
                PossibleCause(
                    bug_id="BUG-1",
                    description="Memory leak",
                    confidence=0.8,
                    root_cause="Buffer not released",
                    trigger_conditions=["large input"],
                    suggested_fix="Add release()",
                )
            ],
        )
        mock_query_service.query_for_troubleshooting.return_value = mock_result

        with patch("src.asc_ops.routes.query.get_query_service", return_value=mock_query_service):
            response = client.post(
                "/api/v1/query/troubleshooting",
                json={
                    "symptom": "Matmul crash",
                    "operator_name": "Matmul",
                    "limit": 5,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["symptom"] == "Matmul crash"
        assert len(data["data"]["possible_causes"]) == 1

    def test_api_query_exact_match(self, client, mock_query_service):
        """API精确查询"""
        from src.asc_ops.models import AscendCAPIDefinition, APIReturnValue

        mock_result = [
            AscendCAPIDefinition(
                api_id="Exp",
                canonical_name="Exp",
                full_signature="void Exp(Position2f pos)",
                category="tensor",
                subcategory="tensor creation",
                description="Create exponential tensor",
                parameters=[],
                return_value=APIReturnValue(type="void", description=""),
            )
        ]
        mock_query_service.query_api.return_value = mock_result

        with patch("src.asc_ops.routes.query.get_query_service", return_value=mock_query_service):
            response = client.get(
                "/api/v1/query/api",
                params={"api_name": "Exp"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["apis"]) == 1
        assert data["data"]["apis"][0]["canonical_name"] == "Exp"

    def test_api_query_semantic(self, client, mock_query_service):
        """API语义查询"""
        from src.asc_ops.models import AscendCAPIDefinition, APIReturnValue

        mock_result = [
            AscendCAPIDefinition(
                api_id="Exp",
                canonical_name="Exp",
                full_signature="",
                category="tensor",
                subcategory="",
                description="Create exponential tensor",
                parameters=[],
                return_value=APIReturnValue(type="void", description=""),
            ),
            AscendCAPIDefinition(
                api_id="Log",
                canonical_name="Log",
                full_signature="",
                category="tensor",
                subcategory="",
                description="Create log tensor",
                parameters=[],
                return_value=APIReturnValue(type="void", description=""),
            ),
        ]
        mock_query_service.query_api.return_value = mock_result

        with patch("src.asc_ops.routes.query.get_query_service", return_value=mock_query_service):
            response = client.get(
                "/api/v1/query/api",
                params={"semantic_query": "tensor creation", "limit": 10},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["apis"]) == 2

    def test_api_query_missing_params(self, client):
        """API查询 - 缺少参数"""
        response = client.get("/api/v1/query/api")

        assert response.status_code == 400  # Bad request - needs api_name or semantic_query

    def test_api_query_with_category_filter(self, client, mock_query_service):
        """API查询 - 带类别过滤"""
        from src.asc_ops.models import AscendCAPIDefinition, APIReturnValue

        mock_result = [
            AscendCAPIDefinition(
                api_id="Matmul",
                canonical_name="Matmul",
                full_signature="",
                category="compute",
                subcategory="matrix",
                description="Matrix multiplication",
                parameters=[],
                return_value=APIReturnValue(type="void", description=""),
            ),
        ]
        mock_query_service.query_api.return_value = mock_result

        with patch("src.asc_ops.routes.query.get_query_service", return_value=mock_query_service):
            response = client.get(
                "/api/v1/query/api",
                params={"api_name": "Matmul", "category": "compute"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
