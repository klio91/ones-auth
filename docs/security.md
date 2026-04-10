# 보안 설계

> Status: Current
> Created: 2026-04-10

---

## PKCE (Proof Key for Code Exchange, RFC 7636)

OIDC Authorization Code 흐름에 PKCE S256을 적용한다.

1. `/auth/login`: `code_verifier` (43자, `secrets.token_urlsafe(32)`) 생성 → `code_challenge = BASE64URL(SHA256(verifier))` 계산 → Keycloak에 `code_challenge` + `code_challenge_method=S256` 전달 → `code_verifier`는 `ones_pkce` 쿠키(HttpOnly, path=/auth)에 저장
2. `/auth/callback`: `ones_pkce` 쿠키에서 `code_verifier` 읽어 Keycloak token endpoint에 전달 → callback 완료 후 쿠키 즉시 삭제

**왜:** Authorization Code 탈취 공격을 차단한다. code만 있어도 token을 발급받을 수 없다.

---

## CSRF 방어 (State 파라미터)

1. `/auth/login`: `state` (43자, `secrets.token_urlsafe(32)`) 생성 → `ones_state` 쿠키(HttpOnly, path=/auth)에 저장 → Keycloak에 `state` 파라미터로 전달
2. `/auth/callback`: query string의 `state`와 `ones_state` 쿠키 값을 비교 → 불일치 시 400 반환 → 성공 시 쿠키 즉시 삭제

**왜:** 공격자가 조작한 callback URL로 인한 CSRF 공격을 방어한다.

---

## JWT 검증 전략

Kong이 JWKS를 통해 서명 검증을 담당한다. ones-auth는 Kong 뒤에서만 동작하므로 서명을 재검증하지 않는다.
대신 아래 최소 검증을 수행한다:

| 항목 | 검증 방법 |
|------|-----------|
| 서명 | 미검증 (Kong에 위임) |
| `iss` (issuer) | `KEYCLOAK_URL/realms/KEYCLOAK_REALM` 일치 여부 확인 |
| `aud` (audience) | 미검증 (`verify_aud=False`) — Keycloak 멀티 클라이언트 환경 호환 |

JWT 검증 실패 시 내부 에러 메시지를 노출하지 않고 `"Invalid token"` 고정 메시지를 반환한다.

---

## 쿠키 정책

| 쿠키명 | 용도 | Path | HttpOnly | Secure | SameSite |
|--------|------|------|----------|--------|----------|
| `ones_access` | Access Token | `/` | ✅ | prod: ✅ | Lax |
| `ones_refresh` | Refresh Token | `/auth` | ✅ | prod: ✅ | Lax |
| `ones_pkce` | PKCE verifier (임시) | `/auth` | ✅ | prod: ✅ | Lax |
| `ones_state` | CSRF state (임시) | `/auth` | ✅ | prod: ✅ | Lax |

---

## PII 로그 정책

사용자 식별 정보(sub, email)는 DEBUG 레벨로만 기록한다. INFO 이상 레벨에서는 PII가 노출되지 않는다.
