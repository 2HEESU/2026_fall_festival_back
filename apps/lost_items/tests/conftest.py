import pytest
from django.test import Client


@pytest.fixture
def auth_headers(settings):
    return {"HTTP_AUTHORIZATION": f"Bearer {settings.ADMIN_API_TOKEN}"}


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def subdomain_admin_client():
    """admin 서브도메인으로 라우팅되는 테스트 클라이언트."""
    return Client(SERVER_NAME="admin.testserver")
