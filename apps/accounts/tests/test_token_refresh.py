"""Token refresh API tests."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import RefreshToken, User
from apps.accounts.views import _hash_token

REFRESH_URL = "/api/accounts/token/refresh/"
RAW_TOKEN = "valid-refresh-token"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create(kakao_id=2001, nickname="리프레시테스트")


@pytest.fixture
def refresh_token(user):
    return RefreshToken.objects.create(
        user=user, token=_hash_token(RAW_TOKEN), expires_at=timezone.now() + timedelta(days=7)
    )


@pytest.mark.django_db
class TestTokenRefresh:
    def test_valid_refresh_token_issues_new_tokens(self, client, refresh_token):
        response = client.post(REFRESH_URL, data={"refresh_token": RAW_TOKEN}, format="json")

        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body["data"]
        assert "refresh_token" in body["data"]
        assert body["data"]["refresh_token"] != RAW_TOKEN

    def test_rotation_invalidates_old_refresh_token(self, client, refresh_token):
        first = client.post(REFRESH_URL, data={"refresh_token": RAW_TOKEN}, format="json")
        assert first.status_code == 200

        second = client.post(REFRESH_URL, data={"refresh_token": RAW_TOKEN}, format="json")
        assert second.status_code == 401

    def test_nonexistent_refresh_token_returns_401(self, client, user):
        response = client.post(REFRESH_URL, data={"refresh_token": "garbage"}, format="json")
        assert response.status_code == 401

    def test_expired_refresh_token_returns_401_and_deletes_row(self, client, user):
        RefreshToken.objects.create(
            user=user,
            token=_hash_token("expired-token"),
            expires_at=timezone.now() - timedelta(days=1),
        )
        response = client.post(REFRESH_URL, data={"refresh_token": "expired-token"}, format="json")

        assert response.status_code == 401
        assert not RefreshToken.objects.filter(token=_hash_token("expired-token")).exists()

    def test_missing_refresh_token_field_returns_400(self, client):
        response = client.post(REFRESH_URL, data={}, format="json")
        assert response.status_code == 400
