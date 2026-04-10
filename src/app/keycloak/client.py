import time

import httpx

from app.error import KeycloakError
from app.keycloak.schema import ClientRepresentation, KeycloakUser, TokenResponse
from app.settings import settings


class KeycloakClient:
    """Keycloak OIDC + Admin API client with token caching."""

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(timeout=10.0)
        self._admin_token: str | None = None
        self._admin_token_expires_at: float = 0

    async def close(self) -> None:
        await self._http.aclose()

    # ── OIDC ──

    def get_authorization_url(self, state: str, code_challenge: str) -> str:
        params: dict[str, str] = {
            "client_id": settings.keycloak_client_id,
            "redirect_uri": settings.keycloak_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if settings.keycloak_idp_hint:
            params["kc_idp_hint"] = settings.keycloak_idp_hint
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{settings.oidc_auth_url}?{query}"

    async def exchange_code(self, code: str, code_verifier: str) -> TokenResponse:
        resp = await self._http.post(
            settings.oidc_token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.keycloak_client_id,
                "client_secret": settings.keycloak_client_secret,
                "code": code,
                "redirect_uri": settings.keycloak_redirect_uri,
                "code_verifier": code_verifier,
            },
        )
        if resp.status_code != 200:
            raise KeycloakError(f"Code exchange failed: {resp.text}")
        return TokenResponse.model_validate(resp.json())

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        resp = await self._http.post(
            settings.oidc_token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.keycloak_client_id,
                "client_secret": settings.keycloak_client_secret,
                "refresh_token": refresh_token,
            },
        )
        if resp.status_code != 200:
            raise KeycloakError(f"Token refresh failed: {resp.text}")
        return TokenResponse.model_validate(resp.json())

    async def logout(self, refresh_token: str) -> None:
        resp = await self._http.post(
            settings.oidc_logout_url,
            data={
                "client_id": settings.keycloak_client_id,
                "client_secret": settings.keycloak_client_secret,
                "refresh_token": refresh_token,
            },
        )
        if resp.status_code not in (200, 204):
            raise KeycloakError(f"Logout failed: {resp.text}")

    # ── Admin API ──

    async def _get_admin_token(self) -> str:
        now = time.time()
        if self._admin_token and now < self._admin_token_expires_at - 30:
            return self._admin_token

        resp = await self._http.post(
            settings.oidc_token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.keycloak_admin_client_id,
                "client_secret": settings.keycloak_admin_client_secret,
            },
        )
        if resp.status_code != 200:
            raise KeycloakError(f"Admin token acquisition failed: {resp.text}")

        data = resp.json()
        self._admin_token = data["access_token"]
        self._admin_token_expires_at = now + data["expires_in"]
        return self._admin_token

    async def _admin_headers(self) -> dict[str, str]:
        token = await self._get_admin_token()
        return {"Authorization": f"Bearer {token}"}

    async def get_user_by_email(self, email: str) -> KeycloakUser | None:
        headers = await self._admin_headers()
        resp = await self._http.get(
            f"{settings.keycloak_admin_base}/users",
            params={"email": email, "exact": "true"},
            headers=headers,
        )
        if resp.status_code != 200:
            raise KeycloakError(f"User lookup failed: {resp.text}")
        users = resp.json()
        if not users:
            return None
        return KeycloakUser.model_validate(users[0])

    async def assign_role(self, user_id: str, role_name: str) -> None:
        headers = await self._admin_headers()
        client_uuid = await self._get_ones_client_uuid(headers)
        role = await self._get_client_role(headers, client_uuid, role_name)

        resp = await self._http.post(
            f"{settings.keycloak_admin_base}/users/{user_id}/role-mappings/clients/{client_uuid}",
            json=[role],
            headers=headers,
        )
        if resp.status_code not in (200, 204):
            raise KeycloakError(f"Role assignment failed: {resp.text}")

    async def remove_role(self, user_id: str, role_name: str) -> None:
        headers = await self._admin_headers()
        client_uuid = await self._get_ones_client_uuid(headers)
        role = await self._get_client_role(headers, client_uuid, role_name)

        resp = await self._http.delete(
            f"{settings.keycloak_admin_base}/users/{user_id}/role-mappings/clients/{client_uuid}",
            json=[role],
            headers=headers,
        )
        if resp.status_code not in (200, 204):
            raise KeycloakError(f"Role removal failed: {resp.text}")

    async def create_service_account(self, name: str) -> ClientRepresentation:
        headers = await self._admin_headers()
        client = ClientRepresentation(
            client_id=f"ones-api-{name}",
            name=name,
            service_accounts_enabled=True,
        )
        resp = await self._http.post(
            f"{settings.keycloak_admin_base}/clients",
            json=client.model_dump(exclude_none=True),
            headers=headers,
        )
        if resp.status_code not in (200, 201):
            raise KeycloakError(f"Service account creation failed: {resp.text}")

        location = resp.headers.get("Location", "")
        client_uuid = location.rsplit("/", 1)[-1]

        secret_resp = await self._http.get(
            f"{settings.keycloak_admin_base}/clients/{client_uuid}/client-secret",
            headers=headers,
        )
        if secret_resp.status_code != 200:
            raise KeycloakError(f"Client secret retrieval failed: {secret_resp.text}")

        return ClientRepresentation(
            id=client_uuid,
            client_id=f"ones-api-{name}",
            secret=secret_resp.json().get("value"),
            name=name,
        )

    async def delete_service_account(self, client_uuid: str) -> None:
        headers = await self._admin_headers()
        resp = await self._http.delete(
            f"{settings.keycloak_admin_base}/clients/{client_uuid}",
            headers=headers,
        )
        if resp.status_code not in (200, 204):
            raise KeycloakError(f"Service account deletion failed: {resp.text}")

    # ── Internal helpers ──

    async def _get_ones_client_uuid(self, headers: dict[str, str]) -> str:
        resp = await self._http.get(
            f"{settings.keycloak_admin_base}/clients",
            params={"clientId": settings.keycloak_client_id},
            headers=headers,
        )
        if resp.status_code != 200:
            raise KeycloakError(f"Client lookup failed: {resp.text}")
        clients = resp.json()
        if not clients:
            raise KeycloakError(f"Client '{settings.keycloak_client_id}' not found")
        return clients[0]["id"]

    async def _get_client_role(self, headers: dict[str, str], client_uuid: str, role_name: str) -> dict:
        resp = await self._http.get(
            f"{settings.keycloak_admin_base}/clients/{client_uuid}/roles/{role_name}",
            headers=headers,
        )
        if resp.status_code != 200:
            raise KeycloakError(f"Role '{role_name}' not found: {resp.text}")
        return resp.json()
