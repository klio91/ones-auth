"""AuthService 단위 테스트."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import JWTError

from app.auth.service import AuthService
from app.error import InvalidTokenError


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
