"""Admin lost-items write API tests (issue #12: create + update)."""

import json

import pytest

from apps.lost_items.models import LostItem, LostItemImage, LostItemTag

pytestmark = pytest.mark.django_db

LIST_URL = "/api/lost-items/"


def post_json(subdomain_admin_client, headers, url, payload):
    return subdomain_admin_client.post(
        url, data=json.dumps(payload), content_type="application/json", **headers
    )


def put_json(subdomain_admin_client, headers, url, payload):
    return subdomain_admin_client.put(
        url, data=json.dumps(payload), content_type="application/json", **headers
    )


BASE_PAYLOAD = {
    "title": "휴대폰케이스 분실물",
    "found_date": "2026-09-29",
    "image_urls": ["https://cdn.example.com/lost/abc.jpg"],
    "tags": ["휴대폰케이스", "검정색", "아이폰14pro"],
}


class TestCreate:
    def test_creates_item_with_ordered_tags_and_images(self, subdomain_admin_client, auth_headers):
        response = post_json(subdomain_admin_client, auth_headers, LIST_URL, BASE_PAYLOAD)
        body = response.json()

        assert response.status_code == 201
        assert body["code"] == "LOST_ITEM_CREATE_SUCCESS"

        item = LostItem.objects.get(pk=body["data"]["lost_item_id"])
        assert [t.sort_order for t in item.tags.order_by("sort_order")] == [1, 2, 3]
        assert item.images.count() == 1
        assert item.updated_at is None

    def test_creates_item_without_images(self, subdomain_admin_client, auth_headers):
        payload = {**BASE_PAYLOAD, "image_urls": []}
        response = post_json(subdomain_admin_client, auth_headers, LIST_URL, payload)

        assert response.status_code == 201

    def test_duplicate_and_hash_prefixed_tags_are_deduplicated(
        self, subdomain_admin_client, auth_headers
    ):
        payload = {**BASE_PAYLOAD, "tags": ["#검정색", "검정색", "지갑"]}
        response = post_json(subdomain_admin_client, auth_headers, LIST_URL, payload)
        item_id = response.json()["data"]["lost_item_id"]

        keywords = list(
            LostItemTag.objects.filter(lost_item_id=item_id)
            .order_by("sort_order")
            .values_list("keyword", flat=True)
        )
        assert keywords == ["검정색", "지갑"]

    def test_empty_tags_is_rejected(self, subdomain_admin_client, auth_headers):
        payload = {**BASE_PAYLOAD, "tags": []}
        response = post_json(subdomain_admin_client, auth_headers, LIST_URL, payload)

        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_INPUT"

    def test_date_outside_festival_is_rejected(self, subdomain_admin_client, auth_headers):
        payload = {**BASE_PAYLOAD, "found_date": "2026-10-05"}
        response = post_json(subdomain_admin_client, auth_headers, LIST_URL, payload)

        assert response.status_code == 400
        assert "found_date" in response.json()["errors"]

    def test_requires_auth(self, subdomain_admin_client):
        response = subdomain_admin_client.post(
            LIST_URL, data=json.dumps(BASE_PAYLOAD), content_type="application/json"
        )
        assert response.status_code == 401


