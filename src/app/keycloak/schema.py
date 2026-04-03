from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int
    token_type: str


class KeycloakUser(BaseModel):
    id: str
    email: str | None = None
    username: str | None = None


class ClientRepresentation(BaseModel):
    id: str | None = None
    client_id: str | None = None
    secret: str | None = None
    name: str | None = None
    service_accounts_enabled: bool = True
    client_authenticator_type: str = "client-secret"
    protocol: str = "openid-connect"
