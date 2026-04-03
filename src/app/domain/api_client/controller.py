from litestar import Controller, get, patch, post
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.api_client.schema import (
    ApiClientCreate,
    ApiClientCreatedResponse,
    ApiClientListResponse,
    ApiClientRead,
    ApiClientResponse,
)
from app.domain.api_client.service import ApiClientService
from app.error import ForbiddenError
from app.keycloak.client import KeycloakClient


class ApiClientController(Controller):
    path = "/auth/api-clients"

    @post("/")
    async def create_api_client(
        self,
        data: ApiClientCreate,
        db_session: AsyncSession,
        keycloak: KeycloakClient,
        x_user_id: str = Parameter(header="X-User-ID", default=""),
        x_user_roles: str = Parameter(header="X-User-Roles", default=""),
    ) -> ApiClientCreatedResponse:
        _require_admin(x_user_roles)
        service = ApiClientService(session=db_session, keycloak=keycloak)
        client, client_id, client_secret = await service.create(name=data.name, created_by=x_user_id)
        await db_session.commit()
        return ApiClientCreatedResponse(
            data=ApiClientRead.model_validate(client, from_attributes=True),
            client_id=client_id,
            client_secret=client_secret,
        )

    @get("/")
    async def list_api_clients(
        self,
        db_session: AsyncSession,
        keycloak: KeycloakClient,
        is_active: bool | None = Parameter(query="is_active", default=None),
        x_user_roles: str = Parameter(header="X-User-Roles", default=""),
    ) -> ApiClientListResponse:
        _require_admin(x_user_roles)
        service = ApiClientService(session=db_session, keycloak=keycloak)
        clients, total = await service.list_clients(is_active=is_active)
        return ApiClientListResponse(
            data=[ApiClientRead.model_validate(c, from_attributes=True) for c in clients],
            total=total,
        )

    @patch("/{client_id:str}/deactivate")
    async def deactivate_api_client(
        self,
        db_session: AsyncSession,
        keycloak: KeycloakClient,
        client_id: str,
        x_user_roles: str = Parameter(header="X-User-Roles", default=""),
    ) -> ApiClientResponse:
        _require_admin(x_user_roles)
        service = ApiClientService(session=db_session, keycloak=keycloak)
        client = await service.deactivate(client_id)
        await db_session.commit()
        return ApiClientResponse(data=ApiClientRead.model_validate(client, from_attributes=True))


def _require_admin(roles_header: str) -> None:
    roles = [r.strip() for r in roles_header.split(",") if r.strip()]
    if "ones-admin" not in roles:
        raise ForbiddenError("Admin role required")
