import datetime

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.coupons.models import BoothVerifyCode, Coupon

COUPON_LIST_URL = "/api/coupons/"


def use_url(coupon_id):
    return f"/api/coupons/{coupon_id}/use/"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user1():
    return User.objects.create(
        kakao_id=100001,
        nickname="유저1",
    )


@pytest.fixture
def user2():
    return User.objects.create(
        kakao_id=100002,
        nickname="유저2",
    )


@pytest.mark.django_db
class TestCouponListAPI:
    def test_unauthorized_without_user(self, api_client):
        response = api_client.get(COUPON_LIST_URL)

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_empty_list(self, api_client, user1):
        api_client.force_authenticate(user=user1)

        response = api_client.get(COUPON_LIST_URL)

        assert response.status_code == 200

        data = response.json()

        assert data["success"] is True
        assert data["data"]["total_count"] == 0
        assert data["data"]["items"] == []

    def test_list_returns_own_coupons(self, api_client, user1):
        api_client.force_authenticate(user=user1)

        coupon = Coupon.objects.create(
            user=user1,
            issued_date=timezone.localdate(),
            daily_sequence=1,
            status=Coupon.Status.WIN,
        )

        response = api_client.get(COUPON_LIST_URL)

        assert response.status_code == 200

        items = response.json()["data"]["items"]

        assert len(items) == 1
        assert items[0]["coupon_id"] == coupon.coupon_id
        assert items[0]["status"] == "WIN"

    def test_list_only_returns_own_coupons(
        self,
        api_client,
        user1,
        user2,
    ):
        Coupon.objects.create(
            user=user1,
            issued_date=timezone.localdate(),
            daily_sequence=1,
            status=Coupon.Status.WIN,
        )

        Coupon.objects.create(
            user=user2,
            issued_date=timezone.localdate(),
            daily_sequence=2,
            status=Coupon.Status.LOSE,
        )

        api_client.force_authenticate(user=user1)

        response = api_client.get(COUPON_LIST_URL)

        assert response.status_code == 200

        items = response.json()["data"]["items"]

        assert len(items) == 1
        assert items[0]["status"] == "WIN"

    def test_status_filter(self, api_client, user1):
        api_client.force_authenticate(user=user1)

        yesterday = timezone.localdate() - datetime.timedelta(days=1)

        Coupon.objects.create(
            user=user1,
            issued_date=timezone.localdate(),
            daily_sequence=1,
            status=Coupon.Status.WIN,
        )

        Coupon.objects.create(
            user=user1,
            issued_date=yesterday,
            daily_sequence=1,
            status=Coupon.Status.LOSE,
        )

        response = api_client.get(
            COUPON_LIST_URL,
            {"status": "WIN"},
        )

        assert response.status_code == 200

        items = response.json()["data"]["items"]

        assert len(items) == 1
        assert items[0]["status"] == "WIN"


@pytest.mark.django_db
class TestCouponUseAPI:
    def test_unauthorized_without_user(
        self,
        api_client,
        user1,
    ):
        coupon = Coupon.objects.create(
            user=user1,
            issued_date=timezone.localdate(),
            daily_sequence=1,
            status=Coupon.Status.WIN,
        )

        response = api_client.post(
            use_url(coupon.coupon_id),
            {
                "verify_code": "lovelion14",
            },
            format="json",
        )

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_missing_verify_code(
        self,
        api_client,
        user1,
    ):
        api_client.force_authenticate(user=user1)

        coupon = Coupon.objects.create(
            user=user1,
            issued_date=timezone.localdate(),
            daily_sequence=1,
            status=Coupon.Status.WIN,
        )

        response = api_client.post(
            use_url(coupon.coupon_id),
            {},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_INPUT"

    def test_wrong_verify_code(
        self,
        api_client,
        user1,
    ):
        api_client.force_authenticate(user=user1)

        coupon = Coupon.objects.create(
            user=user1,
            issued_date=timezone.localdate(),
            daily_sequence=1,
            status=Coupon.Status.WIN,
        )

        response = api_client.post(
            use_url(coupon.coupon_id),
            {
                "verify_code": "WRONG",
            },
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_VERIFY_CODE"

    def test_use_success(
        self,
        api_client,
        user1,
    ):
        BoothVerifyCode.objects.create(
            code="lovelion14",
        )

        coupon = Coupon.objects.create(
            user=user1,
            issued_date=timezone.localdate(),
            daily_sequence=1,
            status=Coupon.Status.WIN,
        )

        api_client.force_authenticate(user=user1)

        response = api_client.post(
            use_url(coupon.coupon_id),
            {
                "verify_code": "lovelion14",
            },
            format="json",
        )

        assert response.status_code == 200

        data = response.json()

        assert data["code"] == "COUPON_USE_SUCCESS"
        assert data["data"]["status"] == "USED"

        coupon.refresh_from_db()

        assert coupon.status == Coupon.Status.USED
        assert coupon.used_at is not None

    def test_use_already_used(
        self,
        api_client,
        user1,
    ):
        BoothVerifyCode.objects.create(
            code="lovelion14",
        )

        coupon = Coupon.objects.create(
            user=user1,
            issued_date=timezone.localdate(),
            daily_sequence=1,
            status=Coupon.Status.WIN,
        )

        api_client.force_authenticate(user=user1)

        first = api_client.post(
            use_url(coupon.coupon_id),
            {
                "verify_code": "lovelion14",
            },
            format="json",
        )

        assert first.status_code == 200

        second = api_client.post(
            use_url(coupon.coupon_id),
            {
                "verify_code": "lovelion14",
            },
            format="json",
        )

        assert second.status_code == 409
        assert second.json()["code"] == "COUPON_ALREADY_USED"

    def test_use_not_win(
        self,
        api_client,
        user1,
    ):
        BoothVerifyCode.objects.create(
            code="lovelion14",
        )

        coupon = Coupon.objects.create(
            user=user1,
            issued_date=timezone.localdate(),
            daily_sequence=1,
            status=Coupon.Status.LOSE,
        )

        api_client.force_authenticate(user=user1)

        response = api_client.post(
            use_url(coupon.coupon_id),
            {
                "verify_code": "lovelion14",
            },
            format="json",
        )

        assert response.status_code == 409
        assert response.json()["code"] == "COUPON_NOT_WIN"

    def test_use_expired(
        self,
        api_client,
        user1,
    ):
        BoothVerifyCode.objects.create(
            code="lovelion14",
        )

        yesterday = timezone.localdate() - datetime.timedelta(days=1)

        coupon = Coupon.objects.create(
            user=user1,
            issued_date=yesterday,
            daily_sequence=1,
            status=Coupon.Status.WIN,
        )

        api_client.force_authenticate(user=user1)

        response = api_client.post(
            use_url(coupon.coupon_id),
            {
                "verify_code": "lovelion14",
            },
            format="json",
        )

        assert response.status_code == 409
        assert response.json()["code"] == "COUPON_EXPIRED"

    def test_cannot_use_other_users_coupon(
        self,
        api_client,
        user1,
        user2,
    ):
        BoothVerifyCode.objects.create(
            code="lovelion14",
        )

        coupon = Coupon.objects.create(
            user=user1,
            issued_date=timezone.localdate(),
            daily_sequence=1,
            status=Coupon.Status.WIN,
        )

        # user2로 로그인
        api_client.force_authenticate(user=user2)

        response = api_client.post(
            use_url(coupon.coupon_id),
            {
                "verify_code": "lovelion14",
            },
            format="json",
        )

        assert response.status_code == 409
        assert response.json()["code"] == "COUPON_NOT_USABLE"
