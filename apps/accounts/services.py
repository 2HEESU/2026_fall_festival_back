"""Transactional accounts state changes."""

import hashlib
import secrets
from datetime import timedelta

import jwt
from django.conf import settings
from django.utils import timezone

from .models import RefreshToken


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_refresh_token(user):
    RefreshToken.objects.filter(user=user, expires_at__lt=timezone.now()).delete()

    MAX_TOKENS_PER_USER = 5
    existing_count = RefreshToken.objects.filter(user=user).count()
    if existing_count >= MAX_TOKENS_PER_USER:
        overflow_count = existing_count - MAX_TOKENS_PER_USER + 1
        oldest_ids = list(
            RefreshToken.objects.filter(user=user)
            .order_by("created_at")
            .values_list("id", flat=True)[:overflow_count]
        )
        RefreshToken.objects.filter(id__in=oldest_ids).delete()

    token = secrets.token_urlsafe(32)

    RefreshToken.objects.create(
        user=user,
        token=_hash_token(token),
        expires_at=timezone.now() + timedelta(days=7),
    )

    return token


def generate_jwt_token(user_id):
    now = timezone.now()

    expired_date = now + timedelta(hours=24)

    payload = {"user_id": user_id, "iat": now.timestamp(), "exp": expired_date.timestamp()}

    token = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm="HS256",  # 대칭키 암호화
    )

    return token
