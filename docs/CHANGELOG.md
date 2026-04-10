# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [2026-04-10]

### Added
- PKCE(S256) 인증 지원: login에서 code_verifier 생성 후 쿠키 저장, callback에서 전달
- CSRF 방어: OIDC state 파라미터 쿠키 저장 및 callback에서 검증
- Keycloak IdP Hint(`kc_idp_hint`) 파라미터 지원 — AD SSO 자동 리다이렉트
- loguru 기반 중앙 로깅 모듈, stdlib logging 인터셉트
- Alembic 초기 마이그레이션 (auth.users, auth.api_clients)
- `AuthService.with_db()` 팩토리 메서드
- `AuthService.exchange_and_upsert()` — callback 비즈니스 로직 통합
- `docs/db.md` — DB 스키마 문서
- `docs/security.md` — 보안 설계 문서
- docker-compose에 ones-auth 서비스 추가, `Dockerfile` 추가

### Changed
- 신규 유저 생성 시 status = `active`, Keycloak role `ones-user` 즉시 할당
- callback 리다이렉트 대상을 `ONES_AUTH_FRONTEND_URL` 환경변수로 변경
- AuthService 모든 static 메서드를 인스턴스 메서드로 변경
- JWT 디코딩에 `verify_aud=False` 옵션 추가, issuer 검증 추가
- JWT 검증 실패 시 내부 에러 메시지 대신 고정 메시지 반환
- PII(sub, email) 로그를 INFO → DEBUG 레벨로 변경
- docker-compose PostgreSQL 포트 5432 → 35432

### Removed
- `/auth/users/{id}/approve` 엔드포인트 제거
- `UserService.approve()` 메서드 제거

## [2026-04-03]

### Added

- 프로젝트 초기화: Litestar + SQLAlchemy async + Keycloak OIDC 연동 구조
- 인증 컨트롤러: /auth/login, callback, refresh, logout
- 사용자 관리 컨트롤러: /auth/users (목록, 승인, 비활성화) — admin 전용
- API 클라이언트 관리 컨트롤러: /auth/api-clients (생성, 목록, 비활성화) — admin 전용
- Keycloak API wrapper: OIDC + Admin API (토큰 캐싱)
- DB 모델: users, api_clients (PostgreSQL auth 스키마)
- Alembic 마이그레이션 설정
- docker-compose.yaml: PostgreSQL 로컬 개발 환경
- .env / .env.example: 환경변수 설정
- docs/architecture.md: 아키텍처 설계 문서
- docs/CHANGELOG.md: 변경 이력
