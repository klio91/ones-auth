# Ones Auth — 아키텍처

> Status: Draft
> Created: 2026-04-03

---

## 1. 시스템 위치

```
┌──────────────┐
│   브라우저   │
│  웹 사용자   │
└──────┬───────┘
       │
       ▼
┌─────────────────┐
│  Kong Gateway   │  JWT 검증 (global, 예외 경로 제외)
└──┬──────┬───┬───┘
   │      │   │
   │ /v1/*│   │ /auth/*
   │      │   ▼
   │      │  ┌──────────────┐     Keycloak Admin API    ┌────────────┐
   │      │  │  ones-auth   │ ◄──────────────────────►  │  Keycloak  │
   │      │  │   (:9000)    │                           │  (ones     │
   │      │  │              │                           │   Realm)   │
   │      │  │- OIDC 인증   │                           └────────────┘
   │      │  │- 사용자 DB   │
   │      │  │- API 클라    │
   │      │  │  이언트 발급 │
   │      │  └──────┬───────┘
   │      │         │
   │      ▼         ▼
   │  ┌──────────────────────────────────────┐
   │  │  PostgreSQL                           │
   │  │  schema: auth   │  schema: ehcro     │
   │  │  ├── users      │  ├── sessions      │
   │  │  └── api_clients│  └── messages      │
   │  └──────────────────────────────────────┘
   │
   ▼
┌──────────┐     ┌────────┐
│ ones-bff │ ──► │ ehcro  │
└──────────┘     └────────┘
```

---

## 2. 내부 구조

```
ones-auth/
├── src/app/
│   ├── main.py             ← Litestar app + DI + lifespan
│   ├── settings.py         ← 환경변수 (pydantic-settings, .env)
│   ├── db.py               ← SQLAlchemy async engine + Base
│   ├── error.py            ← AppError 계층 + 핸들러
│   │
│   ├── auth/               ← OIDC 인증 흐름
│   │   ├── controller.py     /auth/login, callback, refresh, logout
│   │   ├── service.py        code 교환, 쿠키 관리, JWT 디코딩
│   │   └── schema.py         TokenClaims DTO
│   │
│   ├── domain/
│   │   ├── user/           ← 사용자 관리
│   │   │   ├── model.py      users 테이블
│   │   │   ├── repository.py SQLAlchemyAsyncRepository
│   │   │   ├── service.py    생성/비활성화 + Keycloak Role 연동
│   │   │   ├── schema.py     UserRead, UserResponse 등
│   │   │   └── controller.py /auth/users/* (admin 전용)
│   │   │
│   │   └── api_client/     ← API 클라이언트 관리
│   │       ├── model.py      api_clients 테이블
│   │       ├── repository.py
│   │       ├── service.py    Keycloak service account 생성
│   │       ├── schema.py
│   │       └── controller.py /auth/api-clients/* (admin 전용)
│   │
│   └── keycloak/           ← Keycloak API wrapper
│       ├── client.py         OIDC + Admin API (토큰 캐싱)
│       └── schema.py         TokenResponse, KeycloakUser 등
│
├── migrations/             ← Alembic
├── tests/
├── docker-compose.yaml     ← PostgreSQL 로컬 환경
└── pyproject.toml
```

### 레이어 분리

```
controller/ → service/ → repository/ (Litestar SQLAlchemyAsyncRepository)
                ↓
            keycloak/  (외부 API)
```

