"""Database tests."""

import tempfile
from pathlib import Path

import pytest

from stremio_playlists.db.repository import Database


@pytest.fixture
def db_tmp():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test.db"
        d = Database(str(path))
        d.init()
        yield d


def test_create_playlist_and_item(db_tmp):
    uid = db_tmp.create_user("test")
    pid = db_tmp.create_playlist(uid, "Watch Later")
    item_id = db_tmp.add_item(pid, "tt0137523", "Fight Club", year=1999)
    assert item_id
    items, total = db_tmp.list_items(pid)
    assert total == 1
    assert items[0].imdb_id == "tt0137523"


def test_duplicate_item_idempotent(db_tmp):
    uid = db_tmp.create_user()
    pid = db_tmp.create_playlist(uid, "Dup")
    assert db_tmp.add_item(pid, "tt0137523", "Fight Club")
    assert db_tmp.add_item(pid, "tt0137523", "Fight Club") is None


def test_sort_by_year_desc(db_tmp):
    uid = db_tmp.create_user()
    pid = db_tmp.create_playlist(uid, "Sorted", sort_by="year", sort_order="desc")
    db_tmp.add_item(pid, "tt0083658", "Blade Runner", year=1982)
    db_tmp.add_item(pid, "tt0137523", "Fight Club", year=1999)
    items, _ = db_tmp.list_items(pid)
    assert items[0].year == 1999


def test_export_import(db_tmp):
    uid = db_tmp.create_user()
    pid = db_tmp.create_playlist(uid, "Backup")
    db_tmp.add_item(pid, "tt0137523", "Fight Club", year=1999)
    data = db_tmp.export_user_data(uid)
    new_uid = db_tmp.create_user("imported")
    count = db_tmp.import_user_data(new_uid, data)
    assert count >= 1
