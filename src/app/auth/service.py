from __future__ import annotations

from jose import JWTError, jwt
from litestar.response import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schema import TokenClaims
from app.domain.user.model import User
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

    def get_login_url(self, state: str, code_challenge: str) -> str:
        return self._keycloak.get_authorization_url(state=state, code_challenge=code_challenge)

    async def handle_refresh(self, refresh_token: str) -> TokenResponse:
        return await self._keycloak.refresh_token(refresh_token)

    async def handle_logout(self, refresh_token: str) -> None:
        await self._keycloak.logout(refresh_token)

    def decode_access_token(self, token: str) -> TokenClaims:
        from loguru import logger

        try:
            payload = jwt.decode(
                token,
                key="",
                options={"verify_signature": False, "verify_aud": False},
            )
        except JWTError:
            raise InvalidTokenError("Invalid token")

        expected_iss = settings.keycloak_base
        if payload.get("iss") != expected_iss:
            logger.debug("JWT issuer mismatch: got={}, expected={}", payload.get("iss"), expected_iss)
            raise InvalidTokenError("Invalid token")

        logger.debug("JWT claims decoded: sub={}, preferred_username={}", payload.get("sub", ""), payload.get("preferred_username", ""))

        resource_access = payload.get("resource_access", {})
        client_access = resource_access.get(settings.keycloak_client_id, {})
        roles: list[str] = client_access.get("roles", [])

        return TokenClaims(
            sub=payload.get("sub", ""),
            email=payload.get("email", ""),
            preferred_username=payload.get("preferred_username"),
            roles=roles,
        )

    async def exchange_and_upsert(self, code: str, code_verifier: str) -> tuple[TokenResponse, User, bool]:
        """code + code_verifier → token 교환 + 사용자 upsert. with_db()로 생성된 인스턴스 필요."""
        from loguru import logger
        from app.domain.user.service import UserService

        assert self._session is not None, "exchange_and_upsert requires session — use AuthService.with_db()"

        tokens = await self._keycloak.exchange_code(code, code_verifier)
        claims = self.decode_access_token(tokens.access_token)
        login_id = claims.email.split("@")[0]
        logger.debug("callback claims: sub={}, login_id={}", claims.sub, login_id)

        user_service = UserService(session=self._session, keycloak=self._keycloak)
        user, is_new = await user_service.get_or_create(
            login_id=login_id,
            name=claims.preferred_username,
            keycloak_sub=claims.sub,
        )
        return tokens, user, is_new

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
