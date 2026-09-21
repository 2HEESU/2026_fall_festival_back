"""관리자 서브도메인(admin.dgufest.com) 전용 URL 설정."""

from django.urls import include, path

urlpatterns = [
    path("api/lost-items/", include("apps.lost_items.urls")),
    path("api/notices/", include("apps.notices.urls")),
]