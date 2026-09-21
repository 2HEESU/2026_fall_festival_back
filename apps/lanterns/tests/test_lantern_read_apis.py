"""Lantern list/detail (조회) API tests."""

from datetime import date

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.booths.models import Booth
from apps.lanterns.models import Lantern

FESTIVAL_DAY = date(2026, 9, 29)
OTHER_DAY = date(2026, 9, 30)


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create(kakao_id=2001, nickname="테스트유저")


@pytest.fixture
def other_user(db):
    return User.objects.create(kakao_id=2002, nickname="다른유저")


@pytest.fixture
def booth(db):
    return Booth.objects.create(
        name="테스트 부스",
        place_type=Booth.PlaceType.BOOTH,
        category=Booth.Category.ETC,
    )


@pytest.fixture
def auth_client(client, user):
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestLanternList:
    def test_list_excludes_deleted_for_public(self, client, user, booth):
        Lantern.objects.create(user=user, booth=booth, message="공개1", festival_date=FESTIVAL_DAY)
        deleted = Lantern.objects.create(
            user=user, booth=booth, message="삭제됨", festival_date=OTHER_DAY
        )
        deleted.deleted_at = timezone.now()
        deleted.deleted_by = Lantern.DeletedBy.USER
        deleted.save()

        response = client.get("/api/lanterns/")
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "LANTERN_LIST_SUCCESS"
        assert body["data"]["total_count"] == 1
        assert len(body["data"]["items"]) == 1
        assert body["data"]["items"][0]["message"] == "공개1"
        assert body["data"]["items"][0]["status"] == "active"

    def test_list_mine_includes_deleted_and_hides_message(self, auth_client, user, booth):
        Lantern.objects.create(
            user=user, booth=booth, message="살아있음", festival_date=FESTIVAL_DAY
        )
        deleted = Lantern.objects.create(
            user=user, booth=booth, message="삭제될 메시지", festival_date=OTHER_DAY
        )
        deleted.deleted_at = timezone.now()
        deleted.deleted_by = Lantern.DeletedBy.ADMIN
        deleted.save()

        response = auth_client.get("/api/lanterns/", {"mine": "true"})
        assert response.status_code == 200
        items = {item["lantern_id"]: item for item in response.json()["data"]["items"]}
        assert items[deleted.id]["message"] is None
        assert items[deleted.id]["status"] == "deleted_by_admin"

    def test_list_mine_excludes_other_users_lanterns(self, auth_client, user, other_user, booth):
        Lantern.objects.create(
            user=user, booth=booth, message="내 등불", festival_date=FESTIVAL_DAY
        )
        Lantern.objects.create(
            user=other_user, booth=booth, message="남의 등불", festival_date=FESTIVAL_DAY
        )

        response = auth_client.get("/api/lanterns/", {"mine": "true"})
        body = response.json()
        assert body["data"]["total_count"] == 1
        assert body["data"]["items"][0]["message"] == "내 등불"

    def test_list_requires_login_for_mine(self, client):
        response = client.get("/api/lanterns/", {"mine": "true"})
        assert response.status_code == 401

    def test_list_filters_by_booth_id(self, client, user, booth):
        other_booth = Booth.objects.create(
            name="다른 부스", place_type=Booth.PlaceType.BOOTH, category=Booth.Category.ETC
        )
        Lantern.objects.create(user=user, booth=booth, message="A", festival_date=FESTIVAL_DAY)
        Lantern.objects.create(
            user=user, booth=other_booth, message="B", festival_date=FESTIVAL_DAY
        )

        response = client.get("/api/lanterns/", {"booth_id": booth.id})
        body = response.json()
        assert body["data"]["total_count"] == 1
        assert body["data"]["items"][0]["booth_id"] == booth.id

    def test_list_filters_by_date(self, client, user, booth):
        Lantern.objects.create(user=user, booth=booth, message="A", festival_date=FESTIVAL_DAY)
        Lantern.objects.create(user=user, booth=booth, message="B", festival_date=OTHER_DAY)

        response = client.get("/api/lanterns/", {"date": "2026-09-29"})
        body = response.json()
        assert body["data"]["total_count"] == 1
        assert body["data"]["items"][0]["message"] == "A"

    def test_list_rejects_invalid_date_format(self, client):
        response = client.get("/api/lanterns/", {"date": "2026/09/29"})
        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_REQUEST_PARAM"

    def test_list_includes_booth_name(self, client, user, booth):
        Lantern.objects.create(user=user, booth=booth, message="A", festival_date=FESTIVAL_DAY)

        response = client.get("/api/lanterns/")
        body = response.json()
        assert body["data"]["items"][0]["booth_name"] == booth.name

    def test_list_does_not_n_plus_one_query_booth(
        self, client, user, booth, django_assert_num_queries
    ):
        other_booth = Booth.objects.create(
            name="다른 부스", place_type=Booth.PlaceType.BOOTH, category=Booth.Category.ETC
        )
        Lantern.objects.create(user=user, booth=booth, message="A", festival_date=FESTIVAL_DAY)
        Lantern.objects.create(
            user=user, booth=other_booth, message="B", festival_date=FESTIVAL_DAY
        )

        with django_assert_num_queries(2):
            response = client.get("/api/lanterns/")
        assert response.status_code == 200

    def test_list_pagination(self, client, user, booth):
        for i in range(5):
            Lantern.objects.create(
                user=user, booth=booth, message=f"m{i}", festival_date=FESTIVAL_DAY
            )
            booth = Booth.objects.create(
                name=f"부스{i}", place_type=Booth.PlaceType.BOOTH, category=Booth.Category.ETC
            )

        response = client.get("/api/lanterns/", {"page": 0, "size": 2})
        body = response.json()["data"]
        assert body["total_count"] == 5
        assert body["page"] == 0
        assert body["size"] == 2
        assert body["has_next"] is True
        assert len(body["items"]) == 2

    def test_list_marks_is_mine_for_owner_and_others(self, auth_client, user, other_user, booth):
        mine = Lantern.objects.create(
            user=user, booth=booth, message="내 등불", festival_date=FESTIVAL_DAY
        )
        other_booth = Booth.objects.create(
            name="다른 부스", place_type=Booth.PlaceType.BOOTH, category=Booth.Category.ETC
        )
        others = Lantern.objects.create(
            user=other_user, booth=other_booth, message="남의 등불", festival_date=FESTIVAL_DAY
        )

        response = auth_client.get("/api/lanterns/")
        items = {item["lantern_id"]: item for item in response.json()["data"]["items"]}
        assert items[mine.id]["is_mine"] is True
        assert items[others.id]["is_mine"] is False

    def test_list_is_mine_false_when_anonymous(self, client, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="등불", festival_date=FESTIVAL_DAY
        )

        response = client.get("/api/lanterns/")
        items = {item["lantern_id"]: item for item in response.json()["data"]["items"]}
        assert items[lantern.id]["is_mine"] is False

    def test_list_includes_updated_at(self, client, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="등불", festival_date=FESTIVAL_DAY
        )

        response = client.get("/api/lanterns/")
        items = {item["lantern_id"]: item for item in response.json()["data"]["items"]}
        assert items[lantern.id]["updated_at"] is not None


