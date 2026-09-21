from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.notices.models import Notice


@override_settings(ROOT_URLCONF="apps.notices.public_urls")
class UserNoticeAPITestCase(APITestCase):
    """일반 사용자 공지사항 API 테스트."""

    def setUp(self):
        # 1. 일반 공지 2개 생성
        self.normal_notice_1 = Notice.objects.create(
            title="일반 공지 1",
            content="일반 공지 1 본문 내용",
            type=Notice.Type.NORMAL,
        )
        self.normal_notice_2 = Notice.objects.create(
            title="일반 공지 2",
            content="일반 공지 2 본문 내용",
            type=Notice.Type.NORMAL,
        )

        # 2. 긴급 공지 생성
        self.urgent_notice = Notice.objects.create(
            title="긴급 공지",
            content="긴급 공지 본문 내용",
            type=Notice.Type.URGENT,
        )

        # 3. 논리 삭제(Soft Delete)된 공지 생성
        self.deleted_notice = Notice.objects.create(
            title="삭제된 공지",
            content="삭제된 본문",
            type=Notice.Type.NORMAL,
            deleted_at=timezone.now(),
        )

        # URL 네임스페이스가 설정되어 있다면 'notices:notice-list' 등으로 변경
        self.list_url = reverse("notice-list")

    # -------------------------------------------------------------
    # 목록 조회 (List) 테스트
    # -------------------------------------------------------------
    def test_get_notice_list_success(self):
        """비로그인 사용자도 공지사항 목록을 정상 조회할 수 있어야 한다."""
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "NOTICE_LIST_SUCCESS")

        items = response.data["data"]["items"]
        # 삭제된 공지는 제외되고 총 3개여야 함
        self.assertEqual(len(items), 3)

        # 목록 항목에는 content 필드가 포함되지 않아야 함 (네트워크 최적화)
        self.assertNotIn("content", items[0])

    def test_urgent_notice_comes_first_in_list(self):
        """긴급(URGENT) 공지가 목록의 최상단에 우선 정렬되어야 한다."""
        response = self.client.get(self.list_url)
        items = response.data["data"]["items"]

        # 최상단 첫 번째 아이템이 긴급 공지여야 함
        self.assertEqual(items[0]["id"], self.urgent_notice.id)
        self.assertEqual(items[0]["type"], Notice.Type.URGENT)

    def test_filter_notices_by_type(self):
        """type 쿼리 파라미터로 공지 유형을 필터링할 수 있어야 한다."""
        # URGENT 필터링
        response = self.client.get(self.list_url, {"type": "URGENT"})
        items = response.data["data"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], self.urgent_notice.id)

        # NORMAL 필터링
        response = self.client.get(self.list_url, {"type": "NORMAL"})
        items = response.data["data"]["items"]
        self.assertEqual(len(items), 2)
        for item in items:
            self.assertEqual(item["type"], Notice.Type.NORMAL)

    def test_soft_deleted_notices_are_excluded(self):
        """Soft Delete 처리된 공지는 목록에 노출되지 않아야 한다."""
        response = self.client.get(self.list_url)
        item_ids = [item["id"] for item in response.data["data"]["items"]]

        self.assertNotIn(self.deleted_notice.id, item_ids)

    def test_pagination(self):
        """페이지네이션 쿼리 파라미터(page, size)가 올바르게 작동해야 한다."""
        response = self.client.get(self.list_url, {"page": 0, "size": 2})
        data = response.data["data"]

        # 페이지 크기(size=2)만큼 반환되었는지 확인
        self.assertEqual(len(data["items"]), 2)

        # meta 정보가 반환되었는지 확인
        self.assertIn("meta", data)

        # total 관련 키 검증 (total_count, total, total_elements 중 하나 일치 확인)
        meta = data["meta"]
        total = meta.get("total_count") or meta.get("total") or meta.get("total_elements")
        self.assertEqual(total, 3)

    # -------------------------------------------------------------
    # 상세 조회 (Detail) 테스트
    # -------------------------------------------------------------
    def test_get_notice_detail_success(self):
        """공지사항 상세 조회가 성공하고 본문(content)이 포함되어야 한다."""
        url = reverse("notice-detail", kwargs={"notice_id": self.normal_notice_1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "NOTICE_DETAIL_SUCCESS")

        data = response.data["data"]
        self.assertEqual(data["id"], self.normal_notice_1.id)
        self.assertEqual(data["title"], self.normal_notice_1.title)
        self.assertEqual(data["content"], self.normal_notice_1.content)

    def test_get_notice_detail_not_found(self):
        """존재하지 않는 공지 ID 조회 시 404 에러를 반환해야 한다."""
        url = reverse("notice-detail", kwargs={"notice_id": 999999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_deleted_notice_detail_returns_404(self):
        """Soft Delete 처리된 공지 ID 조회 시 404 에러를 반환해야 한다."""
        url = reverse("notice-detail", kwargs={"notice_id": self.deleted_notice.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
