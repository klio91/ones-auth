from litestar.contrib.sqlalchemy.repository import SQLAlchemyAsyncRepository

from app.domain.user.model import User


class UserRepository(SQLAlchemyAsyncRepository[User]):
    model_type = User
