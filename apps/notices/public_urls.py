"""Notices public API routes."""
from django.urls import path
from . import views
app_name = "public_notices"
urlpatterns = [
    path("", views.NoticeListView.as_view(), name="notice-list"),
    path("<int:notice_id>/", views.NoticeDetailView.as_view(), name="notice-detail"),
]