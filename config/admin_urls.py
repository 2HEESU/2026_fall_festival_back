"""관리자 서브도메인(admin.dgufest.com) 전용 URL 설정."""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/schema/", SpectacularAPIView.as_view(urlconf="config.admin_urls"), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/lost-items/", include("apps.lost_items.urls")),
    path("api/notices/", include("apps.notices.urls")),
]
