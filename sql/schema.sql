
PRAGMA foreign_keys = ON;

CREATE TABLE archive_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO archive_state (id, version) VALUES (1, 1);

CREATE TABLE designers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL UNIQUE
        CHECK (length(trim(full_name)) > 0),
    nationality TEXT,
    birth_year INTEGER
        CHECK (birth_year BETWEEN 1800 AND 2100),
    website TEXT,
    biography TEXT
);


CREATE TABLE collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    designer_id INTEGER NOT NULL,

    label TEXT NOT NULL
        CHECK (length(trim(label)) > 0),

    name TEXT
        CHECK (name IS NULL OR length(trim(name)) > 0),

    season TEXT NOT NULL
        CHECK (length(trim(season)) > 0),

    release_year INTEGER NOT NULL
        CHECK (release_year BETWEEN 1900 AND 2100),

    status TEXT NOT NULL
        CHECK (
            status IN (
                'concept',
                'in-production',
                'released',
                'archived'
            )
        ),

    piece_count INTEGER
        CHECK (piece_count IS NULL OR piece_count >= 0),

    description TEXT,

    FOREIGN KEY (designer_id)
        REFERENCES designers(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    UNIQUE (
        designer_id,
        label,
        season,
        release_year
    )
);

CREATE INDEX idx_collections_designer_id
    ON collections(designer_id);
CREATE INDEX idx_designers_nationality
    ON designers(nationality COLLATE NOCASE);
CREATE INDEX idx_collections_label
    ON collections(label COLLATE NOCASE);
CREATE INDEX idx_collections_season
    ON collections(season COLLATE NOCASE);
CREATE INDEX idx_collections_year_status
    ON collections(release_year, status);


CREATE TABLE collection_credits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    designer_id INTEGER NOT NULL,
    credit_role TEXT NOT NULL
        CHECK (credit_role IN ('lead', 'co-designer', 'guest', 'collaborator', 'attribution-note')),
    credit_order INTEGER NOT NULL CHECK (credit_order > 0),
    attribution_note TEXT
        CHECK (attribution_note IS NULL OR length(trim(attribution_note)) > 0),

    FOREIGN KEY (collection_id)
        REFERENCES collections(id)
        ON DELETE CASCADE,
    FOREIGN KEY (designer_id)
        REFERENCES designers(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    UNIQUE (collection_id, designer_id),
    UNIQUE (collection_id, credit_order)
);

CREATE INDEX idx_collection_credits_collection
    ON collection_credits(collection_id);
CREATE INDEX idx_collection_credits_designer
    ON collection_credits(designer_id);

INSERT INTO collection_credits (
    collection_id, designer_id, credit_role, credit_order
)
SELECT id, designer_id, 'lead', 1
FROM collections;


CREATE TABLE collection_media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    media_type TEXT NOT NULL
        CHECK (media_type IN ('source', 'youtube')),
    media_value TEXT NOT NULL
        CHECK (length(trim(media_value)) > 0),

    FOREIGN KEY (collection_id)
        REFERENCES collections(id)
        ON DELETE CASCADE,

    UNIQUE (collection_id, media_type)
);


CREATE INDEX idx_collection_media_collection_id
    ON collection_media(collection_id);


CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clerk_user_id TEXT NOT NULL UNIQUE
        CHECK (length(trim(clerk_user_id)) > 0),
    email TEXT,
    display_name TEXT,
    role TEXT NOT NULL DEFAULT 'member'
        CHECK (role IN ('member', 'moderator', 'admin')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE INDEX idx_users_role
    ON users(role);


CREATE TABLE submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submitter_user_id INTEGER NOT NULL,
    record_type TEXT NOT NULL CHECK (record_type IN ('designer', 'collection')),
    submission_type TEXT NOT NULL CHECK (submission_type IN ('addition', 'correction')),
    target_id INTEGER CHECK (target_id IS NULL OR target_id > 0),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'changes_requested', 'approved', 'rejected', 'rolled_back')),
    proposed_data TEXT NOT NULL CHECK (json_valid(proposed_data)),
    explanation TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submitted_at TEXT,
    reviewed_at TEXT,
    FOREIGN KEY (submitter_user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CHECK ((submission_type = 'addition' AND target_id IS NULL) OR submission_type = 'correction')
);

CREATE INDEX idx_submissions_submitter ON submissions(submitter_user_id);
CREATE INDEX idx_submissions_queue ON submissions(status, submitted_at);

CREATE TABLE submission_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    url TEXT NOT NULL CHECK (length(trim(url)) > 0),
    title TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
);

CREATE INDEX idx_submission_sources_submission ON submission_sources(submission_id);

CREATE TABLE submission_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    reviewer_user_id INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approve', 'reject', 'request_changes')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE RESTRICT,
    FOREIGN KEY (reviewer_user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_submission_decisions_submission ON submission_decisions(submission_id, created_at);

CREATE TABLE submission_promotions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL UNIQUE,
    canonical_record_type TEXT NOT NULL CHECK (canonical_record_type IN ('designer', 'collection')),
    canonical_record_id INTEGER NOT NULL CHECK (canonical_record_id > 0),
    before_snapshot TEXT CHECK (before_snapshot IS NULL OR json_valid(before_snapshot)),
    after_snapshot TEXT NOT NULL CHECK (json_valid(after_snapshot)),
    promoted_by_user_id INTEGER NOT NULL,
    promoted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rolled_back_by_user_id INTEGER,
    rolled_back_at TEXT,
    rollback_reason TEXT,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE RESTRICT,
    FOREIGN KEY (promoted_by_user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (rolled_back_by_user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE submission_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    actor_user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('created', 'draft_updated', 'submitted', 'changes_requested', 'rejected', 'approved', 'rolled_back')),
    from_status TEXT,
    to_status TEXT NOT NULL,
    event_data TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(event_data)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE RESTRICT,
    FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_submission_audit_submission ON submission_audit(submission_id, id);

CREATE TRIGGER submission_audit_no_update BEFORE UPDATE ON submission_audit
BEGIN SELECT RAISE(ABORT, 'submission audit is append-only'); END;
CREATE TRIGGER submission_audit_no_delete BEFORE DELETE ON submission_audit
BEGIN SELECT RAISE(ABORT, 'submission audit is append-only'); END;
CREATE TRIGGER submission_decisions_no_update BEFORE UPDATE ON submission_decisions
BEGIN SELECT RAISE(ABORT, 'submission decisions are append-only'); END;
CREATE TRIGGER submission_decisions_no_delete BEFORE DELETE ON submission_decisions
BEGIN SELECT RAISE(ABORT, 'submission decisions are append-only'); END;
