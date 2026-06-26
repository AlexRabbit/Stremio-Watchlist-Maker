#!/usr/bin/env python3
"""Entry point for Stremio Playlists addon server."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "packages"))

from stremio_playlists.app import create_app
from stremio_playlists.config import settings
from stremio_playlists.logging_setup import setup_logging


def main() -> None:
    setup_logging()
    app = create_app()
    app.run(
        host=settings.host,
        port=settings.port,
        single_process=True,
        access_log=False,
    )


if __name__ == "__main__":
    main()
