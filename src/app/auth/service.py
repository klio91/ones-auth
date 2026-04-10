from __future__ import annotations

from jose import JWTError, jwt
from litestar.response import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schema import TokenClaims
from app.error import InvalidTokenError
from app.keycloak.client import KeycloakClient
from app.keycloak.schema import TokenResponse
from app.settings import settings


class AuthService:
    def __init__(self, keycloak: KeycloakClient, session: AsyncSession | None = None) -> None:
        self._keycloak = keycloak
        self._session = session

    @classmethod
    def with_db(cls, keycloak: KeycloakClient, session: AsyncSession) -> AuthService:
        return cls(keycloak=keycloak, session=session)

    def get_login_url(self, state: str) -> str:
        return self._keycloak.get_authorization_url(state=state)

    async def handle_refresh(self, refresh_token: str) -> TokenResponse:
        return await self._keycloak.refresh_token(refresh_token)

    async def handle_logout(self, refresh_token: str) -> None:
        await self._keycloak.logout(refresh_token)

    def decode_access_token(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
        except JWTError as e:
            raise InvalidTokenError(f"Failed to decode token: {e}")

        roles: list[str] = []
        resource_access = payload.get("resource_access", {})
        client_access = resource_access.get(settings.keycloak_client_id, {})
        roles = client_access.get("roles", [])

        return TokenClaims(
            sub=payload.get("sub", ""),
            email=payload.get("email", ""),
            preferred_username=payload.get("preferred_username"),
            roles=roles,
        )

    def set_token_cookies(self, response: Response, tokens: TokenResponse) -> Response:
        response.set_cookie(
            key=settings.cookie_access_name,
            value=tokens.access_token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            domain=settings.cookie_domain,
            path="/",
        )
        if tokens.refresh_token:
            response.set_cookie(
                key=settings.cookie_refresh_name,
                value=tokens.refresh_token,
                httponly=True,
                secure=settings.cookie_secure,
                samesite=settings.cookie_samesite,
                domain=settings.cookie_domain,
                path="/auth",
            )
        return response

    def clear_token_cookies(self, response: Response) -> Response:
        response.delete_cookie(key=settings.cookie_access_name, path="/")
        response.delete_cookie(key=settings.cookie_refresh_name, path="/auth")
        return response
