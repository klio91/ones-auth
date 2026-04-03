from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "ONES_AUTH_"}

    # Database
    db_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ones"
    db_schema: str = "auth"
    db_echo: bool = False

    # Keycloak OIDC
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "ones"
    keycloak_client_id: str = "ones"
    keycloak_client_secret: str = "dummy-client-secret"
    keycloak_redirect_uri: str = "http://localhost:8000/auth/callback"

    # Keycloak Admin API
    keycloak_admin_client_id: str = "ones-auth-admin"
    keycloak_admin_client_secret: str = "dummy-admin-secret"

    # Cookie
    cookie_domain: str | None = None
    cookie_secure: bool = False
    cookie_samesite: str = "Lax"
    cookie_access_name: str = "ones_access"
    cookie_refresh_name: str = "ones_refresh"

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    @property
    def keycloak_base(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}"

    @property
    def keycloak_admin_base(self) -> str:
        return f"{self.keycloak_url}/admin/realms/{self.keycloak_realm}"

    @property
    def oidc_auth_url(self) -> str:
        return f"{self.keycloak_base}/protocol/openid-connect/auth"

    @property
    def oidc_token_url(self) -> str:
        return f"{self.keycloak_base}/protocol/openid-connect/token"

    @property
    def oidc_logout_url(self) -> str:
        return f"{self.keycloak_base}/protocol/openid-connect/logout"

    @property
    def oidc_certs_url(self) -> str:
        return f"{self.keycloak_base}/protocol/openid-connect/certs"


settings = Settings()
