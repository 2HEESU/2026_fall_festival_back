"""Shared permission primitives.

Admin authentication is still pending the ``apps.admins`` decision, so this
checks a shared bearer token from settings. The interface (``request.admin_id``)
is what the views depend on, so swapping in the real admin model later touches
only this file.
"""

from django.conf import settings
from rest_framework.permissions import BasePermission

from .exceptions import Unauthorized


def is_admin_request(request) -> bool:
    """요청이 관리자 토큰(Bearer ADMIN_API_TOKEN)을 포함하고 있는지 확인합니다."""
    if getattr(request, "is_admin", False):
        return True
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    expected = getattr(settings, "ADMIN_API_TOKEN", "")
    return (
        scheme.lower() == "bearer"
        and bool(token.strip())
        and bool(expected)
        and token.strip() == expected
    )


class IsAdmin(BasePermission):
    """Require ``Authorization: Bearer {admin_token}``."""

    def has_permission(self, request, view):
        if not is_admin_request(request):
            raise Unauthorized()

        request.admin_id = None
        return True
