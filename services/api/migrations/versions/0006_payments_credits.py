"""Razorpay payments and the interview credit ledger."""

import sqlalchemy as sa
from alembic import op

revision = "0006_payments_credits"
down_revision = "0005_report_ratings"
branch_labels = None
depends_on = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "payments",
        *_base(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pack_id", sa.String(64), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("razorpay_order_id", sa.String(64), nullable=False, unique=True),
        sa.Column("razorpay_payment_id", sa.String(64), nullable=True, unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_table(
        "credit_entries",
        *_base(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column(
            "payment_id", sa.Uuid(), sa.ForeignKey("payments.id"), nullable=True, unique=True
        ),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_credit_entries_user_id", "credit_entries", ["user_id"])


def downgrade() -> None:
    op.drop_table("credit_entries")
    op.drop_table("payments")
