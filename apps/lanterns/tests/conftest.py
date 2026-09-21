import pytest
from django.test import Client

from apps.accounts.models import User
from apps.booths.models import Booth


@pytest.fixture
def auth_headers(settings):
    return {"HTTP_AUTHORIZATION": f"Bearer {settings.ADMIN_API_TOKEN}"}


@pytest.fixture
def client():
    return Client(SERVER_NAME="admin.testserver")


@pytest.fixture
def subdomain_admin_client():
    return Client(SERVER_NAME="admin.testserver")


@pytest.fixture
def test_user(db):
    return User.objects.create(kakao_id=12345678, nickname="테스트유저")


@pytest.fixture
def test_booth(db):
    return Booth.objects.create(
        name="멋사 주점",
        subtitle="컴퓨터공학과",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ALCOHOL,
    )
