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
