"""Stremio addon handler tests."""

import json

from stremio_playlists.addon.handlers import (
    ALL_CATALOG_ID,
    MANIFEST_MAX_BYTES,
    build_manifest,
    handle_catalog_sync,
    _manifest_payload_size,
)
from stremio_playlists.db.repository import Database
import tempfile
from pathlib import Path
import pytest


@pytest.fixture
def seeded_db(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test.db"
        d = Database(str(path))
        d.init()
        monkeypatch.setattr("stremio_playlists.addon.handlers.db", d)
        uid = d.create_user()
        pid = d.create_playlist(uid, "Visually Striking")
        d.add_item(pid, "tt2406566", "Spring Breakers", year=2012, genres="Drama, Comedy")
        d.add_item(
            pid,
            "tt1375666",
            "Inception",
            year=2010,
            director="Christopher Nolan",
            genres="Action, Sci-Fi",
            rating=8.8,
        )
        d.add_item(
            pid,
            "tt0081505",
            "The Shining",
            year=1980,
            director="Stanley Kubrick",
            genres="Horror",
            rating=8.4,
        )
        yield uid, pid, d


def test_manifest_fits_stremio_limit(seeded_db):
    uid, pid, _ = seeded_db
    manifest = build_manifest(uid)
    size = _manifest_payload_size(manifest)
    assert size <= MANIFEST_MAX_BYTES
    catalog = next(c for c in manifest["catalogs"] if c["id"] == pid)
    assert catalog["type"] == "channel"
    assert "genres" not in catalog
    assert "extra" not in catalog
    all_catalog = next(c for c in manifest["catalogs"] if c["id"] == ALL_CATALOG_ID)
    extra_names = {e["name"] for e in all_catalog["extra"]}
    assert extra_names == {"skip", "search"}
    assert manifest["behaviorHints"]["configurable"] is True


def test_manifest_has_all_and_playlist_only(seeded_db):
    uid, pid, _ = seeded_db
    manifest = build_manifest(uid)
    ids = {c["id"] for c in manifest["catalogs"]}
    names = {c["name"] for c in manifest["catalogs"]}
    assert ALL_CATALOG_ID in ids
    assert "All" in names
    assert pid in ids
    assert not any(c["id"].startswith("smart_") for c in manifest["catalogs"])
    assert "Comedy Picks" not in names


def test_all_catalog_returns_metas(seeded_db):
    uid, _, _ = seeded_db
    result = handle_catalog_sync(uid, ALL_CATALOG_ID)
    assert len(result["metas"]) == 3


def test_manifest_hides_empty_playlist(seeded_db):
    uid, _, d = seeded_db
    empty_id = d.create_playlist(uid, "Empty Channel")
    manifest = build_manifest(uid)
    ids = {c["id"] for c in manifest["catalogs"]}
    assert empty_id not in ids


def test_catalog_returns_metas(seeded_db):
    uid, pid, _ = seeded_db
    result = handle_catalog_sync(uid, pid)
    assert len(result["metas"]) == 3


def test_catalog_accepts_legacy_playlist_prefix(seeded_db):
    uid, pid, _ = seeded_db
    result = handle_catalog_sync(uid, f"playlist_{pid}")
    assert len(result["metas"]) == 3


def test_catalog_filters_by_genre(seeded_db):
    uid, pid, _ = seeded_db
    result = handle_catalog_sync(uid, pid, "genre=Horror")
    assert len(result["metas"]) == 1
    assert result["metas"][0]["name"] == "The Shining"


def test_catalog_filters_by_director(seeded_db):
    uid, pid, _ = seeded_db
    result = handle_catalog_sync(uid, pid, "director=Christopher%20Nolan")
    assert len(result["metas"]) == 1
    assert "Inception" in result["metas"][0]["name"]


def test_catalog_filters_by_decade(seeded_db):
    uid, pid, _ = seeded_db
    result = handle_catalog_sync(uid, pid, "year=2010s")
    assert len(result["metas"]) == 2


def test_catalog_filters_by_rating(seeded_db):
    uid, pid, _ = seeded_db
    result = handle_catalog_sync(uid, pid, "rating=8%2B")
    assert len(result["metas"]) == 2


def test_manifest_caps_many_playlists(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test.db"
        d = Database(str(path))
        d.init()
        monkeypatch.setattr("stremio_playlists.addon.handlers.db", d)
        uid = d.create_user()
        for i in range(250):
            pid = d.create_playlist(uid, f"Channel number {i:03d} with a longer title")
            d.add_item(pid, f"tt{i:07d}", f"Movie {i}", year=2000 + (i % 20))
        manifest = build_manifest(uid)
        size = _manifest_payload_size(manifest)
        assert size <= MANIFEST_MAX_BYTES
        channel_count = sum(1 for c in manifest["catalogs"] if c["id"] != ALL_CATALOG_ID)
        assert channel_count < 250
