"""ApiClientService 단위 테스트."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.api_client.model import ApiClient
from app.domain.api_client.service import ApiClientService
from app.error import ForbiddenError, KeycloakError
from app.keycloak.schema import ClientRepresentation, KeycloakUser


def _make_client(
    client_id: str = "client-1",
    name: str = "test-client",
    keycloak_client_id: str = "ones-api-test",
    created_by: str = "user-1",
    is_active: bool = True,
) -> ApiClient:
    return ApiClient(
        id=client_id,
        name=name,
        keycloak_client_id=keycloak_client_id,
        created_by=created_by,
        is_active=is_active,
    )


class TestCreate:
    @pytest.mark.asyncio
    async def test_creates_client_with_keycloak(self) -> None:
        kc_client = ClientRepresentation(
            id="kc-uuid", client_id="ones-api-myapp", secret="secret-123", name="myapp"
        )
        keycloak = AsyncMock()
        keycloak.create_service_account.return_value = kc_client
        keycloak.get_user_by_email.return_value = KeycloakUser(id="sa-user-id", email="sa@placeholder.org")

        session = MagicMock()
        repo = AsyncMock()
        repo.add = AsyncMock(side_effect=lambda c: c)

        with patch("app.domain.api_client.service.ApiClientRepository", return_value=repo):
            service = ApiClientService(session=session, keycloak=keycloak)
            client, cid, secret = await service.create(name="myapp", created_by="user-1")

        assert client.name == "myapp"
        assert client.keycloak_client_id == "ones-api-myapp"
        assert cid == "ones-api-myapp"
        assert secret == "secret-123"
        keycloak.assign_role.assert_awaited_once_with("sa-user-id", "ones-api")

    @pytest.mark.asyncio
    async def test_raises_when_keycloak_returns_no_credentials(self) -> None:
        kc_client = ClientRepresentation(id="kc-uuid", client_id=None, secret=None, name="myapp")
        keycloak = AsyncMock()
        keycloak.create_service_account.return_value = kc_client

        session = MagicMock()

        with patch("app.domain.api_client.service.ApiClientRepository", return_value=AsyncMock()):
            service = ApiClientService(session=session, keycloak=keycloak)
            with pytest.raises(KeycloakError, match="Failed to get client credentials"):
                await service.create(name="myapp", created_by="user-1")

    @pytest.mark.asyncio
    async def test_skips_role_when_no_service_account_found(self) -> None:
        kc_client = ClientRepresentation(
            id="kc-uuid", client_id="ones-api-myapp", secret="secret-123", name="myapp"
        )
        keycloak = AsyncMock()
        keycloak.create_service_account.return_value = kc_client
        keycloak.get_user_by_email.return_value = None

        session = MagicMock()
        repo = AsyncMock()
        repo.add = AsyncMock(side_effect=lambda c: c)

        with patch("app.domain.api_client.service.ApiClientRepository", return_value=repo):
            service = ApiClientService(session=session, keycloak=keycloak)
            await service.create(name="myapp", created_by="user-1")

        keycloak.assign_role.assert_not_called()


class TestListClients:
    @pytest.mark.asyncio
    async def test_list_all(self) -> None:
        clients = [_make_client(), _make_client(client_id="client-2", name="other")]
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.list_and_count = AsyncMock(return_value=(clients, 2))

        with patch("app.domain.api_client.service.ApiClientRepository", return_value=repo):
            service = ApiClientService(session=session, keycloak=keycloak)
            result, total = await service.list_clients()

        assert len(result) == 2
        assert total == 2
        repo.list_and_count.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_list_with_active_filter(self) -> None:
        clients = [_make_client()]
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.list_and_count = AsyncMock(return_value=(clients, 1))

        with patch("app.domain.api_client.service.ApiClientRepository", return_value=repo):
            service = ApiClientService(session=session, keycloak=keycloak)
            result, total = await service.list_clients(is_active=True)

        assert total == 1
        repo.list_and_count.assert_awaited_once_with(is_active=True)


class TestGetById:
    @pytest.mark.asyncio
    async def test_returns_client_when_found(self) -> None:
        client = _make_client()
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=client)

        with patch("app.domain.api_client.service.ApiClientRepository", return_value=repo):
            service = ApiClientService(session=session, keycloak=keycloak)
            result = await service.get_by_id("client-1")

        assert result is client

    @pytest.mark.asyncio
    async def test_raises_forbidden_when_not_found(self) -> None:
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=None)

        with patch("app.domain.api_client.service.ApiClientRepository", return_value=repo):
            service = ApiClientService(session=session, keycloak=keycloak)
            with pytest.raises(ForbiddenError):
                await service.get_by_id("nonexistent")


class TestDeactivate:
    @pytest.mark.asyncio
    async def test_active_client_deactivated(self) -> None:
        client = _make_client(is_active=True)
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=client)
        repo.update = AsyncMock(side_effect=lambda c: c)

        with patch("app.domain.api_client.service.ApiClientRepository", return_value=repo):
            service = ApiClientService(session=session, keycloak=keycloak)
            result = await service.deactivate("client-1")

        assert result.is_active is False
        assert result.deactivated_at is not None

    @pytest.mark.asyncio
    async def test_already_inactive_raises_forbidden(self) -> None:
        client = _make_client(is_active=False)
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=client)

        with patch("app.domain.api_client.service.ApiClientRepository", return_value=repo):
            service = ApiClientService(session=session, keycloak=keycloak)
            with pytest.raises(ForbiddenError, match="already inactive"):
                await service.deactivate("client-1")

    @pytest.mark.asyncio
    async def test_nonexistent_raises_forbidden(self) -> None:
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=None)

        with patch("app.domain.api_client.service.ApiClientRepository", return_value=repo):
            service = ApiClientService(session=session, keycloak=keycloak)
            with pytest.raises(ForbiddenError):
                await service.deactivate("nonexistent")
