from rest_framework import serializers

from .models import Coupon


# 나의 쿠폰 목록 조회 응답
# 수령장소 안내는 프론트에서 하드코딩하므로 응답에 포함하지 않음
class CouponListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            "coupon_id",
            "status",
            "issued_date",
            "scratched_at",
            "used_at",
        ]


# 쿠폰 사용 처리 요청
# user 필드는 CouponIssueSerializer와 동일하게 ModelSerializer로 받아서
# 존재하지 않는 user pk면 자동으로 검증 실패하게 함 (교현님 발급 API와 동일 방식)
class CouponUseSerializer(serializers.ModelSerializer):
    verify_code = serializers.CharField(max_length=20)

    class Meta:
        model = Coupon
        fields = [
            "verify_code",
        ]


# 쿠폰 응답
class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon

        fields = [
            "coupon_id",
            "user",
            "issued_date",
            "daily_sequence",
            "status",
            "scratched_at",
            "used_at",
        ]

        read_only_fields = [
            "coupon_id",
            "issued_date",
            "daily_sequence",
            "status",
            "scratched_at",
            "used_at",
        ]


class CouponStatsSerializer(serializers.Serializer):
    date = serializers.DateField()
    issued_count = serializers.IntegerField()
    win_count = serializers.IntegerField()
