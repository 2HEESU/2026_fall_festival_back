"""Logout API tests."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import RefreshToken, User
from apps.accounts.views import _hash_token

LOGOUT_URL = "/api/accounts/logout/"
REFRESH_URL = "/api/accounts/token/refresh/"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create(kakao_id=5001, nickname="로그아웃테스트")


@pytest.fixture
def refresh_token(user):
    return RefreshToken.objects.create(
        user=user,
        token=_hash_token("logout-target-token"),
        expires_at=timezone.now() + timedelta(days=7),
    )


@pytest.fixture
def other_device_token(user):
    return RefreshToken.objects.create(
        user=user,
        token=_hash_token("other-device-token"),
        expires_at=timezone.now() + timedelta(days=7),
    )


@pytest.mark.django_db
class TestLogout:
    def test_logout_deletes_target_token_only(self, client, refresh_token, other_device_token):
        response = client.post(
            LOGOUT_URL, data={"refresh_token": "logout-target-token"}, format="json"
        )

        assert response.status_code == 200
        assert response.json()["code"] == "LOGOUT_SUCCESS"
        assert not RefreshToken.objects.filter(token=_hash_token("logout-target-token")).exists()
        assert RefreshToken.objects.filter(token=_hash_token("other-device-token")).exists()

    def test_logout_with_nonexistent_token_is_idempotent(self, client):
        response = client.post(LOGOUT_URL, data={"refresh_token": "garbage-token"}, format="json")
        assert response.status_code == 200

    def test_logout_missing_field_returns_400(self, client):
        response = client.post(LOGOUT_URL, data={}, format="json")
        assert response.status_code == 400

    def test_logged_out_token_cannot_be_refreshed(self, client, refresh_token):
        client.post(LOGOUT_URL, data={"refresh_token": "logout-target-token"}, format="json")

        response = client.post(
            REFRESH_URL, data={"refresh_token": "logout-target-token"}, format="json"
        )
        assert response.status_code == 401
