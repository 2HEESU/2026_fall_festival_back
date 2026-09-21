"""Lanterns request and response serializers."""

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers, status

from apps.booths.models import Booth
from common.exceptions import ApiError, InvalidInput, NotFound
from common.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

from .models import Lantern, LanternReport
from .validators import contains_forbidden_word


# --- User Serializers ---
class ForbiddenWordValidationMixin:
    def _check_forbidden_word(self, value):
        if contains_forbidden_word(value):
            raise InvalidInput(
                code="FORBIDDEN_WORD_DETECTED",
                message="부적절한 단어가 포함되어 있습니다.",
            )
        return value

    def validate_message(self, value):
        return self._check_forbidden_word(value)

    def validate_nickname(self, value):
        return self._check_forbidden_word(value)


class LanternCreateSerializer(ForbiddenWordValidationMixin, serializers.ModelSerializer):
    lantern_id = serializers.IntegerField(source="id", read_only=True)
    booth_id = serializers.IntegerField()
    nickname = serializers.CharField(max_length=5, required=False, allow_blank=True)
    message = serializers.CharField(max_length=30)

    class Meta:
        model = Lantern
        fields = ["lantern_id", "booth_id", "nickname", "message", "festival_date", "created_at"]
        read_only_fields = ["festival_date", "created_at"]

    def validate(self, attrs):
        today = timezone.localdate()

        self._today = today

        if not attrs.get("nickname"):
            attrs["nickname"] = "익명의 코끼리"

        if not (settings.FESTIVAL_START_DATE <= today <= settings.FESTIVAL_END_DATE):
            raise InvalidInput(
                code="NOT_FESTIVAL_PERIOD", message="등불은 축제 당일에만 달 수 있어요."
            )

        booth_id = attrs["booth_id"]
        booth_exists = Booth.objects.filter(
            id=booth_id, deleted_at__isnull=True, place_type="BOOTH"
        ).exists()
        if not booth_exists:
            raise NotFound(code="BOOTH_NOT_FOUND", message="존재하지 않는 부스입니다.")

        user = self.context["request"].user

        active_duplicate = Lantern.objects.filter(
            user=user, booth_id=booth_id, festival_date=today, deleted_at__isnull=True
        ).exists()
        if active_duplicate:
            raise ApiError(
                code="DUPLICATE_BOOTH_LANTERN",
                message="부스 선택을 변경해주세요.",
                status_code=status.HTTP_409_CONFLICT,
            )

        today_count = Lantern.objects.filter(user=user, festival_date=today).count()
        if today_count >= 3:
            raise ApiError(
                code="DAILY_LIMIT_EXCEEDED",
                message="등불은 하루에 3개씩만 달 수 있어요.",
                status_code=status.HTTP_409_CONFLICT,
            )

        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        booth_id = validated_data["booth_id"]

        try:
            with transaction.atomic():
                type(user).objects.select_for_update().get(pk=user.pk)

                today_count = Lantern.objects.filter(user=user, festival_date=self._today).count()
                if today_count >= 3:
                    raise ApiError(
                        code="DAILY_LIMIT_EXCEEDED",
                        message="등불은 하루에 3개씩만 달 수 있어요.",
                        status_code=status.HTTP_409_CONFLICT,
                    )

                lantern = Lantern.objects.create(
                    user=user, festival_date=self._today, **validated_data
                )
                Booth.objects.filter(id=booth_id).update(lantern_count=F("lantern_count") + 1)
        except IntegrityError as exc:
            raise ApiError(
                code="DUPLICATE_BOOTH_LANTERN",
                message="부스 선택을 변경해주세요.",
                status_code=status.HTTP_409_CONFLICT,
            ) from exc

        return lantern


class LanternUpdateSerializer(ForbiddenWordValidationMixin, serializers.ModelSerializer):
    lantern_id = serializers.IntegerField(source="id", read_only=True)
    nickname = serializers.CharField(max_length=5, required=False, allow_blank=True)
    message = serializers.CharField(max_length=30, required=False)

    class Meta:
        model = Lantern
        fields = ["lantern_id", "nickname", "message", "updated_at"]
        read_only_fields = ["updated_at"]


class LanternReportCreateSerializer(serializers.ModelSerializer):
    report_id = serializers.IntegerField(source="id", read_only=True)

    class Meta:
        model = LanternReport
        fields = ["report_id", "reason"]

    def validate(self, attrs):
        lantern = self.context["lantern"]
        user = self.context["request"].user

        if LanternReport.objects.filter(lantern=lantern, user=user).exists():
            raise ApiError(
                code="ALREADY_REPORTED",
                message="이미 신고한 등불입니다.",
                status_code=status.HTTP_409_CONFLICT,
            )

        return attrs

    def create(self, validated_data):
        try:
            return LanternReport.objects.create(
                lantern=self.context["lantern"],
                user=self.context["request"].user,
                **validated_data,
            )
        except IntegrityError as exc:
            raise ApiError(
                code="ALREADY_REPORTED",
                message="이미 신고한 등불입니다.",
                status_code=status.HTTP_409_CONFLICT,
            ) from exc


