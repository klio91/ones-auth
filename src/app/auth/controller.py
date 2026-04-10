from litestar import Controller, Response, get, post
from litestar.di import Provide
from litestar.params import Parameter
from litestar.response import Redirect
from litestar.status_codes import HTTP_200_OK
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthService
from app.domain.user.schema import UserRead, UserResponse
from app.domain.user.service import UserService
from app.error import InvalidRequestError, InvalidTokenError
from app.keycloak.client import KeycloakClient
from app.settings import settings


class AuthController(Controller):
    path = "/auth"

    @get("/login")
    async def login(self, keycloak: KeycloakClient) -> Redirect:
        auth_service = AuthService(keycloak)
        url = auth_service.get_login_url()
        return Redirect(url)

    @get("/callback")
    async def callback(
        self,
        db_session: AsyncSession,
        keycloak: KeycloakClient,
        code: str = Parameter(query="code", default=""),
    ) -> Response:
        if not code:
            raise InvalidRequestError("Missing authorization code")

        auth_service = AuthService(keycloak)
        tokens = await auth_service.handle_callback(code)

        claims = AuthService.decode_access_token(tokens.access_token)
        user_service = UserService(session=db_session, keycloak=keycloak)
        user, is_new = await user_service.get_or_create(
            email=claims.email,
            keycloak_sub=claims.sub,
        )
        await db_session.commit()

        redirect_path = "/"
        response = Redirect(redirect_path)
        return AuthService.set_token_cookies(response, tokens)

    @post("/refresh")
    async def refresh(
        self,
        keycloak: KeycloakClient,
        request_cookies: dict[str, str] = Parameter(cookie=settings.cookie_refresh_name, default=""),
    ) -> Response:
        refresh_token = request_cookies if isinstance(request_cookies, str) else ""
        if not refresh_token:
            raise InvalidTokenError("Missing refresh token")

        auth_service = AuthService(keycloak)
        tokens = await auth_service.handle_refresh(refresh_token)

        response = Response(content={"data": {"message": "Token refreshed"}}, status_code=HTTP_200_OK)
        return AuthService.set_token_cookies(response, tokens)

    @post("/logout")
    async def logout(
        self,
        keycloak: KeycloakClient,
        request_cookies: dict[str, str] = Parameter(cookie=settings.cookie_refresh_name, default=""),
    ) -> Response:
        refresh_token = request_cookies if isinstance(request_cookies, str) else ""
        auth_service = AuthService(keycloak)

        if refresh_token:
            await auth_service.handle_logout(refresh_token)

        response = Response(content={"data": {"message": "Logged out"}}, status_code=HTTP_200_OK)
        return AuthService.clear_token_cookies(response)

    @get("/me")
    async def me(
        self,
        db_session: AsyncSession,
        keycloak: KeycloakClient,
        x_user_id: str = Parameter(header="X-User-ID", default=""),
        x_user_email: str = Parameter(header="X-User-Email", default=""),
    ) -> UserResponse:
        if not x_user_email:
            raise InvalidRequestError("Missing X-User-Email header")

        user_service = UserService(session=db_session, keycloak=keycloak)
        user = await user_service.get_by_email(x_user_email)
        return UserResponse(data=UserRead.model_validate(user, from_attributes=True))
