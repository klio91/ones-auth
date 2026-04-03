from litestar.contrib.sqlalchemy.repository import SQLAlchemyAsyncRepository

from app.domain.api_client.model import ApiClient


class ApiClientRepository(SQLAlchemyAsyncRepository[ApiClient]):
    model_type = ApiClient