class LanternListQuerySerializer(serializers.Serializer):
    mine = serializers.BooleanField(required=False, default=False)
    booth_id = serializers.IntegerField(required=False)
    date = serializers.DateField(required=False)
    page = serializers.IntegerField(required=False, min_value=0, default=0)
    size = serializers.IntegerField(
        required=False, min_value=1, max_value=MAX_PAGE_SIZE, default=DEFAULT_PAGE_SIZE
    )


def _lantern_status(lantern):
    if lantern.deleted_at is None:
        return "active"
    if lantern.deleted_by == Lantern.DeletedBy.ADMIN:
        return "deleted_by_admin"
    return "deleted_by_user"


def to_lantern_item(lantern):
    lantern_status = _lantern_status(lantern)
    return {
        "lantern_id": lantern.id,
        "booth_id": lantern.booth_id,
        "nickname": lantern.nickname,
        "message": lantern.message if lantern_status == "active" else None,
        "status": lantern_status,
        "created_at": timezone.localtime(lantern.created_at).strftime("%Y-%m-%dT%H:%M:%S"),
    }


# --- Admin Serializers ---
class AdminLanternListQuerySerializer(serializers.Serializer):
    """관리자 등불 목록 조회 쿼리 파라미터."""

    sort = serializers.ChoiceField(
        choices=["REPORT_DESC", "LATEST"],
        default="REPORT_DESC",
        required=False,
        help_text="정렬 기준 (REPORT_DESC: 신고 많은 순, LATEST: 최신 등록순)",
    )
    page = serializers.IntegerField(
        min_value=0,
        default=0,
        required=False,
        help_text="페이지 번호 (0부터 시작)",
    )
    size = serializers.IntegerField(
        min_value=1,
        max_value=100,
        default=20,
        required=False,
        help_text="페이지 당 항목 수 (최대 100)",
    )


class AdminLanternListItemSerializer(serializers.Serializer):
    """관리자 등불 목록 항목 스키마."""

    id = serializers.IntegerField()
    nickname = serializers.CharField()
    message = serializers.CharField()
    booth_name = serializers.CharField()
    report_count = serializers.IntegerField()
    top_report_reason = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


class AdminLanternDetailSerializer(serializers.Serializer):
    """관리자 등불 신고 확인 모달 상세 스키마."""

    id = serializers.IntegerField()
    nickname = serializers.CharField()
    message = serializers.CharField()
    booth_name = serializers.CharField()
    booth_department = serializers.CharField(allow_null=True)
    report_count = serializers.IntegerField()
    top_report_reason = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


def to_admin_lantern_list_item(lantern: Lantern, top_reason: str | None = None) -> dict:
    """Lantern 모델 인스턴스를 관리자 목록 아이템 딕셔너리로 변환합니다."""
    return {
        "id": lantern.id,
        "nickname": lantern.nickname,
        "message": lantern.message,
        "booth_name": lantern.booth.name if lantern.booth else "",
        "report_count": getattr(lantern, "report_count", 0),
        "top_report_reason": top_reason,
        "created_at": lantern.created_at,
    }


def to_admin_lantern_detail(lantern: Lantern, top_reason: str | None = None) -> dict:
    """Lantern 모델 인스턴스를 관리자 상세 딕셔너리로 변환합니다."""
    return {
        "id": lantern.id,
        "nickname": lantern.nickname,
        "message": lantern.message,
        "booth_name": lantern.booth.name if lantern.booth else "",
        "booth_department": lantern.booth.subtitle if lantern.booth else None,
        "report_count": getattr(lantern, "report_count", 0),
        "top_report_reason": top_reason,
        "created_at": lantern.created_at,
    }


class AdminLanternDeleteResponseSerializer(serializers.Serializer):
    """관리자 등불 삭제(블라인드) 응답 스키마."""

    success = serializers.BooleanField(required=True, help_text="성공 여부 (True)")
    code = serializers.CharField(
        required=True, help_text="응답 코드 (ADMIN_LANTERN_DELETE_SUCCESS)"
    )
    message = serializers.CharField(
        required=True, help_text="응답 메시지 (등불이 성공적으로 삭제되었습니다.)"
    )
    data = serializers.DictField(required=True, help_text="응답 데이터 (빈 객체 {})")
