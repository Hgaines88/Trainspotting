"""Portable SQLAlchemy metadata for Trainspotting's canonical schema."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    DDL,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    event,
    func,
)


metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


archive_state = Table(
    "archive_state",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=False),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint("id = 1", name="singleton"),
    CheckConstraint("version > 0", name="version_positive"),
)


designers = Table(
    "designers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("full_name", String(255), nullable=False, unique=True),
    Column("nationality", String(255)),
    Column("birth_year", Integer),
    Column("website", Text),
    Column("biography", Text),
    CheckConstraint("length(trim(full_name)) > 0", name="full_name_not_blank"),
    CheckConstraint(
        "birth_year IS NULL OR birth_year BETWEEN 1800 AND 2100",
        name="birth_year_range",
    ),
)
Index("idx_designers_nationality", designers.c.nationality).ddl_if(
    dialect=("mysql", "mariadb")
)

designer_aliases = Table(
    "designer_aliases",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "designer_id",
        Integer,
        ForeignKey("designers.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("alias", String(255), nullable=False),
    Column("normalized_alias", String(255), nullable=False, unique=True),
    Column("alias_type", String(32), nullable=False),
    Column("source_url", Text, nullable=False),
    CheckConstraint("length(trim(alias)) > 0", name="alias_not_blank"),
    CheckConstraint(
        "length(trim(normalized_alias)) > 0",
        name="normalized_alias_not_blank",
    ),
    CheckConstraint(
        "alias_type IN ('alternate-name', 'former-name', 'legal-name')",
        name="valid_alias_type",
    ),
    CheckConstraint("length(trim(source_url)) > 0", name="source_url_not_blank"),
    UniqueConstraint("designer_id", "alias", name="uq_designer_alias"),
)
Index("idx_designer_aliases_designer", designer_aliases.c.designer_id)
event.listen(
    designers,
    "after_create",
    DDL(
        "CREATE INDEX idx_designers_nationality "
        "ON designers(nationality COLLATE NOCASE)"
    ).execute_if(dialect="sqlite"),
)

collections = Table(
    "collections",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "designer_id",
        Integer,
        ForeignKey("designers.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("label", String(255), nullable=False),
    Column("name", String(255)),
    Column("season", String(100), nullable=False),
    Column("release_year", Integer, nullable=False),
    Column("status", String(32), nullable=False),
    Column("piece_count", Integer),
    Column("description", Text),
    CheckConstraint("length(trim(label)) > 0", name="label_not_blank"),
    CheckConstraint(
        "name IS NULL OR length(trim(name)) > 0", name="name_not_blank"
    ),
    CheckConstraint("length(trim(season)) > 0", name="season_not_blank"),
    CheckConstraint(
        "release_year BETWEEN 1900 AND 2100", name="release_year_range"
    ),
    CheckConstraint(
        "status IN ('concept', 'in-production', 'released', 'archived')",
        name="valid_status",
    ),
    CheckConstraint(
        "piece_count IS NULL OR piece_count >= 0", name="piece_count_nonnegative"
    ),
    UniqueConstraint(
        "designer_id", "label", "season", "release_year", name="uq_collection"
    ),
)
Index("idx_collections_designer_id", collections.c.designer_id)
Index("idx_collections_label", collections.c.label).ddl_if(
    dialect=("mysql", "mariadb")
)
Index("idx_collections_season", collections.c.season).ddl_if(
    dialect=("mysql", "mariadb")
)
event.listen(
    collections,
    "after_create",
    DDL(
        "CREATE INDEX idx_collections_label "
        "ON collections(label COLLATE NOCASE)"
    ).execute_if(dialect="sqlite"),
)
event.listen(
    collections,
    "after_create",
    DDL(
        "CREATE INDEX idx_collections_season "
        "ON collections(season COLLATE NOCASE)"
    ).execute_if(dialect="sqlite"),
)
Index(
    "idx_collections_year_status",
    collections.c.release_year,
    collections.c.status,
)

collection_credits = Table(
    "collection_credits",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "collection_id",
        Integer,
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "designer_id",
        Integer,
        ForeignKey("designers.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("credit_role", String(32), nullable=False),
    Column("credit_order", Integer, nullable=False),
    Column("attribution_note", Text),
    CheckConstraint(
        "credit_role IN ('lead', 'co-designer', 'guest', 'collaborator', "
        "'attribution-note')",
        name="valid_role",
    ),
    CheckConstraint(
        "credit_order > 0",
        name="order_positive",
    ),
    CheckConstraint(
        "attribution_note IS NULL OR length(trim(attribution_note)) > 0",
        name="attribution_note_not_blank",
    ),
    UniqueConstraint(
        "collection_id", "designer_id", name="uq_collection_credit_designer"
    ),
    UniqueConstraint(
        "collection_id", "credit_order", name="uq_collection_credit_order"
    ),
)
Index("idx_collection_credits_collection", collection_credits.c.collection_id)
Index("idx_collection_credits_designer", collection_credits.c.designer_id)

collection_media = Table(
    "collection_media",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "collection_id",
        Integer,
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("media_type", String(32), nullable=False),
    Column("media_value", Text, nullable=False),
    CheckConstraint(
        "media_type IN ('source', 'youtube', 'vimeo')",
        name="valid_media_type",
    ),
    CheckConstraint("length(trim(media_value)) > 0", name="media_value_not_blank"),
    UniqueConstraint("collection_id", "media_type", name="uq_collection_media"),
)
Index("idx_collection_media_collection_id", collection_media.c.collection_id)

collection_descriptors = Table(
    "collection_descriptors",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "collection_id",
        Integer,
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("category", String(32), nullable=False),
    Column("canonical_value", String(64), nullable=False),
    Column("strength", String(16), nullable=False),
    Column("evidence_note", Text, nullable=False),
    Column(
        "source_submission_id",
        Integer,
        ForeignKey("submissions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    ),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint(
        "category IN ('theme', 'motif', 'material', 'texture', 'color', 'silhouette')",
        name="valid_category",
    ),
    CheckConstraint(
        "strength IN ('dominant', 'supporting')", name="valid_strength"
    ),
    CheckConstraint(
        "length(trim(canonical_value)) > 0", name="canonical_value_not_blank"
    ),
    CheckConstraint(
        "length(trim(evidence_note)) > 0", name="evidence_note_not_blank"
    ),
    UniqueConstraint(
        "collection_id", "category", "canonical_value",
        name="uq_collection_descriptor",
    ),
)
Index("idx_collection_descriptors_collection", collection_descriptors.c.collection_id)
Index(
    "idx_collection_descriptors_lookup",
    collection_descriptors.c.category,
    collection_descriptors.c.canonical_value,
)

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("clerk_user_id", String(255), nullable=False, unique=True),
    Column("email", String(320)),
    Column("display_name", String(255)),
    Column("role", String(32), nullable=False, server_default="member"),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint("length(trim(clerk_user_id)) > 0", name="clerk_id_not_blank"),
    CheckConstraint("role IN ('member', 'moderator', 'admin')", name="valid_role"),
)
Index("idx_users_role", users.c.role)

submissions = Table(
    "submissions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "submitter_user_id",
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("record_type", String(32), nullable=False),
    Column("proposal_kind", String(32), nullable=False, server_default="archive_record"),
    Column("submission_type", String(32), nullable=False),
    Column("target_id", Integer),
    Column("status", String(32), nullable=False, server_default="draft"),
    Column("proposed_data", Text, nullable=False),
    Column("explanation", Text),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("submitted_at", DateTime),
    Column("reviewed_at", DateTime),
    CheckConstraint("record_type IN ('designer', 'collection')", name="valid_record_type"),
    CheckConstraint(
        "submission_type IN ('addition', 'correction')", name="valid_submission_type"
    ),
    CheckConstraint("target_id IS NULL OR target_id > 0", name="target_id_positive"),
    CheckConstraint(
        "status IN ('draft', 'submitted', 'changes_requested', 'approved', "
        "'rejected', 'rolled_back')",
        name="valid_status",
    ),
    CheckConstraint("json_valid(proposed_data)", name="proposed_data_json"),
    CheckConstraint("version > 0", name="version_positive"),
    CheckConstraint(
        "(submission_type = 'addition' AND target_id IS NULL) "
        "OR submission_type = 'correction'",
        name="target_matches_type",
    ),
)
Index("idx_submissions_submitter", submissions.c.submitter_user_id)
Index("idx_submissions_queue", submissions.c.status, submissions.c.submitted_at)

submission_sources = Table(
    "submission_sources",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "submission_id",
        Integer,
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("url", Text, nullable=False),
    Column("title", String(500)),
    Column("notes", Text),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint("length(trim(url)) > 0", name="url_not_blank"),
)
Index("idx_submission_sources_submission", submission_sources.c.submission_id)

submission_decisions = Table(
    "submission_decisions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "submission_id",
        Integer,
        ForeignKey("submissions.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "reviewer_user_id",
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("decision", String(32), nullable=False),
    Column("notes", Text),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint(
        "decision IN ('approve', 'reject', 'request_changes')", name="valid_decision"
    ),
)
Index(
    "idx_submission_decisions_submission",
    submission_decisions.c.submission_id,
    submission_decisions.c.created_at,
)

submission_promotions = Table(
    "submission_promotions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "submission_id",
        Integer,
        ForeignKey("submissions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    ),
    Column("canonical_record_type", String(32), nullable=False),
    Column("canonical_record_id", Integer, nullable=False),
    Column("before_snapshot", Text),
    Column("after_snapshot", Text, nullable=False),
    Column(
        "promoted_by_user_id",
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("promoted_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column(
        "rolled_back_by_user_id",
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
    ),
    Column("rolled_back_at", DateTime),
    Column("rollback_reason", Text),
    CheckConstraint(
        "canonical_record_type IN ('designer', 'collection')",
        name="valid_record_type",
    ),
    CheckConstraint("canonical_record_id > 0", name="canonical_id_positive"),
    CheckConstraint(
        "before_snapshot IS NULL OR json_valid(before_snapshot)",
        name="before_snapshot_json",
    ),
    CheckConstraint("json_valid(after_snapshot)", name="after_snapshot_json"),
)

submission_audit = Table(
    "submission_audit",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "submission_id",
        Integer,
        ForeignKey("submissions.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "actor_user_id",
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("event_type", String(32), nullable=False),
    Column("from_status", String(32)),
    Column("to_status", String(32), nullable=False),
    Column("event_data", Text, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint(
        "event_type IN ('created', 'draft_updated', 'submitted', "
        "'changes_requested', 'rejected', 'approved', 'rolled_back')",
        name="valid_event_type",
    ),
    CheckConstraint("json_valid(event_data)", name="event_data_json"),
)
Index(
    "idx_submission_audit_submission",
    submission_audit.c.submission_id,
    submission_audit.c.id,
)

ingestion_batches = Table(
    "ingestion_batches",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("submitter_user_id", Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
    Column("source_name", String(255), nullable=False),
    Column("input_format", String(16), nullable=False),
    Column("status", String(32), nullable=False, server_default="running"),
    Column("total_rows", Integer, nullable=False, server_default="0"),
    Column("valid_rows", Integer, nullable=False, server_default="0"),
    Column("invalid_rows", Integer, nullable=False, server_default="0"),
    Column("duplicate_rows", Integer, nullable=False, server_default="0"),
    Column("review_rows", Integer, nullable=False, server_default="0"),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("completed_at", DateTime),
    CheckConstraint("length(trim(source_name)) > 0", name="source_name_not_blank"),
    CheckConstraint("input_format IN ('csv')", name="valid_input_format"),
    CheckConstraint("status IN ('running', 'completed', 'failed')", name="valid_status"),
    CheckConstraint(
        "total_rows >= 0 AND valid_rows >= 0 AND invalid_rows >= 0 "
        "AND duplicate_rows >= 0 AND review_rows >= 0",
        name="counts_nonnegative",
    ),
)
Index("idx_ingestion_batches_created", ingestion_batches.c.created_at)

ingestion_rows = Table(
    "ingestion_rows",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("batch_id", Integer, ForeignKey("ingestion_batches.id", ondelete="RESTRICT"), nullable=False),
    Column("source_row_number", Integer, nullable=False),
    Column("raw_payload", Text, nullable=False),
    Column("normalized_payload", Text),
    Column("fingerprint", String(64)),
    Column("status", String(32), nullable=False),
    Column("validation_errors", Text),
    Column("submission_id", Integer, ForeignKey("submissions.id", ondelete="RESTRICT")),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint("source_row_number > 0", name="source_row_number_positive"),
    CheckConstraint("json_valid(raw_payload)", name="raw_payload_json"),
    CheckConstraint("normalized_payload IS NULL OR json_valid(normalized_payload)", name="normalized_payload_json"),
    CheckConstraint("validation_errors IS NULL OR json_valid(validation_errors)", name="validation_errors_json"),
    CheckConstraint("fingerprint IS NULL OR length(fingerprint) = 64", name="fingerprint_length"),
    CheckConstraint("status IN ('valid', 'invalid', 'duplicate', 'requiring_review')", name="valid_status"),
    UniqueConstraint("batch_id", "source_row_number", name="uq_ingestion_row_number"),
)
Index("idx_ingestion_rows_batch", ingestion_rows.c.batch_id)
Index("idx_ingestion_rows_fingerprint", ingestion_rows.c.fingerprint)
Index("idx_ingestion_rows_status", ingestion_rows.c.status)

for table in metadata.tables.values():
    table.dialect_options["mysql"]["engine"] = "InnoDB"
    table.dialect_options["mysql"]["charset"] = "utf8mb4"
