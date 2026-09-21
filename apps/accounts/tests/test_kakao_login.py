"""Kakao login API tests."""

from unittest.mock import Mock, patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import RefreshToken, User
from apps.accounts.views import _hash_token

LOGIN_URL = "/api/accounts/login/"


@pytest.fixture
def client():
    return APIClient()


def _fake_response(json_data, status_code=200):
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


@pytest.mark.django_db
class TestKakaoLogin:
    def test_missing_code_returns_400(self, client):
        response = client.post(LOGIN_URL, data={}, format="json")
        assert response.status_code == 400

    def test_kakao_server_connection_failure_returns_502(self, client):
        with patch("apps.accounts.views.requests.post") as mock_post:
            mock_post.side_effect = __import__("requests").exceptions.ConnectionError("boom")
            response = client.post(LOGIN_URL, data={"code": "abc"}, format="json")
        assert response.status_code == 502

    def test_missing_kakao_access_token_returns_401(self, client):
        with patch("apps.accounts.views.requests.post") as mock_post:
            mock_post.return_value = _fake_response({})
            response = client.post(LOGIN_URL, data={"code": "abc"}, format="json")
        assert response.status_code == 401

    def test_new_user_login_success(self, client):
        with (
            patch("apps.accounts.views.requests.post") as mock_post,
            patch("apps.accounts.views.requests.get") as mock_get,
        ):
            mock_post.return_value = _fake_response({"access_token": "kakao-tok"})
            mock_get.return_value = _fake_response(
                {
                    "id": 111222333,
                    "properties": {
                        "nickname": "테스트유저",
                        "profile_image": "http://img.example/x.png",
                    },
                }
            )
            response = client.post(LOGIN_URL, data={"code": "abc"}, format="json")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["is_new_user"] is True
        assert "access_token" in body["data"]
        assert "refresh_token" in body["data"]
        assert User.objects.filter(kakao_id=111222333).exists()
        assert RefreshToken.objects.filter(
            token=_hash_token(body["data"]["refresh_token"])
        ).exists()

    def test_existing_user_login_updates_profile(self, client):
        User.objects.create(kakao_id=555, nickname="OldNick")
        with (
            patch("apps.accounts.views.requests.post") as mock_post,
            patch("apps.accounts.views.requests.get") as mock_get,
        ):
            mock_post.return_value = _fake_response({"access_token": "kakao-tok"})
            mock_get.return_value = _fake_response(
                {"id": 555, "properties": {"nickname": "NewNick"}}
            )
            response = client.post(LOGIN_URL, data={"code": "abc"}, format="json")

        assert response.status_code == 200
        assert response.json()["data"]["is_new_user"] is False
        user = User.objects.get(kakao_id=555)
        assert user.nickname == "NewNick"
        assert User.objects.filter(kakao_id=555).count() == 1

    def test_incomplete_kakao_profile_returns_400(self, client):
        with (
            patch("apps.accounts.views.requests.post") as mock_post,
            patch("apps.accounts.views.requests.get") as mock_get,
        ):
            mock_post.return_value = _fake_response({"access_token": "kakao-tok"})
            mock_get.return_value = _fake_response({"id": 999})  # nickname 없음
            response = client.post(LOGIN_URL, data={"code": "abc"}, format="json")
        assert response.status_code == 400

    def test_refresh_token_count_capped_at_five(self, client):
        for _ in range(10):
            with (
                patch("apps.accounts.views.requests.post") as mock_post,
                patch("apps.accounts.views.requests.get") as mock_get,
            ):
                mock_post.return_value = _fake_response({"access_token": "kakao-tok"})
                mock_get.return_value = _fake_response(
                    {"id": 333, "properties": {"nickname": "캡테스트"}}
                )
                client.post(LOGIN_URL, data={"code": "abc"}, format="json")

        user = User.objects.get(kakao_id=333)
        assert RefreshToken.objects.filter(user=user).count() == 5
