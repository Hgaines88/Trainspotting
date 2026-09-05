"""Add durable curated-ingestion batch and row ledgers."""

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ingestion_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submitter_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("input_format", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), server_default="running", nullable=False),
        sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("valid_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("invalid_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicate_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("review_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.CheckConstraint("length(trim(source_name)) > 0", name="source_name_not_blank"),
        sa.CheckConstraint("input_format IN ('csv')", name="valid_input_format"),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="valid_status"),
        sa.CheckConstraint("total_rows >= 0 AND valid_rows >= 0 AND invalid_rows >= 0 AND duplicate_rows >= 0 AND review_rows >= 0", name="counts_nonnegative"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_ingestion_batches_created", "ingestion_batches", ["created_at"])
    op.create_table(
        "ingestion_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("ingestion_batches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("normalized_payload", sa.Text()),
        sa.Column("fingerprint", sa.String(64)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("validation_errors", sa.Text()),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint("source_row_number > 0", name="source_row_number_positive"),
        sa.CheckConstraint("json_valid(raw_payload)", name="raw_payload_json"),
        sa.CheckConstraint("normalized_payload IS NULL OR json_valid(normalized_payload)", name="normalized_payload_json"),
        sa.CheckConstraint("validation_errors IS NULL OR json_valid(validation_errors)", name="validation_errors_json"),
        sa.CheckConstraint("fingerprint IS NULL OR length(fingerprint) = 64", name="fingerprint_length"),
        sa.CheckConstraint("status IN ('valid', 'invalid', 'duplicate', 'requiring_review')", name="valid_status"),
        sa.UniqueConstraint("batch_id", "source_row_number", name="uq_ingestion_row_number"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_ingestion_rows_batch", "ingestion_rows", ["batch_id"])
    op.create_index("idx_ingestion_rows_fingerprint", "ingestion_rows", ["fingerprint"])
    op.create_index("idx_ingestion_rows_status", "ingestion_rows", ["status"])


def downgrade():
    op.drop_table("ingestion_rows")
    op.drop_table("ingestion_batches")
