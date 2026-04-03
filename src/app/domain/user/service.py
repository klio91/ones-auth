import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.user.model import User
from app.domain.user.repository import UserRepository
from app.error import ForbiddenError, UserAlreadyExistsError, UserNotFoundError
from app.keycloak.client import KeycloakClient


class UserService:
    def __init__(self, session: AsyncSession, keycloak: KeycloakClient) -> None:
        self._repo = UserRepository(session=session)
        self._keycloak = keycloak

    async def get_or_create(self, email: str, keycloak_sub: str) -> tuple[User, bool]:
        """Get existing user or create as waiting. Returns (user, is_new)."""
        existing = await self._repo.get_one_or_none(email=email)
        if existing:
            if existing.keycloak_sub is None:
                existing.keycloak_sub = keycloak_sub
                await self._repo.update(existing)
            return existing, False

        user = User(
            id=str(uuid.uuid4()),
            email=email,
            keycloak_sub=keycloak_sub,
            status="waiting",
        )
        created = await self._repo.add(user)
        await self._keycloak.assign_role(keycloak_sub, "ones-user-waiting")
        return created, True

    async def get_by_id(self, user_id: str) -> User:
        user = await self._repo.get_one_or_none(id=user_id)
        if not user:
            raise UserNotFoundError()
        return user

    async def get_by_email(self, email: str) -> User:
        user = await self._repo.get_one_or_none(email=email)
        if not user:
            raise UserNotFoundError()
        return user

    async def list_users(self, *, status: str | None = None) -> tuple[list[User], int]:
        if status:
            results, total = await self._repo.list_and_count(status=status)
        else:
            results, total = await self._repo.list_and_count()
        return list(results), total

    async def approve(self, user_id: str, approved_by: str) -> User:
        user = await self.get_by_id(user_id)
        if user.status != "waiting":
            raise ForbiddenError(f"Cannot approve user with status '{user.status}'")

        user.status = "active"
        user.approved_at = datetime.now(UTC)
        user.approved_by = approved_by
        updated = await self._repo.update(user)

        if user.keycloak_sub:
            await self._keycloak.remove_role(user.keycloak_sub, "ones-user-waiting")
            await self._keycloak.assign_role(user.keycloak_sub, "ones-user")

        return updated

    async def deactivate(self, user_id: str) -> User:
        user = await self.get_by_id(user_id)
        if user.status == "inactive":
            raise ForbiddenError("User is already inactive")

        user.status = "inactive"
        updated = await self._repo.update(user)

        if user.keycloak_sub:
            await self._keycloak.remove_role(user.keycloak_sub, "ones-user")
            await self._keycloak.remove_role(user.keycloak_sub, "ones-user-waiting")

        return updated
