"""Background import job processor."""

from __future__ import annotations

import asyncio
import json

from stremio_playlists.config import settings
from stremio_playlists.db.repository import db
from stremio_playlists.importer.parser import (
    ExtractedTitle,
    fetch_url_titles,
    parse_bulk_text,
    parse_file_content,
)
from stremio_playlists.logging_setup import get_logger
from stremio_playlists.resolver.cinemeta import resolver

log = get_logger("worker")


class ImportWorker:
    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None
        self._rate_sem = asyncio.Semaphore(settings.import_rate_limit_per_min)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("Import worker started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("Import worker stopped")

    async def _loop(self) -> None:
        while self._running:
            jobs = db.get_pending_jobs(limit=settings.import_batch_size)
            if not jobs:
                await asyncio.sleep(settings.import_worker_interval_sec)
                continue
            for job in jobs:
                db.update_job(job.id, status="processing")
                try:
                    await self._process_job(job.id)
                except Exception as exc:
                    log.exception("Job %s failed: %s", job.id, exc)
                    db.update_job(job.id, status="failed", error=str(exc))

    async def _extract_titles(self, source_type: str, payload: str) -> list[ExtractedTitle]:
        if source_type == "url":
            return await fetch_url_titles(payload.strip())
        if source_type == "bulk":
            return parse_bulk_text(payload)
        if source_type == "file":
            data = json.loads(payload)
            return parse_file_content(data.get("content", ""), data.get("filename", ""))
        return []

    async def _process_job(self, job_id: str) -> None:
        job = db.get_job(job_id)
        if not job or not job.playlist_id:
            return
        titles = await self._extract_titles(job.source_type, job.source_payload)
        db.update_job(job_id, total=len(titles), processed=0, matched=0, failed=0)
        matched = failed = processed = 0
        for item in titles:
            async with self._rate_sem:
                await asyncio.sleep(60 / max(settings.import_rate_limit_per_min, 1))
            processed += 1
            try:
                if item.imdb_id:
                    movie = await resolver.fetch_by_imdb(item.imdb_id)
                else:
                    movie = await resolver.resolve_title(item.title, item.year)
                if movie:
                    added = db.add_item(
                        job.playlist_id,
                        movie.imdb_id,
                        movie.title,
                        year=movie.year,
                        director=movie.director,
                        genres=movie.genres,
                        rating=movie.rating,
                        source=job.source_type,
                    )
                    if added:
                        matched += 1
                    else:
                        failed += 1  # duplicate
                else:
                    failed += 1
                    log.warning("No match for %r", item.title)
            except Exception as exc:
                failed += 1
                log.warning("Resolve failed for %r: %s", item.title, exc)
            db.update_job(
                job_id,
                processed=processed,
                matched=matched,
                failed=failed,
            )
        db.update_job(job_id, status="completed")
        if job.user_id:
            db.bump_manifest_version(job.user_id)
            if db.list_items_missing_metadata(user_id=job.user_id, limit=1):
                db.create_metadata_job(job.user_id, limit=300)


worker = ImportWorker()
