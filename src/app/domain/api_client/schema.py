from datetime import datetime

from pydantic import BaseModel


class ApiClientCreate(BaseModel):
    name: str


class ApiClientRead(BaseModel):
    id: str
    name: str
    keycloak_client_id: str
    created_by: str
    is_active: bool
    created_at: datetime
    deactivated_at: datetime | None


class ApiClientCreatedResponse(BaseModel):
    data: ApiClientRead
    client_id: str
    client_secret: str


class ApiClientResponse(BaseModel):
    data: ApiClientRead


class ApiClientListResponse(BaseModel):
    data: list[ApiClientRead]
    total: int
