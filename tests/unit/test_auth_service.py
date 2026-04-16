"""AuthService 단위 테스트."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import JWTError

from app.auth.service import AuthService
from app.error import InvalidTokenError
from app.keycloak.schema import TokenResponse


def _make_payload(
    sub: str = "user-sub-123",
    email: str = "user@example.com",
    iss: str = "http://localhost:8080/realms/ones",
) -> dict:
    return {
        "sub": sub,
        "email": email,
        "preferred_username": "user",
        "iss": iss,
        "resource_access": {"ones": {"roles": ["ones-user"]}},
    }


def _make_token_response() -> TokenResponse:
    return TokenResponse(
        access_token="access-tok",
        refresh_token="refresh-tok",
        expires_in=300,
        token_type="Bearer",
    )


class TestDecodeAccessToken:
    def test_valid_token_returns_claims(self) -> None:
        service = AuthService(keycloak=MagicMock())
        payload = _make_payload()

        with patch("app.auth.service.jwt.decode", return_value=payload):
            claims = service.decode_access_token("fake.token.value")

        assert claims.sub == "user-sub-123"
        assert claims.email == "user@example.com"
        assert "ones-user" in claims.roles

    def test_wrong_issuer_raises_invalid_token(self) -> None:
        service = AuthService(keycloak=MagicMock())
        payload = _make_payload(iss="http://evil.com/realms/ones")

        with patch("app.auth.service.jwt.decode", return_value=payload):
            with pytest.raises(InvalidTokenError):
                service.decode_access_token("fake.token.value")

    def test_jwt_error_raises_invalid_token(self) -> None:
        service = AuthService(keycloak=MagicMock())

        with patch("app.auth.service.jwt.decode", side_effect=JWTError("bad token")):
            with pytest.raises(InvalidTokenError):
                service.decode_access_token("bad.token.value")

    def test_missing_resource_access_returns_empty_roles(self) -> None:
        service = AuthService(keycloak=MagicMock())
        payload = _make_payload()
        payload.pop("resource_access")

        with patch("app.auth.service.jwt.decode", return_value=payload):
            claims = service.decode_access_token("fake.token.value")

        assert claims.roles == []


class TestWithDb:
    def test_with_db_creates_instance_with_session(self) -> None:
        keycloak = MagicMock()
        session = MagicMock()
        service = AuthService.with_db(keycloak, session)

        assert service._keycloak is keycloak
        assert service._session is session

    def test_without_db_session_is_none(self) -> None:
        service = AuthService(keycloak=MagicMock())
        assert service._session is None


class TestGetLoginUrl:
    def test_delegates_to_keycloak(self) -> None:
        keycloak = MagicMock()
        keycloak.get_authorization_url.return_value = "https://keycloak/auth?client_id=ones"
        service = AuthService(keycloak=keycloak)

        url = service.get_login_url(state="abc", code_challenge="xyz")

        assert url == "https://keycloak/auth?client_id=ones"
        keycloak.get_authorization_url.assert_called_once_with(state="abc", code_challenge="xyz")


class TestHandleRefresh:
    @pytest.mark.asyncio
    async def test_delegates_to_keycloak(self) -> None:
        tokens = _make_token_response()
        keycloak = AsyncMock()
        keycloak.refresh_token.return_value = tokens
        service = AuthService(keycloak=keycloak)

        result = await service.handle_refresh("old-refresh-tok")

        assert result is tokens
        keycloak.refresh_token.assert_awaited_once_with("old-refresh-tok")


class TestHandleLogout:
    @pytest.mark.asyncio
    async def test_delegates_to_keycloak(self) -> None:
        keycloak = AsyncMock()
        service = AuthService(keycloak=keycloak)

        await service.handle_logout("refresh-tok")

        keycloak.logout.assert_awaited_once_with("refresh-tok")


class TestExchangeAndUpsert:
    @pytest.mark.asyncio
    async def test_exchanges_code_and_creates_user(self) -> None:
        tokens = _make_token_response()
        keycloak = AsyncMock()
        keycloak.exchange_code.return_value = tokens

        session = MagicMock()
        service = AuthService.with_db(keycloak, session)

        payload = _make_payload()
        mock_user = MagicMock()

        with (
            patch.object(service, "decode_access_token") as mock_decode,
            patch("app.domain.user.service.UserService") as MockUserService,
        ):
            mock_decode.return_value = MagicMock(sub="user-sub-123", email="user@example.com", preferred_username="User Name")
            mock_user_service = AsyncMock()
            mock_user_service.get_or_create.return_value = (mock_user, True)
            MockUserService.return_value = mock_user_service

            result_tokens, user, is_new = await service.exchange_and_upsert("auth-code", "verifier")

        assert result_tokens is tokens
        assert user is mock_user
        assert is_new is True
        keycloak.exchange_code.assert_awaited_once_with("auth-code", "verifier")

    @pytest.mark.asyncio
    async def test_raises_without_session(self) -> None:
        service = AuthService(keycloak=AsyncMock())

        with pytest.raises(AssertionError, match="requires session"):
            await service.exchange_and_upsert("code", "verifier")


class TestSetTokenCookies:
    def test_sets_access_and_refresh_cookies(self) -> None:
        service = AuthService(keycloak=MagicMock())
        tokens = _make_token_response()
        response = MagicMock()

        service.set_token_cookies(response, tokens)

        assert response.set_cookie.call_count == 2
        calls = response.set_cookie.call_args_list
        assert calls[0].kwargs["key"] == "ones_access"
        assert calls[0].kwargs["value"] == "access-tok"
        assert calls[0].kwargs["httponly"] is True
        assert calls[1].kwargs["key"] == "ones_refresh"
        assert calls[1].kwargs["value"] == "refresh-tok"

    def test_skips_refresh_cookie_when_none(self) -> None:
        service = AuthService(keycloak=MagicMock())
        tokens = TokenResponse(access_token="access-tok", refresh_token=None, expires_in=300, token_type="Bearer")
        response = MagicMock()

        service.set_token_cookies(response, tokens)

        assert response.set_cookie.call_count == 1
        assert response.set_cookie.call_args.kwargs["key"] == "ones_access"


class TestClearTokenCookies:
    def test_deletes_both_cookies(self) -> None:
        service = AuthService(keycloak=MagicMock())
        response = MagicMock()

        service.clear_token_cookies(response)

        assert response.delete_cookie.call_count == 2
        calls = response.delete_cookie.call_args_list
        assert calls[0].kwargs["key"] == "ones_access"
        assert calls[1].kwargs["key"] == "ones_refresh"
