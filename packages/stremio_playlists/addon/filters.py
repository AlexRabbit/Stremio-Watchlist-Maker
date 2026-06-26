"""Catalog filter options and matching for Stremio Discover extras."""

from __future__ import annotations

import re

from stremio_playlists.db.repository import PlaylistItem

RATING_BUCKETS = ("9+", "8+", "7+", "6+", "Below 6")
FILTER_EXTRA_ORDER = ("genre", "director", "year", "rating")
SORT_BY_RELEASE = "-by release date"
SORT_BY_DIRECTOR = "-Directors"


def decade_to_short_label(decade: str) -> str:
    """1990s -> -90s so sort options appear at top of dropdowns."""
    decade = decade.strip()
    if len(decade) == 5 and decade.endswith("s") and decade[:4].isdigit():
        return f"-{decade[2:4]}s"
    return f"-{decade}"


def short_decade_to_full(label: str) -> str | None:
    m = re.match(r"^-(\d{2})s$", label.strip(), re.I)
    if not m:
        return None
    yy = int(m.group(1))
    century = 1900 if yy >= 30 else 2000
    return f"{century + yy}s"


def is_sort_genre_option(value: str) -> bool:
    v = value.strip()
    return v.startswith("-") and (
        v == SORT_BY_RELEASE
        or v == SORT_BY_DIRECTOR
        or short_decade_to_full(v) is not None
    )


def parse_genre_filter(value: str) -> tuple[str, str]:
    """Return (mode, payload) where mode is sort|decade|genre."""
    v = value.strip()
    if v == SORT_BY_RELEASE:
        return "sort", "release"
    if v == SORT_BY_DIRECTOR:
        return "sort", "director"
    full = short_decade_to_full(v)
    if full:
        return "decade", full
    return "genre", v


def apply_catalog_sort(items: list[PlaylistItem], sort_key: str) -> list[PlaylistItem]:
    if sort_key == "release":
        return sorted(items, key=lambda i: (i.year or 0, i.title.lower()), reverse=True)
    if sort_key == "director":
        return sorted(
            items,
            key=lambda i: ((i.director or "zzz").lower(), i.title.lower()),
        )
    return items


def year_to_decade(year: int | None) -> str | None:
    if not year or year < 1900:
        return None
    decade = (year // 10) * 10
    return f"{decade}s"


def decade_range(decade_label: str) -> tuple[int, int] | None:
    label = decade_label.strip().lower().rstrip("s")
    if not label.isdigit() or len(label) != 4:
        return None
    start = int(label)
    return start, start + 9


def rating_bucket(rating: float | None) -> str | None:
    if rating is None:
        return None
    if rating >= 9:
        return "9+"
    if rating >= 8:
        return "8+"
    if rating >= 7:
        return "7+"
    if rating >= 6:
        return "6+"
    return "Below 6"


def item_genres(item: PlaylistItem) -> list[str]:
    return [g.strip() for g in (item.genres or "").split(",") if g.strip()]


def _prepend_sort_options(
    genres: list[str],
    decades: list[str],
    directors: list[str],
) -> dict[str, list[str]]:
    decade_short = [decade_to_short_label(d) for d in decades]
    sort_genre = [SORT_BY_RELEASE, SORT_BY_DIRECTOR, *decade_short]
    director_opts = [SORT_BY_DIRECTOR, *directors] if directors else []
    year_opts = [*decade_short, *decades] if decades else []
    return {
        "genre": sort_genre + genres,
        "director": director_opts[:81],
        "year": year_opts[:31],
        "rating": [],
    }


def build_filter_options(items: list[PlaylistItem]) -> dict[str, list[str]]:
    genres: set[str] = set()
    directors: set[str] = set()
    decades: set[str] = set()
    ratings: set[str] = set()
    for item in items:
        genres.update(item_genres(item))
        director = (item.director or "").strip()
        if director:
            directors.add(director)
        decade = year_to_decade(item.year)
        if decade:
            decades.add(decade)
        bucket = rating_bucket(item.rating)
        if bucket:
            ratings.add(bucket)
    genres = sorted(genres, key=str.lower)[:80]
    directors = sorted(directors, key=str.lower)[:80]
    decades = sorted(decades, reverse=True)[:30]
    rating_list = [b for b in RATING_BUCKETS if b in ratings]
    merged = _prepend_sort_options(genres, decades, directors)
    merged["rating"] = rating_list
    return merged


def item_matches_filters(
    item: PlaylistItem,
    *,
    search: str = "",
    genre: str = "",
    director: str = "",
    year: str = "",
    rating: str = "",
) -> bool:
    if search and search not in item.title.lower():
        return False
    if genre:
        mode, payload = parse_genre_filter(genre)
        if mode == "decade":
            decade = year_to_decade(item.year)
            if decade != payload:
                return False
        elif mode == "genre":
            wanted = payload.lower()
            if not any(g.lower() == wanted for g in item_genres(item)):
                return False
    if director:
        d = director.strip()
        if d == SORT_BY_DIRECTOR:
            pass
        elif (item.director or "").strip().lower() != d.lower():
            return False
    if year:
        y = year.strip()
        full = short_decade_to_full(y)
        decade_label = full or y
        decade = year_to_decade(item.year)
        if decade != decade_label:
            return False
    if rating:
        bucket = rating_bucket(item.rating)
        if bucket != rating.strip():
            return False
    return True
