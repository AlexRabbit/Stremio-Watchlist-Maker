"""Extensive structured logging — separate files per subsystem."""

from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from stremio_playlists.config import settings

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(api[_-]?key|token|password|secret)\s*[:=]\s*\S+", re.I),
        r"\1=***REDACTED***",
    ),
    (re.compile(r"Bearer\s+\S+", re.I), "Bearer ***REDACTED***"),
]


def _scrub(msg: str) -> str:
    out = msg
    for pat, repl in _SECRET_PATTERNS:
        out = pat.sub(repl, out)
    return out


class ScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _scrub(record.msg)
        if record.args:
            record.args = tuple(
                _scrub(a) if isinstance(a, str) else a for a in record.args
            )
        return True


def _make_handler(path: Path, level: int) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(ScrubFilter())
    return handler


def setup_logging() -> None:
    settings.ensure_dirs()
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level, logging.DEBUG))
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
    console.addFilter(ScrubFilter())
    root.addHandler(console)

    subsystems = (
        "app",
        "addon",
        "api",
        "db",
        "importer",
        "resolver",
        "worker",
        "security",
        "audit",
    )
    for name in subsystems:
        log_path = settings.log_dir / f"{name}.log"
        logging.getLogger(name).addHandler(
            _make_handler(log_path, logging.DEBUG)
        )
        logging.getLogger(name).propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
