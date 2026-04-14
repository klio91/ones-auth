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


class TestGetById:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self) -> None:
        user = _make_user()
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=user)

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            result = await service.get_by_id("user-id-1")

        assert result is user

    @pytest.mark.asyncio
    async def test_raises_not_found(self) -> None:
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=None)

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            with pytest.raises(UserNotFoundError):
                await service.get_by_id("nonexistent")


class TestGetByEmail:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self) -> None:
        user = _make_user()
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=user)

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            result = await service.get_by_email("test@example.com")

        assert result is user

    @pytest.mark.asyncio
    async def test_raises_not_found(self) -> None:
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=None)

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            with pytest.raises(UserNotFoundError):
                await service.get_by_email("no@example.com")


class TestListUsers:
    @pytest.mark.asyncio
    async def test_list_all(self) -> None:
        users = [_make_user(), _make_user(user_id="user-id-2", email="b@example.com")]
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.list_and_count = AsyncMock(return_value=(users, 2))

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            result, total = await service.list_users()

        assert len(result) == 2
        assert total == 2
        repo.list_and_count.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self) -> None:
        users = [_make_user(status="active")]
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.list_and_count = AsyncMock(return_value=(users, 1))

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            result, total = await service.list_users(status="active")

        assert total == 1
        repo.list_and_count.assert_awaited_once_with(status="active")


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

    @pytest.mark.asyncio
    async def test_deactivate_skips_keycloak_when_no_sub(self) -> None:
        user = _make_user(status="active", keycloak_sub=None)  # type: ignore[arg-type]
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=user)
        repo.update = AsyncMock(side_effect=lambda u: u)

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            result = await service.deactivate("user-id-1")

        assert result.status == "inactive"
        keycloak.remove_role.assert_not_called()

    @pytest.mark.asyncio
    async def test_deactivate_nonexistent_raises_not_found(self) -> None:
        session = MagicMock()
        keycloak = AsyncMock()

        repo = AsyncMock()
        repo.get_one_or_none = AsyncMock(return_value=None)

        with patch("app.domain.user.service.UserRepository", return_value=repo):
            service = UserService(session=session, keycloak=keycloak)
            with pytest.raises(UserNotFoundError):
                await service.deactivate("nonexistent")
