from litestar import Controller, get, patch
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.user.schema import UserListResponse, UserRead, UserResponse
from app.domain.user.service import UserService
from app.error import ForbiddenError
from app.keycloak.client import KeycloakClient


class UserController(Controller):
    path = "/auth/users"

    @get("/")
    async def list_users(
        self,
        db_session: AsyncSession,
        keycloak: KeycloakClient,
        status: str | None = Parameter(query="status", default=None),
        x_user_roles: str = Parameter(header="X-User-Roles", default=""),
    ) -> UserListResponse:
        _require_admin(x_user_roles)
        service = UserService(session=db_session, keycloak=keycloak)
        users, total = await service.list_users(status=status)
        return UserListResponse(
            data=[UserRead.model_validate(u, from_attributes=True) for u in users],
            total=total,
        )

    @patch("/{user_id:str}/approve")
    async def approve_user(
        self,
        db_session: AsyncSession,
        keycloak: KeycloakClient,
        user_id: str,
        x_user_id: str = Parameter(header="X-User-ID", default=""),
        x_user_roles: str = Parameter(header="X-User-Roles", default=""),
    ) -> UserResponse:
        _require_admin(x_user_roles)
        service = UserService(session=db_session, keycloak=keycloak)
        user = await service.approve(user_id, approved_by=x_user_id)
        await db_session.commit()
        return UserResponse(data=UserRead.model_validate(user, from_attributes=True))

    @patch("/{user_id:str}/deactivate")
    async def deactivate_user(
        self,
        db_session: AsyncSession,
        keycloak: KeycloakClient,
        user_id: str,
        x_user_roles: str = Parameter(header="X-User-Roles", default=""),
    ) -> UserResponse:
        _require_admin(x_user_roles)
        service = UserService(session=db_session, keycloak=keycloak)
        user = await service.deactivate(user_id)
        await db_session.commit()
        return UserResponse(data=UserRead.model_validate(user, from_attributes=True))


def _require_admin(roles_header: str) -> None:
    roles = [r.strip() for r in roles_header.split(",") if r.strip()]
    if "ones-admin" not in roles:
        raise ForbiddenError("Admin role required")
