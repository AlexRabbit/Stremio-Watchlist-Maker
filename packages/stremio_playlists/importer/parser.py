"""Title extraction from URLs, bulk text, and files."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup

from stremio_playlists.config import settings
from stremio_playlists.logging_setup import get_logger

log = get_logger("importer")

# Numbered list: "15. The Act of Killing" or "1) Movie Name (1999)"
NUMBERED_RE = re.compile(
    r"^\s*(?:\d+[\.\)]\s*)(.+?)(?:\s*\((\d{4})\))?\s*$"
)
BULLET_RE = re.compile(r"^\s*[-*•]\s+(.+?)(?:\s*\((\d{4})\))?\s*$")
IMDB_LINE_RE = re.compile(r"(tt\d{7,8})")
YEAR_PAREN_RE = re.compile(r"\((\d{4})\)")
TOC_PAGE_SUFFIX_RE = re.compile(r"/(\d+)/?$")
USER_AGENT = "ChannelOrganizer/0.5 (+https://github.com/AlexRabbit/stremio)"


@dataclass
class ExtractedTitle:
    title: str
    year: int | None = None
    imdb_id: str | None = None
    raw: str = ""


def _parse_line(line: str) -> ExtractedTitle | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    imdb = IMDB_LINE_RE.search(line)
    if imdb:
        title_part = IMDB_LINE_RE.sub("", line).strip(" -–—|")
        year_m = YEAR_PAREN_RE.search(line)
        return ExtractedTitle(
            title=title_part or imdb.group(),
            year=int(year_m.group(1)) if year_m else None,
            imdb_id=imdb.group(),
            raw=line,
        )
    for pattern in (NUMBERED_RE, BULLET_RE):
        m = pattern.match(line)
        if m:
            title = m.group(1).strip()
            year = int(m.group(2)) if m.lastindex and m.group(2) else None
            if not year:
                ym = YEAR_PAREN_RE.search(title)
                if ym:
                    year = int(ym.group(1))
                    title = YEAR_PAREN_RE.sub("", title).strip()
            return ExtractedTitle(title=title, year=year, raw=line)
    if len(line) > 1:
        year = None
        ym = YEAR_PAREN_RE.search(line)
        if ym:
            year = int(ym.group(1))
            title = YEAR_PAREN_RE.sub("", line).strip()
        else:
            title = line
        return ExtractedTitle(title=title, year=year, raw=line)
    return None


def parse_bulk_text(text: str) -> list[ExtractedTitle]:
    """Parse newline-separated titles; uses Rust parser if binary exists."""
    rust_bin = settings.rust_parser_bin
    if rust_bin.exists():
        try:
            proc = subprocess.run(
                [str(rust_bin), "--stdin"],
                input=text,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                items = json.loads(proc.stdout)
                return [
                    ExtractedTitle(
                        title=i["title"],
                        year=i.get("year"),
                        imdb_id=i.get("imdb_id"),
                        raw=i.get("raw", ""),
                    )
                    for i in items
                ]
        except Exception as exc:
            log.debug("Rust parser unavailable, using Python: %s", exc)

    results: list[ExtractedTitle] = []
    for line in text.splitlines():
        item = _parse_line(line)
        if item:
            results.append(item)
    return results


def parse_file_content(content: str, filename: str = "") -> list[ExtractedTitle]:
    """Parse .txt or .md files — strips markdown links."""
    if filename.endswith(".md"):
        content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)
        content = re.sub(r"^#+\s+", "", content, flags=re.M)
    return parse_bulk_text(content)


def extract_from_html(html: str, url: str = "") -> list[ExtractedTitle]:
    """Extract movie titles from list-style web pages."""
    soup = BeautifulSoup(html, "lxml")
    candidates: list[str] = []

    article = soup.find("article") or soup.find("main") or soup.body
    if article:
        for tag in article.find_all(["h2", "h3", "h4", "strong", "b", "li"]):
            text = tag.get_text(" ", strip=True)
            if text and len(text) < 200:
                candidates.append(text)
        # Numbered list posts often use <p><strong>N. Title</strong></p>
        for tag in article.find_all("p"):
            text = tag.get_text(" ", strip=True)
            if text and len(text) < 160 and NUMBERED_RE.match(text):
                candidates.append(text)

    if len(candidates) < 3:
        for li in soup.find_all("li"):
            text = li.get_text(" ", strip=True)
            if text:
                candidates.append(text)

    seen: set[str] = set()
    results: list[ExtractedTitle] = []
    skip_words = (
        "comments",
        "pages:",
        "share",
        "subscribe",
        "cookie",
        "rarely is a film",
        "this list",
        "read more",
    )
    for raw in candidates:
        item = _parse_line(raw)
        if not item or item.title.lower() in seen:
            continue
        low = item.title.lower()
        if any(w in low for w in skip_words):
            continue
        if len(item.title) > 100 and not NUMBERED_RE.match(raw):
            continue
        seen.add(item.title.lower())
        results.append(item)

    log.info("Extracted %d titles from %s", len(results), url or "html")
    return results


def normalize_tasteofcinema_url(url: str) -> str:
    """Strip pagination suffix so imports always start at page 1."""
    url = url.split("#")[0].split("?")[0].strip()
    url = TOC_PAGE_SUFFIX_RE.sub("/", url)
    if not url.endswith("/"):
        url += "/"
    return url


def merge_titles(
    batches: Iterable[list[ExtractedTitle]],
) -> list[ExtractedTitle]:
    seen: set[str] = set()
    merged: list[ExtractedTitle] = []
    for batch in batches:
        for item in batch:
            key = item.title.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


async def _fetch_tasteofcinema_list(url: str) -> list[ExtractedTitle]:
    base = normalize_tasteofcinema_url(url)
    batches: list[list[ExtractedTitle]] = []
    page = 1
    while page <= 50:
        page_url = base if page == 1 else f"{base.rstrip('/')}/{page}/"
        try:
            html = await _fetch_html(page_url)
        except Exception as exc:
            if page == 1:
                raise
            log.debug("Taste of Cinema page %d ended: %s", page, exc)
            break
        titles = extract_from_html(html, page_url)
        if not titles:
            if page == 1:
                batches.append([])
            break
        prev = len(merge_titles(batches))
        batches.append(titles)
        total = len(merge_titles(batches))
        if page > 1 and total == prev:
            break
        page += 1
    results = merge_titles(batches)
    log.info("Taste of Cinema: %d titles from %s (%d page(s))", len(results), base, page - 1)
    return results


async def fetch_url_titles(url: str) -> list[ExtractedTitle]:
    import aiohttp

    url_lower = url.lower()
    if "tasteofcinema.com" in url_lower:
        return await _fetch_tasteofcinema_list(url)
    if "letterboxd.com" in url_lower and "/list/" in url_lower:
        return await _fetch_letterboxd_list(url)
    if "imdb.com/list/" in url_lower:
        return await _fetch_imdb_list(url)

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30),
        headers={"User-Agent": USER_AGENT},
    ) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            html = await resp.text()
    return extract_from_html(html, url)


async def _fetch_html(url: str) -> str:
    import aiohttp

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30),
        headers={"User-Agent": USER_AGENT},
    ) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.text()


async def _fetch_letterboxd_list(url: str) -> list[ExtractedTitle]:
    html = await _fetch_html(url)
    soup = BeautifulSoup(html, "lxml")
    results: list[ExtractedTitle] = []
    seen: set[str] = set()
    for link in soup.select('a[href*="/film/"]'):
        href = link.get("href", "")
        slug = href.rstrip("/").split("/film/")[-1].split("/")[0]
        title = link.get_text(" ", strip=True) or slug.replace("-", " ")
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        results.append(ExtractedTitle(title=title, raw=href))
    log.info("Letterboxd list: %d titles from %s", len(results), url)
    return results


async def _fetch_imdb_list(url: str) -> list[ExtractedTitle]:
    html = await _fetch_html(url)
    soup = BeautifulSoup(html, "lxml")
    results: list[ExtractedTitle] = []
    seen: set[str] = set()
    for link in soup.select('a[href*="/title/tt"]'):
        href = link.get("href", "")
        m = IMDB_LINE_RE.search(href)
        if not m:
            continue
        imdb_id = m.group(1)
        if imdb_id in seen:
            continue
        seen.add(imdb_id)
        title = link.get_text(" ", strip=True)
        year_m = YEAR_PAREN_RE.search(title)
        year = int(year_m.group(1)) if year_m else None
        if year_m:
            title = YEAR_PAREN_RE.sub("", title).strip()
        results.append(
            ExtractedTitle(title=title or imdb_id, year=year, imdb_id=imdb_id, raw=href)
        )
    log.info("IMDb list: %d titles from %s", len(results), url)
    return results
