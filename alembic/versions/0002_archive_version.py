"""Add the transactional canonical archive version ledger."""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "archive_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint("id = 1", name="ck_archive_state_singleton"),
        sa.CheckConstraint("version > 0", name="ck_archive_state_version_positive"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.execute("INSERT INTO archive_state (id, version) VALUES (1, 1)")


def downgrade():
    op.drop_table("archive_state")
