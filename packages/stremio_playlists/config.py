"""Application configuration from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _path(key: str, default: str) -> Path:
    raw = os.getenv(key, default)
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    base_url: str
    data_dir: Path
    db_path: Path
    log_dir: Path
    log_level: str
    log_max_bytes: int
    log_backup_count: int
    cinemeta_base: str
    metahub_poster: str
    tmdb_api_key: str
    import_worker_interval_sec: float
    import_batch_size: int
    import_rate_limit_per_min: int
    cors_origins: str
    api_token: str
    lock_configure_api: bool
    configure_allowed_origins: str
    configure_allowed_referer_prefix: str
    stremio_streaming_server: str
    backup_schema_version: int
    rust_parser_bin: Path

    @classmethod
    def load(cls) -> "Settings":
        data_dir = _path("DATA_DIR", "data")
        return cls(
            host=os.getenv("HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "7010")),
            base_url=os.getenv("BASE_URL", "http://127.0.0.1:7010").rstrip("/"),
            data_dir=data_dir,
            db_path=_path("DB_PATH", "data/playlists.db"),
            log_dir=_path("LOG_DIR", "logs"),
            log_level=os.getenv("LOG_LEVEL", "DEBUG").upper(),
            log_max_bytes=int(os.getenv("LOG_MAX_BYTES", "10485760")),
            log_backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
            cinemeta_base=os.getenv(
                "CINEMETA_BASE", "https://v3-cinemeta.strem.io"
            ).rstrip("/"),
            metahub_poster=os.getenv(
                "METAHUB_POSTER", "https://images.metahub.space/poster/medium"
            ).rstrip("/"),
            tmdb_api_key=os.getenv("TMDB_API_KEY", "").strip(),
            import_worker_interval_sec=float(
                os.getenv("IMPORT_WORKER_INTERVAL_SEC", "2")
            ),
            import_batch_size=int(os.getenv("IMPORT_BATCH_SIZE", "5")),
            import_rate_limit_per_min=int(
                os.getenv("IMPORT_RATE_LIMIT_PER_MIN", "30")
            ),
            cors_origins=os.getenv(
                "CORS_ORIGINS", "https://alexrabbit.github.io,*"
            ),
            api_token=os.getenv("API_TOKEN", "").strip(),
            lock_configure_api=os.getenv("LOCK_CONFIGURE_API", "0").strip()
            in ("1", "true", "yes"),
            configure_allowed_origins=os.getenv(
                "CONFIGURE_ALLOWED_ORIGINS", "https://alexrabbit.github.io"
            ),
            configure_allowed_referer_prefix=os.getenv(
                "CONFIGURE_ALLOWED_REFERER_PREFIX",
                "https://alexrabbit.github.io/Stremio-Watchlist-Maker",
            ).rstrip("/"),
            backup_schema_version=int(os.getenv("BACKUP_SCHEMA_VERSION", "1")),
            stremio_streaming_server=os.getenv(
                "STREMIO_STREAMING_SERVER", "http://127.0.0.1:11470"
            ).rstrip("/"),
            rust_parser_bin=ROOT
            / "rust"
            / "title_parser"
            / "target"
            / "release"
            / ("title_parser.exe" if os.name == "nt" else "title_parser"),
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings.load()
