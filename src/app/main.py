from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from litestar import Litestar, get
from litestar.di import Provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.controller import AuthController
from app.db import async_session, engine
from app.domain.api_client.controller import ApiClientController
from app.domain.user.controller import UserController
from app.error import AppError, app_error_handler
from app.keycloak.client import KeycloakClient
from app.logging import setup_logging
from app.settings import settings

setup_logging()

_keycloak_client = KeycloakClient()


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncGenerator[None]:
    yield
    await _keycloak_client.close()
    await engine.dispose()


async def provide_db_session() -> AsyncGenerator[AsyncSession]:
    async with async_session() as session:
        yield session


async def provide_keycloak() -> KeycloakClient:
    return _keycloak_client


@get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app = Litestar(
    route_handlers=[
        health,
        AuthController,
        UserController,
        ApiClientController,
    ],
    dependencies={
        "db_session": Provide(provide_db_session),
        "keycloak": Provide(provide_keycloak),
    },
    exception_handlers={AppError: app_error_handler},
    lifespan=[lifespan],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
