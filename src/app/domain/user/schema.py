from datetime import datetime

from pydantic import BaseModel


class UserRead(BaseModel):
    id: str
    email: str
    keycloak_sub: str | None
    status: str
    joined_at: datetime
    approved_at: datetime | None
    approved_by: str | None


class UserListResponse(BaseModel):
    data: list[UserRead]
    total: int


class UserResponse(BaseModel):
    data: UserRead


class MeResponse(BaseModel):
    data: UserRead
