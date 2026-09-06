"""Add sourced designer aliases for normalized discovery."""

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "designer_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "designer_id",
            sa.Integer(),
            sa.ForeignKey("designers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias", sa.String(255), nullable=False),
        sa.Column("normalized_alias", sa.String(255), nullable=False),
        sa.Column("alias_type", sa.String(32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "length(trim(alias)) > 0",
            name="ck_designer_aliases_alias_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(normalized_alias)) > 0",
            name="ck_designer_aliases_normalized_alias_not_blank",
        ),
        sa.CheckConstraint(
            "alias_type IN ('alternate-name', 'former-name', 'legal-name')",
            name="ck_designer_aliases_valid_alias_type",
        ),
        sa.CheckConstraint(
            "length(trim(source_url)) > 0",
            name="ck_designer_aliases_source_url_not_blank",
        ),
        sa.UniqueConstraint(
            "normalized_alias",
            name="uq_designer_aliases_normalized_alias",
        ),
        sa.UniqueConstraint(
            "designer_id",
            "alias",
            name="uq_designer_aliases_designer_alias",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "idx_designer_aliases_designer",
        "designer_aliases",
        ["designer_id"],
    )


def downgrade():
    op.drop_table("designer_aliases")
