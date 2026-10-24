"""Join cost attribution and waitlist migration histories."""

revision = "0004_cost_waitlist"
down_revision = ("0003_clerk_cost", "0003_clerk_waitlist")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
