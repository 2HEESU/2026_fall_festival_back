import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.booths.models import Booth
from apps.lanterns.models import Lantern, LanternReport

ADMIN_LANTERNS_URL = "/api/lanterns/"


@pytest.mark.django_db
class TestAdminLanternListAPI:
    def test_unauthorized_access_denied(self, client):
        response = client.get(ADMIN_LANTERNS_URL, HTTP_AUTHORIZATION="Bearer invalid-token")
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "UNAUTHORIZED"

    def test_list_lanterns_report_desc_ordering_by_default(
        self, client, auth_headers, test_user, test_booth
    ):
        # 1. 신고 없는 등불
        l1 = Lantern.objects.create(
            user=test_user,
            booth=test_booth,
            nickname="유저1",
            message="등불 메시지 1",
        )

        # 2. 신고 2건 등불 (욕설 및 비방 2건)
        user2 = User.objects.create(kakao_id=2222, nickname="유저2")
        l2 = Lantern.objects.create(
            user=user2,
            booth=test_booth,
            nickname="유저2",
            message="등불 메시지 2",
        )
        report_user1 = User.objects.create(kakao_id=3001, nickname="신고자1")
        report_user2 = User.objects.create(kakao_id=3002, nickname="신고자2")
        LanternReport.objects.create(
            lantern=l2, user=report_user1, reason=LanternReport.Reason.ABUSE
        )
        LanternReport.objects.create(
            lantern=l2, user=report_user2, reason=LanternReport.Reason.ABUSE
        )

        # 3. 신고 1건 등불 (허위정보 1건)
        user3 = User.objects.create(kakao_id=3333, nickname="유저3")
        l3 = Lantern.objects.create(
            user=user3,
            booth=test_booth,
            nickname="유저3",
            message="등불 메시지 3",
        )
        LanternReport.objects.create(
            lantern=l3, user=report_user1, reason=LanternReport.Reason.FALSE_INFO
        )

        response = client.get(ADMIN_LANTERNS_URL, **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "ADMIN_LANTERN_LIST_SUCCESS"

        items = data["data"]["items"]
        assert len(items) == 3

        # 신고 많은 순 정렬: l2 (2건) -> l3 (1건) -> l1 (0건)
        assert items[0]["id"] == l2.id
        assert items[0]["report_count"] == 2
        assert items[0]["top_report_reason"] == "욕설 및 비방"
        assert items[0]["booth_name"] == "멋사 주점"

        assert items[1]["id"] == l3.id
        assert items[1]["report_count"] == 1
        assert items[1]["top_report_reason"] == "허위정보"

        assert items[2]["id"] == l1.id
        assert items[2]["report_count"] == 0
        assert items[2]["top_report_reason"] is None

    def test_top_report_reason_tie_selects_first_reported(
        self, client, auth_headers, test_user, test_booth
    ):
        # 욕설 1건(먼저 등록), 음란 1건(나중에 등록) 동률일 때 최초 신고인 욕설이 선택되어야 함
        lantern = Lantern.objects.create(
            user=test_user,
            booth=test_booth,
            message="동률 테스트 등불",
        )
        u1 = User.objects.create(kakao_id=5001, nickname="신고자1")
        u2 = User.objects.create(kakao_id=5002, nickname="신고자2")

        LanternReport.objects.create(lantern=lantern, user=u1, reason=LanternReport.Reason.ABUSE)
        LanternReport.objects.create(lantern=lantern, user=u2, reason=LanternReport.Reason.OBSCENE)

        response = client.get(ADMIN_LANTERNS_URL, **auth_headers)
        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["report_count"] == 2
        assert items[0]["top_report_reason"] == "욕설 및 비방"

    def test_list_lanterns_latest_ordering(self, client, auth_headers, test_user, test_booth):
        user2 = User.objects.create(kakao_id=2000, nickname="유저2")
        l1 = Lantern.objects.create(user=test_user, booth=test_booth, message="메시지 1")
        l2 = Lantern.objects.create(user=user2, booth=test_booth, message="메시지 2")

        # l1에 신고 추가 (신고는 l1이 많지만 최신순 정렬 시 l2가 먼저 와야 함)
        report_user = User.objects.create(kakao_id=3000, nickname="신고자")
        LanternReport.objects.create(
            lantern=l1, user=report_user, reason=LanternReport.Reason.ABUSE
        )

        response = client.get(f"{ADMIN_LANTERNS_URL}?sort=LATEST", **auth_headers)
        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert items[0]["id"] == l2.id
        assert items[1]["id"] == l1.id

    def test_soft_deleted_lanterns_excluded(self, client, auth_headers, test_user, test_booth):
        active_lantern = Lantern.objects.create(
            user=test_user, booth=test_booth, message="활성 등불"
        )
        user2 = User.objects.create(kakao_id=2001, nickname="유저2")
        deleted_lantern = Lantern.objects.create(
            user=user2,
            booth=test_booth,
            message="삭제된 등불",
            deleted_at=timezone.now(),
            deleted_by=Lantern.DeletedBy.ADMIN,
        )

        response = client.get(ADMIN_LANTERNS_URL, **auth_headers)
        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["id"] == active_lantern.id
        assert all(item["id"] != deleted_lantern.id for item in items)

    def test_pagination(self, client, auth_headers, test_booth):
        for i in range(5):
            u = User.objects.create(kakao_id=1000 + i, nickname=f"유저{i}")
            Lantern.objects.create(user=u, booth=test_booth, message=f"메시지 {i}")

        response = client.get(f"{ADMIN_LANTERNS_URL}?page=0&size=2", **auth_headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["items"]) == 2
        assert data["meta"]["total_count"] == 5
        assert data["meta"]["page"] == 0
        assert data["meta"]["size"] == 2
        assert data["meta"]["has_next"] is True

    def test_invalid_query_params_returns_400(self, client, auth_headers):
        response = client.get(f"{ADMIN_LANTERNS_URL}?sort=INVALID_SORT", **auth_headers)
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "INVALID_INPUT"


@pytest.mark.django_db
class TestAdminLanternDetailAPI:
    def test_unauthorized_access_denied(self, client):
        response = client.get(f"{ADMIN_LANTERNS_URL}1/", HTTP_AUTHORIZATION="Bearer invalid-token")
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "UNAUTHORIZED"

    def test_get_lantern_detail_success(self, client, auth_headers, test_user):
        booth = Booth.objects.create(
            name="동빛 주점",
            subtitle="산업시스템공학과",
            place_type=Booth.PlaceType.BOOTH,
            category=Booth.Category.ALCOHOL,
        )
        lantern = Lantern.objects.create(
            user=test_user,
            booth=booth,
            nickname="행복한 코끼리",
            message="축제 너무 재밌어요!",
        )

        r_user1 = User.objects.create(kakao_id=4001, nickname="신고1")
        r_user2 = User.objects.create(kakao_id=4002, nickname="신고2")
        r_user3 = User.objects.create(kakao_id=4003, nickname="신고3")

        # 음란·불쾌 2건, 기타 1건 -> 최다 신고 사유: 음란·불쾌
        LanternReport.objects.create(
            lantern=lantern, user=r_user1, reason=LanternReport.Reason.OBSCENE
        )
        LanternReport.objects.create(
            lantern=lantern, user=r_user2, reason=LanternReport.Reason.OBSCENE
        )
        LanternReport.objects.create(lantern=lantern, user=r_user3, reason=LanternReport.Reason.ETC)

        response = client.get(f"{ADMIN_LANTERNS_URL}{lantern.id}/", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "ADMIN_LANTERN_DETAIL_SUCCESS"

        detail = data["data"]
        assert detail["id"] == lantern.id
        assert detail["nickname"] == "행복한 코끼리"
        assert detail["message"] == "축제 너무 재밌어요!"
        assert detail["booth_name"] == "동빛 주점"
        assert detail["booth_department"] == "산업시스템공학과"
        assert detail["report_count"] == 3
        assert detail["top_report_reason"] == "음란·불쾌"
        assert "created_at" in detail

    def test_get_lantern_detail_not_found(self, client, auth_headers):
        response = client.get(f"{ADMIN_LANTERNS_URL}99999/", **auth_headers)
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "NOT_FOUND"

    def test_get_soft_deleted_lantern_returns_404(
        self, client, auth_headers, test_user, test_booth
    ):
        lantern = Lantern.objects.create(
            user=test_user,
            booth=test_booth,
            message="삭제된 등불",
            deleted_at=timezone.now(),
            deleted_by=Lantern.DeletedBy.ADMIN,
        )

        response = client.get(f"{ADMIN_LANTERNS_URL}{lantern.id}/", **auth_headers)
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "NOT_FOUND"
