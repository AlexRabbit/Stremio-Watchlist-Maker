"""Stremio local streaming server — library / watched state."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from stremio_playlists.config import settings
from stremio_playlists.logging_setup import get_logger

log = get_logger("library")

_cache: set[str] = set()
_cache_at: float = 0.0
_CACHE_TTL = 60.0


async def _fetch_json(path: str) -> Any:
    url = f"{settings.stremio_streaming_server}{path}"
    timeout = aiohttp.ClientTimeout(total=5)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            return await resp.json(content_type=None)


def _extract_ids(payload: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(payload, dict):
        for key in ("result", "items", "library", "data"):
            if key in payload:
                ids.update(_extract_ids(payload[key]))
        for key, val in payload.items():
            if key in ("_id", "id", "imdb_id") and isinstance(val, str) and val.startswith("tt"):
                ids.add(val)
            elif isinstance(val, (dict, list)):
                ids.update(_extract_ids(val))
    elif isinstance(payload, list):
        for entry in payload:
            if isinstance(entry, str) and entry.startswith("tt"):
                ids.add(entry)
            elif isinstance(entry, dict):
                for key in ("_id", "id", "imdb_id"):
                    val = entry.get(key)
                    if isinstance(val, str) and val.startswith("tt"):
                        ids.add(val)
                state = entry.get("state") or {}
                if isinstance(state, dict):
                    times = state.get("timesWatched") or state.get("times_watched") or 0
                    if times and isinstance(val := entry.get("_id") or entry.get("id"), str):
                        if val.startswith("tt"):
                            ids.add(val)
                ids.update(_extract_ids(entry))
    return ids


async def get_watched_imdb_ids() -> set[str]:
    """Best-effort watched IDs from local Stremio streaming server."""
    global _cache, _cache_at
    now = asyncio.get_event_loop().time()
    if _cache and (now - _cache_at) < _CACHE_TTL:
        return _cache

    paths = (
        "/api/v1/library",
        "/api/library",
        "/library",
        "/api/cache/library",
    )
    watched: set[str] = set()
    for path in paths:
        try:
            data = await _fetch_json(path)
            if data:
                watched = _extract_ids(data)
                if watched:
                    break
        except Exception as exc:
            log.debug("Library fetch %s failed: %s", path, exc)

    _cache = watched
    _cache_at = now
    return watched
