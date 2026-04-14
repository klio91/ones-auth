"""KeycloakClient 단위 테스트."""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.error import KeycloakError
from app.keycloak.client import KeycloakClient


def _mock_response(status_code: int = 200, json_data: dict | list | None = None, text: str = "", headers: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.headers = headers or {}
    return resp


class TestGetAuthorizationUrl:
    def test_builds_correct_url(self) -> None:
        client = KeycloakClient()

        url = client.get_authorization_url(state="abc123", code_challenge="challenge456")

        assert "response_type=code" in url
        assert "state=abc123" in url
        assert "code_challenge=challenge456" in url
        assert "code_challenge_method=S256" in url
        assert "scope=openid+email+profile" in url

    def test_includes_idp_hint_when_configured(self) -> None:
        client = KeycloakClient()

        with patch("app.keycloak.client.settings") as mock_settings:
            mock_settings.keycloak_client_id = "ones"
            mock_settings.keycloak_redirect_uri = "http://localhost:8000/auth/callback"
            mock_settings.oidc_auth_url = "http://localhost:8080/realms/ones/protocol/openid-connect/auth"
            mock_settings.keycloak_idp_hint = "adsso"

            url = client.get_authorization_url(state="s", code_challenge="c")

        assert "kc_idp_hint=adsso" in url

    def test_no_idp_hint_when_none(self) -> None:
        client = KeycloakClient()

        with patch("app.keycloak.client.settings") as mock_settings:
            mock_settings.keycloak_client_id = "ones"
            mock_settings.keycloak_redirect_uri = "http://localhost:8000/auth/callback"
            mock_settings.oidc_auth_url = "http://localhost:8080/realms/ones/protocol/openid-connect/auth"
            mock_settings.keycloak_idp_hint = None

            url = client.get_authorization_url(state="s", code_challenge="c")

        assert "kc_idp_hint" not in url


class TestExchangeCode:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        token_data = {
            "access_token": "at-123",
            "refresh_token": "rt-456",
            "expires_in": 300,
            "token_type": "Bearer",
        }
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.post.return_value = _mock_response(200, token_data)

        result = await client.exchange_code("auth-code", "verifier")

        assert result.access_token == "at-123"
        assert result.refresh_token == "rt-456"

    @pytest.mark.asyncio
    async def test_failure_raises_keycloak_error(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.post.return_value = _mock_response(400, text="invalid_grant")

        with pytest.raises(KeycloakError, match="Code exchange failed"):
            await client.exchange_code("bad-code", "verifier")


class TestRefreshToken:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        token_data = {
            "access_token": "new-at",
            "refresh_token": "new-rt",
            "expires_in": 300,
            "token_type": "Bearer",
        }
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.post.return_value = _mock_response(200, token_data)

        result = await client.refresh_token("old-rt")

        assert result.access_token == "new-at"

    @pytest.mark.asyncio
    async def test_failure_raises_keycloak_error(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.post.return_value = _mock_response(400, text="invalid_grant")

        with pytest.raises(KeycloakError, match="Token refresh failed"):
            await client.refresh_token("expired-rt")


class TestLogout:
    @pytest.mark.asyncio
    async def test_success_200(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.post.return_value = _mock_response(200)

        await client.logout("rt-token")  # should not raise

    @pytest.mark.asyncio
    async def test_success_204(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.post.return_value = _mock_response(204)

        await client.logout("rt-token")  # should not raise

    @pytest.mark.asyncio
    async def test_failure_raises_keycloak_error(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.post.return_value = _mock_response(400, text="bad request")

        with pytest.raises(KeycloakError, match="Logout failed"):
            await client.logout("rt-token")


class TestGetAdminToken:
    @pytest.mark.asyncio
    async def test_fetches_new_token(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.post.return_value = _mock_response(200, {"access_token": "admin-tok", "expires_in": 300})

        token = await client._get_admin_token()

        assert token == "admin-tok"
        assert client._admin_token == "admin-tok"

    @pytest.mark.asyncio
    async def test_returns_cached_token_when_valid(self) -> None:
        client = KeycloakClient()
        client._admin_token = "cached-tok"
        client._admin_token_expires_at = time.time() + 120  # well in the future
        client._http = AsyncMock()

        token = await client._get_admin_token()

        assert token == "cached-tok"
        client._http.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_refreshes_when_near_expiry(self) -> None:
        client = KeycloakClient()
        client._admin_token = "old-tok"
        client._admin_token_expires_at = time.time() + 10  # within 30s buffer
        client._http = AsyncMock()
        client._http.post.return_value = _mock_response(200, {"access_token": "new-tok", "expires_in": 300})

        token = await client._get_admin_token()

        assert token == "new-tok"

    @pytest.mark.asyncio
    async def test_failure_raises_keycloak_error(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.post.return_value = _mock_response(401, text="unauthorized")

        with pytest.raises(KeycloakError, match="Admin token acquisition failed"):
            await client._get_admin_token()


class TestGetUserByEmail:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._get_admin_token = AsyncMock(return_value="admin-tok")
        client._http.get.return_value = _mock_response(200, [{"id": "u-1", "email": "a@b.com"}])

        user = await client.get_user_by_email("a@b.com")

        assert user is not None
        assert user.id == "u-1"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._get_admin_token = AsyncMock(return_value="admin-tok")
        client._http.get.return_value = _mock_response(200, [])

        user = await client.get_user_by_email("nobody@b.com")

        assert user is None

    @pytest.mark.asyncio
    async def test_failure_raises_keycloak_error(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._get_admin_token = AsyncMock(return_value="admin-tok")
        client._http.get.return_value = _mock_response(500, text="server error")

        with pytest.raises(KeycloakError, match="User lookup failed"):
            await client.get_user_by_email("a@b.com")


class TestAssignRole:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._get_admin_token = AsyncMock(return_value="admin-tok")
        client._get_ones_client_uuid = AsyncMock(return_value="client-uuid")
        client._get_client_role = AsyncMock(return_value={"id": "role-id", "name": "ones-user"})
        client._http.post.return_value = _mock_response(204)

        await client.assign_role("user-id", "ones-user")

        client._http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure_raises_keycloak_error(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._get_admin_token = AsyncMock(return_value="admin-tok")
        client._get_ones_client_uuid = AsyncMock(return_value="client-uuid")
        client._get_client_role = AsyncMock(return_value={"id": "role-id", "name": "ones-user"})
        client._http.post.return_value = _mock_response(403, text="forbidden")

        with pytest.raises(KeycloakError, match="Role assignment failed"):
            await client.assign_role("user-id", "ones-user")


class TestRemoveRole:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._get_admin_token = AsyncMock(return_value="admin-tok")
        client._get_ones_client_uuid = AsyncMock(return_value="client-uuid")
        client._get_client_role = AsyncMock(return_value={"id": "role-id", "name": "ones-user"})
        client._http.delete.return_value = _mock_response(204)

        await client.remove_role("user-id", "ones-user")

        client._http.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure_raises_keycloak_error(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._get_admin_token = AsyncMock(return_value="admin-tok")
        client._get_ones_client_uuid = AsyncMock(return_value="client-uuid")
        client._get_client_role = AsyncMock(return_value={"id": "role-id", "name": "ones-user"})
        client._http.delete.return_value = _mock_response(500, text="internal")

        with pytest.raises(KeycloakError, match="Role removal failed"):
            await client.remove_role("user-id", "ones-user")


class TestCreateServiceAccount:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._get_admin_token = AsyncMock(return_value="admin-tok")

        create_resp = _mock_response(201, headers={"Location": "http://kc/clients/new-uuid"})
        secret_resp = _mock_response(200, {"value": "the-secret"})
        client._http.post.return_value = create_resp
        client._http.get.return_value = secret_resp

        result = await client.create_service_account("myapp")

        assert result.id == "new-uuid"
        assert result.client_id == "ones-api-myapp"
        assert result.secret == "the-secret"

    @pytest.mark.asyncio
    async def test_creation_failure_raises_keycloak_error(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._get_admin_token = AsyncMock(return_value="admin-tok")
        client._http.post.return_value = _mock_response(409, text="conflict")

        with pytest.raises(KeycloakError, match="Service account creation failed"):
            await client.create_service_account("myapp")

    @pytest.mark.asyncio
    async def test_secret_retrieval_failure_raises_keycloak_error(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._get_admin_token = AsyncMock(return_value="admin-tok")

        create_resp = _mock_response(201, headers={"Location": "http://kc/clients/new-uuid"})
        secret_resp = _mock_response(404, text="not found")
        client._http.post.return_value = create_resp
        client._http.get.return_value = secret_resp

        with pytest.raises(KeycloakError, match="Client secret retrieval failed"):
            await client.create_service_account("myapp")


class TestDeleteServiceAccount:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._get_admin_token = AsyncMock(return_value="admin-tok")
        client._http.delete.return_value = _mock_response(204)

        await client.delete_service_account("uuid-123")

        client._http.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure_raises_keycloak_error(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._get_admin_token = AsyncMock(return_value="admin-tok")
        client._http.delete.return_value = _mock_response(404, text="not found")

        with pytest.raises(KeycloakError, match="Service account deletion failed"):
            await client.delete_service_account("uuid-123")


class TestGetOnesClientUuid:
    @pytest.mark.asyncio
    async def test_returns_uuid(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.get.return_value = _mock_response(200, [{"id": "ones-uuid-1"}])

        uuid = await client._get_ones_client_uuid({"Authorization": "Bearer tok"})

        assert uuid == "ones-uuid-1"

    @pytest.mark.asyncio
    async def test_empty_list_raises_keycloak_error(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.get.return_value = _mock_response(200, [])

        with pytest.raises(KeycloakError, match="not found"):
            await client._get_ones_client_uuid({"Authorization": "Bearer tok"})

    @pytest.mark.asyncio
    async def test_api_failure_raises_keycloak_error(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.get.return_value = _mock_response(500, text="error")

        with pytest.raises(KeycloakError, match="Client lookup failed"):
            await client._get_ones_client_uuid({"Authorization": "Bearer tok"})


class TestGetClientRole:
    @pytest.mark.asyncio
    async def test_returns_role(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.get.return_value = _mock_response(200, {"id": "role-1", "name": "ones-user"})

        role = await client._get_client_role({"Authorization": "Bearer tok"}, "client-uuid", "ones-user")

        assert role["name"] == "ones-user"

    @pytest.mark.asyncio
    async def test_not_found_raises_keycloak_error(self) -> None:
        client = KeycloakClient()
        client._http = AsyncMock()
        client._http.get.return_value = _mock_response(404, text="not found")

        with pytest.raises(KeycloakError, match="Role.*not found"):
            await client._get_client_role({"Authorization": "Bearer tok"}, "client-uuid", "bad-role")
