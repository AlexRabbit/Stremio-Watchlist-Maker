# Deploy overview

## Users

Open **https://alexrabbit.github.io/Stremio-Watchlist-Maker/configure.html** — no local install required.

## Architecture

| Part | Host |
|------|------|
| Configure UI | GitHub Pages (`/Stremio-Watchlist-Maker/`) |
| API + Stremio addon | Maintainer's HTTPS server |

Stremio installs the addon from `{API_URL}/{userId}/manifest.json`, not from GitHub Pages.

## Maintainer setup (private)

Do **not** commit to this repo:

- API URLs or tunnel hostnames
- Tokens, `.env`, or server addresses
- Personal bookmarks or backup files

Add GitHub **Actions secrets** (not Variables):

| Secret | Purpose |
|--------|---------|
| `PUBLIC_API_URL` | HTTPS API base (no trailing slash) |
| `CONFIGURE_API_TOKEN` | Same as `API_TOKEN` on your server |

Then run the **GitHub Pages** workflow.

Server install scripts stay in your **private** ops folder, not in this repo.

## Auto-sync tunnel URL (quick tunnels)

If the API uses an ephemeral `trycloudflare.com` URL, install **tunnel-sync** from the Playlists-Randomizer repo (`deploy/ops/tunnel-sync/`) on your VPS. It watches `/data/stremio-channel-organizer/logs/tunnel.url`, updates the GitHub secret `PUBLIC_API_URL`, updates `BASE_URL` in the server `.env`, and triggers the **GitHub Pages** workflow automatically after reboot.

```sh
# On VPS (see Playlists-Randomizer docs/DEPLOY.md for full setup)
printf '%s' 'YOUR_GITHUB_PAT' > /etc/tunnel-sync/github.token
chmod 600 /etc/tunnel-sync/github.token
/data/ops/tunnel-sync/.venv/bin/python /data/ops/tunnel-sync/sync.py --once
```

`CONFIGURE_API_TOKEN` is **not** rotated when the tunnel URL changes. Users only see `github.io` and `trycloudflare.com` — never the VPS IP.
