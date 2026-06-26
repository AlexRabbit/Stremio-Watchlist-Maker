"""Stremio desktop launcher tests."""

from stremio_playlists.stremio_launcher import (
    _manifest_allowed,
    http_to_stremio_install_url,
    install_message_candidates,
    launch_stremio_install,
)


def test_manifest_allowed():
    assert _manifest_allowed("http://127.0.0.1:7010/abc123/manifest.json")
    assert not _manifest_allowed("http://evil.com/manifest.json")


def test_stremio_install_url_localhost():
    url = "http://127.0.0.1:7010/testuser1234567890/manifest.json"
    stremio = http_to_stremio_install_url(url)
    assert stremio.startswith("stremio:///addons?addon=")
    assert "7010" in stremio
    assert "127.0.0.1" in stremio


def test_install_candidates_addons_route_first():
    url = "http://127.0.0.1:7010/u1/manifest.json"
    candidates = install_message_candidates(url)
    assert candidates[0].startswith("stremio:///addons?addon=")


def test_launch_rejects_foreign_url():
    result = launch_stremio_install("http://evil.com/abc/manifest.json")
    assert result["ok"] is False
