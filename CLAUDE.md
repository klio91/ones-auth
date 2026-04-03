# Ones Auth — 사용자 인증/인가 서비스

## 개요

Ones 서비스의 인증/인가 담당. Keycloak OIDC(ones Realm) 연동 + 사용자 DB 관리 + API 클라이언트 발급.

```
ones-auth/
├── src/
│   └── app/
│       ├── main.py             ← Litestar app
│       ├── settings.py         ← 환경변수 (pydantic-settings)
│       ├── db.py               ← SQLAlchemy async engine
│       ├── error.py            ← 공통 에러 핸들러
│       ├── domain/
│       │   ├── user/           ← 사용자 CRUD + 승인
│       │   └── api_client/     ← API 클라이언트 관리
│       ├── auth/               ← OIDC 인증 흐름
│       └── keycloak/           ← Keycloak API wrapper
├── migrations/                 ← Alembic
├── tests/
├── pyproject.toml
└── CLAUDE.md
```

## Tech Stack

- Python 3.13, uv, hatchling
- Litestar 2.18, Pydantic 2.12, SQLAlchemy async + asyncpg
- Alembic (마이그레이션), httpx (Keycloak API), python-jose (JWT 디코딩)
- PostgreSQL (`auth` 스키마)

## 규칙

### 레이어 분리

```
controller/ → service/ → repository/ (Litestar SQLAlchemyAsyncRepository)
                ↓
            keycloak/  (외부 API)
```

- controller: HTTP 파싱/응답만. 비즈니스 로직 금지.
- service: 핵심 로직. Keycloak + DB 조합.
- repository: Litestar Repository 패턴 사용.
- keycloak/: Keycloak API 호출 격리.

### 응답 포맷

```json
// 성공
{ "data": { ... } }
// 목록
{ "data": [...], "total": 42 }
// 에러
{ "error": { "code": "USER_NOT_FOUND", "message": "..." } }
```

### 인증

- Kong이 JWT 검증 후 `X-User-ID`, `X-User-Email`, `X-User-Roles` 헤더를 주입.
- ones-auth는 이 헤더를 신뢰한다 (Kong 뒤에서만 동작).
- Admin API (`/auth/users/*`, `/auth/api-clients/*`)는 `X-User-Roles`에 `ones-admin` 필수.

### DB

- 스키마: `auth`
- 테이블: `users`, `api_clients`
- 마이그레이션: Alembic (`migrations/`)

### 환경변수

prefix: `ONES_AUTH_`

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DB_URL` | PostgreSQL 연결 문자열 | `postgresql+asyncpg://postgres:postgres@localhost:5432/ones` |
| `KEYCLOAK_URL` | Keycloak 서버 URL | `http://localhost:8080` |
| `KEYCLOAK_REALM` | Realm 이름 | `ones` |
| `KEYCLOAK_CLIENT_ID` | OIDC Client ID | `ones` |
| `KEYCLOAK_CLIENT_SECRET` | OIDC Client Secret | dummy |
| `KEYCLOAK_REDIRECT_URI` | OIDC callback URI | `http://localhost:8000/auth/callback` |
| `KEYCLOAK_ADMIN_CLIENT_ID` | Admin API 서비스 계정 | `ones-auth-admin` |
| `KEYCLOAK_ADMIN_CLIENT_SECRET` | Admin API Secret | dummy |

### 실행

```bash
uv run python -m app.main
```

### 테스트

```bash
uv run pytest tests/ -x -q
```
