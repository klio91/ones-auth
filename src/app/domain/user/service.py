import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.user.model import User
from app.domain.user.repository import UserRepository
from app.error import ForbiddenError, UserNotFoundError
from app.keycloak.client import KeycloakClient


class UserService:
    def __init__(self, session: AsyncSession, keycloak: KeycloakClient) -> None:
        self._repo = UserRepository(session=session)
        self._keycloak = keycloak

    async def get_or_create(self, login_id: str, name: str | None, keycloak_sub: str) -> tuple[User, bool]:
        """Get existing user or create as active. Returns (user, is_new)."""
        existing = await self._repo.get_one_or_none(login_id=login_id)
        if existing:
            if existing.keycloak_sub is None:
                existing.keycloak_sub = keycloak_sub
                await self._repo.update(existing)
            return existing, False

        user = User(
            id=str(uuid.uuid4()),
            login_id=login_id,
            name=name,
            keycloak_sub=keycloak_sub,
            status="active",
        )
        created = await self._repo.add(user)
        await self._keycloak.assign_role(keycloak_sub, "ones-user")
        return created, True

    async def get_by_id(self, user_id: str) -> User:
        user = await self._repo.get_one_or_none(id=user_id)
        if not user:
            raise UserNotFoundError()
        return user

    async def get_by_login_id(self, login_id: str) -> User:
        user = await self._repo.get_one_or_none(login_id=login_id)
        if not user:
            raise UserNotFoundError()
        return user

    async def list_users(self, *, status: str | None = None) -> tuple[list[User], int]:
        if status:
            results, total = await self._repo.list_and_count(status=status)
        else:
            results, total = await self._repo.list_and_count()
        return list(results), total

    async def deactivate(self, user_id: str) -> User:
        user = await self.get_by_id(user_id)
        if user.status == "inactive":
            raise ForbiddenError("User is already inactive")

        user.status = "inactive"
        updated = await self._repo.update(user)

        if user.keycloak_sub:
            await self._keycloak.remove_role(user.keycloak_sub, "ones-user")

        return updated
