"""Admin lost-items read API tests (issue #8: list + detail only)."""

from datetime import date

import pytest

from apps.lost_items.models import LostItem, LostItemImage, LostItemTag

pytestmark = pytest.mark.django_db

LIST_URL = "/api/lost-items/"


def make_item(*, title="휴대폰케이스 분실물", found_date=date(2026, 9, 29), tags=None, images=None):
    item = LostItem.objects.create(title=title, found_date=found_date)
    for index, keyword in enumerate(tags or [], start=1):
        LostItemTag.objects.create(lost_item=item, keyword=keyword, sort_order=index)
    for index, url in enumerate(images or [], start=1):
        LostItemImage.objects.create(lost_item=item, image_url=url, sort_order=index)
    return item


class TestAuthentication:
    def test_missing_token_returns_401(self, subdomain_admin_client):
        response = subdomain_admin_client.get(LIST_URL)
        body = response.json()

        assert response.status_code == 401
        assert body["success"] is False
        assert body["code"] == "UNAUTHORIZED"

    def test_wrong_token_returns_401(self, subdomain_admin_client):
        response = subdomain_admin_client.get(LIST_URL, HTTP_AUTHORIZATION="Bearer nope")
        assert response.status_code == 401

    def test_detail_also_requires_auth(self, subdomain_admin_client):
        item = make_item(tags=["지갑"])
        response = subdomain_admin_client.get(f"{LIST_URL}{item.pk}/")
        assert response.status_code == 401


class TestList:
    def test_empty_result_is_200_with_empty_items(self, subdomain_admin_client, auth_headers):
        body = subdomain_admin_client.get(LIST_URL, **auth_headers).json()

        assert body["code"] == "LOST_ITEM_LIST_SUCCESS"
        assert body["data"]["total_count"] == 0
        assert body["data"]["items"] == []

    def test_returns_at_most_three_tags_and_a_thumbnail(self, subdomain_admin_client, auth_headers):
        make_item(
            tags=["휴대폰케이스", "검정색", "아이폰14pro", "대운동장"],
            images=["https://cdn.example.com/lost/abc.jpg"],
        )

        item = subdomain_admin_client.get(LIST_URL, **auth_headers).json()["data"]["items"][0]

        assert item["tags"] == ["휴대폰케이스", "검정색", "아이폰14pro"]
        assert item["thumbnail_url"] == "https://cdn.example.com/lost/abc.jpg"

    def test_thumbnail_is_null_without_images(self, subdomain_admin_client, auth_headers):
        make_item(tags=["지갑"])

        item = subdomain_admin_client.get(LIST_URL, **auth_headers).json()["data"]["items"][0]
        assert item["thumbnail_url"] is None

    def test_found_date_filter(self, subdomain_admin_client, auth_headers):
        make_item(found_date=date(2026, 9, 29), tags=["A"])
        make_item(found_date=date(2026, 10, 1), tags=["B"])

        body = subdomain_admin_client.get(
            LIST_URL, {"found_date": "2026-10-01"}, **auth_headers
        ).json()
        assert body["data"]["total_count"] == 1
        assert body["data"]["items"][0]["tags"] == ["B"]

    def test_pagination_reports_has_next(self, subdomain_admin_client, auth_headers):
        for i in range(3):
            make_item(title=f"item-{i}", tags=["A"])

        body = subdomain_admin_client.get(LIST_URL, {"page": 0, "size": 2}, **auth_headers).json()
        assert body["data"]["has_next"] is True
        assert len(body["data"]["items"]) == 2

        body = subdomain_admin_client.get(LIST_URL, {"page": 1, "size": 2}, **auth_headers).json()
        assert body["data"]["has_next"] is False
        assert len(body["data"]["items"]) == 1

    def test_size_over_limit_is_rejected(self, subdomain_admin_client, auth_headers):
        response = subdomain_admin_client.get(LIST_URL, {"size": 101}, **auth_headers)
        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_INPUT"

    def test_soft_deleted_item_is_excluded(self, subdomain_admin_client, auth_headers):
        item = make_item(tags=["A"])
        item.deleted_at = "2026-09-30T00:00:00Z"
        item.save(update_fields=["deleted_at"])

        body = subdomain_admin_client.get(LIST_URL, **auth_headers).json()
        assert body["data"]["total_count"] == 0

    def test_soft_deleted_tag_is_excluded_but_item_still_shows(
        self, subdomain_admin_client, auth_headers
    ):
        # 아이템 전체가 아니라 태그 한 개만 삭제된 경우도 응답에서 빠져야 한다.
        item = make_item(tags=["살아있음", "지워짐"])
        item.tags.filter(keyword="지워짐").update(deleted_at="2026-09-30T00:00:00Z")

        body = subdomain_admin_client.get(LIST_URL, **auth_headers).json()
        assert body["data"]["total_count"] == 1
        assert body["data"]["items"][0]["tags"] == ["살아있음"]


class TestDetail:
    def test_returns_all_tags(self, subdomain_admin_client, auth_headers):
        item = make_item(tags=["휴대폰케이스", "검정색", "아이폰14pro", "대운동장"])

        body = subdomain_admin_client.get(f"{LIST_URL}{item.pk}/", **auth_headers).json()
        data = body["data"]
        tag = data["tags"][0]

        assert body["code"] == "LOST_ITEM_DETAIL_SUCCESS"
        assert len(data["tags"]) == 4
        assert isinstance(tag["tag_id"], int)
        assert tag["keyword"] == "휴대폰케이스"
        assert tag["sort_order"] == 1
        assert data["updated_at"] is None

    def test_unknown_id_returns_404(self, subdomain_admin_client, auth_headers):
        response = subdomain_admin_client.get(f"{LIST_URL}9999/", **auth_headers)
        body = response.json()

        assert response.status_code == 404
        assert body["code"] == "LOST_ITEM_NOT_FOUND"

    def test_soft_deleted_item_returns_404(self, subdomain_admin_client, auth_headers):
        item = make_item(tags=["A"])
        item.deleted_at = "2026-09-30T00:00:00Z"
        item.save(update_fields=["deleted_at"])

        response = subdomain_admin_client.get(f"{LIST_URL}{item.pk}/", **auth_headers)
        assert response.status_code == 404