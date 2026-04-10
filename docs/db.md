# DB 스키마

> Status: Current
> Created: 2026-04-10

---

## 스키마: `auth`

### `auth.users`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | TEXT PK | UUID |
| `email` | TEXT UNIQUE NOT NULL | 로그인 이메일 |
| `keycloak_sub` | TEXT UNIQUE | Keycloak user ID |
| `status` | TEXT NOT NULL | `active` / `inactive` |
| `joined_at` | TIMESTAMPTZ | 최초 로그인 시각 |
| `approved_at` | TIMESTAMPTZ | (레거시, 미사용) |
| `approved_by` | TEXT | (레거시, 미사용) |

### `auth.api_clients`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | TEXT PK | UUID |
| `name` | TEXT NOT NULL | 클라이언트 이름 |
| `keycloak_client_id` | TEXT UNIQUE NOT NULL | Keycloak client_id |
| `created_by` | TEXT FK→auth.users.id | 생성한 사용자 |
| `is_active` | BOOLEAN NOT NULL | 활성 여부 |
| `created_at` | TIMESTAMPTZ | 생성 시각 |
| `deactivated_at` | TIMESTAMPTZ | 비활성화 시각 |

---

## 마이그레이션

Alembic으로 관리. `migrations/versions/` 참조.

```bash
uv run alembic upgrade head   # 최신으로 올리기
uv run alembic downgrade -1   # 한 단계 되돌리기
uv run alembic current        # 현재 버전 확인
```
