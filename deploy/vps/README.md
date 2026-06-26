# VPS deployment (see also SPV/stremio-channel-organizer on your machine)

Use a **domain name** for `BASE_URL` and `PUBLIC_API_URL`. Do not commit numeric host addresses.

## Quick path

1. Pack: `SPV/stremio-channel-organizer/scripts/pack-for-vps.ps1`
2. Upload `app/` → `/opt/stremio-channel-organizer` on server
3. `cp deploy/env.example .env` → set `BASE_URL=https://YOUR_PUBLIC_HOSTNAME`
4. `./deploy/install.sh`
5. Nginx: `deploy/nginx-site.conf.example`
6. GitHub variable `PUBLIC_API_URL=https://YOUR_PUBLIC_HOSTNAME`
7. Re-run GitHub Pages workflow

Full steps: `SPV/stremio-channel-organizer/README.md`
