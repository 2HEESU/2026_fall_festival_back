"""Read-only lanterns queries and business aggregations."""

from collections import defaultdict

from django.db.models import Count, Min, Q, QuerySet

from apps.lanterns.models import Lantern, LanternReport


# --- User Selectors ---
def lantern_list_queryset(*, user, mine, booth_id=None, festival_date=None):
    if mine:
        queryset = Lantern.objects.filter(user=user)
    else:
        queryset = Lantern.objects.filter(deleted_at__isnull=True)

    if booth_id is not None:
        queryset = queryset.filter(booth_id=booth_id)
    if festival_date is not None:
        queryset = queryset.filter(festival_date=festival_date)

    return queryset.select_related("booth").order_by("-created_at")


def get_lantern(lantern_id):
    return Lantern.objects.select_related("booth").filter(pk=lantern_id).first()


# --- Admin Selectors ---
def get_admin_lanterns_queryset(*, sort: str = "REPORT_DESC") -> QuerySet[Lantern]:
    """관리자 등불 목록을 조회하는 쿼리셋을 반환합니다.

    - 삭제된 등불(deleted_at is not None)은 제외합니다.
    - booth 정보를 select_related로 함께 조회합니다.
    - 신고 건수(report_count)를 annotate로 집계합니다.
    - sort:
      - 'REPORT_DESC': 누적 신고 많은 순 내림차순, 동일 시 최신 등록순
      - 'LATEST': 최신 등록순
    """
    queryset = (
        Lantern.objects.filter(deleted_at__isnull=True)
        .select_related("booth")
        .annotate(
            report_count=Count(
                "lantern_reports",
                filter=Q(lantern_reports__deleted_at__isnull=True),
            )
        )
    )

    if sort == "LATEST":
        return queryset.order_by("-created_at")
    # Default is REPORT_DESC
    return queryset.order_by("-report_count", "-created_at")


def get_top_report_reasons_for_lanterns(lantern_ids: list[int]) -> dict[int, str | None]:
    """주어진 등불 ID 목록에 대해 각 등불의 최다 신고 사유(라벨)를 계산하여 반환합니다.

    - 신고 횟수가 동률일 경우, 최초 접수된 신고(가장 이른 created_at / id)의 사유를 우선 선택합니다.
    - 반환 형식: {lantern_id: "욕설 및 비방", ...}
    - 신고가 없거나 조회되지 않는 등불은 None을 반환합니다.
    """
    if not lantern_ids:
        return {}

    reports = (
        LanternReport.objects.filter(lantern_id__in=lantern_ids, deleted_at__isnull=True)
        .values("lantern_id", "reason")
        .annotate(
            count=Count("id"),
            first_reported_at=Min("created_at"),
            first_report_id=Min("id"),
        )
        .order_by("lantern_id", "-count", "first_reported_at", "first_report_id")
    )

    reason_label_map = dict(LanternReport.Reason.choices)
    top_reasons: dict[int, str | None] = defaultdict(lambda: None)

    for item in reports:
        lantern_id = item["lantern_id"]
        # 정렬 기준 첫 번째 항목이 최다(동률 시 최초) 신고 사유
        if lantern_id not in top_reasons:
            raw_reason = item["reason"]
            top_reasons[lantern_id] = reason_label_map.get(raw_reason, raw_reason)

    return top_reasons


def get_admin_lantern_by_id(*, lantern_id: int) -> Lantern | None:
    """단일 관리자 등불 상세 정보를 조회합니다 (삭제된 등불 제외)."""
    return (
        Lantern.objects.filter(id=lantern_id, deleted_at__isnull=True)
        .select_related("booth")
        .annotate(
            report_count=Count(
                "lantern_reports",
                filter=Q(lantern_reports__deleted_at__isnull=True),
            )
        )
        .first()
    )
