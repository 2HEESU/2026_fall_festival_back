"""Notices API views."""

from drf_spectacular.utils import extend_schema
from rest_framework import status as http_status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from common.exceptions import InvalidImageFile, InvalidInput, NotFound, custom_exception_handler
from common.pagination import paginate
from common.permissions import IsAdmin
from common.responses import success_response
from common.schema import ErrorResponseSerializer

from . import selectors, services
from .serializers import (
    AdminNoticeCreateResponseSerializer,
    AdminNoticeCreateSerializer,
    AdminNoticeDeleteResponseSerializer,
    AdminNoticeDetailResponseSerializer,
    AdminNoticeImageUploadResponseSerializer,
    AdminNoticeImageUploadSerializer,
    AdminNoticeListQuerySerializer,
    AdminNoticeListResponseSerializer,
    AdminNoticeUpdateResponseSerializer,
    AdminNoticeUpdateSerializer,
    NoticeListQuerySerializer,
    NoticeRollingItemSerializer,
    NoticeRollingListResponseSerializer,
    UserNoticeDetailResponseSerializer,
    UserNoticeListResponseSerializer,
    to_admin_notice_detail,
    to_admin_notice_list_item,
    to_user_notice_detail,
    to_user_notice_list_item,
)


class AdminNoticeAPIView(APIView):
    """관리자 공지 API 기본 뷰."""

    permission_classes = [IsAdmin]

    def get_exception_handler(self):
        return custom_exception_handler


