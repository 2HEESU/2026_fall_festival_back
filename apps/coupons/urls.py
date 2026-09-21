from django.urls import path

from .views import (
    CouponIssueView,
    CouponListView,
    CouponScratchView,
    CouponUseView,
    CouponStatsView,
)

urlpatterns = [
    # 쿠폰 목록 조회
    path("", CouponListView.as_view(), name="coupon-list"),
    # 쿠폰 발급
    path("issue/", CouponIssueView.as_view(), name="coupon-issue"),
    # 쿠폰 긁기
    path("<int:coupon_id>/scratch/", CouponScratchView.as_view(), name="coupon-scratch"),
    # 쿠폰 사용 처리
    path("<int:coupon_id>/use/", CouponUseView.as_view(), name="coupon-use"),
    # 쿠폰 현황
    path("stats/", CouponStatsView.as_view(), name="coupon-stats"),
]