@pytest.mark.django_db
class TestLanternDetail:
    def test_detail_success(self, client, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="화이팅", festival_date=FESTIVAL_DAY
        )
        response = client.get(f"/api/lanterns/{lantern.id}/")
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "LANTERN_DETAIL_SUCCESS"
        assert body["data"]["lantern_id"] == lantern.id
        assert body["data"]["status"] == "active"

    def test_detail_includes_booth_name(self, client, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="화이팅", festival_date=FESTIVAL_DAY
        )
        response = client.get(f"/api/lanterns/{lantern.id}/")
        body = response.json()
        assert body["data"]["booth_name"] == booth.name

    def test_detail_rejects_missing_lantern(self, client):
        response = client.get("/api/lanterns/999999/")
        assert response.status_code == 404
        assert response.json()["code"] == "LANTERN_NOT_FOUND"

    def test_detail_owner_can_see_deleted(self, auth_client, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="삭제될 메시지", festival_date=FESTIVAL_DAY
        )
        lantern.deleted_at = timezone.now()
        lantern.deleted_by = Lantern.DeletedBy.USER
        lantern.save()

        response = auth_client.get(f"/api/lanterns/{lantern.id}/")
        assert response.status_code == 200
        body = response.json()["data"]
        assert body["status"] == "deleted_by_user"
        assert body["message"] is None

    def test_detail_hides_others_deleted_lantern(self, client, other_user, booth):
        lantern = Lantern.objects.create(
            user=other_user, booth=booth, message="삭제됨", festival_date=FESTIVAL_DAY
        )
        lantern.deleted_at = timezone.now()
        lantern.deleted_by = Lantern.DeletedBy.USER
        lantern.save()

        response = client.get(f"/api/lanterns/{lantern.id}/")
        assert response.status_code == 404
        assert response.json()["code"] == "LANTERN_NOT_FOUND"

    def test_detail_is_mine_true_for_owner(self, auth_client, user, booth):
        lantern = Lantern.objects.create(
            user=user, booth=booth, message="화이팅", festival_date=FESTIVAL_DAY
        )
        response = auth_client.get(f"/api/lanterns/{lantern.id}/")
        body = response.json()["data"]
        assert body["is_mine"] is True
        assert body["updated_at"] is not None

    def test_detail_is_mine_false_for_others(self, auth_client, other_user, booth):
        lantern = Lantern.objects.create(
            user=other_user, booth=booth, message="남의 등불", festival_date=FESTIVAL_DAY
        )
        response = auth_client.get(f"/api/lanterns/{lantern.id}/")
        body = response.json()["data"]
        assert body["is_mine"] is False
