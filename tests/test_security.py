"""Security regression tests."""

import pytest
from stremio_playlists.db.repository import Database
import tempfile
from pathlib import Path


def test_sql_injection_playlist_name():
    with tempfile.TemporaryDirectory() as td:
        d = Database(str(Path(td) / "t.db"))
        d.init()
        uid = d.create_user()
        malicious = "'; DROP TABLE playlists; --"
        pid = d.create_playlist(uid, malicious)
        pls = d.list_playlists(uid)
        assert len(pls) == 1
        assert pls[0].name == malicious


def test_invalid_sort_field_rejected():
    with tempfile.TemporaryDirectory() as td:
        d = Database(str(Path(td) / "t.db"))
        d.init()
        uid = d.create_user()
        pid = d.create_playlist(uid, "x", sort_by="; DELETE FROM users")
        pl = d.get_playlist(pid)
        assert pl.sort_by == "position"
