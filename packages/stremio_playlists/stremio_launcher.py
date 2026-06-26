"""Launch Stremio Desktop install flow (Windows named-pipe IPC)."""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from stremio_playlists.config import settings
from stremio_playlists.logging_setup import get_logger

log = get_logger("app")


def _candidate_exes() -> list[Path]:
    custom = os.getenv("STREMIO_EXE_PATH", "").strip()
    if custom:
        return [Path(custom)]
    localappdata = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(localappdata) / "Programs" / "Stremio" / "stremio-shell-ng.exe",
        Path(localappdata) / "Programs" / "Stremio" / "Stremio.exe",
        Path(r"C:\Program Files\Stremio\Stremio.exe"),
        Path(r"C:\Program Files (x86)\Stremio\Stremio.exe"),
    ]
    if sys.platform == "darwin":
        candidates.insert(
            0, Path("/Applications/Stremio.app/Contents/MacOS/Stremio")
        )
    which = shutil.which("stremio")
    if which:
        candidates.insert(0, Path(which))
    return candidates


def find_stremio_exe() -> Path | None:
    for path in _candidate_exes():
        if path.is_file():
            return path
    return None


def stremio_pipe_path() -> str:
    """Stremio v5 single-instance pipe (see stremio-shell-ng constants)."""
    return rf"\\.\pipe\com.stremio5.{getpass.getuser()}"


def _manifest_allowed(manifest_url: str) -> bool:
    base = settings.base_url.rstrip("/")
    return manifest_url.startswith(f"{base}/") and manifest_url.endswith("/manifest.json")


def http_to_stremio_install_url(manifest_url: str) -> str:
    """Local addons: pass full http URL via /addons route (keeps port).

    Torrentio uses stremio://remote.host/config/manifest.json on port 443.
    localhost:7010 must use stremio:///addons?addon=<encoded http url>.
    """
    return f"stremio:///addons?addon={quote(manifest_url, safe='')}"


def http_to_stremio_direct_url(manifest_url: str) -> str:
    """Direct stremio://host/path — works for remote HTTPS hosts only."""
    from urllib.parse import urlparse

    parsed = urlparse(manifest_url)
    if not parsed.netloc:
        return manifest_url.replace("https://", "stremio://", 1).replace(
            "http://", "stremio://", 1
        )
    return f"stremio://{parsed.netloc}{parsed.path}"


def install_message_candidates(manifest_url: str) -> list[str]:
    stremio_addons = http_to_stremio_install_url(manifest_url)
    stremio_direct = http_to_stremio_direct_url(manifest_url)
    return [stremio_addons, manifest_url, stremio_direct]


def send_stremio_pipe(message: str) -> bool:
    """Send open-media command to running Stremio Desktop (Windows)."""
    if os.name != "nt":
        return False
    pipe = stremio_pipe_path()
    try:
        with open(pipe, "wb") as handle:
            handle.write(message.encode("utf-8"))
            handle.flush()
        return True
    except OSError as exc:
        log.debug("Stremio pipe unavailable (%s): %s", pipe, exc)
        return False


def launch_stremio_install(manifest_url: str) -> dict[str, object]:
    if not _manifest_allowed(manifest_url):
        log.warning("Rejected install launch for URL: %s", manifest_url)
        return {"ok": False, "error": "invalid manifest url for this server"}

    for message in install_message_candidates(manifest_url):
        if send_stremio_pipe(message):
            log.info("Install triggered via Stremio pipe: %s", message)
            return {
                "ok": True,
                "method": "pipe",
                "message": message,
                "hint": "Check Stremio for the Install popup. If missing: Addons → paste (Ctrl+V).",
            }

    exe = find_stremio_exe()
    if exe:
        arg = http_to_stremio_install_url(manifest_url)
        log.info("Starting Stremio with install arg: %s", arg)
        subprocess.Popen(
            [str(exe), arg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return {
            "ok": True,
            "method": "desktop",
            "message": arg,
            "hint": "Stremio is starting — Install popup should appear. Else paste URL in Addons.",
        }

    if os.name == "nt":
        arg = http_to_stremio_install_url(manifest_url)
        log.info("Fallback stremio:// handler: %s", arg)
        os.startfile(arg)  # noqa: S606
        return {"ok": True, "method": "protocol", "message": arg}

    return {
        "ok": False,
        "error": "Stremio Desktop not running. Start Stremio, then try again or paste URL in Addons.",
    }
