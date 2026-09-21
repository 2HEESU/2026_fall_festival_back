"""Accounts API routes."""

from django.urls import path

from .views import KakaoLoginView, LogoutView, TokenRefreshView

urlpatterns = [
    path("login/", KakaoLoginView.as_view(), name="kakao-login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
