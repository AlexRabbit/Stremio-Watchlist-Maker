"""Parser unit tests."""

import pytest

from stremio_playlists.importer.parser import parse_bulk_text, _parse_line


@pytest.mark.parametrize(
    "line,expected_title,expected_year",
    [
        ("15. The Act of Killing", "The Act of Killing", None),
        ("Blade Runner (1982)", "Blade Runner", 1982),
        ("- Her", "Her", None),
        ("tt0137523", "tt0137523", None),
        ("Fight Club - tt0137523", "Fight Club", None),
        ("", None, None),
        ("# comment", None, None),
    ],
)
def test_parse_line(line, expected_title, expected_year):
    result = _parse_line(line)
    if expected_title is None:
        assert result is None
    else:
        assert result.title == expected_title
        assert result.year == expected_year


def test_bulk_text():
    text = "Her\n2046\nScott Pilgrim vs. the World"
    items = parse_bulk_text(text)
    assert len(items) == 3
    assert items[0].title == "Her"


def test_numbered_list():
    text = "15. Spring Breakers\n14. 2046 (2004)"
    items = parse_bulk_text(text)
    assert items[0].title == "Spring Breakers"
    assert items[1].year == 2004
