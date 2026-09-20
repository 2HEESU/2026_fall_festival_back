from django.db import models


# 당첨 번호
class WinningNumber(models.Model):
    number = models.PositiveIntegerField(unique=True)

    def __str__(self):
        return str(self.number)


# 하루 전체 쿠폰 발급 순번 관리
class DailyCouponCounter(models.Model):
    date = models.DateField(unique=True)

    count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.date} - {self.count}"


# 쿠폰
class Coupon(models.Model):
    coupon_id = models.BigAutoField(primary_key=True)

    class Status(models.TextChoices):
        UNSCRATCHED = "UNSCRATCHED", "미긁음"
        WIN = "WIN", "당첨"
        LOSE = "LOSE", "꽝"
        USED = "USED", "사용 완료"
        EXPIRED = "EXPIRED", "기간 만료"

    # 쿠폰 소유자
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="coupons")

    # 쿠폰을 발급받은 날짜
    issued_date = models.DateField()

    # 오늘 전체 쿠폰 중 몇 번째인지
    daily_sequence = models.PositiveIntegerField()

    # 현재 쿠폰 상태
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNSCRATCHED)

    # 긁은 시간
    scratched_at = models.DateTimeField(null=True, blank=True)

    # 사용 완료 시간
    used_at = models.DateTimeField(null=True, blank=True)

    # 실제 쿠폰이 DB에 생성된 시각
    created_at = models.DateTimeField(auto_now_add=True)

    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # 하루에 같은 발급 순번이 두 개 생기지 않도록
            models.UniqueConstraint(
                fields=["issued_date", "daily_sequence"], name="unique_daily_coupon_sequence"
            ),
            # 한 유저가 하루에 쿠폰 2개 받지 못하도록
            models.UniqueConstraint(
                fields=["user", "issued_date"], name="unique_daily_coupon_per_user"
            ),
        ]

    def __str__(self):
        return f"Coupon {self.coupon_id} - {self.status}"


# 쿠폰 사용 확인 코드 (수령장소는 프론트에서 하드코딩, 백엔드는 코드 검증만 담당)
class BoothVerifyCode(models.Model):
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.code
