"""Notices URL configuration."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.NoticeListView.as_view(), name="notice-list"),
    path("<int:notice_id>/", views.NoticeDetailView.as_view(), name="notice-detail"),    

    path("", views.AdminNoticeListView.as_view(), name="admin-notice-list"),
    path("images/", views.AdminNoticeImageUploadView.as_view(), name="admin-notice-image-upload"),
    path("<int:notice_id>/", views.AdminNoticeDetailView.as_view(), name="admin-notice-detail"),

    path("rolling/", NoticeRollingListView.as_view(), name="notice-rolling-list"),
]