- **controller**: HTTP 파싱/응답만. 비즈니스 로직 금지.
- **service**: 핵심 로직. Keycloak API + DB 조합.
- **repository**: Litestar Repository 패턴.
- **keycloak/**: Keycloak API 호출 격리. IdP 변경 시 여기만 교체.

---

## 3. 엔드포인트

| Method | Path | Kong JWT | Role | 설명 |
|--------|------|:--------:|------|------|
| GET | `/auth/login` | OFF | - | Keycloak 로그인 리다이렉트 |
| GET | `/auth/callback` | OFF | - | OIDC callback (code → token → 쿠키) |
| POST | `/auth/refresh` | OFF | - | Access Token 갱신 |
| POST | `/auth/logout` | OFF | - | 로그아웃 + 쿠키 삭제 |
| GET | `/auth/me` | ON | 아무 Role | 현재 유저 정보 |
| GET | `/auth/users` | ON | `ones-admin` | 사용자 목록 |
| PATCH | `/auth/users/{id}/deactivate` | ON | `ones-admin` | 비활성화 |
| POST | `/auth/api-clients` | ON | `ones-admin` | API 클라이언트 생성 |
| GET | `/auth/api-clients` | ON | `ones-admin` | API 클라이언트 목록 |
| PATCH | `/auth/api-clients/{id}/deactivate` | ON | `ones-admin` | API 클라이언트 비활성화 |
| GET | `/health` | OFF | - | 서버 상태 확인 |

---

## 4. DB 스키마

```sql
-- schema: auth

CREATE TABLE users (
    id           TEXT PRIMARY KEY,
    email        TEXT NOT NULL UNIQUE,
    keycloak_sub TEXT UNIQUE,
    status       TEXT NOT NULL DEFAULT 'active',  -- active / inactive
    joined_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at  TIMESTAMPTZ,
    approved_by  TEXT
);

CREATE TABLE api_clients (
    id                 TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    keycloak_client_id TEXT NOT NULL UNIQUE,
    created_by         TEXT NOT NULL REFERENCES auth.users(id),
    is_active          BOOLEAN NOT NULL DEFAULT true,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    deactivated_at     TIMESTAMPTZ
);
```

---

## 5. Keycloak 연동

### OIDC 엔드포인트

| 용도 | Keycloak 엔드포인트 |
|------|---------------------|
| 로그인 리다이렉트 | `GET /realms/ones/protocol/openid-connect/auth` |
| code → token 교환 | `POST /realms/ones/protocol/openid-connect/token` |
| token 갱신 | `POST /realms/ones/protocol/openid-connect/token` |
| 로그아웃 | `POST /realms/ones/protocol/openid-connect/logout` |
| JWKS (Kong용) | `GET /realms/ones/protocol/openid-connect/certs` |

### Admin API

ones-auth 서비스 계정 (`ones-auth-admin`)으로 호출. 최소 권한: `view-users`, `manage-users`, `manage-clients`.

| 용도 | 엔드포인트 |
|------|-----------|
| 사용자 조회 | `GET /admin/realms/ones/users?email=xxx` |
| Role 부여 | `POST /admin/realms/ones/users/{id}/role-mappings/clients/{client-id}` |
| Role 제거 | `DELETE /admin/realms/ones/users/{id}/role-mappings/clients/{client-id}` |
| Service account 생성 | `POST /admin/realms/ones/clients` |
| Service account 삭제 | `DELETE /admin/realms/ones/clients/{id}` |

Admin API 토큰은 메모리 캐싱 (만료 30초 전 자동 갱신).

---

## 6. 로그인 흐름 (OIDC + PKCE + CSRF)

```
┌──────────┐     ┌──────────────┐     ┌───────────┐     ┌───────────┐
│  브라우저  │     │ Kong Gateway │     │ ones-auth │     │ Keycloak  │
│          │     │  :8000       │     │  :9000    │     │           │
└────┬─────┘     └──────┬───────┘     └─────┬─────┘     └─────┬─────┘
     │                  │                   │                  │
     │ ① GET /auth/login│                   │                  │
     │─────────────────>│                   │                  │
     │                  │ ② 프록시          │                  │
     │                  │──────────────────>│                  │
     │                  │                   │                  │
     │                  │                   │ state 생성       │
     │                  │                   │ code_verifier 생성│
     │                  │                   │ code_challenge    │
     │                  │                   │   = SHA256(verifier)
     │                  │                   │                  │
     │          ③ 302 Redirect to Keycloak  │                  │
     │          + Set-Cookie: ones_state    │                  │
     │          + Set-Cookie: ones_pkce     │                  │
     │<─────────────────────────────────────│                  │
     │                  │                   │                  │
     │ ④ GET /realms/ones/protocol/openid-connect/auth         │
     │    ?code_challenge=xxx&state=xxx&kc_idp_hint=adsso      │
     │────────────────────────────────────────────────────────>│
     │                  │                   │                  │
     │                  │                   │    ⑤ AD SSO 인증  │
     │                  │                   │    (adsso IdP)   │
     │                  │                   │                  │
     │ ⑥ 302 Redirect to redirect_uri                         │
     │    localhost:8000/auth/callback?code=xxx&state=xxx      │
     │<────────────────────────────────────────────────────────│
     │                  │                   │                  │
     │ ⑦ GET /auth/callback?code=xxx&state=xxx                │
     │    + Cookie: ones_state, ones_pkce   │                  │
     │─────────────────>│                   │                  │
     │                  │ ⑧ 프록시          │                  │
     │                  │──────────────────>│                  │
     │                  │                   │                  │
     │                  │                   │ ⑨ CSRF 검증      │
     │                  │                   │  (state == cookie)│
     │                  │                   │                  │
     │                  │                   │ ⑩ POST token     │
     │                  │                   │  code + verifier │
     │                  │                   │─────────────────>│
     │                  │                   │                  │
     │                  │                   │ ⑪ access_token   │
     │                  │                   │    refresh_token │
     │                  │                   │<─────────────────│
     │                  │                   │                  │
     │                  │                   │ ⑫ JWT iss 검증   │
     │                  │                   │ ⑬ DB 유저 upsert │
     │                  │                   │   (status=active)│
     │                  │                   │                  │
     │        ⑭ 302 Redirect to frontend_url                  │
     │        + Set-Cookie: ones_access (path=/)               │
     │        + Set-Cookie: ones_refresh (path=/auth)          │
     │        + Delete: ones_state, ones_pkce                  │
     │<─────────────────────────────────────│                  │
     │                  │                   │                  │
     │ ⑮ 프론트엔드 접속 (로그인 완료)       │                  │
     │                  │                   │                  │
```

**핵심 포인트:**
- 브라우저는 항상 **Gateway(:8000)** 를 통해 요청한다.
- `ONES_AUTH_KEYCLOAK_REDIRECT_URI`는 Gateway 주소(`localhost:8000/auth/callback`)여야 한다.
- PKCE(`code_verifier`)는 ones-auth가 생성하고, Keycloak이 token 발급 시 검증한다.
- CSRF state는 쿠키와 query parameter를 비교하여 검증한다.
- ones-auth → Keycloak token 교환(⑩)은 서버 간 직접 호출이다.

---

## 7. 쿠키 정책

| 쿠키명 | 용도 | Path | HttpOnly | Secure | SameSite |
|--------|------|------|----------|--------|----------|
| `ones_access` | Access Token | `/` | ✅ | prod: ✅ | Lax |
| `ones_refresh` | Refresh Token | `/auth` | ✅ | prod: ✅ | Lax |
| `ones_pkce` | PKCE verifier (임시) | `/auth` | ✅ | prod: ✅ | Lax |
| `ones_state` | CSRF state (임시) | `/auth` | ✅ | prod: ✅ | Lax |

---

## 8. 응답 포맷

```json
// 성공
{ "data": { "id": "...", "email": "...", "status": "active" } }

// 목록
{ "data": [{ ... }], "total": 42 }

// 에러
{ "error": { "code": "USER_NOT_FOUND", "message": "User not found" } }
```

### 에러 코드

| HTTP | Code | 상황 |
|------|------|------|
| 400 | `INVALID_REQUEST` | 잘못된 파라미터 |
| 401 | `TOKEN_EXPIRED` | Access Token 만료 |
| 401 | `INVALID_TOKEN` | 유효하지 않은 토큰 |
| 403 | `FORBIDDEN` | Role 권한 부족 |
| 404 | `USER_NOT_FOUND` | 사용자 없음 |
| 409 | `USER_ALREADY_EXISTS` | 중복 사용자 |
| 502 | `KEYCLOAK_ERROR` | Keycloak API 호출 실패 |
