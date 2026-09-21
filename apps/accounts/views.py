"""Accounts API views."""

import requests
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RefreshToken, User
from .serializers import LoginSerializer, RefreshTokenSerializer, UserSerializer
from .services import _hash_token, generate_jwt_token, issue_refresh_token


class KakaoLoginView(APIView):
    """카카오 로그인 처리"""

    def post(self, request):
        # 코드 검증
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "code": "400",
                    "message": "입력값이 올바르지 않습니다.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = serializer.validated_data["code"]

        # 코드 검증 후 access_token 추출
        kakao_token_url = "https://kauth.kakao.com/oauth/token"

        token_params = {
            "grant_type": "authorization_code",
            "client_id": settings.KAKAO_CLIENT_ID,
            "redirect_uri": settings.KAKAO_REDIRECT_URI,
            "code": code,
        }
        if settings.KAKAO_CLIENT_SECRET:
            token_params["client_secret"] = settings.KAKAO_CLIENT_SECRET

        try:
            token_response = requests.post(kakao_token_url, data=token_params, timeout=5)

            token_response.raise_for_status()

        except requests.exceptions.RequestException as error:
            try:
                error_detail = token_response.json()
            except Exception:
                error_detail = str(error)

            return Response(
                {
                    "success": False,
                    "code": "502",
                    "message": "카카오 서버 연결 실패",
                    "errors": {"kakao_api": error_detail},
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        token_data = token_response.json()
        kakao_access_token = token_data.get("access_token")

        if not kakao_access_token:
            return Response(
                {
                    "success": False,
                    "code": "401",
                    "message": "카카오 인증에 실패했습니다.",
                    "errors": {"kakao_auth": "유효하지않은 인증 코드"},
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # access_token으로 사용자 정보 조회
        kakao_user_url = "https://kapi.kakao.com/v2/user/me"

        headers = {
            "Authorization": f"Bearer {kakao_access_token}",
            "Content-type": "application/x-www-form-urlencoded;charset=utf-8",
        }

        try:
            user_response = requests.get(kakao_user_url, headers=headers, timeout=5)

            user_response.raise_for_status()

        except requests.exceptions.RequestException:
            return Response(
                {
                    "success": False,
                    "code": "401",
                    "message": "카카오 사용자 정보 조회 실패",
                    "errors": {"access_token": "유효하지 않은 토큰"},
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        kakao_user_data = user_response.json()

        kakao_id = kakao_user_data.get("id")
        nickname = kakao_user_data.get("properties", {}).get("nickname") or kakao_user_data.get(
            "kakao_account", {}
        ).get("profile", {}).get("nickname")
        profile_image = kakao_user_data.get("properties", {}).get(
            "profile_image"
        ) or kakao_user_data.get("kakao_account", {}).get("profile", {}).get("profile_image")

        if not kakao_id or not nickname:
            return Response(
                {
                    "success": False,
                    "code": "400",
                    "message": "카카오 사용자 정보가 불완전합니다",
                    "errors": {
                        "kakao_id": "kakao_id가 없습니다" if not kakao_id else None,
                        "nickname": "nickname이 없습니다" if not nickname else None,
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # DB에 사용자 저장 및 조회
        try:
            user, is_new_user = User.objects.update_or_create(
                kakao_id=kakao_id,
                defaults={"nickname": nickname, "profile_image": profile_image},
            )

        except Exception as error:
            return Response(
                {
                    "success": False,
                    "code": "DB_ERROR",
                    "message": "사용자 저장 중 오류가 발생했습니다.",
                    "errors": {"database": str(error)},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            access_token = generate_jwt_token(user.id)
            refresh_token = issue_refresh_token(user)

        except Exception as error:
            return Response(
                {
                    "success": False,
                    "code": "TOKEN_GENERATION_ERROR",
                    "message": "토큰 생성 중 오류가 발생했습니다",
                    "errors": {"token": str(error)},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 최종 응답 반환
        return Response(
            {
                "success": True,
                "code": "LOGIN_SUCCESS",
                "message": "카카오톡 1초 로그인 성공",
                "data": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "is_new_user": is_new_user,
                    "user": UserSerializer(user).data,
                },
            },
            status=status.HTTP_200_OK,
        )


class TokenRefreshView(APIView):
    """refresh_token으로 access_token 재발급"""

    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "code": "400",
                    "message": "입력값이 올바르지 않습니다.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_value = serializer.validated_data["refresh_token"]

        try:
            refresh_token = RefreshToken.objects.get(token=_hash_token(token_value))
        except RefreshToken.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "code": "INVALID_REFRESH_TOKEN",
                    "message": "유효하지 않거나 만료된 refresh_token입니다.",
                    "errors": {"refresh_token": "재로그인이 필요합니다."},
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = refresh_token.user
        is_expired = refresh_token.expires_at < timezone.now()

        deleted_count, _ = RefreshToken.objects.filter(id=refresh_token.id).delete()

        if is_expired or deleted_count == 0:
            return Response(
                {
                    "success": False,
                    "code": "INVALID_REFRESH_TOKEN",
                    "message": "유효하지 않거나 만료된 refresh_token입니다.",
                    "errors": {"refresh_token": "재로그인이 필요합니다."},
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        new_access_token = generate_jwt_token(user.id)
        new_refresh_token = issue_refresh_token(user)

        return Response(
            {
                "success": True,
                "code": "TOKEN_REFRESHED",
                "message": "토큰이 재발급되었습니다",
                "data": {
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token,
                },
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """로그아웃 함수 (refresh_token 무효화)"""

    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "code": "400",
                    "message": "입력값이 올바르지 않습니다.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_value = serializer.validated_data["refresh_token"]
        RefreshToken.objects.filter(token=_hash_token(token_value)).delete()

        return Response(
            {
                "success": True,
                "code": "LOGOUT_SUCCESS",
                "message": "로그아웃 되었습니다",
            },
            status=status.HTTP_200_OK,
        )
