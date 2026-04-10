"""UserService 단위 테스트."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.user.model import User
from app.domain.user.service import UserService
from app.error import ForbiddenError, UserNotFoundError


def _make_user(
    user_id: str = "user-id-1",
    email: str = "test@example.com",
    keycloak_sub: str = "kc-sub-1",
    status: str = "active",
) -> User:
    return User(id=user_id, email=email, keycloak_sub=keycloak_sub, status=status)


class TestGetOrCreate:
    @pytest.mark.asyncio
    async def test_new_user_created_as_active(self) -> None:
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=None)
        repo.add = AsyncMock(side_effect=lambda u: u)

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            user, is_new = await service.get_or_create(
                email="new@example.com", keycloak_sub="kc-sub-new"
            )

        assert user.status == "active"
        assert is_new is True

    @pytest.mark.asyncio
    async def test_new_user_gets_ones_user_role(self) -> None:
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=None)
        repo.add = AsyncMock(side_effect=lambda u: u)

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            await service.get_or_create(email="new@example.com", keycloak_sub="kc-sub-new")

        keycloak.assign_role.assert_awaited_once_with("kc-sub-new", "ones-user")

    @pytest.mark.asyncio
    async def test_existing_user_returned_as_is(self) -> None:
        existing = _make_user()
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=existing)

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            user, is_new = await service.get_or_create(
                email="test@example.com", keycloak_sub="kc-sub-1"
            )

        assert user is existing
        assert is_new is False
        keycloak.assign_role.assert_not_called()

    @pytest.mark.asyncio
    async def test_existing_user_without_sub_gets_sub_updated(self) -> None:
        existing = _make_user(keycloak_sub=None)  # type: ignore[arg-type]
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=existing)
        repo.update = AsyncMock(side_effect=lambda u: u)

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            user, is_new = await service.get_or_create(
                email="test@example.com", keycloak_sub="kc-sub-new"
            )

        assert user.keycloak_sub == "kc-sub-new"
        repo.update.assert_awaited_once()


class TestDeactivate:
    @pytest.mark.asyncio
    async def test_active_user_deactivated(self) -> None:
        user = _make_user(status="active")
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=user)
        repo.update = AsyncMock(side_effect=lambda u: u)

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            result = await service.deactivate("user-id-1")

        assert result.status == "inactive"
        keycloak.remove_role.assert_awaited_once_with("kc-sub-1", "ones-user")

    @pytest.mark.asyncio
    async def test_already_inactive_raises_forbidden(self) -> None:
        user = _make_user(status="inactive")
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=user)

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            with pytest.raises(ForbiddenError):
                await service.deactivate("user-id-1")
