# 1. 파이썬 3.11 경량화(slim) 베이스 이미지 사용
FROM python:3.11-slim

# 파이썬 버퍼링 및 .pyc 생성 방지 (컨테이너 표준 설정)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 2. 컨테이너 내부 작업 디렉터리 설정
WORKDIR /app

# 3. PostgreSQL 연결 및 빌드에 필요한 최소 필수 패키지 설치
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. 의존성 파일 복사 및 패키지 일괄 설치
# (우리 프로젝트의 pyproject.toml 기반으로 설치)
COPY pyproject.toml README.md /app/
RUN pip install --upgrade pip \
    && pip install .

# 5. 프로젝트 소스코드 전체 복사
COPY . /app/

# 6. Gunicorn 실행 (gthread 방식, 워커 2개, 스레드 4개, 포트 8000)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--worker-class", "gthread", "--threads", "4", "--timeout", "60", "config.wsgi:application"]