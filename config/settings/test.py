"""Automated test settings."""

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "test-only-secret-key"
ALLOWED_HOSTS = ["testserver", "admin.testserver"]
ADMIN_HOSTS = ["admin.testserver"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

ADMIN_API_TOKEN = "test-admin-token"  # 어드민 토큰
