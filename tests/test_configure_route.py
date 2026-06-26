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


def test_user_configure_redirects_to_pages(client):
    uid = "testuser1234567890"
    _, resp = client.get(f"/{uid}/configure", allow_redirects=False)
    assert resp.status in (301, 302, 303, 307, 308)
    location = resp.headers.get("location", "")
    assert f"user={uid}" in location
    assert "configure.html" in location


def test_manifest_allows_stremio_cors(client):
    uid = "testuser1234567890"
    client.post("/api/users", json={})
    _, resp = client.get(
        f"/{uid}/manifest.json",
        headers={"Origin": "https://app.strem.io"},
    )
    assert resp.status == 200
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_manifest_head_reports_content_length(client):
    uid = "testuser1234567890"
    client.post("/api/users", json={})
    _, get_resp = client.get(f"/{uid}/manifest.json")
    _, head_resp = client.head(f"/{uid}/manifest.json")
    assert head_resp.status == 200
    assert int(head_resp.headers.get("content-length", 0)) == len(get_resp.body)
