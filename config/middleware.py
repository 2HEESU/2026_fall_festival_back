"""서브도메인 기준 URL 라우팅 미들웨어."""

from django.conf import settings


class SubdomainURLRoutingMiddleware:
    """Host가 ADMIN_HOSTS에 포함되면 admin 전용 urlconf로 전환한다."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_hosts = {h.split(":")[0].lower() for h in settings.ADMIN_HOSTS}

    def __call__(self, request):
        host = request.get_host().split(":")[0].lower()
        if host in self.admin_hosts:
            request.urlconf = "config.admin_urls"
        return self.get_response(request)
