"""Notices API serializers."""

from rest_framework import serializers

from common.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

from .models import Notice


class AdminNoticeListQuerySerializer(serializers.Serializer):
    """관리자 공지 목록 조회 쿼리 파라미터 검증."""

    type = serializers.ChoiceField(
        choices=["ALL", "URGENT", "NORMAL"],
        default="ALL",
        required=False,
        help_text="공지 유형 필터 (ALL, URGENT, NORMAL)",
    )
    page = serializers.IntegerField(
        default=0,
        min_value=0,
        required=False,
        help_text="페이지 번호 (0부터 시작)",
    )
    size = serializers.IntegerField(
        default=DEFAULT_PAGE_SIZE,
        min_value=1,
        max_value=MAX_PAGE_SIZE,
        required=False,
        help_text="페이지 크기",
    )


class AdminNoticeCreateSerializer(serializers.Serializer):
    """관리자 공지사항 신규 등록 요청 바디 검증."""

    type = serializers.ChoiceField(
        choices=Notice.Type.choices,
        default=Notice.Type.NORMAL,
        required=False,
        help_text="공지 유형 (URGENT: 긴급, NORMAL: 일반)",
    )
    title = serializers.CharField(
        max_length=200,
        allow_blank=False,
        trim_whitespace=True,
        help_text="공지 제목",
    )
    content = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        help_text="공지 본문",
    )
    image_url = serializers.URLField(
        max_length=500,
        required=False,
        allow_null=True,
        allow_blank=True,
        default=None,
        help_text="첨부 사진 URL",
    )


class AdminNoticeUpdateSerializer(serializers.Serializer):
    """관리자 공지사항 수정 요청 바디 검증."""

    type = serializers.ChoiceField(
        choices=Notice.Type.choices,
        required=True,
        help_text="공지 유형 (URGENT: 긴급, NORMAL: 일반)",
    )
    title = serializers.CharField(
        max_length=200,
        allow_blank=False,
        trim_whitespace=True,
        required=True,
        help_text="공지 제목",
    )
    content = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        required=True,
        help_text="공지 본문",
    )
    image_url = serializers.URLField(
        max_length=500,
        required=False,
        allow_null=True,
        allow_blank=True,
        default=None,
        help_text="첨부 사진 URL",
    )


class AdminNoticeListItemSerializer(serializers.ModelSerializer):
    """관리자 공지 목록 아이템 응답 스키마."""

    class Meta:
        model = Notice
        fields = [
            "id",
            "type",
            "title",
            "content",
            "image_url",
            "created_at",
            "updated_at",
        ]


class AdminNoticeDetailSerializer(serializers.ModelSerializer):
    """관리자 공지 상세/생성/수정 응답 스키마."""

    class Meta:
        model = Notice
        fields = [
            "id",
            "type",
            "title",
            "content",
            "image_url",
            "created_at",
            "updated_at",
        ]


def to_admin_notice_detail(notice: Notice) -> dict:
    """Notice 모델 인스턴스를 관리자 응답 딕셔너리로 변환합니다."""
    return {
        "id": notice.id,
        "type": notice.type,
        "title": notice.title,
        "content": notice.content,
        "image_url": notice.image_url,
        "created_at": notice.created_at,
        "updated_at": notice.updated_at,
    }


def to_admin_notice_list_item(notice: Notice) -> dict:
    """Notice 모델 인스턴스를 관리자 목록 아이템 딕셔너리로 변환합니다."""
    return to_admin_notice_detail(notice)


class AdminNoticeImageUploadSerializer(serializers.Serializer):
    """관리자 공지 이미지 업로드 요청 스키마."""

    image = serializers.FileField(
        required=True,
        help_text="업로드할 이미지 파일 (JPG, PNG, WebP, 최대 10MB)",
    )


class AdminNoticeImageUploadDataSerializer(serializers.Serializer):
    """관리자 공지 이미지 업로드 데이터 스키마."""

    image_url = serializers.URLField(help_text="업로드된 이미지의 접근 URL")


class AdminNoticeImageUploadResponseSerializer(serializers.Serializer):
    """관리자 공지 이미지 업로드 응답 스키마."""

    success = serializers.BooleanField(default=True, help_text="성공 여부")
    code = serializers.CharField(default="IMAGE_UPLOAD_SUCCESS", help_text="응답 코드")
    message = serializers.CharField(
        default="이미지가 성공적으로 업로드되었습니다.", help_text="응답 메시지"
    )
    data = AdminNoticeImageUploadDataSerializer(help_text="응답 데이터")

class NoticeListQuerySerializer(serializers.Serializer):
    """일반 사용자 공지 목록 조회 쿼리 파라미터 검증."""

    type = serializers.ChoiceField(
        choices=["ALL", "URGENT", "NORMAL"],
        default="ALL",
        required=False,
        help_text="공지 유형 필터 (ALL, URGENT, NORMAL)",
    )
    page = serializers.IntegerField(
        default=0,
        min_value=0,
        required=False,
        help_text="페이지 번호 (0부터 시작)",
    )
    size = serializers.IntegerField(
        default=DEFAULT_PAGE_SIZE,
        min_value=1,
        max_value=MAX_PAGE_SIZE,
        required=False,
        help_text="페이지 크기",
    )


class NoticeListItemSerializer(serializers.ModelSerializer):
    """일반 사용자 공지 목록 아이템 응답 스키마."""

    class Meta:
        model = Notice
        fields = [
            "id",
            "type",
            "title",
            "image_url",
            "created_at",
            "updated_at",
        ]


class NoticeDetailSerializer(serializers.ModelSerializer):
    """일반 사용자 공지 상세 응답 스키마."""

    class Meta:
        model = Notice
        fields = [
            "id",
            "type",
            "title",
            "content",
            "image_url",
            "created_at",
            "updated_at",
        ]


def to_user_notice_list_item(notice: Notice) -> dict:
    """Notice 모델 인스턴스를 일반 사용자 목록 아이템 딕셔너리로 변환합니다 (content 제외)."""
    return {
        "id": notice.id,
        "type": notice.type,
        "title": notice.title,
        "image_url": notice.image_url,
        "created_at": notice.created_at,
        "updated_at": notice.updated_at,
    }


def to_user_notice_detail(notice: Notice) -> dict:
    """Notice 모델 인스턴스를 일반 사용자 상세 딕셔너리로 변환합니다."""
    return {
        "id": notice.id,
        "type": notice.type,
        "title": notice.title,
        "content": notice.content,
        "image_url": notice.image_url,
        "created_at": notice.created_at,
        "updated_at": notice.updated_at,
    }


class NoticeRollingItemSerializer(serializers.ModelSerializer):
    notice_id = serializers.IntegerField(source="id")
    created_at = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%S")

    class Meta:
        model = Notice
        fields = ["notice_id", "type", "title", "created_at"]


class NoticeRollingListResponseSerializer(serializers.Serializer):
    """Swagger 문서화용 응답 래퍼 Serializer"""
    notices = NoticeRollingItemSerializer(many=True)