"""Stremio addon manifest and catalog/meta handlers."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote

from stremio_playlists.addon.filters import (
    FILTER_EXTRA_ORDER,
    apply_catalog_sort,
    build_filter_options,
    item_matches_filters,
    parse_genre_filter,
)
from stremio_playlists.config import settings
from stremio_playlists.db.repository import PlaylistItem, db
from stremio_playlists.logging_setup import get_logger

log = get_logger("addon")

ADDON_ID = "com.alexrabbit.stremio.playlists"
CATALOG_PREFIX = "playlist_"
ALL_CATALOG_ID = "all"
STREMIO_CATALOG_TYPE = "channel"
META_ITEM_TYPE = "movie"
PAGE_SIZE = 100
# Stremio stores manifest in the user profile; hard limit ~8192 bytes (JSON).
MANIFEST_MAX_BYTES = 7800
MANIFEST_NAME_MAX = 36


def _minimal_catalog_extras() -> list[dict[str, Any]]:
    return [
        {"name": "skip", "isRequired": False},
        {"name": "search", "isRequired": False},
    ]


def _manifest_payload_size(manifest: dict[str, Any]) -> int:
    return len(
        json.dumps(manifest, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    )


def _slim_catalog_entry(catalog_id: str, name: str) -> dict[str, Any]:
    return {
        "type": STREMIO_CATALOG_TYPE,
        "id": catalog_id,
        "name": name[:MANIFEST_NAME_MAX],
    }


def _manifest_shell(*, manifest_ver: int, catalogs: list[dict[str, Any]]) -> dict[str, Any]:
    pages_assets = "https://alexrabbit.github.io/Stremio-Watchlist-Maker/static"
    return {
        "id": ADDON_ID,
        "version": f"0.5.{manifest_ver}",
        "name": "Stremio Watchlist Maker",
        "description": "Personal movie channels in Stremio Discover.",
        "logo": f"{pages_assets}/logo.svg",
        "background": f"{pages_assets}/bg.svg",
        "resources": ["catalog", "meta"],
        "types": ["channel", "movie"],
        "catalogs": catalogs,
        "idPrefixes": ["tt"],
        "behaviorHints": {
            "configurable": False,
            "configurationRequired": False,
        },
    }


def manifest_stats(user_id: str) -> dict[str, int]:
    """How many channels fit in Stremio's ~8KB manifest limit."""
    db.ensure_user(user_id)
    playlists = db.list_playlists(user_id)
    non_empty = 0
    for pl in playlists:
        _items, total = db.list_items(pl.id, skip=0, limit=1)
        if total > 0:
            non_empty += 1
    manifest = build_manifest(user_id)
    shown = len(manifest.get("catalogs") or [])
    has_all = any(c.get("id") == ALL_CATALOG_ID for c in manifest.get("catalogs") or [])
    return {
        "bytes": _manifest_payload_size(manifest),
        "max_bytes": MANIFEST_MAX_BYTES,
        "catalogs_in_manifest": shown - (1 if has_all else 0),
        "catalogs_total": non_empty,
    }


def build_manifest(user_id: str) -> dict[str, Any]:
    db.ensure_user(user_id)
    playlists = db.list_playlists(user_id)
    manifest_ver = db.get_manifest_version(user_id)

    all_items = db.list_all_user_items(user_id)
    catalogs: list[dict[str, Any]] = []
    if all_items:
        catalogs.append(
            {
                "type": STREMIO_CATALOG_TYPE,
                "id": ALL_CATALOG_ID,
                "name": "All",
                "extra": _minimal_catalog_extras(),
            }
        )

    for pl in playlists:
        _items, total = db.list_items(pl.id, skip=0, limit=1)
        if total == 0:
            continue
        catalogs.append(_slim_catalog_entry(pl.id, pl.name))
        trial = _manifest_shell(manifest_ver=manifest_ver, catalogs=catalogs)
        if _manifest_payload_size(trial) > MANIFEST_MAX_BYTES:
            catalogs.pop()
            log.warning(
                "Manifest cap reached for user %s after %d channel(s); %d playlist(s) omitted from manifest",
                user_id,
                len(catalogs) - (1 if all_items else 0),
                sum(1 for p in playlists if db.list_items(p.id, skip=0, limit=1)[1] > 0)
                - (len(catalogs) - (1 if all_items else 0)),
            )
            break

    manifest = _manifest_shell(manifest_ver=manifest_ver, catalogs=catalogs)
    size = _manifest_payload_size(manifest)
    if size > MANIFEST_MAX_BYTES:
        log.error("Manifest still %d bytes for user %s (limit %d)", size, user_id, MANIFEST_MAX_BYTES)
    return manifest


def _parse_extra(extra: str) -> dict[str, str]:
    if not extra:
        return {}
    if extra.endswith(".json"):
        extra = extra[:-5]
    result: dict[str, str] = {}
    for part in extra.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            result[k] = unquote(v)
        elif part.startswith("search="):
            result["search"] = unquote(part[7:])
    return result


