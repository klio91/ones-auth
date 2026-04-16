"""rename email to login_id, add name column

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-16

"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "email", new_column_name="login_id", schema="auth")
    op.add_column("users", sa.Column("name", sa.String(), nullable=True), schema="auth")


def downgrade() -> None:
    op.drop_column("users", "name", schema="auth")
    op.alter_column("users", "login_id", new_column_name="email", schema="auth")
