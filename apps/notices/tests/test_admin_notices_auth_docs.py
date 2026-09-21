"""Tests for Admin Notices authentication, host routing, and OpenAPI documentation."""

import io

import pytest
import yaml
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from apps.notices.models import Notice

pytestmark = pytest.mark.django_db


def create_dummy_image(name="test.jpg", ext="JPEG"):
    file_obj = io.BytesIO()
    image = Image.new("RGB", (100, 100), color=(255, 0, 0))
    image.save(file_obj, format=ext)
    file_obj.seek(0)
    return SimpleUploadedFile(name, file_obj.read(), content_type=f"image/{ext.lower()}")


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
def sample_notice():
    return Notice.objects.create(
        title="테스트 공지사항",
        content="테스트 본문 내용입니다.",
        type=Notice.Type.NORMAL,
    )


class TestAdminNoticesAuth:
    """관리자 공지 6개 엔드포인트의 IsAdmin 권한 및 토큰 검증 테스트."""

    # 1. 누락된 토큰 (Missing Token) -> 401
    def test_missing_token_returns_401(self, unauth_client, sample_notice):
        # 1) 목록 조회
        res = unauth_client.get("/api/notices/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

        # 2) 등록
        res = unauth_client.post(
            "/api/notices/",
            {"title": "제목", "content": "내용", "type": "NORMAL"},
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

        # 3) 상세 조회
        res = unauth_client.get(f"/api/notices/{sample_notice.id}/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

        # 4) 수정
        res = unauth_client.put(
            f"/api/notices/{sample_notice.id}/",
            {"title": "수정", "content": "수정내용", "type": "NORMAL"},
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

        # 5) 삭제
        res = unauth_client.delete(f"/api/notices/{sample_notice.id}/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

        # 6) 이미지 업로드
        img = create_dummy_image()
        res = unauth_client.post(
            "/api/notices/images/",
            {"image": img},
            format="multipart",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

    # 2. 유효하지 않은 토큰 (Invalid Token / Wrong Scheme) -> 401
    def test_invalid_token_returns_401(self, invalid_token_client, sample_notice):
        # 1) 목록 조회
        res = invalid_token_client.get("/api/notices/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

        # 2) 등록
        res = invalid_token_client.post(
            "/api/notices/",
            {"title": "제목", "content": "내용", "type": "NORMAL"},
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

        # 3) 상세 조회
        res = invalid_token_client.get(f"/api/notices/{sample_notice.id}/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

        # 4) 수정
        res = invalid_token_client.put(
            f"/api/notices/{sample_notice.id}/",
            {"title": "수정", "content": "수정내용", "type": "NORMAL"},
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

        # 5) 삭제
        res = invalid_token_client.delete(f"/api/notices/{sample_notice.id}/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

        # 6) 이미지 업로드
        img = create_dummy_image()
        res = invalid_token_client.post(
            "/api/notices/images/",
            {"image": img},
            format="multipart",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["code"] == "UNAUTHORIZED"

    # 3. 유효한 토큰 (Valid Token) -> 성공 (200 / 201)
    def test_authorized_requests_succeed(self, auth_client, sample_notice):
        # 1) 목록 조회
        res_list = auth_client.get("/api/notices/")
        assert res_list.status_code == status.HTTP_200_OK
        assert res_list.data["code"] == "ADMIN_NOTICE_LIST_SUCCESS"

        # 2) 신규 등록
        res_create = auth_client.post(
            "/api/notices/",
            {"title": "신규 공지", "content": "신규 본문", "type": "NORMAL"},
            format="json",
        )
        assert res_create.status_code == status.HTTP_201_CREATED
        assert res_create.data["code"] == "ADMIN_NOTICE_CREATE_SUCCESS"

        # 3) 상세 조회
        res_detail = auth_client.get(f"/api/notices/{sample_notice.id}/")
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.data["code"] == "ADMIN_NOTICE_DETAIL_SUCCESS"

        # 4) 수정
        res_update = auth_client.put(
            f"/api/notices/{sample_notice.id}/",
            {"title": "수정제목", "content": "수정본문", "type": "URGENT"},
            format="json",
        )
        assert res_update.status_code == status.HTTP_200_OK
        assert res_update.data["code"] == "ADMIN_NOTICE_UPDATE_SUCCESS"

        # 5) 삭제
        res_delete = auth_client.delete(f"/api/notices/{sample_notice.id}/")
        assert res_delete.status_code == status.HTTP_200_OK
        assert res_delete.data["code"] == "ADMIN_NOTICE_DELETE_SUCCESS"

        # 6) 이미지 업로드
        img = create_dummy_image()
        res_img = auth_client.post(
            "/api/notices/images/",
            {"image": img},
            format="multipart",
        )
        assert res_img.status_code == status.HTTP_201_CREATED
        assert res_img.data["code"] == "IMAGE_UPLOAD_SUCCESS"


class TestAdminNoticesHostRouting:
    """도메인/호스트별 URL 라우팅 분리 테스트."""

    def test_user_domain_reaches_public_notices_without_auth(self, sample_notice):
        client = Client(SERVER_NAME="testserver")

        # 1) 일반 도메인 공지 목록 조회 -> 인증 없이 200 OK
        res = client.get("/api/notices/")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["code"] == "NOTICE_LIST_SUCCESS"

        # 2) 일반 도메인 공지 상세 조회 -> 인증 없이 200 OK
        res_detail = client.get(f"/api/notices/{sample_notice.id}/")
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.json()["code"] == "NOTICE_DETAIL_SUCCESS"

        # 3) 일반 도메인 롤링 공지 조회 -> 인증 없이 200 OK
        res_rolling = client.get("/api/notices/rolling/")
        assert res_rolling.status_code == status.HTTP_200_OK
        assert res_rolling.json()["code"] == "NOTICE_ROLLING_LIST_SUCCESS"

    def test_user_domain_cannot_reach_admin_only_endpoints(self):
        client = Client(SERVER_NAME="testserver")
        auth_header = {"HTTP_AUTHORIZATION": f"Bearer {settings.ADMIN_API_TOKEN}"}

        # /api/notices/images/ 는 admin_urls 에만 존재하므로 일반 도메인에서는 404
        res = client.post("/api/notices/images/", **auth_header)
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_domain_routing_and_docs(self):
        client = Client(SERVER_NAME="admin.testserver")
        auth_header = {"HTTP_AUTHORIZATION": f"Bearer {settings.ADMIN_API_TOKEN}"}

        # 1) 관리자 도메인 공지 목록 -> 인증 필요 (미인증 401, 인증 200)
        res_unauth = client.get("/api/notices/")
        assert res_unauth.status_code == status.HTTP_401_UNAUTHORIZED

        res_auth = client.get("/api/notices/", **auth_header)
        assert res_auth.status_code == status.HTTP_200_OK
        assert res_auth.json()["code"] == "ADMIN_NOTICE_LIST_SUCCESS"

        # 2) 관리자 도메인 schema & docs 접근 가능
        res_schema = client.get("/api/schema/")
        assert res_schema.status_code == status.HTTP_200_OK

        res_docs = client.get("/api/docs/")
        assert res_docs.status_code == status.HTTP_200_OK


class TestAdminNoticesDocsSchema:
    """Swagger OpenAPI 스키마 검증 테스트."""

    def test_schema_includes_admin_and_user_notices_endpoints(self, unauth_client):
        res = unauth_client.get("/api/schema/")
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

        # 2. /api/notices/ -> GET (admin_notice_list), POST (admin_notice_create)
        assert "/api/notices/" in paths
        notice_root = paths["/api/notices/"]
        assert "get" in notice_root
        get_op = notice_root["get"]
        assert get_op["operationId"] == "admin_notice_list"
        assert "admin-notices" in get_op["tags"]
        assert "200" in get_op["responses"]
        assert "400" in get_op["responses"]
        assert "401" in get_op["responses"]

        assert "post" in notice_root
        post_op = notice_root["post"]
        assert post_op["operationId"] == "admin_notice_create"
        assert "admin-notices" in post_op["tags"]
        assert "201" in post_op["responses"]
        assert "400" in post_op["responses"]
        assert "401" in post_op["responses"]

        # 3. /api/notices/{notice_id}/ -> GET, PUT, DELETE
        assert "/api/notices/{notice_id}/" in paths
        notice_detail = paths["/api/notices/{notice_id}/"]
        detail_get = notice_detail["get"]
        assert detail_get["operationId"] == "admin_notice_detail"
        assert "admin-notices" in detail_get["tags"]
        assert "200" in detail_get["responses"]
        assert "401" in detail_get["responses"]
        assert "404" in detail_get["responses"]

        detail_put = notice_detail["put"]
        assert detail_put["operationId"] == "admin_notice_update"
        assert "admin-notices" in detail_put["tags"]
        assert "200" in detail_put["responses"]
        assert "400" in detail_put["responses"]
        assert "401" in detail_put["responses"]
        assert "404" in detail_put["responses"]

        detail_delete = notice_detail["delete"]
        assert detail_delete["operationId"] == "admin_notice_delete"
        assert "admin-notices" in detail_delete["tags"]
        assert "200" in detail_delete["responses"]
        assert "401" in detail_delete["responses"]
        assert "404" in detail_delete["responses"]

        # 4. /api/notices/images/ -> POST
        assert "/api/notices/images/" in paths
        notice_images = paths["/api/notices/images/"]
        img_post = notice_images["post"]
        assert img_post["operationId"] == "admin_notice_image_upload"
        assert "admin-notices" in img_post["tags"]
        assert "201" in img_post["responses"]
        assert "400" in img_post["responses"]
        assert "401" in img_post["responses"]
        assert "413" in img_post["responses"]

        # 5. Components / Schemas 검증
        schemas = components.get("schemas", {})
        expected_schemas = [
            "AdminNoticeListResponse",
            "AdminNoticeDetailResponse",
            "AdminNoticeCreateResponse",
            "AdminNoticeUpdateResponse",
            "AdminNoticeDeleteResponse",
            "AdminNoticeImageUploadResponse",
            "ErrorResponse",
        ]
        for schema_name in expected_schemas:
            assert schema_name in schemas
            schema_def = schemas[schema_name]
            assert "properties" in schema_def
            assert "success" in schema_def["properties"]
            assert "code" in schema_def["properties"]
            assert "message" in schema_def["properties"]
