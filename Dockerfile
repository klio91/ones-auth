# ones-auth 서비스 — Keycloak OIDC 인증/인가
FROM python:3.13-slim

WORKDIR /app

# 패키지 매니저 설치
RUN pip install uv

# 의존성 먼저 복사하여 Docker 레이어 캐싱 활용
# uv.lock*: lock 파일이 없는 경우에도 빌드 가능
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# 소스 코드 + Alembic 마이그레이션 복사
COPY src/ ./src/
COPY migrations/ ./migrations/

ENV PYTHONPATH=/app/src

# Litestar 서버 포트 (settings.py 기본값: 8080)
EXPOSE 8080

CMD ["uv", "run", "python", "-m", "app.main"]
