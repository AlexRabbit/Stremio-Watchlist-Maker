"""Configure route for Stremio addon base path."""

import tempfile
from pathlib import Path

import pytest

from stremio_playlists.app import create_app
from stremio_playlists.db.repository import Database


@pytest.fixture
def client(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test.db"
        d = Database(str(path))
        d.init()
        monkeypatch.setattr("stremio_playlists.app.db", d)
        monkeypatch.setattr("stremio_playlists.addon.handlers.db", d)
        app = create_app()
        yield app.test_client


def test_user_configure_page(client):
    uid = "testuser1234567890"
    _, resp = client.get(f"/{uid}/configure")
    assert resp.status == 200
    assert b"Channel Organizer" in resp.body
