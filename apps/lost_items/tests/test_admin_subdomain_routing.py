"""서브도메인 기준 관리자/사용자 API 라우팅 테스트 (lost_items)."""

import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def subdomain_admin_client():
    return Client(SERVER_NAME="admin.testserver")


@pytest.fixture
def admin_headers(settings):
    return {"HTTP_AUTHORIZATION": f"Bearer {settings.ADMIN_API_TOKEN}"}


@pytest.mark.django_db
def test_user_host_cannot_reach_admin_lost_items(client, admin_headers):
    # /images/ 업로드는 admin_urls에만 있는 경로라 일반 도메인에선 404여야 함
    response = client.post("/api/lost-items/images/", SERVER_NAME="testserver", **admin_headers)
    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_host_reaches_admin_lost_items(subdomain_admin_client, admin_headers):
    response = subdomain_admin_client.get("/api/lost-items/", **admin_headers)
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_host_still_requires_admin_auth(subdomain_admin_client):
    response = subdomain_admin_client.get("/api/lost-items/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_admin_host_cannot_reach_user_only_api(subdomain_admin_client):
    for path in ("/api/accounts/", "/api/booths/", "/api/lanterns/", "/api/performances/"):
        response = subdomain_admin_client.get(path)
        assert response.status_code == 404, path
