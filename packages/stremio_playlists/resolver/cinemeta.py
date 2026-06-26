"""Movie metadata resolution via Cinemeta (Stremio's public metadata API)."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

import aiohttp

from stremio_playlists.config import settings
from stremio_playlists.logging_setup import get_logger

log = get_logger("resolver")

IMDB_RE = re.compile(r"tt\d{7,8}")


@dataclass
class ResolvedMovie:
    imdb_id: str
    title: str
    year: int | None
    director: str
    genres: str
    rating: float | None
    poster: str | None


class CinemetaResolver:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()
        self._cache: dict[str, ResolvedMovie | None] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _poster(self, imdb_id: str) -> str:
        return f"{settings.metahub_poster}/{imdb_id}/img"

    def _parse_meta(self, meta: dict[str, Any]) -> ResolvedMovie:
        imdb_id = meta.get("id", "")
        director = ""
        cast = meta.get("cast") or meta.get("director") or []
        if isinstance(cast, list) and cast:
            director = cast[0] if isinstance(cast[0], str) else str(cast[0])
        elif isinstance(cast, str):
            director = cast
        genres = meta.get("genre") or meta.get("genres") or []
        if isinstance(genres, list):
            genres_str = ", ".join(str(g) for g in genres)
        else:
            genres_str = str(genres)
        rating = meta.get("imdbRating") or meta.get("rating")
        try:
            rating_f = float(rating) if rating is not None else None
        except (TypeError, ValueError):
            rating_f = None
        year_raw = meta.get("year") or meta.get("releaseInfo")
        year: int | None = None
        if isinstance(year_raw, int):
            year = year_raw
        elif isinstance(year_raw, str):
            m = re.search(r"\d{4}", year_raw)
            if m:
                year = int(m.group())
        return ResolvedMovie(
            imdb_id=imdb_id,
            title=meta.get("name", meta.get("title", "Unknown")),
            year=year,
            director=director,
            genres=genres_str,
            rating=rating_f,
            poster=self._poster(imdb_id),
        )

    async def fetch_by_imdb(self, imdb_id: str) -> ResolvedMovie | None:
        if not imdb_id.startswith("tt"):
            if imdb_id.isdigit():
                imdb_id = f"tt{imdb_id}"
        if imdb_id in self._cache:
            return self._cache[imdb_id]
        url = f"{settings.cinemeta_base}/meta/movie/{imdb_id}.json"
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    self._cache[imdb_id] = None
                    return None
                data = await resp.json()
        except Exception as exc:
            log.warning("Cinemeta fetch failed for %s: %s", imdb_id, exc)
            return None
        meta = data.get("meta")
        if not meta:
            self._cache[imdb_id] = None
            return None
        resolved = self._parse_meta(meta)
        self._cache[imdb_id] = resolved
        return resolved

    async def search(self, query: str, year: int | None = None) -> ResolvedMovie | None:
        key = f"{query}|{year}"
        if key in self._cache:
            return self._cache[key]
        encoded = aiohttp.helpers.quote(query)
        url = f"{settings.cinemeta_base}/catalog/movie/top/search={encoded}.json"
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        except Exception as exc:
            log.warning("Cinemeta search failed for %r: %s", query, exc)
            return None
        metas = data.get("metas") or []
        if not metas:
            self._cache[key] = None
            return None
        best = None
        query_lower = query.lower().strip()
        for meta in metas:
            title = (meta.get("name") or "").lower()
            meta_year = meta.get("year")
            if title == query_lower or query_lower in title:
                if year is None or meta_year == year:
                    best = meta
                    break
        if best is None:
            best = metas[0]
        resolved = self._parse_meta(best)
        self._cache[key] = resolved
        return resolved

    async def resolve_title(
        self, title: str, year: int | None = None
    ) -> ResolvedMovie | None:
        title = title.strip()
        if not title:
            return None
        imdb_match = IMDB_RE.search(title)
        if imdb_match:
            return await self.fetch_by_imdb(imdb_match.group())
        return await self.search(title, year)


resolver = CinemetaResolver()
