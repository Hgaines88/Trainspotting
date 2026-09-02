CREATE TABLE IF NOT EXISTS submissions (
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
    CHECK (
        (submission_type = 'addition' AND target_id IS NULL)
        OR submission_type = 'correction'
    )
);

CREATE INDEX IF NOT EXISTS idx_submissions_submitter ON submissions(submitter_user_id);
CREATE INDEX IF NOT EXISTS idx_submissions_queue ON submissions(status, submitted_at);

CREATE TABLE IF NOT EXISTS submission_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    url TEXT NOT NULL CHECK (length(trim(url)) > 0),
    title TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_submission_sources_submission
    ON submission_sources(submission_id);

CREATE TABLE IF NOT EXISTS submission_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    reviewer_user_id INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approve', 'reject', 'request_changes')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE RESTRICT,
    FOREIGN KEY (reviewer_user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_submission_decisions_submission
    ON submission_decisions(submission_id, created_at);

CREATE TABLE IF NOT EXISTS submission_promotions (
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

CREATE TABLE IF NOT EXISTS submission_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    actor_user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (
        event_type IN ('created', 'draft_updated', 'submitted', 'changes_requested', 'rejected', 'approved', 'rolled_back')
    ),
    from_status TEXT,
    to_status TEXT NOT NULL,
    event_data TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(event_data)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE RESTRICT,
    FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_submission_audit_submission
    ON submission_audit(submission_id, id);

CREATE TRIGGER IF NOT EXISTS submission_audit_no_update
BEFORE UPDATE ON submission_audit
BEGIN
    SELECT RAISE(ABORT, 'submission audit is append-only');
END;

CREATE TRIGGER IF NOT EXISTS submission_audit_no_delete
BEFORE DELETE ON submission_audit
BEGIN
    SELECT RAISE(ABORT, 'submission audit is append-only');
END;

CREATE TRIGGER IF NOT EXISTS submission_decisions_no_update
BEFORE UPDATE ON submission_decisions
BEGIN
    SELECT RAISE(ABORT, 'submission decisions are append-only');
END;

CREATE TRIGGER IF NOT EXISTS submission_decisions_no_delete
BEFORE DELETE ON submission_decisions
BEGIN
    SELECT RAISE(ABORT, 'submission decisions are append-only');
END;
