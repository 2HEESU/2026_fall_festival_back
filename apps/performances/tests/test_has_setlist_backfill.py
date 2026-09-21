"""has_setlist 백필 마이그레이션 테스트 (0002_performance_has_setlist).

기존 데이터(마이그레이션 적용 전에 이미 있던 행)는 affiliation이 없으면
연예인 공연이라는 옛 관례를 따랐다. 그 관례를 has_setlist=False로 한 번
정리해주는 backfill_has_setlist()가 실제로 그렇게 동작하는지 검증한다.
"""

import importlib
from datetime import date, datetime, time

import pytest
from django.apps import apps as live_apps
from django.utils import timezone

from apps.performances.models import Performance

# 마이그레이션 파일명이 숫자로 시작해서 일반 import 문법으로는 못 불러온다.
_migration = importlib.import_module("apps.performances.migrations.0002_performance_has_setlist")
backfill_has_setlist = _migration.backfill_has_setlist

pytestmark = pytest.mark.django_db


def make_performance(*, affiliation, has_setlist):
    """백필 전 상태를 흉내낸다: 필드는 이미 있지만 아직 정리는 안 된 값."""
    start_at = timezone.make_aware(datetime.combine(date(2026, 9, 29), time(16, 0)))
    return Performance.objects.create(
        team_name="테스트 공연",
        affiliation=affiliation,
        has_setlist=has_setlist,
        festival_date=date(2026, 9, 29),
        start_at=start_at,
        end_at=start_at,
    )


def test_backfill_sets_false_for_rows_without_affiliation():
    performance = make_performance(affiliation=None, has_setlist=True)

    backfill_has_setlist(live_apps, None)

    performance.refresh_from_db()
    assert performance.has_setlist is False


def test_backfill_leaves_rows_with_affiliation_untouched():
    performance = make_performance(affiliation="밴드동아리", has_setlist=True)

    backfill_has_setlist(live_apps, None)

    performance.refresh_from_db()
    assert performance.has_setlist is True


def test_backfill_does_not_touch_rows_already_marked_false():
    # affiliation이 있는데 누가 이미 has_setlist=False로 명시한 경우까지
    # 덮어쓰면 안 된다. 이 마이그레이션의 조건은 affiliation IS NULL 뿐이다.
    performance = make_performance(affiliation="밴드동아리", has_setlist=False)

    backfill_has_setlist(live_apps, None)

    performance.refresh_from_db()
    assert performance.has_setlist is False