# Security audit (APEX checklist)

Last reviewed: 2026-06-26

## Authentication

- Set `API_TOKEN` in `.env` for production; all `/api/*` routes check Bearer token when configured.
- Stremio protocol routes (`manifest`, `catalog`, `meta`) are intentionally public (required by Stremio).

## Input validation

- User IDs: `[a-zA-Z0-9]{8,64}` regex on Stremio routes.
- Playlist sort fields: allowlist `SORT_FIELDS` in repository.
- Import payloads: size-limited by worker batch; URLs fetched with timeout and custom User-Agent.

## Recommendations

1. **Never expose port 7010 to the public internet** without reverse proxy + TLS + API token.
2. **Bind to 127.0.0.1** (`HOST=127.0.0.1`) for local-only use.
3. **Rotate `API_TOKEN`** if the configure page is shared.
4. Run `pip audit` periodically on `requirements.txt`.
5. SQLite path should stay under `data/` with OS file permissions.

## Dependency scan

```bash
python -m pip install pip-audit
pip-audit -r requirements.txt
```

## CORS

- Default `CORS_ORIGINS=*` is fine for local Stremio; restrict in production deployments.
