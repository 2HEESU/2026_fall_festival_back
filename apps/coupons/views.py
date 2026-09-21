from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    BoothVerifyCode,
    Coupon,
    DailyCouponCounter,
    User,
    WinningNumber,
)
from .serializers import (
    CouponIssueSerializer,
    CouponListItemSerializer,
    CouponSerializer,
    CouponUseSerializer,
    CouponStatsSerializer,
)


# 쿠폰 발급
class CouponIssueView(APIView):
    @transaction.atomic
    def post(self, request):

        serializer = CouponIssueSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        # 같은 유저가 동시에 쿠폰 발급 요청하는 것 방지
        user = User.objects.select_for_update().get(pk=user.pk)

        today = timezone.localdate()

        # 오늘 이미 쿠폰을 받은 적 있는지 확인
        already_issued = Coupon.objects.filter(user=user, issued_date=today).exists()

        if already_issued:
            return Response(
                {"message": "오늘 이미 쿠폰을 발급받았습니다."}, status=status.HTTP_400_BAD_REQUEST
            )

        # 오늘 날짜의 쿠폰 카운터
        counter, created = DailyCouponCounter.objects.get_or_create(
            date=today, defaults={"count": 0}
        )

        # 동시에 여러 명이 발급받아도
        # 같은 daily_sequence가 생기지 않도록 잠금
        counter = DailyCouponCounter.objects.select_for_update().get(pk=counter.pk)

        counter.count += 1

        counter.save(update_fields=["count"])

        # 쿠폰 생성
        coupon = Coupon.objects.create(
            user=user,
            issued_date=today,
            daily_sequence=counter.count,
            status=Coupon.Status.UNSCRATCHED,
        )

        return Response(CouponSerializer(coupon).data, status=status.HTTP_201_CREATED)


# 쿠폰 긁기
class CouponScratchView(APIView):
    @transaction.atomic
    def post(self, request, coupon_id):

        try:
            coupon = Coupon.objects.select_for_update().get(
                coupon_id=coupon_id, deleted_at__isnull=True
            )

        except Coupon.DoesNotExist:
            return Response(
                {"message": "존재하지 않는 쿠폰입니다."}, status=status.HTTP_404_NOT_FOUND
            )

        # 이미 긁은 쿠폰
        if coupon.status != Coupon.Status.UNSCRATCHED:
            return Response(
                {"message": "이미 확인한 쿠폰입니다."}, status=status.HTTP_400_BAD_REQUEST
            )

        # 당일 쿠폰만 스크래치 가능
        if coupon.issued_date != timezone.localdate():
            coupon.status = Coupon.Status.EXPIRED

            coupon.save(
                update_fields=[
                    "status",
                ]
            )

            data = CouponSerializer(coupon).data
            data["message"] = "기간이 만료된 쿠폰입니다."

            return Response(data, status=status.HTTP_400_BAD_REQUEST)

        # daily_sequence가 당첨번호 DB에 존재하는지 확인
        is_win = WinningNumber.objects.filter(number=coupon.daily_sequence).exists()

        coupon.scratched_at = timezone.now()

        # 당첨
        if is_win:
            coupon.status = Coupon.Status.WIN

            coupon.save(
                update_fields=[
                    "status",
                    "scratched_at",
                ]
            )

            return Response(CouponSerializer(coupon).data, status=status.HTTP_200_OK)

        # 꽝
        coupon.status = Coupon.Status.LOSE

        coupon.save(
            update_fields=[
                "status",
                "scratched_at",
            ]
        )

        return Response(CouponSerializer(coupon).data, status=status.HTTP_200_OK)


