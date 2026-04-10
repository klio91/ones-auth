import secrets

from litestar import Controller, Response, get, post
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
        state = secrets.token_urlsafe(32)
        auth_service = AuthService(keycloak)
        url = auth_service.get_login_url(state=state)
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

        auth_service = AuthService.with_db(keycloak, db_session)
        tokens, user, is_new = await auth_service.exchange_and_upsert(code)
        await db_session.commit()

        response: Response = Redirect("/")
        return auth_service.set_token_cookies(response, tokens)

    @post("/refresh")
    async def refresh(
        self,
        keycloak: KeycloakClient,
        request_cookies: str = Parameter(cookie=settings.cookie_refresh_name, default=""),
    ) -> Response:
        if not request_cookies:
            raise InvalidTokenError("Missing refresh token")

        auth_service = AuthService(keycloak)
        tokens = await auth_service.handle_refresh(request_cookies)

        response = Response(content={"data": {"message": "Token refreshed"}}, status_code=HTTP_200_OK)
        return auth_service.set_token_cookies(response, tokens)

    @post("/logout")
    async def logout(
        self,
        keycloak: KeycloakClient,
        request_cookies: str = Parameter(cookie=settings.cookie_refresh_name, default=""),
    ) -> Response:
        auth_service = AuthService(keycloak)
        if request_cookies:
            await auth_service.handle_logout(request_cookies)

        response = Response(content={"data": {"message": "Logged out"}}, status_code=HTTP_200_OK)
        return auth_service.clear_token_cookies(response)

    @get("/me")
    async def me(
        self,
        db_session: AsyncSession,
        keycloak: KeycloakClient,
        x_user_email: str = Parameter(header="X-User-Email", default=""),
    ) -> UserResponse:
        if not x_user_email:
            raise InvalidRequestError("Missing X-User-Email header")

        user_service = UserService(session=db_session, keycloak=keycloak)
        user = await user_service.get_by_email(x_user_email)
        return UserResponse(data=UserRead.model_validate(user, from_attributes=True))
