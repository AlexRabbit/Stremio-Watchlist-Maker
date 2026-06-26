"""SQLite schema and migrations."""

SCHEMA_VERSION = 2

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT 'Default',
    manifest_version INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS playlists (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    sort_by TEXT NOT NULL DEFAULT 'position',
    sort_order TEXT NOT NULL DEFAULT 'asc',
    content_type TEXT NOT NULL DEFAULT 'channel',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_playlists_user ON playlists(user_id);

CREATE TABLE IF NOT EXISTS playlist_items (
    id TEXT PRIMARY KEY,
    playlist_id TEXT NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    imdb_id TEXT NOT NULL,
    title TEXT NOT NULL,
    year INTEGER,
    director TEXT DEFAULT '',
    genres TEXT DEFAULT '',
    rating REAL,
    position INTEGER NOT NULL DEFAULT 0,
    source TEXT DEFAULT 'manual',
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(playlist_id, imdb_id)
);

CREATE INDEX IF NOT EXISTS idx_items_playlist ON playlist_items(playlist_id);
CREATE INDEX IF NOT EXISTS idx_items_year ON playlist_items(year);
CREATE INDEX IF NOT EXISTS idx_items_title ON playlist_items(title);

CREATE TABLE IF NOT EXISTS import_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    playlist_id TEXT REFERENCES playlists(id) ON DELETE SET NULL,
    source_type TEXT NOT NULL,
    source_payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    total INTEGER DEFAULT 0,
    processed INTEGER DEFAULT 0,
    matched INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    error TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON import_jobs(status);

CREATE TABLE IF NOT EXISTS metadata_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    limit_count INTEGER NOT NULL DEFAULT 200,
    processed INTEGER NOT NULL DEFAULT 0,
    error TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_metadata_jobs_status ON metadata_jobs(status);
"""
