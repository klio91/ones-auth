# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
