from dataclasses import dataclass

from litestar import Response
from litestar.connection import Request
from litestar.status_codes import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_502_BAD_GATEWAY,
)


@dataclass
class AppError(Exception):
    code: str
    message: str
    status_code: int = HTTP_400_BAD_REQUEST


class InvalidRequestError(AppError):
    def __init__(self, message: str = "Invalid request") -> None:
        super().__init__(code="INVALID_REQUEST", message=message, status_code=HTTP_400_BAD_REQUEST)


class TokenExpiredError(AppError):
    def __init__(self, message: str = "Token expired") -> None:
        super().__init__(code="TOKEN_EXPIRED", message=message, status_code=HTTP_401_UNAUTHORIZED)


class InvalidTokenError(AppError):
    def __init__(self, message: str = "Invalid token") -> None:
        super().__init__(code="INVALID_TOKEN", message=message, status_code=HTTP_401_UNAUTHORIZED)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(code="FORBIDDEN", message=message, status_code=HTTP_403_FORBIDDEN)


class UserNotFoundError(AppError):
    def __init__(self, message: str = "User not found") -> None:
        super().__init__(code="USER_NOT_FOUND", message=message, status_code=HTTP_404_NOT_FOUND)


class UserAlreadyExistsError(AppError):
    def __init__(self, message: str = "User already exists") -> None:
        super().__init__(code="USER_ALREADY_EXISTS", message=message, status_code=HTTP_409_CONFLICT)


class KeycloakError(AppError):
    def __init__(self, message: str = "Keycloak API error") -> None:
        super().__init__(code="KEYCLOAK_ERROR", message=message, status_code=HTTP_502_BAD_GATEWAY)


def app_error_handler(_: Request, exc: AppError) -> Response:
    return Response(
        content={"error": {"code": exc.code, "message": exc.message}},
        status_code=exc.status_code,
    )
