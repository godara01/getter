"""Waitlist and persistent per-IP request limits."""

import sqlalchemy as sa
from alembic import op

revision = "0002_waitlist"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "waitlist",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("role_interest", sa.String(32), nullable=False),
    )
    op.create_table(
        "waitlist_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_waitlist_attempts_ip_hash", "waitlist_attempts", ["ip_hash"])


def downgrade() -> None:
    op.drop_table("waitlist_attempts")
    op.drop_table("waitlist")
