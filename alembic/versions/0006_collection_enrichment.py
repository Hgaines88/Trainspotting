"""Add reviewed collection enrichment descriptors."""

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    # Adding a check constraint would require rebuilding the SQLite submissions
    # table, which is referenced by the append-only moderation ledger. The API
    # owns this two-value validation; descriptor fields remain DB-constrained.
    op.add_column(
        "submissions",
        sa.Column(
            "proposal_kind",
            sa.String(32),
            nullable=False,
            server_default="archive_record",
        ),
    )
    op.create_table(
        "collection_descriptors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "collection_id",
            sa.Integer(),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("canonical_value", sa.String(64), nullable=False),
        sa.Column("strength", sa.String(16), nullable=False),
        sa.Column("evidence_note", sa.Text(), nullable=False),
        sa.Column(
            "source_submission_id",
            sa.Integer(),
            sa.ForeignKey("submissions.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint(
            "category IN ('theme', 'motif', 'material', 'texture', 'color', 'silhouette')",
            name="ck_collection_descriptors_valid_category",
        ),
        sa.CheckConstraint(
            "strength IN ('dominant', 'supporting')",
            name="ck_collection_descriptors_valid_strength",
        ),
        sa.CheckConstraint(
            "length(trim(canonical_value)) > 0",
            name="ck_collection_descriptors_canonical_value_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(evidence_note)) > 0",
            name="ck_collection_descriptors_evidence_note_not_blank",
        ),
        sa.UniqueConstraint(
            "collection_id",
            "category",
            "canonical_value",
            name="uq_collection_descriptor",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "idx_collection_descriptors_collection",
        "collection_descriptors",
        ["collection_id"],
    )
    op.create_index(
        "idx_collection_descriptors_lookup",
        "collection_descriptors",
        ["category", "canonical_value"],
    )


def downgrade():
    op.drop_table("collection_descriptors")
    op.drop_column("submissions", "proposal_kind")
