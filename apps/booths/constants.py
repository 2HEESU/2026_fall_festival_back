"""Booths domain constants."""

from datetime import date, time

FESTIVAL_DATES = [date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1)]
DEFAULT_FESTIVAL_DATE = FESTIVAL_DATES[0]

# 이 시각 이전 요청은 DAY, 이후는 NIGHT 기본값
DAY_NIGHT_BOUNDARY = time(16, 30)

# 컬러칩 4종. 'BOOTH' 칩은 협업 부스(COLLAB)와 일반 부스(ETC)를 함께 묶음
CATEGORY_CHIPS = ["BOOTH", "TOILET", "ALCOHOL", "ECO"]
BOOTH_CHIP = "BOOTH"
BOOTH_CHIP_CATEGORIES = ["COLLAB", "ETC"]

# 다회용기 부스는 협업(COLLAB)으로 분류했지만 '동빛에코' 칩에도 계속 보여야 한다.
# category가 한 칸이라 이름으로 예외를 둔다 (부스 이름이 바뀌면 여기도 고칠 것).
ECO_CHIP_EXTRA_BOOTH_NAMES = ["다회용기 부스 (혜화관)", "다회용기 부스 (팔정도)"]
