from pydantic import BaseModel


class LoginRedirect(BaseModel):
    redirect_url: str


class TokenClaims(BaseModel):
    sub: str
    email: str
    preferred_username: str | None = None
    roles: list[str] = []
