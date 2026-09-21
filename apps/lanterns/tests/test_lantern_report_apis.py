"""Lantern report API tests."""

from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.booths.models import Booth
from apps.lanterns.models import Lantern, LanternReport
from apps.lanterns.serializers import LanternReportCreateSerializer
from common.exceptions import ApiError


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create(kakao_id=3001, nickname="신고자")


@pytest.fixture
def other_user(db):
    return User.objects.create(kakao_id=3002, nickname="작성자")


@pytest.fixture
def booth(db):
    return Booth.objects.create(
        name="테스트 부스", place_type=Booth.PlaceType.BOOTH, category=Booth.Category.ETC
    )


@pytest.fixture
def lantern(booth, other_user):
    return Lantern.objects.create(user=other_user, booth=booth, message="신고 대상")


@pytest.fixture
def auth_client(client, user):
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestLanternReport:
    def test_report_success(self, auth_client, user, lantern):
        response = auth_client.post(f"/api/lanterns/{lantern.id}/reports/", {"reason": "ABUSE"})
        assert response.status_code == 201
        body = response.json()
        assert body["code"] == "LANTERN_REPORT_SUCCESS"
        assert LanternReport.objects.filter(lantern=lantern, user=user, reason="ABUSE").exists()

    def test_report_rejects_invalid_reason(self, auth_client, lantern):
        response = auth_client.post(f"/api/lanterns/{lantern.id}/reports/", {"reason": "WRONG"})
        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_REQUEST_PARAM"

    def test_report_rejects_missing_lantern(self, auth_client):
        response = auth_client.post("/api/lanterns/999999/reports/", {"reason": "ABUSE"})
        assert response.status_code == 404
        assert response.json()["code"] == "LANTERN_NOT_FOUND"

    def test_report_rejects_deleted_lantern(self, auth_client, lantern):
        lantern.deleted_at = timezone.now()
        lantern.deleted_by = Lantern.DeletedBy.USER
        lantern.save()

        response = auth_client.post(f"/api/lanterns/{lantern.id}/reports/", {"reason": "ABUSE"})
        assert response.status_code == 404
        assert response.json()["code"] == "LANTERN_NOT_FOUND"

    def test_report_rejects_duplicate(self, auth_client, user, lantern):
        LanternReport.objects.create(lantern=lantern, user=user, reason="ABUSE")
        response = auth_client.post(f"/api/lanterns/{lantern.id}/reports/", {"reason": "ETC"})
        assert response.status_code == 409
        assert response.json()["code"] == "ALREADY_REPORTED"

    def test_report_requires_authentication(self, client, lantern):
        response = client.post(f"/api/lanterns/{lantern.id}/reports/", {"reason": "ABUSE"})
        assert response.status_code in (401, 403)

    def test_create_handles_race_duplicate_report(self, user, lantern):
        LanternReport.objects.create(lantern=lantern, user=user, reason="ABUSE")

        serializer = LanternReportCreateSerializer(
            context={"request": SimpleNamespace(user=user), "lantern": lantern}
        )

        with pytest.raises(ApiError) as exc_info:
            serializer.create({"reason": "ETC"})

        assert exc_info.value.code == "ALREADY_REPORTED"
