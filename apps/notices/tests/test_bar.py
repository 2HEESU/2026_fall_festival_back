from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.notices.models import Notice


class NoticeRollingListViewTestCase(APITestCase):
    """홈 상단 롤링 공지 목록 조회 API 테스트"""

    def setUp(self):
        # urls.py에 설정한 name (예: 'notice-rolling-list')
        # 만약 app_name="notices"가 설정되어 있다면 reverse("notices:notice-rolling-list")로 변경
        self.url = reverse("notice-rolling-list")

    def test_get_rolling_notices_empty_state(self):
        """1. 등록된 공지가 0건일 때 빈 배열([])과 200 OK를 정상 반환하는지 테스트"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get("success"))
        self.assertEqual(response.data.get("code"), "NOTICE_ROLLING_LIST_SUCCESS")
        self.assertEqual(response.data.get("message"), "상단 롤링 공지 목록을 조회했습니다.")
        self.assertEqual(response.data["data"]["notices"], [])

    def test_get_rolling_notices_priority_and_ordering(self):
        """2. 긴급 공지(URGENT)가 일반 공지보다 우선 정렬되고 최신순 정렬되는지 테스트"""
        now = timezone.now()

        # 과거에 작성된 긴급 공지
        urgent_old = Notice.objects.create(
            title="긴급 공지 (과거)",
            content="내용",
            type=Notice.Type.URGENT,
        )
        # 방금 작성된 일반 공지
        normal_recent = Notice.objects.create(
            title="일반 공지 (최신)",
            content="내용",
            type=Notice.Type.NORMAL,
        )
        # 더 최근에 작성된 긴급 공지
        urgent_recent = Notice.objects.create(
            title="긴급 공지 (최신)",
            content="내용",
            type=Notice.Type.URGENT,
        )

        # auto_now_add가 있는 created_at 강제 업데이트 (시간차 부여)
        Notice.objects.filter(id=urgent_old.id).update(created_at=now - timedelta(hours=2))
        Notice.objects.filter(id=normal_recent.id).update(created_at=now - timedelta(minutes=10))
        Notice.objects.filter(id=urgent_recent.id).update(created_at=now)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notices = response.data["data"]["notices"]
        self.assertEqual(len(notices), 3)

        # 정렬 순서 기대값: 긴급(최신) -> 긴급(과거) -> 일반(최신)
        expected_ids = [urgent_recent.id, urgent_old.id, normal_recent.id]
        actual_ids = [notice["notice_id"] for notice in notices]
        self.assertEqual(actual_ids, expected_ids)

        # 응답 필드 규격 확인 (notice_id, type, title, created_at)
        first_item = notices[0]
        self.assertIn("notice_id", first_item)
        self.assertEqual(first_item["type"], "URGENT")
        self.assertIn("title", first_item)
        self.assertIn("created_at", first_item)

    def test_get_rolling_notices_max_three_limit(self):
        """3. 공지가 4개 이상일 때 상위 3개까지만 제한되어 반환되는지 테스트"""
        now = timezone.now()

        # 총 5개의 일반 공지 생성
        for i in range(5):
            notice = Notice.objects.create(
                title=f"일반 공지 {i + 1}",
                content=f"내용 {i + 1}",
                type=Notice.Type.NORMAL,
            )
            Notice.objects.filter(id=notice.id).update(created_at=now + timedelta(minutes=i))

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notices = response.data["data"]["notices"]

        # 최대 3건 반환 확인
        self.assertEqual(len(notices), 3)

        # 최신순 3건 (5 -> 4 -> 3번) 확인
        self.assertEqual(notices[0]["title"], "일반 공지 5")
        self.assertEqual(notices[1]["title"], "일반 공지 4")
        self.assertEqual(notices[2]["title"], "일반 공지 3")

    def test_get_rolling_notices_soft_deleted_excluded(self):
        """4. 소프트 삭제(Soft Delete)된 공지는 노출 목록에서 제외되는지 테스트"""
        now = timezone.now()

        # 정상 공지 1건 생성
        active_notice = Notice.objects.create(
            title="정상 공지",
            content="내용",
            type=Notice.Type.NORMAL,
        )

        # 삭제 대상 공지 생성 후 deleted_at 설정 (Soft Delete 상태 만들기)
        deleted_notice = Notice.objects.create(
            title="삭제된 긴급 공지",
            content="내용",
            type=Notice.Type.URGENT,
        )
        # delete() 대신 deleted_at 설정 후 저장 (혹은 deleted_at 필드 update)
        deleted_notice.deleted_at = now
        deleted_notice.save(update_fields=["deleted_at"])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notices = response.data["data"]["notices"]

        # 삭제된 공지는 제외되고 정상 공지 1건만 반환되는지 검증
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["notice_id"], active_notice.id)
