import pytest

from stremio_playlists.importer.parser import (
    merge_titles,
    normalize_tasteofcinema_url,
)
from stremio_playlists.importer.parser import ExtractedTitle


def test_normalize_tasteofcinema_strips_page():
    url = "https://www.tasteofcinema.com/2015/10-great-movies/2/"
    assert normalize_tasteofcinema_url(url) == (
        "https://www.tasteofcinema.com/2015/10-great-movies/"
    )


def test_merge_titles_dedupes():
    a = [ExtractedTitle(title="Fight Club"), ExtractedTitle(title="Se7en")]
    b = [ExtractedTitle(title="fight club"), ExtractedTitle(title="Zodiac")]
    merged = merge_titles([a, b])
    assert [t.title for t in merged] == ["Fight Club", "Se7en", "Zodiac"]


@pytest.mark.asyncio
async def test_tasteofcinema_fetches_multiple_pages(monkeypatch):
    pages = {
        1: "<article><h2>1. Movie One (1999)</h2></article>",
        2: "<article><h2>2. Movie Two (2000)</h2></article>",
        3: "",
    }

    async def fake_fetch(url: str) -> str:
        if url.endswith("/2/"):
            return pages[2]
        if url.endswith("/3/"):
            raise RuntimeError("404")
        return pages[1]

    from stremio_playlists.importer import parser as mod

    monkeypatch.setattr(mod, "_fetch_html", fake_fetch)
    titles = await mod._fetch_tasteofcinema_list(
        "https://www.tasteofcinema.com/2015/sample-list/"
    )
    assert len(titles) == 2
