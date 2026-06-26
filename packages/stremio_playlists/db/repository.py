"""Data access layer — SQLite with connection per request."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, fields
from typing import Any, Generator, Iterable, TypeVar

from stremio_playlists.config import settings
from stremio_playlists.db.schema import SCHEMA_SQL, SCHEMA_VERSION
from stremio_playlists.logging_setup import get_logger

log = get_logger("db")

T = TypeVar("T")

SORT_FIELDS = frozenset(
    {"position", "title", "year", "director", "genres", "rating", "added_at"}
)


@dataclass
class Playlist:
    id: str
    user_id: str
    name: str
    description: str
    sort_by: str
    sort_order: str
    content_type: str = "channel"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class PlaylistItem:
    id: str
    playlist_id: str
    imdb_id: str
    title: str
    year: int | None
    director: str
    genres: str
    rating: float | None
    position: int
    source: str
    added_at: str = ""


@dataclass
class ImportJob:
    id: str
    user_id: str
    playlist_id: str | None
    source_type: str
    source_payload: str
    status: str
    total: int
    processed: int
    matched: int
    failed: int
    error: str
    created_at: str = ""
    updated_at: str = ""


class Database:
    def __init__(self, path: str | None = None) -> None:
        self.path = str(path or settings.db_path)

    @staticmethod
    def _row_to_dataclass(cls: type[T], row: sqlite3.Row) -> T:
        """Map a DB row to a dataclass, ignoring unknown columns."""
        data = dict(row)
        allowed = {f.name for f in fields(cls)}
        return cls(**{k: data[k] for k in allowed if k in data})

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def session(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        settings.ensure_dirs()
        with self.session() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                "INSERT OR IGNORE INTO schema_meta(key, value) VALUES (?, ?)",
                ("version", str(SCHEMA_VERSION)),
            )
            self._migrate(conn)
        log.info("Database initialized at %s", self.path)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "manifest_version" not in cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN manifest_version INTEGER NOT NULL DEFAULT 0"
            )
        pl_cols = {row[1] for row in conn.execute("PRAGMA table_info(playlists)")}
        if "content_type" not in pl_cols:
            conn.execute(
                "ALTER TABLE playlists ADD COLUMN content_type TEXT NOT NULL DEFAULT 'channel'"
            )
            pl_cols.add("content_type")
        if "content_type" in pl_cols:
            conn.execute(
                "UPDATE playlists SET content_type='channel' "
                "WHERE content_type IS NULL OR content_type IN ('movie', 'series', '')"
            )

    def queue_metadata_backfill(self) -> int:
        """Queue background metadata enrichment for all users with sparse items."""
        try:
            queued = 0
            for row in self.list_users():
                uid = row["id"]
                if self.list_items_missing_metadata(user_id=uid, limit=1):
                    self.create_metadata_job(uid, limit=500)
                    queued += 1
            return queued
        except sqlite3.OperationalError as exc:
            log.warning("metadata backfill skipped: %s", exc)
            return 0

    def ensure_user(self, user_id: str, name: str = "Default") -> None:
        with self.session() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users(id, name) VALUES (?, ?)",
                (user_id, name),
            )

    def create_user(self, name: str = "My Playlists") -> str:
        user_id = uuid.uuid4().hex[:16]
        with self.session() as conn:
            conn.execute(
                "INSERT INTO users(id, name) VALUES (?, ?)", (user_id, name)
            )
        return user_id

    def list_users(self) -> list[dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute("SELECT id, name, created_at FROM users").fetchall()
        return [dict(r) for r in rows]

    def create_playlist(
        self,
        user_id: str,
        name: str,
        description: str = "",
        sort_by: str = "position",
        sort_order: str = "asc",
        content_type: str = "channel",
    ) -> str:
        if sort_by not in SORT_FIELDS:
            sort_by = "position"
        if sort_order not in ("asc", "desc"):
            sort_order = "asc"
        if content_type not in ("movie", "series", "channel"):
            content_type = "channel"
        pid = uuid.uuid4().hex[:12]
        with self.session() as conn:
            conn.execute(
                """INSERT INTO playlists(id, user_id, name, description, sort_by, sort_order, content_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (pid, user_id, name, description, sort_by, sort_order, content_type),
            )
        return pid

    def update_playlist(
        self,
        playlist_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> bool:
        fields: list[str] = []
        values: list[Any] = []
        if name is not None:
            fields.append("name=?")
            values.append(name)
        if description is not None:
            fields.append("description=?")
            values.append(description)
        if sort_by is not None and sort_by in SORT_FIELDS:
            fields.append("sort_by=?")
            values.append(sort_by)
        if sort_order is not None and sort_order in ("asc", "desc"):
            fields.append("sort_order=?")
            values.append(sort_order)
        if not fields:
            return False
        fields.append("updated_at=datetime('now')")
        values.append(playlist_id)
        with self.session() as conn:
            cur = conn.execute(
                f"UPDATE playlists SET {', '.join(fields)} WHERE id=?",
                values,
            )
        return cur.rowcount > 0

    def delete_playlist(self, playlist_id: str) -> bool:
        with self.session() as conn:
            cur = conn.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
        return cur.rowcount > 0

    def _playlist_from_row(self, row: sqlite3.Row) -> Playlist:
        pl = self._row_to_dataclass(Playlist, row)
        if not getattr(pl, "content_type", None):
            pl.content_type = "channel"
        return pl

    def _item_from_row(self, row: sqlite3.Row) -> PlaylistItem:
        return self._row_to_dataclass(PlaylistItem, row)

    def get_playlist(self, playlist_id: str) -> Playlist | None:
        with self.session() as conn:
            row = conn.execute(
                "SELECT * FROM playlists WHERE id=?", (playlist_id,)
            ).fetchone()
        if not row:
            return None
        return self._playlist_from_row(row)

    def list_playlists(self, user_id: str) -> list[Playlist]:
        with self.session() as conn:
            rows = conn.execute(
                "SELECT * FROM playlists WHERE user_id=? ORDER BY name",
                (user_id,),
            ).fetchall()
        return [self._playlist_from_row(r) for r in rows]

    def _order_clause(self, sort_by: str, sort_order: str) -> str:
        direction = "DESC" if sort_order == "desc" else "ASC"
        if sort_by == "genres":
            return f"genres {direction}, title ASC"
        if sort_by in SORT_FIELDS:
            return f"{sort_by} {direction}, title ASC"
        return f"position {direction}"

    def bump_manifest_version(self, user_id: str) -> int:
        try:
            with self.session() as conn:
                cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
                if "manifest_version" not in cols:
                    return 0
                conn.execute(
                    "UPDATE users SET manifest_version = manifest_version + 1 WHERE id=?",
                    (user_id,),
                )
                row = conn.execute(
                    "SELECT manifest_version FROM users WHERE id=?", (user_id,)
                ).fetchone()
            return int(row[0]) if row else 0
        except sqlite3.OperationalError as exc:
            log.warning("bump_manifest_version skipped: %s", exc)
            return 0

    def get_manifest_version(self, user_id: str) -> int:
        try:
            with self.session() as conn:
                cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
                if "manifest_version" not in cols:
                    return 0
                row = conn.execute(
                    "SELECT manifest_version FROM users WHERE id=?", (user_id,)
                ).fetchone()
            return int(row[0]) if row else 0
        except sqlite3.OperationalError:
            return 0

    def get_filter_stats(self, user_id: str) -> dict[str, Any]:
        with self.session() as conn:
            row = conn.execute(
                """SELECT COUNT(*),
                          SUM(CASE WHEN genres IS NOT NULL AND genres != '' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN director IS NOT NULL AND director != '' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN year IS NOT NULL THEN 1 ELSE 0 END),
                          SUM(CASE WHEN rating IS NOT NULL THEN 1 ELSE 0 END)
                   FROM playlist_items pi
                   JOIN playlists p ON p.id = pi.playlist_id
                   WHERE p.user_id=?""",
                (user_id,),
            ).fetchone()
        total = int(row[0] or 0)
        return {
            "total_items": total,
            "with_genres": int(row[1] or 0),
            "with_director": int(row[2] or 0),
            "with_year": int(row[3] or 0),
            "with_rating": int(row[4] or 0),
            "manifest_version": self.get_manifest_version(user_id),
        }

    def list_all_user_items(self, user_id: str, *, content_type: str | None = None) -> list[PlaylistItem]:
        query = """SELECT pi.* FROM playlist_items pi
                   JOIN playlists p ON p.id = pi.playlist_id
                   WHERE p.user_id=?"""
        params: list[Any] = [user_id]
        if content_type:
            query += " AND p.content_type=?"
            params.append(content_type)
        query += " ORDER BY pi.title ASC"
        with self.session() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._item_from_row(r) for r in rows]

    def list_items_missing_metadata(
        self, *, user_id: str = "", limit: int = 200
    ) -> list[PlaylistItem]:
        query = """SELECT pi.* FROM playlist_items pi
                   JOIN playlists p ON p.id = pi.playlist_id
                   WHERE (pi.genres IS NULL OR pi.genres = ''
                          OR pi.director IS NULL OR pi.director = ''
                          OR pi.year IS NULL)"""
        params: list[Any] = []
        if user_id:
            query += " AND p.user_id=?"
            params.append(user_id)
        query += " ORDER BY pi.added_at DESC LIMIT ?"
        params.append(limit)
        with self.session() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._item_from_row(r) for r in rows]

    def update_item_metadata(
        self,
        item_id: str,
        *,
        year: int | None = None,
        director: str = "",
        genres: str = "",
        rating: float | None = None,
    ) -> bool:
        with self.session() as conn:
            cur = conn.execute(
                """UPDATE playlist_items
                   SET year=COALESCE(?, year),
                       director=CASE WHEN ? != '' THEN ? ELSE director END,
                       genres=CASE WHEN ? != '' THEN ? ELSE genres END,
                       rating=COALESCE(?, rating)
                   WHERE id=?""",
                (year, director, director, genres, genres, rating, item_id),
            )
        return cur.rowcount > 0

    def create_metadata_job(self, user_id: str, limit: int = 200) -> str:
        job_id = uuid.uuid4().hex[:12]
        with self.session() as conn:
            conn.execute(
                """INSERT INTO metadata_jobs(id, user_id, limit_count)
                   VALUES (?, ?, ?)""",
                (job_id, user_id, limit),
            )
        return job_id

    def get_pending_metadata_jobs(self, limit: int = 3) -> list[dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                """SELECT * FROM metadata_jobs WHERE status='pending'
                   ORDER BY created_at LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_metadata_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        processed: int | None = None,
        error: str | None = None,
    ) -> None:
        fields: list[str] = ["updated_at=datetime('now')"]
        values: list[Any] = []
        for key, val in (("status", status), ("processed", processed), ("error", error)):
            if val is not None:
                fields.append(f"{key}=?")
                values.append(val)
        values.append(job_id)
        with self.session() as conn:
            conn.execute(
                f"UPDATE metadata_jobs SET {', '.join(fields)} WHERE id=?",
                values,
            )

    def get_filter_options(
        self,
        playlist_id: str,
        *,
        limit_per: int = 80,
    ) -> dict[str, list[str]]:
        from stremio_playlists.addon.filters import build_filter_options

        items, _ = self.list_items(playlist_id, skip=0, limit=100_000)
        opts = build_filter_options(items)
        return {k: v[:limit_per] for k, v in opts.items()}

    def list_items(
        self,
        playlist_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[PlaylistItem], int]:
        pl = self.get_playlist(playlist_id)
        if not pl:
            return [], 0
        order = self._order_clause(pl.sort_by, pl.sort_order)
        with self.session() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM playlist_items WHERE playlist_id=?",
                (playlist_id,),
            ).fetchone()[0]
            rows = conn.execute(
                f"""SELECT * FROM playlist_items WHERE playlist_id=?
                    ORDER BY {order} LIMIT ? OFFSET ?""",
                (playlist_id, limit, skip),
            ).fetchall()
        return [self._item_from_row(r) for r in rows], total

    def add_item(
        self,
        playlist_id: str,
        imdb_id: str,
        title: str,
        *,
        year: int | None = None,
        director: str = "",
        genres: str = "",
        rating: float | None = None,
        source: str = "manual",
    ) -> str | None:
        if not imdb_id.startswith("tt"):
            imdb_id = f"tt{imdb_id}" if imdb_id.isdigit() else imdb_id
        item_id = uuid.uuid4().hex[:12]
        with self.session() as conn:
            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), -1) FROM playlist_items WHERE playlist_id=?",
                (playlist_id,),
            ).fetchone()[0]
            try:
                conn.execute(
                    """INSERT INTO playlist_items
                       (id, playlist_id, imdb_id, title, year, director, genres, rating, position, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item_id,
                        playlist_id,
                        imdb_id,
                        title,
                        year,
                        director,
                        genres,
                        rating,
                        max_pos + 1,
                        source,
                    ),
                )
            except sqlite3.IntegrityError:
                return None
            conn.execute(
                "UPDATE playlists SET updated_at=datetime('now') WHERE id=?",
                (playlist_id,),
            )
        return item_id

    def get_item_user_id(self, item_id: str) -> str | None:
        with self.session() as conn:
            row = conn.execute(
                """SELECT p.user_id FROM playlist_items pi
                   JOIN playlists p ON p.id = pi.playlist_id
                   WHERE pi.id=?""",
                (item_id,),
            ).fetchone()
        return str(row[0]) if row else None

    def remove_item(self, item_id: str) -> bool:
        with self.session() as conn:
            cur = conn.execute(
                "DELETE FROM playlist_items WHERE id=?", (item_id,)
            )
        return cur.rowcount > 0

    def create_import_job(
        self,
        user_id: str,
        playlist_id: str,
        source_type: str,
        source_payload: str,
    ) -> str:
        job_id = uuid.uuid4().hex[:12]
        with self.session() as conn:
            conn.execute(
                """INSERT INTO import_jobs
                   (id, user_id, playlist_id, source_type, source_payload)
                   VALUES (?, ?, ?, ?, ?)""",
                (job_id, user_id, playlist_id, source_type, source_payload),
            )
        return job_id

    def get_pending_jobs(self, limit: int = 5) -> list[ImportJob]:
        with self.session() as conn:
            rows = conn.execute(
                """SELECT * FROM import_jobs WHERE status='pending'
                   ORDER BY created_at LIMIT ?""",
                (limit,),
            ).fetchall()
        return [ImportJob(**dict(r)) for r in rows]

    def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        total: int | None = None,
        processed: int | None = None,
        matched: int | None = None,
        failed: int | None = None,
        error: str | None = None,
    ) -> None:
        fields: list[str] = ["updated_at=datetime('now')"]
        values: list[Any] = []
        for key, val in (
            ("status", status),
            ("total", total),
            ("processed", processed),
            ("matched", matched),
            ("failed", failed),
            ("error", error),
        ):
            if val is not None:
                fields.append(f"{key}=?")
                values.append(val)
        values.append(job_id)
        with self.session() as conn:
            conn.execute(
                f"UPDATE import_jobs SET {', '.join(fields)} WHERE id=?",
                values,
            )

    def get_job(self, job_id: str) -> ImportJob | None:
        with self.session() as conn:
            row = conn.execute(
                "SELECT * FROM import_jobs WHERE id=?", (job_id,)
            ).fetchone()
        return ImportJob(**dict(row)) if row else None

    def export_user_data(self, user_id: str) -> dict[str, Any]:
        playlists = self.list_playlists(user_id)
        items_by_pl: dict[str, list[dict[str, Any]]] = {}
        for pl in playlists:
            items, _ = self.list_items(pl.id, limit=100_000)
            items_by_pl[pl.id] = [
                {
                    "imdb_id": i.imdb_id,
                    "title": i.title,
                    "year": i.year,
                    "director": i.director,
                    "genres": i.genres,
                    "rating": i.rating,
                    "position": i.position,
                    "source": i.source,
                }
                for i in items
            ]
        return {
            "schema_version": settings.backup_schema_version,
            "user_id": user_id,
            "playlists": [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "sort_by": p.sort_by,
                    "sort_order": p.sort_order,
                    "items": items_by_pl.get(p.id, []),
                }
                for p in playlists
            ],
        }

    def import_user_data(self, user_id: str, data: dict[str, Any]) -> dict[str, int]:
        self.ensure_user(user_id)
        playlists_created = 0
        items_imported = 0
        items_skipped = 0
        for pl_data in data.get("playlists", []):
            pid = self.create_playlist(
                user_id,
                pl_data.get("name", "Imported"),
                pl_data.get("description", ""),
                pl_data.get("sort_by", "position"),
                pl_data.get("sort_order", "asc"),
            )
            playlists_created += 1
            for item in pl_data.get("items", []):
                imdb_id = (item.get("imdb_id") or "").strip()
                if not imdb_id:
                    items_skipped += 1
                    continue
                if self.add_item(
                    pid,
                    imdb_id,
                    item.get("title", "Unknown"),
                    year=item.get("year"),
                    director=item.get("director", ""),
                    genres=item.get("genres", ""),
                    rating=item.get("rating"),
                    source=item.get("source", "import"),
                ):
                    items_imported += 1
                else:
                    items_skipped += 1
        if playlists_created:
            self.bump_manifest_version(user_id)
        return {
            "playlists_created": playlists_created,
            "imported_items": items_imported,
            "items_skipped": items_skipped,
        }


db = Database()
