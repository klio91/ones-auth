# Ones Auth

Ones 서비스의 인증/인가 서비스. Keycloak OIDC 연동, 사용자 관리, API 클라이언트 발급.

## 빠른 시작

```bash
# 의존성 설치
uv sync

# 서버 실행
uv run python -m app.main

# 테스트
uv run pytest tests/ -x -q
```

## API 엔드포인트

### 인증 (Kong JWT 검증 OFF)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/auth/login` | Keycloak 로그인 리다이렉트 |
| GET | `/auth/callback` | OIDC callback (code → token) |
| POST | `/auth/refresh` | Access Token 갱신 |
| POST | `/auth/logout` | 로그아웃 |

### 사용자 정보 (Kong JWT 검증 ON)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/auth/me` | 현재 로그인 유저 정보 |

### 사용자 관리 — Admin 전용 (Kong JWT 검증 ON + ones-admin Role)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/auth/users` | 사용자 목록 |
| PATCH | `/auth/users/{id}/approve` | 사용자 승인 (waiting → active) |
| PATCH | `/auth/users/{id}/deactivate` | 사용자 비활성화 |

### API 클라이언트 관리 — Admin 전용

| Method | Path | 설명 |
|--------|------|------|
| POST | `/auth/api-clients` | API 클라이언트 생성 |
| GET | `/auth/api-clients` | API 클라이언트 목록 |
| PATCH | `/auth/api-clients/{id}/deactivate` | API 클라이언트 비활성화 |

### 헬스 체크

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 서버 상태 확인 |

## 마이그레이션

```bash
# 최신 스키마 적용
uv run alembic upgrade head

# 새 마이그레이션 생성 (모델 변경 후)
uv run alembic revision --autogenerate -m "변경 설명"

# 현재 버전 확인
uv run alembic current
```

## 상세 문서

- [CLAUDE.md](CLAUDE.md) — 프로젝트 규칙, 아키텍처, 환경변수
