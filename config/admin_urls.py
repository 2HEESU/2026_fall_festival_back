"""관리자 서브도메인(admin.dgufest.com) 전용 URL 설정."""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/schema/", SpectacularAPIView.as_view(urlconf="config.admin_urls"), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/lost-items/", include("apps.lost_items.urls")),
    path("api/notices/", include("apps.notices.urls")),
    path("api/lanterns/", include("apps.lanterns.admin_urls")),
]

# 분실물 이미지 업로드가 admin 서브도메인에서 동작하고, 응답 image_url도
# admin.localhost 기준으로 만들어지기 때문에 여기서도 media를 서빙해야 한다.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
