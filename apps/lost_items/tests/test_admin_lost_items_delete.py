"""Admin lost-items delete API tests (issue #12: delete)."""

import json

import pytest

from apps.lost_items.models import LostItem, LostItemImage, LostItemTag

pytestmark = pytest.mark.django_db

LIST_URL = "/api/lost-items/"

BASE_PAYLOAD = {
    "title": "휴대폰케이스 분실물",
    "found_date": "2026-09-29",
    "image_urls": ["https://cdn.example.com/lost/abc.jpg"],
    "tags": ["휴대폰케이스", "검정색"],
}


def create_item(subdomain_admin_client, headers):
    response = subdomain_admin_client.post(
        LIST_URL, data=json.dumps(BASE_PAYLOAD), content_type="application/json", **headers
    )
    return response.json()["data"]["lost_item_id"]


class TestDelete:
    def test_deletes_item_and_returns_deleted_at(self, subdomain_admin_client, auth_headers):
        item_id = create_item(subdomain_admin_client, auth_headers)

        response = subdomain_admin_client.delete(f"{LIST_URL}{item_id}/", **auth_headers)
        body = response.json()

        assert response.status_code == 200
        assert body["code"] == "LOST_ITEM_DELETE_SUCCESS"
        assert body["data"]["lost_item_id"] == item_id
        assert body["data"]["deleted_at"] is not None

    def test_item_itself_is_soft_deleted(self, subdomain_admin_client, auth_headers):
        item_id = create_item(subdomain_admin_client, auth_headers)
        subdomain_admin_client.delete(f"{LIST_URL}{item_id}/", **auth_headers)

        item = LostItem.objects.get(pk=item_id)
        assert item.deleted_at is not None

    def test_child_images_and_tags_are_soft_deleted_too(self, subdomain_admin_client, auth_headers):
        item_id = create_item(subdomain_admin_client, auth_headers)
        subdomain_admin_client.delete(f"{LIST_URL}{item_id}/", **auth_headers)

        # 실제로 지워지는 게 아니라 deleted_at만 채워진다 — 행 자체는 남아있다.
        assert LostItemImage.objects.filter(lost_item_id=item_id).count() == 1
        assert LostItemImage.objects.alive().filter(lost_item_id=item_id).count() == 0
        assert LostItemTag.objects.filter(lost_item_id=item_id).count() == 2
        assert LostItemTag.objects.alive().filter(lost_item_id=item_id).count() == 0

    def test_item_images_and_tags_have_the_same_deleted_at(
        self, subdomain_admin_client, auth_headers
    ):
        # delete_lost_item()이 timezone.now()를 한 번만 호출해서 분실물·이미지·
        # 태그에 똑같이 찍는다는 걸 이 테스트로 보장한다. 각자 now()를 따로
        # 호출하는 실수를 하면(밀리초 단위로 값이 달라짐) 이 테스트가 잡아낸다.
        item_id = create_item(subdomain_admin_client, auth_headers)
        subdomain_admin_client.delete(f"{LIST_URL}{item_id}/", **auth_headers)

        item = LostItem.objects.get(pk=item_id)
        image = LostItemImage.objects.get(lost_item_id=item_id)
        tags = LostItemTag.objects.filter(lost_item_id=item_id)

        assert image.deleted_at == item.deleted_at
        for tag in tags:
            assert tag.deleted_at == item.deleted_at

    def test_deleted_item_disappears_from_list_and_detail(
        self, subdomain_admin_client, auth_headers
    ):
        item_id = create_item(subdomain_admin_client, auth_headers)
        subdomain_admin_client.delete(f"{LIST_URL}{item_id}/", **auth_headers)

        list_body = subdomain_admin_client.get(LIST_URL, **auth_headers).json()
        assert list_body["data"]["total_count"] == 0

        detail_response = subdomain_admin_client.get(f"{LIST_URL}{item_id}/", **auth_headers)
        assert detail_response.status_code == 404

    def test_deleting_already_deleted_item_returns_404(self, subdomain_admin_client, auth_headers):
        item_id = create_item(subdomain_admin_client, auth_headers)
        subdomain_admin_client.delete(f"{LIST_URL}{item_id}/", **auth_headers)

        response = subdomain_admin_client.delete(f"{LIST_URL}{item_id}/", **auth_headers)
        assert response.status_code == 404
        assert response.json()["code"] == "LOST_ITEM_NOT_FOUND"

    def test_deleting_unknown_id_returns_404(self, subdomain_admin_client, auth_headers):
        response = subdomain_admin_client.delete(f"{LIST_URL}9999/", **auth_headers)
        assert response.status_code == 404

    def test_requires_auth(self, subdomain_admin_client, auth_headers):
        item_id = create_item(subdomain_admin_client, auth_headers)
        response = subdomain_admin_client.delete(f"{LIST_URL}{item_id}/")
        assert response.status_code == 401
