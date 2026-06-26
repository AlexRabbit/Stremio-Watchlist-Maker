# Deploy Channel Organizer

## For everyone (users)

**You do not run anything locally.**

1. Open **https://alexrabbit.github.io/stremio/configure.html**
2. Click **New ID** → create channels → import lists
3. Install addon in Stremio (pink button)
4. Watch in **Discover → Channel**

The configure page is on **GitHub Pages**. Your playlists live on a **shared API** hosted by the project (Render).

---

## For the repo owner (one-time setup)

Do these **once** so Pages + API work for all users.

### Step 1 — Enable GitHub Pages

1. Push this repo to `AlexRabbit/stremio` (project site → `/stremio/` path)
2. GitHub → **Settings → Pages**
3. **Build and deployment → Source:** `GitHub Actions`
4. Push to `main` (or run **Actions → GitHub Pages → Run workflow**)
5. Confirm: https://alexrabbit.github.io/stremio/configure.html loads *(not 404)*

### Step 2 — Deploy the shared API

**Option A — Your VPS (recommended)**

See [deploy/vps/README.md](deploy/vps/README.md) and local pack scripts in `SPV/stremio-channel-organizer/`.

Set GitHub variable `PUBLIC_API_URL` to `https://YOUR_PUBLIC_HOSTNAME` (domain only).

**Option B — Render (free tier)**

1. [render.com](https://render.com) → **Blueprint** → connect repo
2. Set `BASE_URL` to your Render HTTPS URL
3. Set `PUBLIC_API_URL` in GitHub variables

### Step 3 — Wire Pages to your API

1. GitHub repo → **Settings → Secrets and variables → Actions → Variables**
2. Add variable: `PUBLIC_API_URL` = `https://stremio-channel-organizer.onrender.com`
3. Re-run **GitHub Pages** workflow (or push any change to `web/`)

The workflow injects that URL into `configure.html` at build time.

### Step 4 — Verify end-to-end

| Check | URL |
|-------|-----|
| Configure UI | https://alexrabbit.github.io/stremio/configure.html |
| API health | `https://YOUR-RENDER-URL.onrender.com/api/health` |
| Manifest (example) | `https://YOUR-RENDER-URL.onrender.com/{userId}/manifest.json` |

Open configure → **New ID** → should work without `run.bat`.

---

## Architecture

```
Users browser
    → alexrabbit.github.io/stremio/configure.html   (static UI)
    → YOUR-RENDER-URL.onrender.com/api/*          (channels, imports)
Stremio app
    → YOUR-RENDER-URL.onrender.com/{userId}/manifest.json
```

---

## Local development (optional)

Only for contributors — not required for users.

```bat
run.bat
```

- UI: http://127.0.0.1:7010/configure  
- Or Pages UI with `?dev=1&api=http://127.0.0.1:7010`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| **404 on GitHub Pages** | Enable Pages → GitHub Actions; push `web/`; wait for workflow |
| **Configure can't reach API** | Deploy Render; set `PUBLIC_API_URL`; redeploy Pages |
| **Stremio install fails** | Manifest URL must be **Render URL**, not Pages URL |
| **Free Render slow** | First request wakes service; upgrade plan or use paid host |
| **Data lost on Render free** | Free tier disk is ephemeral — use paid disk or external DB for production |

---

## Stremio install link

```
stremio:///addons?addon=https%3A%2F%2FYOUR-RENDER-URL.onrender.com%2F{userId}%2Fmanifest.json
```
