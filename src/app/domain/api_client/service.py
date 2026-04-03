import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.api_client.model import ApiClient
from app.domain.api_client.repository import ApiClientRepository
from app.error import ForbiddenError, KeycloakError
from app.keycloak.client import KeycloakClient


class ApiClientService:
    def __init__(self, session: AsyncSession, keycloak: KeycloakClient) -> None:
        self._repo = ApiClientRepository(session=session)
        self._keycloak = keycloak

    async def create(self, name: str, created_by: str) -> tuple[ApiClient, str, str]:
        """Create API client. Returns (api_client, client_id, client_secret)."""
        kc_client = await self._keycloak.create_service_account(name)
        if not kc_client.client_id or not kc_client.secret:
            raise KeycloakError("Failed to get client credentials from Keycloak")

        # Assign ones-api role to the service account
        if kc_client.id:
            service_account = await self._keycloak.get_user_by_email(
                f"service-account-{kc_client.client_id}@placeholder.org"
            )
            if service_account:
                await self._keycloak.assign_role(service_account.id, "ones-api")

        api_client = ApiClient(
            id=str(uuid.uuid4()),
            name=name,
            keycloak_client_id=kc_client.client_id,
            created_by=created_by,
        )
        created = await self._repo.add(api_client)
        return created, kc_client.client_id, kc_client.secret

    async def list_clients(self, *, is_active: bool | None = None) -> tuple[list[ApiClient], int]:
        if is_active is not None:
            results, total = await self._repo.list_and_count(is_active=is_active)
        else:
            results, total = await self._repo.list_and_count()
        return list(results), total

    async def get_by_id(self, client_id: str) -> ApiClient:
        client = await self._repo.get_one_or_none(id=client_id)
        if not client:
            raise ForbiddenError("API client not found")
        return client

    async def deactivate(self, client_id: str) -> ApiClient:
        client = await self.get_by_id(client_id)
        if not client.is_active:
            raise ForbiddenError("API client is already inactive")

        client.is_active = False
        client.deactivated_at = datetime.now(UTC)
        updated = await self._repo.update(client)
        return updated
