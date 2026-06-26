"""Sanic application — Stremio addon + management API + configure UI."""

from __future__ import annotations

import json
import re
from pathlib import Path

from sanic import Sanic, response
from sanic.exceptions import NotFound, SanicException
from sanic.request import Request

from stremio_playlists.addon.handlers import build_manifest, handle_meta
from stremio_playlists.config import ROOT, settings
from stremio_playlists.db.repository import db
from stremio_playlists.logging_setup import get_logger
from stremio_playlists.worker.background import worker
from stremio_playlists.worker.metadata import metadata_worker

log = get_logger("app")
STATIC_DIR = ROOT / "web" / "static"

USER_ID_RE = re.compile(r"^[a-zA-Z0-9]{8,64}$")


def _valid_user_id(user_id: str) -> bool:
    return bool(user_id and USER_ID_RE.match(user_id))


def _cors_headers(
    resp: response.HTTPResponse, request: Request | None = None
) -> response.HTTPResponse:
    allowed = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    req_origin = (request.headers.get("origin") or "").strip() if request else ""
    if "*" in allowed:
        resp.headers["Access-Control-Allow-Origin"] = "*"
    elif req_origin and req_origin in allowed:
        resp.headers["Access-Control-Allow-Origin"] = req_origin
    elif len(allowed) == 1:
        resp.headers["Access-Control-Allow-Origin"] = allowed[0]
    elif allowed:
        resp.headers["Access-Control-Allow-Origin"] = allowed[0]
    else:
        resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Max-Age"] = "86400"
    return resp


def _check_api_auth(request: Request) -> bool:
    token = settings.api_token
    if not token:
        return True
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {token}":
        return True
    return request.args.get("token") == token


def _configure_origins() -> set[str]:
    return {
        o.strip()
        for o in settings.configure_allowed_origins.split(",")
        if o.strip()
    }


def _check_configure_api_access(request: Request) -> bool:
    """Block /api/* unless request comes from the official GitHub Pages configure UI."""
    if not settings.lock_configure_api:
        return _check_api_auth(request)
    if not _check_api_auth(request):
        return False
    origin = (request.headers.get("origin") or "").strip()
    referer = (request.headers.get("referer") or "").strip()
    allowed = _configure_origins()
    prefix = settings.configure_allowed_referer_prefix
    if origin and origin in allowed:
        return True
    if referer and (
        referer.startswith(prefix + "/")
        or referer.startswith(prefix + "?")
        or referer.rstrip("/") == prefix
    ):
        return True
    return False


