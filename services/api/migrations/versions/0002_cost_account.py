"""Preserve cost attribution after session deletion."""

import sqlalchemy as sa
from alembic import op

revision = "0002_cost"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("llm_calls") as table:
        table.add_column(sa.Column("user_id", sa.Uuid(), nullable=True))
        table.create_foreign_key(
            "fk_llm_calls_user_id", "users", ["user_id"], ["id"], ondelete="SET NULL"
        )
        table.create_index("ix_llm_calls_user_id", ["user_id"])
    op.execute(
        "UPDATE llm_calls SET user_id = (SELECT user_id FROM sessions WHERE sessions.id = llm_calls.session_id)"
    )


def downgrade() -> None:
    with op.batch_alter_table("llm_calls") as table:
        table.drop_index("ix_llm_calls_user_id")
        table.drop_constraint("fk_llm_calls_user_id", type_="foreignkey")
        table.drop_column("user_id")
