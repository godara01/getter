"""Clerk identity, separate from development email accounts."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as table:
        table.add_column(sa.Column("clerk_user_id", sa.String(200), nullable=True))
        table.create_unique_constraint("uq_users_clerk_user_id", ["clerk_user_id"])


def downgrade() -> None:
    with op.batch_alter_table("users") as table:
        table.drop_constraint("uq_users_clerk_user_id", type_="unique")
        table.drop_column("clerk_user_id")
