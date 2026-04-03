from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ApiClient(Base):
    __tablename__ = "api_clients"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    keycloak_client_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    deactivated_at: Mapped[datetime | None] = mapped_column()
