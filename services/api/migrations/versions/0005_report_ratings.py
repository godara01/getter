"""Candidate usefulness ratings of feedback reports."""

import sqlalchemy as sa
from alembic import op

revision = "0005_report_ratings"
down_revision = "0004_cost_waitlist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_ratings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "report_id",
            sa.Uuid(),
            sa.ForeignKey("feedback_reports.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("report_ratings")
