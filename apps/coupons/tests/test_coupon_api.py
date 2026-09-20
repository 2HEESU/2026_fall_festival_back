import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.coupons.models import (
    Coupon,
    DailyCouponCounter,
    WinningNumber,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def users():
    return [
        User.objects.create(
            kakao_id=100001,
            nickname="테스트유저1",
        ),
        User.objects.create(
            kakao_id=100002,
            nickname="테스트유저2",
        ),
    ]


# 쿠폰 발급 테스트
@pytest.mark.django_db
def test_coupon_issue(api_client, users):
    user = users[0]

    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse("coupon-issue"),
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()

    assert data["user"] == user.id
    assert data["daily_sequence"] == 1
    assert data["status"] == Coupon.Status.UNSCRATCHED

    coupon = Coupon.objects.get(user=user)

    assert coupon.daily_sequence == 1
    assert coupon.issued_date == timezone.localdate()

    counter = DailyCouponCounter.objects.get(
        date=timezone.localdate()
    )

    assert counter.count == 1


# 같은 사용자가 하루에 두 번 발급받지 못하는지 테스트
@pytest.mark.django_db
def test_coupon_duplicate_issue(api_client, users):
    user = users[0]

    api_client.force_authenticate(user=user)

    url = reverse("coupon-issue")

    first_response = api_client.post(
        url,
        format="json",
    )

    second_response = api_client.post(
        url,
        format="json",
    )

    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_400_BAD_REQUEST

    assert (
        Coupon.objects.filter(
            user=user,
            issued_date=timezone.localdate(),
        ).count()
        == 1
    )


# daily_sequence가 순서대로 증가하는지 테스트
@pytest.mark.django_db
def test_daily_sequence_increases(api_client, users):
    issue_url = reverse("coupon-issue")

    # 1번 유저
    api_client.force_authenticate(user=users[0])

    response1 = api_client.post(
        issue_url,
        format="json",
    )

    # 2번 유저
    api_client.force_authenticate(user=users[1])

    response2 = api_client.post(
        issue_url,
        format="json",
    )

    assert response1.status_code == status.HTTP_201_CREATED
    assert response2.status_code == status.HTTP_201_CREATED

    assert response1.json()["daily_sequence"] == 1
    assert response2.json()["daily_sequence"] == 2

    counter = DailyCouponCounter.objects.get(
        date=timezone.localdate()
    )

    assert counter.count == 2


# 쿠폰 당첨 스크래치 테스트
@pytest.mark.django_db
def test_coupon_scratch_win(api_client, users):
    user = users[0]

    api_client.force_authenticate(user=user)

    # 첫 번째 발급 쿠폰이 당첨
    WinningNumber.objects.create(number=1)

    issue_response = api_client.post(
        reverse("coupon-issue"),
        format="json",
    )

    coupon_id = issue_response.json()["coupon_id"]

    response = api_client.post(
        reverse(
            "coupon-scratch",
            kwargs={"coupon_id": coupon_id},
        )
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["status"] == Coupon.Status.WIN
    assert data["scratched_at"] is not None

    coupon = Coupon.objects.get(coupon_id=coupon_id)

    assert coupon.status == Coupon.Status.WIN
    assert coupon.scratched_at is not None


# 쿠폰 꽝 스크래치 테스트
@pytest.mark.django_db
def test_coupon_scratch_lose(api_client, users):
    user = users[0]

    api_client.force_authenticate(user=user)

    # 당첨번호 없음 -> daily_sequence=1은 꽝
    issue_response = api_client.post(
        reverse("coupon-issue"),
        format="json",
    )

    coupon_id = issue_response.json()["coupon_id"]

    response = api_client.post(
        reverse(
            "coupon-scratch",
            kwargs={"coupon_id": coupon_id},
        )
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["status"] == Coupon.Status.LOSE
    assert data["scratched_at"] is not None


# 이미 결과가 정해진 쿠폰을 다시 긁어도 같은 결과를 반환하는지 테스트
@pytest.mark.django_db
def test_coupon_scratch_returns_same_result_when_called_twice(
    api_client,
    users,
):
    user = users[0]

    api_client.force_authenticate(user=user)

    WinningNumber.objects.create(number=1)

    issue_response = api_client.post(
        reverse("coupon-issue"),
        format="json",
    )

    coupon_id = issue_response.json()["coupon_id"]

    scratch_url = reverse(
        "coupon-scratch",
        kwargs={"coupon_id": coupon_id},
    )

    first_response = api_client.post(scratch_url)
    second_response = api_client.post(scratch_url)

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_200_OK

    first_data = first_response.json()
    second_data = second_response.json()

    assert first_data["status"] == Coupon.Status.WIN
    assert second_data["status"] == Coupon.Status.WIN

    assert first_data["coupon_id"] == second_data["coupon_id"]
    assert first_data["daily_sequence"] == second_data["daily_sequence"]

    coupon = Coupon.objects.get(coupon_id=coupon_id)

    assert coupon.status == Coupon.Status.WIN


# 날짜별 쿠폰 발급 수 / 당첨 수 조회 테스트
@pytest.mark.django_db
def test_coupon_stats(api_client, users):
    # 첫 번째 쿠폰만 당첨
    WinningNumber.objects.create(number=1)

    # 1번 유저 발급
    api_client.force_authenticate(user=users[0])

    response1 = api_client.post(
        reverse("coupon-issue"),
        format="json",
    )

    # 2번 유저 발급
    api_client.force_authenticate(user=users[1])

    response2 = api_client.post(
        reverse("coupon-issue"),
        format="json",
    )

    coupon1_id = response1.json()["coupon_id"]
    coupon2_id = response2.json()["coupon_id"]

    # 1번 유저 쿠폰 긁기
    api_client.force_authenticate(user=users[0])

    api_client.post(
        reverse(
            "coupon-scratch",
            kwargs={"coupon_id": coupon1_id},
        )
    )

    # 2번 유저 쿠폰 긁기
    api_client.force_authenticate(user=users[1])

    api_client.post(
        reverse(
            "coupon-scratch",
            kwargs={"coupon_id": coupon2_id},
        )
    )

    # 통계 조회
    response = api_client.get(
        reverse("coupon-stats")
    )

    assert response.status_code == status.HTTP_200_OK

    body = response.json()

    assert body["success"] is True
    assert body["code"] == "COUPON_STATS_SUCCESS"

    assert len(body["data"]) == 1

    stats = body["data"][0]

    assert stats["date"] == str(timezone.localdate())

    # 오늘 총 2개 발급
    assert stats["issued_count"] == 2

    # daily_sequence=1만 당첨
    assert stats["win_count"] == 1