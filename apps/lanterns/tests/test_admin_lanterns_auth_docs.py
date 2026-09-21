"""Tests for Admin Lanterns authentication, subdomain routing, and OpenAPI documentation."""

import pytest
import yaml
from django.conf import settings
from django.test import Client
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.booths.models import Booth
from apps.lanterns.models import Lantern

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client():
    client = APIClient(SERVER_NAME="admin.testserver")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {settings.ADMIN_API_TOKEN}")
    return client


@pytest.fixture
def unauth_client():
    return APIClient(SERVER_NAME="admin.testserver")


@pytest.fixture
def invalid_token_client():
    client = APIClient(SERVER_NAME="admin.testserver")
    client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token-12345")
    return client


@pytest.fixture
def sample_lantern():
    user = User.objects.create(kakao_id=987654321, nickname="테스터")
    booth = Booth.objects.create(
        name="테스트 부스",
        place_type="BOOTH",
        lantern_count=1,
    )
    return Lantern.objects.create(
        user=user,
        booth=booth,
        nickname="익명의 코끼리",
        message="테스트 등불 메시지입니다.",
    )


class TestAdminLanternsAuth:
    """관리자 등불 3개 엔드포인트(목록, 상세, 삭제)의 권한 및 토큰 검증 테스트."""

    # 1. 누락된 토큰 (Missing Token) -> 401
    def test_missing_token_returns_401(self, unauth_client, sample_lantern):
        # 1) 목록 조회
        res_list = unauth_client.get("/api/lanterns/")
        assert res_list.status_code == status.HTTP_401_UNAUTHORIZED
        assert res_list.data["code"] == "UNAUTHORIZED"

        # 2) 상세 조회
        res_detail = unauth_client.get(f"/api/lanterns/{sample_lantern.id}/")
        assert res_detail.status_code == status.HTTP_401_UNAUTHORIZED
        assert res_detail.data["code"] == "UNAUTHORIZED"

        # 3) 삭제 (블라인드)
        res_delete = unauth_client.delete(f"/api/lanterns/{sample_lantern.id}/")
        assert res_delete.status_code == status.HTTP_401_UNAUTHORIZED
        assert res_delete.data["code"] == "UNAUTHORIZED"

    # 2. 잘못된 토큰 (Invalid Token) -> 401
    def test_invalid_token_returns_401(self, invalid_token_client, sample_lantern):
        # 1) 목록 조회
        res_list = invalid_token_client.get("/api/lanterns/")
        assert res_list.status_code == status.HTTP_401_UNAUTHORIZED
        assert res_list.data["code"] == "UNAUTHORIZED"

        # 2) 상세 조회
        res_detail = invalid_token_client.get(f"/api/lanterns/{sample_lantern.id}/")
        assert res_detail.status_code == status.HTTP_401_UNAUTHORIZED
        assert res_detail.data["code"] == "UNAUTHORIZED"

        # 3) 삭제 (블라인드)
        res_delete = invalid_token_client.delete(f"/api/lanterns/{sample_lantern.id}/")
        assert res_delete.status_code == status.HTTP_401_UNAUTHORIZED
        assert res_delete.data["code"] == "UNAUTHORIZED"

    # 3. 정상 토큰 (Valid Token) -> 200
    def test_authorized_requests_succeed(self, auth_client, sample_lantern):
        # 1) 목록 조회
        res_list = auth_client.get("/api/lanterns/")
        assert res_list.status_code == status.HTTP_200_OK
        assert res_list.data["code"] == "ADMIN_LANTERN_LIST_SUCCESS"
        assert len(res_list.data["data"]["items"]) == 1

        # 2) 상세 조회
        res_detail = auth_client.get(f"/api/lanterns/{sample_lantern.id}/")
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.data["code"] == "ADMIN_LANTERN_DETAIL_SUCCESS"
        assert res_detail.data["data"]["id"] == sample_lantern.id

        # 3) 삭제 (블라인드)
        res_delete = auth_client.delete(f"/api/lanterns/{sample_lantern.id}/")
        assert res_delete.status_code == status.HTTP_200_OK
        assert res_delete.data["code"] == "ADMIN_LANTERN_DELETE_SUCCESS"

        # 삭제 후 DB 상태 확인
        sample_lantern.refresh_from_db()
        assert sample_lantern.deleted_at is not None
        assert sample_lantern.deleted_by == Lantern.DeletedBy.ADMIN


