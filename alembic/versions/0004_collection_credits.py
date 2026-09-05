"""Add ordered collection credits and backfill existing lead designers."""

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "collection_credits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "collection_id",
            sa.Integer(),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "designer_id",
            sa.Integer(),
            sa.ForeignKey(
                "designers.id", onupdate="CASCADE", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("credit_role", sa.String(32), nullable=False),
        sa.Column("credit_order", sa.Integer(), nullable=False),
        sa.Column("attribution_note", sa.Text()),
        sa.CheckConstraint(
            "credit_role IN ('lead', 'co-designer', 'guest', "
            "'collaborator', 'attribution-note')",
            name="ck_collection_credits_valid_role",
        ),
        sa.CheckConstraint(
            "credit_order > 0", name="ck_collection_credits_order_positive"
        ),
        sa.CheckConstraint(
            "attribution_note IS NULL OR length(trim(attribution_note)) > 0",
            name="ck_collection_credits_attribution_note_not_blank",
        ),
        sa.UniqueConstraint(
            "collection_id",
            "designer_id",
            name="uq_collection_credit_designer",
        ),
        sa.UniqueConstraint(
            "collection_id",
            "credit_order",
            name="uq_collection_credit_order",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "idx_collection_credits_collection",
        "collection_credits",
        ["collection_id"],
    )
    op.create_index(
        "idx_collection_credits_designer",
        "collection_credits",
        ["designer_id"],
    )
    op.execute(
        sa.text(
            "INSERT INTO collection_credits "
            "(collection_id, designer_id, credit_role, credit_order) "
            "SELECT id, designer_id, 'lead', 1 FROM collections"
        )
    )


def downgrade():
    op.drop_table("collection_credits")
