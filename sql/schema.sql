
PRAGMA foreign_keys = ON;

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