# 나의 쿠폰 목록 조회
class CouponListView(APIView):
    def get(self, request):
        # TODO: 로그인 붙으면 request.user로 대체
        user_id = request.query_params.get("user")

        if not user_id:
            return Response(
                {
                    "success": False,
                    "code": "UNAUTHORIZED",
                    "message": "로그인이 필요합니다.",
                    "errors": {},
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        coupons = Coupon.objects.filter(user_id=user_id, deleted_at__isnull=True).order_by(
            "-created_at"
        )

        status_filter = request.query_params.get("status")

        if status_filter:
            coupons = coupons.filter(status=status_filter)

        items = CouponListItemSerializer(coupons, many=True).data

        return Response(
            {
                "success": True,
                "code": "COUPON_LIST_SUCCESS",
                "message": "쿠폰 목록을 조회했습니다.",
                "data": {
                    "total_count": len(items),
                    "items": items,
                },
            },
            status=status.HTTP_200_OK,
        )


# 쿠폰 사용 처리 (확인 코드 검증)
class CouponUseView(APIView):
    @transaction.atomic
    def post(self, request, coupon_id):
        serializer = CouponUseSerializer(data=request.data)

        if not serializer.is_valid():
            # verify_code 누락 시 명세서 문구 사용, 그 외(user 없음 등)는
            # DRF 검증 메시지 그대로 전달
            errors = (
                {"verify_code": "확인 코드를 입력해주세요."}
                if "verify_code" in serializer.errors
                else serializer.errors
            )

            return Response(
                {
                    "success": False,
                    "code": "INVALID_INPUT",
                    "message": "필수 입력값이 누락되었습니다.",
                    "errors": errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_id = serializer.validated_data["user"].pk

        verify_code = serializer.validated_data["verify_code"]

        try:
            # 본인 소유 쿠폰 잠금 (동시 중복 사용 방지)
            coupon = Coupon.objects.select_for_update().get(
                coupon_id=coupon_id, user_id=user_id, deleted_at__isnull=True
            )

        except Coupon.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "code": "COUPON_NOT_USABLE",
                    "message": "사용할 수 없는 쿠폰입니다.",
                    "errors": {
                        "status": "이미 사용되었거나 당첨 쿠폰이 아니거나 기간이 만료되었습니다."
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 이미 사용된 쿠폰
        if coupon.status == Coupon.Status.USED:
            return Response(
                {
                    "success": False,
                    "code": "COUPON_ALREADY_USED",
                    "message": "이미 사용된 쿠폰입니다.",
                    "errors": {},
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 기간 만료 (오늘 발급된 쿠폰이 아니거나 이미 만료 처리됨)
        if coupon.status == Coupon.Status.EXPIRED or coupon.issued_date != timezone.localdate():
            return Response(
                {
                    "success": False,
                    "code": "COUPON_EXPIRED",
                    "message": "사용 기간이 만료된 쿠폰입니다.",
                    "errors": {},
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 당첨 쿠폰이 아님 (꽝이거나 아직 스크래치 안 함)
        if coupon.status != Coupon.Status.WIN:
            return Response(
                {
                    "success": False,
                    "code": "COUPON_NOT_WIN",
                    "message": "당첨된 쿠폰이 아닙니다.",
                    "errors": {},
                },
                status=status.HTTP_409_CONFLICT,
            )

        matched_code = BoothVerifyCode.objects.filter(code=verify_code).first()

        if not matched_code:
            return Response(
                {
                    "success": False,
                    "code": "INVALID_VERIFY_CODE",
                    "message": "올바른 코드가 아닙니다.",
                    "errors": {"verify_code": "확인 코드가 일치하지 않습니다."},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        coupon.status = Coupon.Status.USED

        coupon.used_at = timezone.now()

        coupon.save(
            update_fields=[
                "status",
                "used_at",
            ]
        )

        return Response(
            {
                "success": True,
                "code": "COUPON_USE_SUCCESS",
                "message": "쿠폰이 사용 처리되었습니다.",
                "data": {
                    "coupon_id": coupon.coupon_id,
                    "status": coupon.status,
                    "used_at": coupon.used_at,
                },
            },
            status=status.HTTP_200_OK,
        )


# 날짜별 쿠폰 발급/당첨 현황 조회
class CouponStatsView(APIView):
    def get(self, request):
        counters = DailyCouponCounter.objects.all().order_by("date")

        stats = []

        for counter in counters:
            win_count = Coupon.objects.filter(
                issued_date=counter.date,
                status__in=[
                    Coupon.Status.WIN,
                    Coupon.Status.USED,
                ],
                deleted_at__isnull=True,
            ).count()

            stats.append(
                {
                    "date": counter.date,
                    "issued_count": counter.count,
                    "win_count": win_count,
                }
            )

        serializer = CouponStatsSerializer(stats, many=True)

        return Response(
            {
                "success": True,
                "code": "COUPON_STATS_SUCCESS",
                "message": "쿠폰 발급 및 당첨 현황을 조회했습니다.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
