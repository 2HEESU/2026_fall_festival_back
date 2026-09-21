"""Transactional lanterns state changes."""

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.booths.models import Booth
from apps.lanterns.models import Lantern
from common.exceptions import NotFound


@transaction.atomic
def delete_admin_lantern(lantern: Lantern) -> None:
    """관리자가 부적절한 등불을 블라인드(Soft Delete) 처리하고,
    연관된 부스의 등불 카운트를 1 차감합니다.

    - 동시 요청 시 중복 차감 방지를 위해 deleted_at__isnull=True 조건부 UPDATE로
      영향 받은 행 수를 확인합니다.
    - 이미 삭제되었거나 영향 받은 행이 0개인 경우 NotFound를 발생시킵니다.
    """
    now = timezone.now()
    updated_rows = Lantern.objects.filter(
        id=lantern.id,
        deleted_at__isnull=True,
    ).update(
        deleted_at=now,
        deleted_by=Lantern.DeletedBy.ADMIN,
        updated_at=now,
    )

    if updated_rows == 0:
        raise NotFound("해당 등불을 찾을 수 없습니다.")

    lantern.deleted_at = now
    lantern.deleted_by = Lantern.DeletedBy.ADMIN

    Booth.objects.filter(id=lantern.booth_id, lantern_count__gt=0).update(
        lantern_count=F("lantern_count") - 1
    )
