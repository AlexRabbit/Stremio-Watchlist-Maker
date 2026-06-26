# APEX Security Gate — Stremio Playlists (pre-VPS deploy)

Run security-focused units before exposing to the internet.

## Scope: Tier M (API + DB + local server)

| Unit | Status | Notes |
|------|--------|-------|
| U04 AuthN | PASS | Optional `API_TOKEN` bearer |
| U05 Injection | PASS | Parameterized SQL only |
| U06 XSS | PASS | `escapeHtml` in configure UI |
| U09 Secrets | PASS | Log scrub filter |
| U14 Rate limits | PARTIAL | Import worker rate limit |
| U07 Network | WARN | Defaults to 127.0.0.1 — set HOST carefully on VPS |

## Pre-deploy checklist

- [ ] Set `API_TOKEN` in `.env`
- [ ] Bind `HOST=127.0.0.1` unless behind reverse proxy + auth
- [ ] Never commit `.env`
- [ ] Run `pytest tests/test_security.py`

## Findings backlog

- Add reverse-proxy auth for public GitHub Pages → API bridge (future)
