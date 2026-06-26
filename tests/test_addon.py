"""Stremio addon handler tests."""

from stremio_playlists.addon.handlers import (
    ALL_CATALOG_ID,
    build_manifest,
    handle_catalog_sync,
    CATALOG_PREFIX,
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


def test_manifest_lists_playlists_with_genres_field(seeded_db):
    uid, pid, _ = seeded_db
    manifest = build_manifest(uid)
    assert manifest["types"] == ["channel"]
    catalog = next(c for c in manifest["catalogs"] if c["id"] == f"{CATALOG_PREFIX}{pid}")
    assert catalog["type"] == "channel"
    assert "genres" in catalog
    assert "Horror" in catalog["genres"]
    extra_names = {e["name"] for e in catalog["extra"]}
    assert "genre" in extra_names
    assert "director" in extra_names
    assert "year" in extra_names
    assert "rating" in extra_names


def test_manifest_has_all_and_playlist_only(seeded_db):
    uid, pid, _ = seeded_db
    manifest = build_manifest(uid)
    ids = {c["id"] for c in manifest["catalogs"]}
    names = {c["name"] for c in manifest["catalogs"]}
    assert ALL_CATALOG_ID in ids
    assert "All" in names
    assert f"{CATALOG_PREFIX}{pid}" in ids
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
    assert f"{CATALOG_PREFIX}{empty_id}" not in ids


def test_catalog_returns_metas(seeded_db):
    uid, pid, _ = seeded_db
    result = handle_catalog_sync(uid, f"{CATALOG_PREFIX}{pid}")
    assert len(result["metas"]) == 3


def test_catalog_filters_by_genre(seeded_db):
    uid, pid, _ = seeded_db
    result = handle_catalog_sync(uid, f"{CATALOG_PREFIX}{pid}", "genre=Horror")
    assert len(result["metas"]) == 1
    assert result["metas"][0]["name"] == "The Shining"


def test_catalog_filters_by_director(seeded_db):
    uid, pid, _ = seeded_db
    result = handle_catalog_sync(uid, f"{CATALOG_PREFIX}{pid}", "director=Christopher%20Nolan")
    assert len(result["metas"]) == 1
    assert "Inception" in result["metas"][0]["name"]


def test_catalog_filters_by_decade(seeded_db):
    uid, pid, _ = seeded_db
    result = handle_catalog_sync(uid, f"{CATALOG_PREFIX}{pid}", "year=2010s")
    assert len(result["metas"]) == 2


def test_catalog_filters_by_rating(seeded_db):
    uid, pid, _ = seeded_db
    result = handle_catalog_sync(uid, f"{CATALOG_PREFIX}{pid}", "rating=8%2B")
    assert len(result["metas"]) == 2