class TestAdminLanternsHostRouting:
    """호스트/도메인별 등불 라우팅 격리 테스트."""

    def test_user_domain_reaches_public_lanterns(self, sample_lantern):
        client = Client(SERVER_NAME="testserver")

        # 공개 호스트 등불 목록 조회 -> 인증 없이 200 OK (UserLanternListResponse)
        res = client.get("/api/lanterns/")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["code"] == "LANTERN_LIST_SUCCESS"

        # 공개 호스트 등불 상세 조회 -> 인증 없이 200 OK (UserLanternDetailResponse)
        res_detail = client.get(f"/api/lanterns/{sample_lantern.id}/")
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.json()["code"] == "LANTERN_DETAIL_SUCCESS"

    def test_admin_domain_routing_and_docs(self, sample_lantern):
        client = Client(SERVER_NAME="admin.testserver")
        auth_header = {"HTTP_AUTHORIZATION": f"Bearer {settings.ADMIN_API_TOKEN}"}

        # 관리자 호스트 등불 목록 -> 인증 미포함 401, 인증 포함 200
        res_unauth = client.get("/api/lanterns/")
        assert res_unauth.status_code == status.HTTP_401_UNAUTHORIZED

        res_auth = client.get("/api/lanterns/", **auth_header)
        assert res_auth.status_code == status.HTTP_200_OK
        assert res_auth.json()["code"] == "ADMIN_LANTERN_LIST_SUCCESS"

        # 관리자 호스트 스키마 및 Swagger UI 접근 가능
        res_schema = client.get("/api/schema/")
        assert res_schema.status_code == status.HTTP_200_OK

        res_docs = client.get("/api/docs/")
        assert res_docs.status_code == status.HTTP_200_OK


class TestAdminLanternsDocsSchema:
    """Swagger OpenAPI 스키마 검증 테스트."""

    def test_admin_schema_includes_admin_lanterns_endpoints(self):
        client = Client(SERVER_NAME="admin.testserver")
        res = client.get("/api/schema/")
        assert res.status_code == status.HTTP_200_OK

        schema = yaml.safe_load(res.content)
        paths = schema.get("paths", {})

        # 1. BearerAuth 보안 스키마 확인
        components = schema.get("components", {})
        security_schemes = components.get("securitySchemes", {})
        assert "BearerAuth" in security_schemes
        bearer_auth = security_schemes["BearerAuth"]
        assert bearer_auth["type"] == "http"
        assert bearer_auth["scheme"] == "bearer"

        # 2. /api/lanterns/ -> GET (admin_lantern_list)
        assert "/api/lanterns/" in paths
        lantern_root = paths["/api/lanterns/"]
        assert "get" in lantern_root
        get_op = lantern_root["get"]
        assert get_op["operationId"] == "admin_lantern_list"
        assert "admin-lanterns" in get_op["tags"]
        assert "200" in get_op["responses"]
        assert "400" in get_op["responses"]
        assert "401" in get_op["responses"]

        # 3. /api/lanterns/{lantern_id}/ -> GET (detail), DELETE (delete)
        assert "/api/lanterns/{lantern_id}/" in paths
        lantern_detail = paths["/api/lanterns/{lantern_id}/"]
        detail_get = lantern_detail["get"]
        assert detail_get["operationId"] == "admin_lantern_detail"
        assert "admin-lanterns" in detail_get["tags"]
        assert "200" in detail_get["responses"]
        assert "401" in detail_get["responses"]
        assert "404" in detail_get["responses"]

        detail_delete = lantern_detail["delete"]
        assert detail_delete["operationId"] == "admin_lantern_delete"
        assert "admin-lanterns" in detail_delete["tags"]
        assert "200" in detail_delete["responses"]
        assert "401" in detail_delete["responses"]
        assert "404" in detail_delete["responses"]

        # 4. Components / Schemas 검증
        schemas = components.get("schemas", {})
        expected_schemas = [
            "AdminLanternListResponse",
            "AdminLanternDetailResponse",
            "AdminLanternDeleteResponse",
            "ErrorResponse",
        ]
        for schema_name in expected_schemas:
            assert schema_name in schemas, f"{schema_name} not found in OpenAPI schemas"
            schema_def = schemas[schema_name]
            assert "properties" in schema_def
            assert "success" in schema_def["properties"]
            assert "code" in schema_def["properties"]
            assert "message" in schema_def["properties"]