def _catalog_id_to_playlist(catalog_id: str) -> str | None:
    if catalog_id.startswith(CATALOG_PREFIX):
        return catalog_id[len(CATALOG_PREFIX) :]
    if db.get_playlist(catalog_id):
        return catalog_id
    return None


def _item_to_meta(
    item: PlaylistItem,
    *,
    catalog_type: str = META_ITEM_TYPE,
) -> dict[str, Any]:
    from stremio_playlists.addon.filters import item_genres, year_to_decade

    name = item.title
    release = ""
    if item.year:
        release = str(item.year)
        decade = year_to_decade(item.year)
        if decade:
            release = f"{item.year} · {decade}"

    meta: dict[str, Any] = {
        "id": item.imdb_id,
        "type": catalog_type,
        "name": name,
        "poster": f"{settings.metahub_poster}/{item.imdb_id}/img",
        "genres": item_genres(item),
    }
    if release:
        meta["releaseInfo"] = release
    if item.year:
        meta["year"] = item.year
    if item.rating is not None:
        meta["imdbRating"] = item.rating
    return meta


def _dedupe_items(items: list[PlaylistItem]) -> list[PlaylistItem]:
    seen: set[str] = set()
    unique: list[PlaylistItem] = []
    for item in items:
        if item.imdb_id in seen:
            continue
        seen.add(item.imdb_id)
        unique.append(item)
    return unique


def _load_catalog_items(user_id: str, catalog_id: str) -> tuple[list[PlaylistItem], str]:
    if catalog_id == ALL_CATALOG_ID:
        items = _dedupe_items(db.list_all_user_items(user_id))
        return items, META_ITEM_TYPE

    playlist_id = _catalog_id_to_playlist(catalog_id)
    if playlist_id:
        items, _ = db.list_items(playlist_id, skip=0, limit=100_000)
        return items, META_ITEM_TYPE

    return [], META_ITEM_TYPE


async def handle_catalog_async(
    user_id: str,
    catalog_id: str,
    extra: str = "",
) -> dict[str, Any]:
    items, catalog_type = _load_catalog_items(user_id, catalog_id)
    known = (
        catalog_id == ALL_CATALOG_ID
        or catalog_id.startswith(CATALOG_PREFIX)
        or _catalog_id_to_playlist(catalog_id)
    )
    if not items and not known:
        log.warning("Unknown catalog %s", catalog_id)
        return {"metas": []}

    extra_params = _parse_extra(extra)
    skip = int(extra_params.get("skip", 0) or 0)
    search = extra_params.get("search", "").strip().lower()
    genre = extra_params.get("genre", "").strip()
    director = extra_params.get("director", "").strip()
    year = extra_params.get("year", "").strip()
    rating = extra_params.get("rating", "").strip()

    filtered = [
        item
        for item in items
        if item_matches_filters(
            item,
            search=search,
            genre=genre,
            director=director,
            year=year,
            rating=rating,
        )
    ]

    if genre:
        mode, payload = parse_genre_filter(genre)
        if mode == "sort":
            filtered = apply_catalog_sort(filtered, payload)

    page = filtered[skip : skip + PAGE_SIZE]
    metas = [_item_to_meta(item, catalog_type=catalog_type) for item in page]
    log.debug(
        "Catalog %s skip=%d filters=%s returned %d/%d metas",
        catalog_id,
        skip,
        {k: extra_params.get(k) for k in FILTER_EXTRA_ORDER + ("search",) if extra_params.get(k)},
        len(metas),
        len(filtered),
    )
    return {"metas": metas}


async def handle_catalog(
    user_id: str,
    catalog_id: str,
    extra: str = "",
) -> dict[str, Any]:
    return await handle_catalog_async(user_id, catalog_id, extra)


def handle_catalog_sync(
    user_id: str,
    catalog_id: str,
    extra: str = "",
) -> dict[str, Any]:
    import asyncio

    return asyncio.run(handle_catalog_async(user_id, catalog_id, extra))


def handle_meta(user_id: str, meta_type: str, meta_id: str) -> dict[str, Any]:
    with db.session() as conn:
        row = conn.execute(
            "SELECT * FROM playlist_items WHERE imdb_id=? LIMIT 1",
            (meta_id,),
        ).fetchone()
    if not row:
        return {"meta": None}
    item = dict(row)
    return {
        "meta": {
            "id": item["imdb_id"],
            "type": meta_type,
            "name": item["title"],
            "poster": f"{settings.metahub_poster}/{item['imdb_id']}/img",
            "year": item["year"],
            "releaseInfo": str(item["year"]) if item["year"] else "",
            "genres": [g.strip() for g in (item["genres"] or "").split(",") if g.strip()],
            "imdbRating": item["rating"],
            "description": f"From playlist · Director: {item['director'] or 'Unknown'}",
        }
    }
