"""Background metadata enrichment for playlist items."""

from __future__ import annotations

import asyncio

from stremio_playlists.config import settings
from stremio_playlists.db.repository import db
from stremio_playlists.logging_setup import get_logger
from stremio_playlists.resolver.cinemeta import resolver

log = get_logger("metadata_worker")


class MetadataWorker:
    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None
        self._sem = asyncio.Semaphore(2)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("Metadata worker started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while self._running:
            jobs = db.get_pending_metadata_jobs(limit=1)
            if not jobs:
                await asyncio.sleep(settings.import_worker_interval_sec)
                continue
            for job in jobs:
                db.update_metadata_job(job["id"], status="processing")
                try:
                    await self._process_job(job)
                    db.update_metadata_job(job["id"], status="completed")
                    if job.get("user_id"):
                        db.bump_manifest_version(job["user_id"])
                except Exception as exc:
                    log.exception("Metadata job %s failed: %s", job["id"], exc)
                    db.update_metadata_job(job["id"], status="failed", error=str(exc))

    async def _process_job(self, job: dict) -> None:
        user_id = job.get("user_id", "")
        items = db.list_items_missing_metadata(user_id=user_id, limit=job.get("limit_count", 200))
        updated = 0
        for item in items:
            async with self._sem:
                await asyncio.sleep(60 / max(settings.import_rate_limit_per_min, 1))
            try:
                movie = await resolver.fetch_by_imdb(item.imdb_id)
                if not movie:
                    movie = await resolver.resolve_title(item.title, item.year)
                if movie:
                    if db.update_item_metadata(
                        item.id,
                        year=movie.year,
                        director=movie.director,
                        genres=movie.genres,
                        rating=movie.rating,
                    ):
                        updated += 1
            except Exception as exc:
                log.warning("Metadata refresh failed for %s: %s", item.imdb_id, exc)
            db.update_metadata_job(job["id"], processed=updated)
        log.info("Metadata job %s updated %d items", job["id"], updated)


metadata_worker = MetadataWorker()
