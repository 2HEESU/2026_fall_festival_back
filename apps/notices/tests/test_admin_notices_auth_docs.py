"""Tests for Admin Notices authentication and OpenAPI documentation."""

import pytest
import yaml
from rest_framework import status
from rest_framework.test import APIClient

from apps.notices.models import Notice

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client():
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer test-admin-token")
    return client


@pytest.fixture
def unauth_client():
    return APIClient()


@pytest.fixture
def sample_notice():
    return Notice.objects.create(
        title="테스트 공지사항",
        content="테스트 본문 내용입니다.",
        type=Notice.Type.NORMAL,
    )


class TestAdminNoticesAuth:
    """관리자 공지 6개 엔드포인트의 IsAdmin 권한 연동 테스트."""

    def test_list_unauthorized_fails(self, unauth_client):
        res = unauth_client.get("/api/notices/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

    def test_create_unauthorized_fails(self, unauth_client):
        res = unauth_client.post(
            "/api/notices/",
            {"title": "제목", "content": "내용", "type": "NORMAL"},
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

    def test_detail_unauthorized_fails(self, unauth_client, sample_notice):
        res = unauth_client.get(f"/api/notices/{sample_notice.id}/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

    def test_update_unauthorized_fails(self, unauth_client, sample_notice):
        res = unauth_client.put(
            f"/api/notices/{sample_notice.id}/",
            {"title": "수정", "content": "수정내용", "type": "NORMAL"},
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

    def test_delete_unauthorized_fails(self, unauth_client, sample_notice):
        res = unauth_client.delete(f"/api/notices/{sample_notice.id}/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

    def test_image_upload_unauthorized_fails(self, unauth_client):
        res = unauth_client.post("/api/notices/images/", format="multipart")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

    def test_authorized_requests_succeed(self, auth_client, sample_notice):
        # 목록
        res_list = auth_client.get("/api/notices/")
        assert res_list.status_code == status.HTTP_200_OK
        assert res_list.data["code"] == "ADMIN_NOTICE_LIST_SUCCESS"

        # 상세
        res_detail = auth_client.get(f"/api/notices/{sample_notice.id}/")
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.data["code"] == "ADMIN_NOTICE_DETAIL_SUCCESS"

        # 수정
        res_update = auth_client.put(
            f"/api/notices/{sample_notice.id}/",
            {"title": "수정제목", "content": "수정본문", "type": "URGENT"},
            format="json",
        )
        assert res_update.status_code == status.HTTP_200_OK
        assert res_update.data["code"] == "ADMIN_NOTICE_UPDATE_SUCCESS"

        # 삭제
        res_delete = auth_client.delete(f"/api/notices/{sample_notice.id}/")
        assert res_delete.status_code == status.HTTP_200_OK
        assert res_delete.data["code"] == "ADMIN_NOTICE_DELETE_SUCCESS"


class TestAdminNoticesDocsSchema:
    """Swagger OpenAPI 스키마 검증 테스트."""

    def test_schema_includes_admin_notices_endpoints(self, unauth_client):
        res = unauth_client.get("/api/schema/")
        assert res.status_code == status.HTTP_200_OK

        schema = yaml.safe_load(res.content)
        paths = schema.get("paths", {})

        # 1. /api/notices/ -> GET (admin_notice_list), POST (admin_notice_create)
        assert "/api/notices/" in paths
        notice_root = paths["/api/notices/"]
        assert "get" in notice_root
        assert notice_root["get"]["operationId"] == "admin_notice_list"
        assert "admin-notices" in notice_root["get"]["tags"]

        assert "post" in notice_root
        assert notice_root["post"]["operationId"] == "admin_notice_create"
        assert "admin-notices" in notice_root["post"]["tags"]

        # 2. /api/notices/{notice_id}/ -> GET, PUT, DELETE
        assert "/api/notices/{notice_id}/" in paths
        notice_detail = paths["/api/notices/{notice_id}/"]
        assert notice_detail["get"]["operationId"] == "admin_notice_detail"
        assert "admin-notices" in notice_detail["get"]["tags"]
        assert notice_detail["put"]["operationId"] == "admin_notice_update"
        assert "admin-notices" in notice_detail["put"]["tags"]
        assert notice_detail["delete"]["operationId"] == "admin_notice_delete"
        assert "admin-notices" in notice_detail["delete"]["tags"]

        # 3. /api/notices/images/ -> POST
        assert "/api/notices/images/" in paths
        notice_images = paths["/api/notices/images/"]
        assert notice_images["post"]["operationId"] == "admin_notice_image_upload"
        assert "admin-notices" in notice_images["post"]["tags"]

        # 4. Components / Schemas 검증
        components = schema.get("components", {}).get("schemas", {})
        expected_schemas = [
            "AdminNoticeListResponse",
            "AdminNoticeDetailResponse",
            "AdminNoticeCreateResponse",
            "AdminNoticeUpdateResponse",
            "AdminNoticeDeleteResponse",
            "AdminNoticeImageUploadResponse",
        ]
        for schema_name in expected_schemas:
            assert schema_name in components
            schema_def = components[schema_name]
            assert "properties" in schema_def
            assert "success" in schema_def["properties"]
            assert "code" in schema_def["properties"]
            assert "message" in schema_def["properties"]
            assert "data" in schema_def["properties"]
            assert "required" in schema_def
            assert set(["success", "code", "message", "data"]).issubset(set(schema_def["required"]))
