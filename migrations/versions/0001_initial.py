"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-10

"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("keycloak_sub", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'waiting'")),
        sa.Column(
            "joined_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("keycloak_sub", name=op.f("uq_users_keycloak_sub")),
        schema="auth",
    )
    op.create_table(
        "api_clients",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("keycloak_client_id", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deactivated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["auth.users.id"],
            name=op.f("fk_api_clients_created_by_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_clients")),
        sa.UniqueConstraint("keycloak_client_id", name=op.f("uq_api_clients_keycloak_client_id")),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_table("api_clients", schema="auth")
    op.drop_table("users", schema="auth")
