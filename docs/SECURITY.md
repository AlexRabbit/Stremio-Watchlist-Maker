# Security

## Public repository

This repo must contain **only** open-source addon code and the static configure UI.

Never commit:

- `.env` or API tokens
- Live API / tunnel URLs
- Server IPs or SSH keys
- Personal bookmark exports or backup JSON

## API (maintainer server)

- `LOCK_CONFIGURE_API` limits `/api/*` to the official GitHub Pages configure origin
- `API_TOKEN` is set on the server and injected at Pages build time via GitHub **Secrets** (not stored in git)
- Stremio routes (`manifest`, `catalog`, `meta`) stay readable per user ID (required by Stremio)

## Local development

- Default bind: `127.0.0.1:7010`
- Use `LOCK_CONFIGURE_API=0` in local `.env`
