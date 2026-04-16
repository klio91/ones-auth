# ones-auth 서비스 — Keycloak OIDC 인증/인가
FROM python:3.13-slim

WORKDIR /app

# uv 바이너리 복사 (Bart registry)
COPY --from=ghcr-docker-remote.bart.sec.samsung.net/ghcr.io/astral-sh/uv:0.9.9 /uv /uvx /usr/local/bin

# non-root 유저 생성
RUN groupadd --system app && useradd --system --gid app --no-create-home app

# 의존성 먼저 복사하여 Docker 레이어 캐싱 활용
# uv.lock*: lock 파일이 없는 경우에도 빌드 가능
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

# 소스 코드 + Alembic 마이그레이션 복사
COPY src/ ./src/
COPY migrations/ ./migrations/

# 앱 파일 소유권 설정 후 유저 전환
RUN chown -R app:app /app
USER app

ENV PYTHONPATH=/app/src

# Litestar 서버 포트 (settings.py 기본값: 9000)
EXPOSE 9000

CMD ["uv", "run", "python", "-m", "app.main"]