class AdminNoticeListView(AdminNoticeAPIView):
    """관리자 공지사항 목록 조회 (GET) 및 신규 등록 (POST) API."""

    @extend_schema(
        tags=["admin-notices"],
        summary="관리자 공지 목록 조회",
        description=(
            "관리자 공지 목록을 조회합니다. "
            "긴급 공지가 최우선 노출되며 일반 공지는 최신순으로 정렬됩니다."
        ),
        operation_id="admin_notice_list",
        parameters=[AdminNoticeListQuerySerializer],
        responses={
            200: AdminNoticeListResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def get(self, request):
        query_serializer = AdminNoticeListQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            raise InvalidInput("입력값이 올바르지 않습니다.", errors=query_serializer.errors)

        notice_type = query_serializer.validated_data["type"]
        page = query_serializer.validated_data["page"]
        size = query_serializer.validated_data["size"]

        queryset = selectors.get_admin_notices_queryset(notice_type=notice_type)
        page_data = paginate(queryset, page=page, size=size)

        items = [to_admin_notice_list_item(notice) for notice in page_data.items]
        return success_response(
            "ADMIN_NOTICE_LIST_SUCCESS",
            "공지 목록 조회에 성공했습니다.",
            {
                "items": items,
                "meta": page_data.as_meta(),
            },
        )

    @extend_schema(
        tags=["admin-notices"],
        summary="관리자 공지 신규 등록",
        description="새로운 공지사항을 등록합니다. 제목과 본문은 필수이며 이미지는 선택입니다.",
        operation_id="admin_notice_create",
        request=AdminNoticeCreateSerializer,
        responses={
            201: AdminNoticeCreateResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def post(self, request):
        serializer = AdminNoticeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            raise InvalidInput("입력값이 올바르지 않습니다.", errors=serializer.errors)

        notice = services.create_notice(
            title=serializer.validated_data["title"],
            content=serializer.validated_data["content"],
            type=serializer.validated_data.get("type", "NORMAL"),
            image_url=serializer.validated_data.get("image_url"),
            admin=getattr(request, "admin", None),
            admin_id=getattr(request, "admin_id", None),
        )

        return success_response(
            "ADMIN_NOTICE_CREATE_SUCCESS",
            "공지사항이 성공적으로 등록되었습니다.",
            to_admin_notice_detail(notice),
            status=http_status.HTTP_201_CREATED,
        )


class AdminNoticeDetailView(AdminNoticeAPIView):
    """관리자 공지사항 상세 조회 (GET), 수정 (PUT), 삭제 (DELETE) API."""

    @extend_schema(
        tags=["admin-notices"],
        summary="관리자 공지 상세 조회",
        description="특정 공지사항의 상세 정보(제목, 본문, 유형, 이미지 등)를 조회합니다.",
        operation_id="admin_notice_detail",
        responses={
            200: AdminNoticeDetailResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request, notice_id: int):
        notice = selectors.get_notice_by_id(notice_id=notice_id)
        if notice is None:
            raise NotFound("해당 공지사항을 찾을 수 없습니다.")

        return success_response(
            "ADMIN_NOTICE_DETAIL_SUCCESS",
            "공지 상세 조회에 성공했습니다.",
            to_admin_notice_detail(notice),
        )

    @extend_schema(
        tags=["admin-notices"],
        summary="관리자 공지 수정",
        description="기존 공지사항의 제목, 본문, 유형, 이미지를 수정합니다.",
        operation_id="admin_notice_update",
        request=AdminNoticeUpdateSerializer,
        responses={
            200: AdminNoticeUpdateResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def put(self, request, notice_id: int):
        notice = selectors.get_notice_by_id(notice_id=notice_id)
        if notice is None:
            raise NotFound("해당 공지사항을 찾을 수 없습니다.")

        serializer = AdminNoticeUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise InvalidInput("입력값이 올바르지 않습니다.", errors=serializer.errors)

        updated_notice = services.update_notice(
            notice,
            title=serializer.validated_data["title"],
            content=serializer.validated_data["content"],
            type=serializer.validated_data["type"],
            image_url=serializer.validated_data.get("image_url"),
        )

        return success_response(
            "ADMIN_NOTICE_UPDATE_SUCCESS",
            "공지사항이 성공적으로 수정되었습니다.",
            to_admin_notice_detail(updated_notice),
        )

    @extend_schema(
        tags=["admin-notices"],
        summary="관리자 공지 삭제 (Soft Delete)",
        description="공지사항을 논리 삭제(Soft Delete) 처리합니다.",
        operation_id="admin_notice_delete",
        responses={
            200: AdminNoticeDeleteResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def delete(self, request, notice_id: int):
        notice = selectors.get_notice_by_id(notice_id=notice_id)
        if notice is None:
            raise NotFound("해당 공지사항을 찾을 수 없습니다.")

        services.delete_notice(notice)

        return success_response(
            "ADMIN_NOTICE_DELETE_SUCCESS",
            "공지사항이 성공적으로 삭제되었습니다.",
            {},
        )


class AdminNoticeImageUploadView(AdminNoticeAPIView):
    """관리자 공지 이미지 업로드 API (POST /api/notices/images/)."""

    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["admin-notices"],
        summary="관리자 공지 이미지 업로드",
        description=(
            "공지 첨부용 이미지(JPG, PNG, WebP, 최대 10MB)를 업로드하고 접근 URL을 발급받습니다."
        ),
        operation_id="admin_notice_image_upload",
        request=AdminNoticeImageUploadSerializer,
        responses={
            201: AdminNoticeImageUploadResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            413: ErrorResponseSerializer,
        },
    )
    def post(self, request):
        serializer = AdminNoticeImageUploadSerializer(data=request.data)
        if not serializer.is_valid():
            raise InvalidImageFile(
                errors={"image": "JPG, PNG, WebP 형식의 이미지 파일만 업로드할 수 있습니다."}
            )

        image_file = serializer.validated_data["image"]
        image_url = services.upload_notice_image(image_file, request=request)

        return success_response(
            "IMAGE_UPLOAD_SUCCESS",
            "이미지가 성공적으로 업로드되었습니다.",
            {"image_url": image_url},
            status=http_status.HTTP_201_CREATED,
        )


class UserNoticeAPIView(APIView):
    """일반 사용자 공지사항 기본 API 뷰 (인증 불필요)."""

    permission_classes = [AllowAny]

    def get_exception_handler(self):
        return custom_exception_handler


class NoticeListView(UserNoticeAPIView):
    """일반 사용자 공지사항 목록 조회 API."""

    @extend_schema(
        tags=["notices"],
        summary="일반 사용자 공지사항 목록 조회",
        description="삭제되지 않은 공지사항 목록을 조회합니다.",
        operation_id="user_notice_list",
        auth=[],
        parameters=[NoticeListQuerySerializer],
        responses={
            200: UserNoticeListResponseSerializer,
            400: ErrorResponseSerializer,
        },
    )
    def get(self, request):
        query_serializer = NoticeListQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            raise InvalidInput("입력값이 올바르지 않습니다.", errors=query_serializer.errors)

        notice_type = query_serializer.validated_data["type"]
        page = query_serializer.validated_data["page"]
        size = query_serializer.validated_data["size"]

        queryset = selectors.get_user_notices_queryset(notice_type=notice_type)
        page_data = paginate(queryset, page=page, size=size)

        items = [to_user_notice_list_item(notice) for notice in page_data.items]
        return success_response(
            "NOTICE_LIST_SUCCESS",
            "공지 목록 조회에 성공했습니다.",
            {
                "items": items,
                "meta": page_data.as_meta(),
            },
        )


class NoticeDetailView(UserNoticeAPIView):
    """일반 사용자 공지사항 상세 조회 API."""

    @extend_schema(
        tags=["notices"],
        summary="일반 사용자 공지사항 상세 조회",
        description="특정 공지사항의 상세 내용을 조회합니다.",
        operation_id="user_notice_detail",
        auth=[],
        responses={
            200: UserNoticeDetailResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request, notice_id: int):
        notice = selectors.get_notice_by_id(notice_id=notice_id)
        if notice is None:
            raise NotFound("해당 공지사항을 찾을 수 없습니다.")

        return success_response(
            "NOTICE_DETAIL_SUCCESS",
            "공지 상세 조회에 성공했습니다.",
            to_user_notice_detail(notice),
        )


class NoticeRollingListView(APIView):
    """홈 상단 롤링 공지 목록 조회 API (비로그인 사용자 가능)"""

    @extend_schema(
        tags=["notices"],
        summary="상단 롤링 공지 목록 조회",
        description="홈 상단 롤링 바에 노출할 공지 3건을 긴급공지 우선, 최신순으로 조회합니다.",
        operation_id="user_notice_rolling_list",
        auth=[],
        responses={200: NoticeRollingListResponseSerializer},
    )
    def get(self, request):
        notices = selectors.get_rolling_notices()
        serializer = NoticeRollingItemSerializer(notices, many=True)

        return success_response(
            code="NOTICE_ROLLING_LIST_SUCCESS",
            message="상단 롤링 공지 목록을 조회했습니다.",
            data={"notices": serializer.data},
            status=http_status.HTTP_200_OK,
        )