class TestUpdate:
    def _create(self, subdomain_admin_client, auth_headers, **overrides):
        payload = {**BASE_PAYLOAD, **overrides}
        response = post_json(subdomain_admin_client, auth_headers, LIST_URL, payload)
        return response.json()["data"]["lost_item_id"]

    def test_replaces_title_date_images_and_tags(self, subdomain_admin_client, auth_headers):
        item_id = self._create(subdomain_admin_client, auth_headers)
        detail_url = f"{LIST_URL}{item_id}/"

        response = put_json(
            subdomain_admin_client,
            auth_headers,
            detail_url,
            {
                "title": "지갑 분실물",
                "found_date": "2026-09-30",
                "image_urls": ["https://cdn.example.com/lost/new.jpg"],
                "tags": ["지갑", "갈색"],
            },
        )
        body = response.json()
        data = body["data"]

        assert response.status_code == 200
        assert body["code"] == "LOST_ITEM_UPDATE_SUCCESS"
        assert data["title"] == "지갑 분실물"
        assert data["found_date"] == "2026-09-30"
        assert data["updated_at"] is not None
        assert [t["keyword"] for t in data["tags"]] == ["지갑", "갈색"]
        assert [t["sort_order"] for t in data["tags"]] == [1, 2]
        assert len(data["images"]) == 1
        assert data["images"][0]["image_url"] == "https://cdn.example.com/lost/new.jpg"

    def test_old_tags_and_images_are_soft_deleted_not_removed(
        self, subdomain_admin_client, auth_headers
    ):
        item_id = self._create(subdomain_admin_client, auth_headers)  # 태그 3개, 이미지 1개로 시작
        detail_url = f"{LIST_URL}{item_id}/"

        put_json(
            subdomain_admin_client,
            auth_headers,
            detail_url,
            {"title": "x", "found_date": "2026-09-29", "tags": ["새태그"]},
        )

        # 옛 태그 3개 + 새 태그 1개 = 4행이 DB에 남아있어야 하고(soft delete),
        # 살아있는 건 새 태그 1개뿐이어야 한다.
        assert LostItemTag.objects.filter(lost_item_id=item_id).count() == 4
        assert LostItemTag.objects.alive().filter(lost_item_id=item_id).count() == 1
        assert LostItemImage.objects.filter(lost_item_id=item_id).count() == 1
        assert LostItemImage.objects.alive().filter(lost_item_id=item_id).count() == 0

    def test_omitting_image_urls_clears_existing_images(self, subdomain_admin_client, auth_headers):
        # image_urls가 선택값이라, 안 보내면 기존 사진이 전부 빠진다.
        # 이건 replace-all의 의도된 동작이라 프론트가 최종 배열을 매번
        # 전부 보내야 한다는 걸 이 테스트로 남겨둔다.
        item_id = self._create(subdomain_admin_client, auth_headers)
        detail_url = f"{LIST_URL}{item_id}/"

        response = put_json(
            subdomain_admin_client,
            auth_headers,
            detail_url,
            {"title": "지갑", "found_date": "2026-09-29", "tags": ["지갑"]},
        )
        assert response.json()["data"]["images"] == []

    def test_empty_tags_is_rejected(self, subdomain_admin_client, auth_headers):
        item_id = self._create(subdomain_admin_client, auth_headers)
        detail_url = f"{LIST_URL}{item_id}/"

        response = put_json(
            subdomain_admin_client,
            auth_headers,
            detail_url,
            {"title": "x", "found_date": "2026-09-29", "tags": []},
        )
        assert response.status_code == 400

    def test_date_outside_festival_is_rejected(self, subdomain_admin_client, auth_headers):
        item_id = self._create(subdomain_admin_client, auth_headers)
        detail_url = f"{LIST_URL}{item_id}/"

        response = put_json(
            subdomain_admin_client,
            auth_headers,
            detail_url,
            {"title": "x", "found_date": "2026-10-10", "tags": ["a"]},
        )
        assert response.status_code == 400

    def test_unknown_id_returns_404(self, subdomain_admin_client, auth_headers):
        response = put_json(
            subdomain_admin_client,
            auth_headers,
            f"{LIST_URL}9999/",
            {"title": "x", "found_date": "2026-09-29", "tags": ["a"]},
        )
        assert response.status_code == 404
        assert response.json()["code"] == "LOST_ITEM_NOT_FOUND"

    def test_soft_deleted_item_returns_404(self, subdomain_admin_client, auth_headers):
        item_id = self._create(subdomain_admin_client, auth_headers)
        item = LostItem.objects.get(pk=item_id)
        item.deleted_at = "2026-09-30T00:00:00Z"
        item.save(update_fields=["deleted_at"])

        response = put_json(
            subdomain_admin_client,
            auth_headers,
            f"{LIST_URL}{item_id}/",
            {"title": "x", "found_date": "2026-09-29", "tags": ["a"]},
        )
        assert response.status_code == 404

    def test_requires_auth(self, subdomain_admin_client, auth_headers):
        item_id = self._create(subdomain_admin_client, auth_headers)
        response = subdomain_admin_client.put(
            f"{LIST_URL}{item_id}/",
            data=json.dumps({"title": "x", "found_date": "2026-09-29", "tags": ["a"]}),
            content_type="application/json",
        )
        assert response.status_code == 401