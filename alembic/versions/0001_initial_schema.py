"""Create the portable Trainspotting schema."""

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def timestamps():
    return (
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
    )


def upgrade():
    op.create_table(
        "designers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("nationality", sa.String(255)), sa.Column("birth_year", sa.Integer()),
        sa.Column("website", sa.Text()), sa.Column("biography", sa.Text()),
        sa.CheckConstraint("length(trim(full_name)) > 0", name="ck_designers_full_name_not_blank"),
        sa.CheckConstraint("birth_year IS NULL OR birth_year BETWEEN 1800 AND 2100", name="ck_designers_birth_year_range"),
        sa.UniqueConstraint("full_name", name="uq_designers_full_name"), mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("designer_id", sa.Integer(), sa.ForeignKey("designers.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(255), nullable=False), sa.Column("name", sa.String(255)),
        sa.Column("season", sa.String(100), nullable=False), sa.Column("release_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("piece_count", sa.Integer()), sa.Column("description", sa.Text()),
        sa.CheckConstraint("length(trim(label)) > 0", name="ck_collections_label_not_blank"),
        sa.CheckConstraint("name IS NULL OR length(trim(name)) > 0", name="ck_collections_name_not_blank"),
        sa.CheckConstraint("length(trim(season)) > 0", name="ck_collections_season_not_blank"),
        sa.CheckConstraint("release_year BETWEEN 1900 AND 2100", name="ck_collections_release_year_range"),
        sa.CheckConstraint("status IN ('concept', 'in-production', 'released', 'archived')", name="ck_collections_valid_status"),
        sa.CheckConstraint("piece_count IS NULL OR piece_count >= 0", name="ck_collections_piece_count_nonnegative"),
        sa.UniqueConstraint("designer_id", "label", "season", "release_year", name="uq_collection"), mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_collections_designer_id", "collections", ["designer_id"])
    op.create_table(
        "collection_media",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("collection_id", sa.Integer(), sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_type", sa.String(32), nullable=False), sa.Column("media_value", sa.Text(), nullable=False),
        sa.CheckConstraint("media_type IN ('source', 'youtube')", name="ck_collection_media_valid_media_type"),
        sa.CheckConstraint("length(trim(media_value)) > 0", name="ck_collection_media_media_value_not_blank"),
        sa.UniqueConstraint("collection_id", "media_type", name="uq_collection_media"), mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_collection_media_collection_id", "collection_media", ["collection_id"])
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("clerk_user_id", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320)), sa.Column("display_name", sa.String(255)),
        sa.Column("role", sa.String(32), server_default="member", nullable=False), *timestamps(),
        sa.CheckConstraint("length(trim(clerk_user_id)) > 0", name="ck_users_clerk_id_not_blank"),
        sa.CheckConstraint("role IN ('member', 'moderator', 'admin')", name="ck_users_valid_role"),
        sa.UniqueConstraint("clerk_user_id", name="uq_users_clerk_user_id"), mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_users_role", "users", ["role"])
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submitter_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("record_type", sa.String(32), nullable=False), sa.Column("submission_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.Integer()), sa.Column("status", sa.String(32), server_default="draft", nullable=False),
        sa.Column("proposed_data", sa.Text(), nullable=False), sa.Column("explanation", sa.Text()),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False), *timestamps(),
        sa.Column("submitted_at", sa.DateTime()), sa.Column("reviewed_at", sa.DateTime()),
        sa.CheckConstraint("record_type IN ('designer', 'collection')", name="ck_submissions_valid_record_type"),
        sa.CheckConstraint("submission_type IN ('addition', 'correction')", name="ck_submissions_valid_submission_type"),
        sa.CheckConstraint("target_id IS NULL OR target_id > 0", name="ck_submissions_target_id_positive"),
        sa.CheckConstraint("status IN ('draft', 'submitted', 'changes_requested', 'approved', 'rejected', 'rolled_back')", name="ck_submissions_valid_status"),
        sa.CheckConstraint("json_valid(proposed_data)", name="ck_submissions_proposed_data_json"),
        sa.CheckConstraint("version > 0", name="ck_submissions_version_positive"),
        sa.CheckConstraint("(submission_type = 'addition' AND target_id IS NULL) OR submission_type = 'correction'", name="ck_submissions_target_matches_type"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_submissions_submitter", "submissions", ["submitter_user_id"])
    op.create_index("idx_submissions_queue", "submissions", ["status", "submitted_at"])
    op.create_table(
        "submission_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False), sa.Column("title", sa.String(500)), sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint("length(trim(url)) > 0", name="ck_submission_sources_url_not_blank"), mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_submission_sources_submission", "submission_sources", ["submission_id"])
    op.create_table(
        "submission_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False), sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint("decision IN ('approve', 'reject', 'request_changes')", name="ck_submission_decisions_valid_decision"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_submission_decisions_submission", "submission_decisions", ["submission_id", "created_at"])
    op.create_table(
        "submission_promotions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("canonical_record_type", sa.String(32), nullable=False), sa.Column("canonical_record_id", sa.Integer(), nullable=False),
        sa.Column("before_snapshot", sa.Text()), sa.Column("after_snapshot", sa.Text(), nullable=False),
        sa.Column("promoted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("promoted_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("rolled_back_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("rolled_back_at", sa.DateTime()), sa.Column("rollback_reason", sa.Text()),
        sa.CheckConstraint("canonical_record_type IN ('designer', 'collection')", name="ck_submission_promotions_valid_record_type"),
        sa.CheckConstraint("canonical_record_id > 0", name="ck_submission_promotions_canonical_id_positive"),
        sa.CheckConstraint("before_snapshot IS NULL OR json_valid(before_snapshot)", name="ck_submission_promotions_before_snapshot_json"),
        sa.CheckConstraint("json_valid(after_snapshot)", name="ck_submission_promotions_after_snapshot_json"),
        sa.UniqueConstraint("submission_id", name="uq_submission_promotions_submission_id"), mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_table(
        "submission_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False), sa.Column("from_status", sa.String(32)),
        sa.Column("to_status", sa.String(32), nullable=False), sa.Column("event_data", sa.Text(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint("event_type IN ('created', 'draft_updated', 'submitted', 'changes_requested', 'rejected', 'approved', 'rolled_back')", name="ck_submission_audit_valid_event_type"),
        sa.CheckConstraint("json_valid(event_data)", name="ck_submission_audit_event_data_json"), mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_submission_audit_submission", "submission_audit", ["submission_id", "id"])
    install_append_only_triggers()


def install_append_only_triggers():
    dialect = op.get_bind().dialect.name
    for table in ("submission_audit", "submission_decisions"):
        for action in ("UPDATE", "DELETE"):
            trigger = f"{table}_no_{action.lower()}"
            if dialect == "mysql":
                op.execute(sa.text(f"CREATE TRIGGER {trigger} BEFORE {action} ON {table} FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '{table.replace('_', ' ')} is append-only'"))
            else:
                op.execute(sa.text(f"CREATE TRIGGER {trigger} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, '{table.replace('_', ' ')} is append-only'); END"))


def downgrade():
    for table in ("submission_audit", "submission_decisions"):
        for action in ("update", "delete"):
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {table}_no_{action}"))
    for table in ("submission_audit", "submission_promotions", "submission_decisions", "submission_sources", "submissions", "collection_media", "collections", "users", "designers"):
        op.drop_table(table)