def create_app() -> Sanic:
    app = Sanic("stremio-playlists")
    app.config.ACCESS_LOG = False
    app.config.REQUEST_MAX_SIZE = 64 * 1024 * 1024
    app.config.REQUEST_TIMEOUT = 300

    @app.listener("before_server_start")
    async def setup(_app: Sanic) -> None:
        db.init()
        queued = db.queue_metadata_backfill()
        if queued:
            log.info("Queued metadata backfill for %d user(s)", queued)
        await worker.start()
        await metadata_worker.start()
        log.info("Server starting on %s:%s", settings.host, settings.port)

    @app.listener("after_server_stop")
    async def teardown(_app: Sanic) -> None:
        await worker.stop()
        await metadata_worker.stop()
        from stremio_playlists.resolver.cinemeta import resolver

        await resolver.close()

    @app.exception(SanicException)
    async def sanic_error(request: Request, exc: SanicException):
        if exc.status_code >= 500:
            log.exception("Request failed: %s", exc)
        return _cors_headers(
            response.json({"error": exc.message}, status=exc.status_code),
            request,
        )

    @app.exception(Exception)
    async def unhandled_error(_request: Request, exc: Exception):
        log.exception("Request failed: %s", exc)
        return response.json({"error": str(exc)}, status=500)

    @app.middleware("request")
    async def protect_management_api(request: Request):
        if request.method == "OPTIONS" or not request.path.startswith("/api/"):
            return
        if not _check_configure_api_access(request):
            raise SanicException("forbidden", status_code=403)

    @app.middleware("response")
    async def cors_middleware(request: Request, resp: response.HTTPResponse):
        return _cors_headers(resp, request)

    @app.options("/<path:path>")
    async def cors_preflight(request: Request, path: str):
        return _cors_headers(response.empty(), request)

    # --- Stremio protocol ---
    @app.get("/")
    async def index(_request: Request):
        return response.redirect("/configure")

    @app.get("/favicon.ico")
    async def favicon(_request: Request):
        logo = STATIC_DIR / "logo.svg"
        if logo.is_file():
            return await response.file(logo, mime_type="image/svg+xml")
        raise NotFound("favicon not found")

    @app.get("/configure")
    async def configure_page(_request: Request):
        html_path = ROOT / "web" / "configure.html"
        return await response.file(html_path)

    @app.get("/<user_id:str>/configure")
    async def user_configure_page(request: Request, user_id: str):
        """Stremio opens {addon-base}/configure when user clicks Configure."""
        if not _valid_user_id(user_id):
            return response.redirect("/configure")
        db.ensure_user(user_id)
        html_path = ROOT / "web" / "configure.html"
        return await response.file(html_path)

    @app.get("/<user_id:str>/manifest.json")
    async def manifest(request: Request, user_id: str):
        if not _valid_user_id(user_id):
            return _cors_headers(
                response.json({"error": "invalid user id"}, status=400),
                request,
            )
        db.ensure_user(user_id)
        return response.json(build_manifest(user_id))

    @app.get("/<user_id:str>/catalog/<type:str>/<path:path>")
    async def catalog_route(request: Request, user_id: str, type: str, path: str):
        if not path.endswith(".json"):
            return response.json({"metas": []})
        inner = path[:-5]
        from stremio_playlists.addon.handlers import handle_catalog

        if "/" in inner:
            catalog_id, extra = inner.split("/", 1)
            return response.json(await handle_catalog(user_id, catalog_id, extra))
        return response.json(await handle_catalog(user_id, inner))

    @app.get("/<user_id:str>/meta/<type:str>/<path:path>")
    async def meta_route(request: Request, user_id: str, type: str, path: str):
        if not path.endswith(".json"):
            return response.json({"meta": None})
        meta_id = path[:-5]
        return response.json(handle_meta(user_id, type, meta_id))

    # --- Management API ---
    @app.get("/api/health")
    async def health(request: Request):
        if settings.lock_configure_api and not _check_configure_api_access(request):
            raise SanicException("forbidden", status_code=403)
        return response.json({"status": "ok", "version": "0.5.1"})

    @app.post("/api/users")
    async def create_user(request: Request):
        body = request.json or {}
        user_id = db.create_user(body.get("name", "My Playlists"))
        return response.json({"user_id": user_id, "configure_url": f"/configure?user={user_id}"})

    @app.get("/api/users/<user_id:str>/playlists")
    async def list_playlists(request: Request, user_id: str):
        if not _check_api_auth(request):
            return response.json({"error": "unauthorized"}, status=401)
        try:
            db.ensure_user(user_id)
            pls = db.list_playlists(user_id)
            return response.json(
                {
                    "playlists": [
                        {
                            "id": p.id,
                            "name": p.name,
                            "description": p.description,
                            "sort_by": p.sort_by,
                            "sort_order": p.sort_order,
                        }
                        for p in pls
                    ]
                }
            )
        except Exception as exc:
            log.exception("list_playlists failed for %s", user_id)
            return response.json({"error": str(exc)}, status=500)

    @app.post("/api/users/<user_id:str>/playlists")
    async def create_playlist(request: Request, user_id: str):
        if not _check_api_auth(request):
            return response.json({"error": "unauthorized"}, status=401)
        try:
            body = request.json or {}
            name = str(body.get("name", "New Channel")).strip()[:120]
            if not name:
                return response.json({"error": "name required"}, status=400)
            db.ensure_user(user_id)
            pid = db.create_playlist(
                user_id,
                name,
                body.get("description", ""),
                body.get("sort_by", "position"),
                body.get("sort_order", "asc"),
                body.get("content_type", "channel"),
            )
            db.bump_manifest_version(user_id)
            return response.json({"id": pid})
        except Exception as exc:
            log.exception("create_playlist failed for %s", user_id)
            return response.json({"error": str(exc)}, status=500)

    @app.patch("/api/playlists/<playlist_id:str>")
    async def update_playlist(request: Request, playlist_id: str):
        if not _check_api_auth(request):
            return response.json({"error": "unauthorized"}, status=401)
        body = request.json or {}
        ok = db.update_playlist(
            playlist_id,
            name=body.get("name"),
            description=body.get("description"),
            sort_by=body.get("sort_by"),
            sort_order=body.get("sort_order"),
        )
        return response.json({"ok": ok})

    @app.delete("/api/playlists/<playlist_id:str>")
    async def delete_playlist(request: Request, playlist_id: str):
        if not _check_api_auth(request):
            return response.json({"error": "unauthorized"}, status=401)
        pl = db.get_playlist(playlist_id)
        ok = db.delete_playlist(playlist_id)
        if ok and pl:
            db.bump_manifest_version(pl.user_id)
        return response.json({"ok": ok})

    @app.get("/api/playlists/<playlist_id:str>/items")
    async def list_items(request: Request, playlist_id: str):
        if not _check_api_auth(request):
            return response.json({"error": "unauthorized"}, status=401)
        skip = int(request.args.get("skip", 0))
        limit = min(int(request.args.get("limit", 50)), 200)
        items, total = db.list_items(playlist_id, skip=skip, limit=limit)
        return response.json(
            {
                "total": total,
                "items": [
                    {
                        "id": i.id,
                        "imdb_id": i.imdb_id,
                        "title": i.title,
                        "year": i.year,
                        "director": i.director,
                        "genres": i.genres,
                        "rating": i.rating,
                        "position": i.position,
                    }
                    for i in items
                ],
            }
        )

    @app.post("/api/playlists/<playlist_id:str>/items")
    async def add_item(request: Request, playlist_id: str):
        if not _check_api_auth(request):
            return response.json({"error": "unauthorized"}, status=401)
        body = request.json or {}
        from stremio_playlists.resolver.cinemeta import resolver

        imdb_id = body.get("imdb_id", "")
        title = body.get("title", "")
        if imdb_id:
            movie = await resolver.fetch_by_imdb(imdb_id)
        elif title:
            movie = await resolver.resolve_title(title, body.get("year"))
        else:
            return response.json({"error": "title or imdb_id required"}, status=400)
        if not movie:
            return response.json({"error": "movie not found"}, status=404)
        item_id = db.add_item(
            playlist_id,
            movie.imdb_id,
            movie.title,
            year=movie.year,
            director=movie.director,
            genres=movie.genres,
            rating=movie.rating,
            source="manual",
        )
        pl = db.get_playlist(playlist_id)
        if pl:
            db.bump_manifest_version(pl.user_id)
        return response.json({"id": item_id, "imdb_id": movie.imdb_id})

    @app.delete("/api/items/<item_id:str>")
    async def remove_item(request: Request, item_id: str):
        if not _check_api_auth(request):
            return response.json({"error": "unauthorized"}, status=401)
        user_id = db.get_item_user_id(item_id)
        ok = db.remove_item(item_id)
        if ok and user_id:
            db.bump_manifest_version(user_id)
        return response.json({"ok": ok})

    @app.post("/api/playlists/<playlist_id:str>/import")
    async def start_import(request: Request, playlist_id: str):
        if not _check_api_auth(request):
            return response.json({"error": "unauthorized"}, status=401)
        body = request.json or {}
        source_type = body.get("type", "bulk")
        payload = body.get("payload", "")
        user_id = body.get("user_id", "")
        if not payload:
            return response.json({"error": "payload required"}, status=400)
        job_id = db.create_import_job(user_id, playlist_id, source_type, payload)
        return response.json({"job_id": job_id, "status": "pending"})

    @app.get("/api/jobs/<job_id:str>")
    async def job_status(request: Request, job_id: str):
        if not _check_api_auth(request):
            return response.json({"error": "unauthorized"}, status=401)
        job = db.get_job(job_id)
        if not job:
            return response.json({"error": "not found"}, status=404)
        return response.json(
            {
                "id": job.id,
                "status": job.status,
                "total": job.total,
                "processed": job.processed,
                "matched": job.matched,
                "failed": job.failed,
                "error": job.error,
            }
        )

    @app.get("/api/users/<user_id:str>/export")
    async def export_data(request: Request, user_id: str):
        if not _check_api_auth(request):
            return response.json({"error": "unauthorized"}, status=401)
        data = db.export_user_data(user_id)
        return response.json(data)

    @app.post("/api/users/<user_id:str>/import-backup")
    async def import_backup(request: Request, user_id: str):
        if not _valid_user_id(user_id):
            return response.json({"error": "invalid user id"}, status=400)
        if not _check_api_auth(request):
            return response.json({"error": "unauthorized"}, status=401)
        try:
            body = request.json or {}
        except Exception:
            return response.json({"error": "invalid json body"}, status=400)
        if not isinstance(body.get("playlists"), list):
            return response.json({"error": "expected { playlists: [...] }"}, status=400)
        try:
            stats = db.import_user_data(user_id, body)
        except Exception as exc:
            log.exception("import-backup failed for %s", user_id)
            return response.json({"error": str(exc)}, status=500)
        return response.json(stats)

    if STATIC_DIR.exists():
        app.static("/static", STATIC_DIR)

    return app
