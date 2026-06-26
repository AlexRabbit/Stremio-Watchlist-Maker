from stremio_playlists.addon.filters import (
    build_filter_options,
    item_matches_filters,
    rating_bucket,
    year_to_decade,
)
from stremio_playlists.db.repository import PlaylistItem


def test_year_to_decade():
    assert year_to_decade(1980) == "1980s"
    assert year_to_decade(2012) == "2010s"


def test_rating_bucket():
    assert rating_bucket(8.5) == "8+"
    assert rating_bucket(9.1) == "9+"


def test_build_filter_options_decades():
    items = [
        PlaylistItem("1", "p", "tt1", "A", 1980, "", "Horror", 7.0, 0, "x"),
        PlaylistItem("2", "p", "tt2", "B", 2010, "", "Drama", 8.0, 1, "x"),
    ]
    opts = build_filter_options(items)
    assert "-by release date" in opts["genre"][0:3]
    assert "-80s" in opts["genre"]
    assert "1980s" in opts["year"]
    assert "8+" in opts["rating"]


def test_short_decade_filter():
    from stremio_playlists.addon.filters import short_decade_to_full

    assert short_decade_to_full("-90s") == "1990s"
    assert short_decade_to_full("-10s") == "2010s"


def test_item_matches_decade_filter():
    item = PlaylistItem("1", "p", "tt1", "A", 1984, "", "Horror", None, 0, "x")
    assert item_matches_filters(item, year="1980s")
    assert not item_matches_filters(item, year="1990s")
