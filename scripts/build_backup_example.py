#!/usr/bin/env python3
"""Build BackupExample.json from Chrome bookmarks (Entretenimiento > Peliculas).

Usage:
  PYTHONPATH=packages python scripts/build_backup_example.py [bookmarks.html]
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from bs4 import BeautifulSoup

from stremio_playlists.importer.parser import (
    ExtractedTitle,
    extract_from_html,
    fetch_url_titles,
    parse_bulk_text,
)
from stremio_playlists.resolver.cinemeta import resolver

BOOKMARKS_DEFAULT = ROOT / "bookmarks.html"
OUTPUT = ROOT / "BackupExample.json"
SCHEMA_VERSION = 1
USER_ID = "demo00000000000001"
RATE_DELAY_SEC = 0.12
RESOLVE_CONCURRENCY = 6

NOISE_SUFFIXES = (
    "that are worth your time",
    "that are worth watching",
    "you need to watch",
    "you need to see",
    "you shouldn't miss",
    "you must watch",
    "every movie fan should see",
    "every photographer should watch",
    "worth your time",
    " - google search",
    " - buscar con google",
    " - youtube",
    "« taste of cinema",
    "– taste of cinema",
)


def extract_peliculas_links(html: str) -> list[tuple[str, str]]:
    start = html.lower().find(">peliculas</h3>")
    if start < 0:
        raise SystemExit("Peliculas folder not found in bookmarks")
    chunk = html[start:]
    end = chunk.find("</DL><p>", 20)
    section = chunk[:end] if end > 0 else chunk
    return re.findall(r'<A HREF="([^"]+)"[^>]*>([^<]+)</A>', section, re.I)


def clean_list_title(raw: str) -> str:
    title = raw.split("«")[0].split("–")[0].split("|")[0].strip()
    title = re.sub(r"^\d+\s+", "", title)
    low = title.lower()
    for suffix in NOISE_SUFFIXES:
        if suffix in low:
            idx = low.index(suffix)
            title = title[:idx].strip(" -–—")
            low = title.lower()
    # Keep "Great Psychopath Movies" style — only strip leading filler adjectives.
    title = re.sub(
        r"^(totally awesome|essential|best|top)\s+",
        "",
        title,
        flags=re.I,
    ).strip()
    return title[:96] or raw[:96]


def google_query(url: str, bookmark_title: str) -> str | None:
    parsed = urlparse(url)
    if "google." not in parsed.netloc:
        return None
    q = parse_qs(parsed.query).get("q", [""])[0]
    if q:
        return unquote(q).replace("+", " ").strip()
    return clean_list_title(bookmark_title)


async def fetch_youtube_description(url: str) -> str:
    import aiohttp

    headers = {"User-Agent": "ChannelOrganizer/0.5"}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return ""
            html = await resp.text()
    soup = BeautifulSoup(html, "lxml")
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return meta["content"]
    og = soup.find("meta", property="og:description")
    if og and og.get("content"):
        return og["content"]
    return ""


async def titles_for_link(url: str, bookmark_title: str) -> tuple[str, list[ExtractedTitle]]:
    low = url.lower()
    name = clean_list_title(bookmark_title)

    if "tasteofcinema.com" in low:
        titles = await fetch_url_titles(url)
        return name, titles

    if "imdb.com/list/" in low:
        titles = await fetch_url_titles(url)
        return name, titles

    if "youtube.com/watch" in low or "youtu.be/" in low:
        desc = await fetch_youtube_description(url)
        parsed = parse_bulk_text(desc) if desc else []
        if parsed:
            return name, parsed
        # Trailer/single video — try title before "Official Trailer" etc.
        single = re.split(
            r"\s+[\(\|]\s*(official|original|exclusive|hd|4k)",
            name,
            maxsplit=1,
            flags=re.I,
        )[0].strip()
        if single and "best movies" not in single.lower():
            return name, [ExtractedTitle(title=single)]
        return name, []

    if "google." in low:
        query = google_query(url, bookmark_title)
        if query:
            return query, [ExtractedTitle(title=query)]
        return name, []

    if "wikipedia.org" in low and "filmograf" in low:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                html = await resp.text()
        soup = BeautifulSoup(html, "lxml")
        titles: list[ExtractedTitle] = []
        seen: set[str] = set()
        for row in soup.select("table.wikitable tr"):
            cells = row.find_all("td")
            if not cells:
                continue
            text = cells[0].get_text(" ", strip=True)
            italic = cells[0].find("i")
            if italic:
                text = italic.get_text(" ", strip=True)
            if text and len(text) < 120 and text.lower() not in seen:
                seen.add(text.lower())
                titles.append(ExtractedTitle(title=text))
        return name or "Wikipedia Filmography", titles

    # Generic article / review pages
    import aiohttp

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return name, []
            html = await resp.text()
    titles = extract_from_html(html, url)
    if not titles and "rottentomatoes.com" in low:
        soup = BeautifulSoup(html, "lxml")
        h1 = soup.find("h1")
        if h1:
            titles = [ExtractedTitle(title=h1.get_text(strip=True))]
    return name, titles


async def resolve_titles(titles: list[ExtractedTitle]) -> list[dict]:
    sem = asyncio.Semaphore(RESOLVE_CONCURRENCY)

    async def one(pos: int, extracted: ExtractedTitle) -> dict | None:
        async with sem:
            movie = None
            if extracted.imdb_id:
                movie = await resolver.fetch_by_imdb(extracted.imdb_id)
            if movie is None:
                movie = await resolver.resolve_title(extracted.title, extracted.year)
            await asyncio.sleep(RATE_DELAY_SEC)
        if not movie:
            return None
        return {
            "imdb_id": movie.imdb_id,
            "title": movie.title,
            "year": movie.year,
            "director": movie.director,
            "genres": movie.genres,
            "rating": movie.rating,
            "position": pos,
            "source": "bookmark",
        }

    results = await asyncio.gather(*(one(i, t) for i, t in enumerate(titles)))
    return [r for r in results if r]


async def build_backup(links: list[tuple[str, str]]) -> dict:
    playlists: list[dict] = []
    total = len(links)
    for idx, (url, bookmark_title) in enumerate(links, 1):
        t0 = time.time()
        try:
            name, extracted = await titles_for_link(url, bookmark_title)
            if not name:
                name = clean_list_title(bookmark_title)
            items = await resolve_titles(extracted) if extracted else []
            playlists.append(
                {
                    "name": name,
                    "description": url,
                    "sort_by": "position",
                    "sort_order": "asc",
                    "items": items,
                }
            )
            print(
                f"[{idx}/{total}] {name!r}: {len(items)}/{len(extracted)} resolved "
                f"({time.time()-t0:.1f}s)",
                flush=True,
            )
            if idx % 10 == 0:
                partial = {
                    "schema_version": SCHEMA_VERSION,
                    "user_id": USER_ID,
                    "playlists": playlists,
                }
                OUTPUT.write_text(
                    json.dumps(partial, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        except Exception as exc:
            print(f"[{idx}/{total}] FAILED {url}: {exc}", flush=True)
            playlists.append(
                {
                    "name": clean_list_title(bookmark_title),
                    "description": f"FAILED: {url} ({exc})",
                    "sort_by": "position",
                    "sort_order": "asc",
                    "items": [],
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "user_id": USER_ID,
        "playlists": playlists,
    }


async def main() -> None:
    bookmarks_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BOOKMARKS_DEFAULT
    html = bookmarks_path.read_text(encoding="utf-8", errors="replace")
    links = extract_peliculas_links(html)
    print(f"Found {len(links)} links in Peliculas", flush=True)
    backup = await build_backup(links)
    OUTPUT.write_text(json.dumps(backup, indent=2, ensure_ascii=False), encoding="utf-8")
    total_items = sum(len(p["items"]) for p in backup["playlists"])
    print(f"Wrote {OUTPUT} — {len(backup['playlists'])} playlists, {total_items} movies")
    await resolver.close()


if __name__ == "__main__":
    asyncio.run(main())
