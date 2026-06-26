<p align="center">
  <img src="web/static/logo.svg" width="96" alt="Channel Organizer logo">
</p>

<h1 align="center">🎬 Channel Organizer</h1>
<p align="center"><strong>Movie channels in Stremio — no install, no local server for users.</strong></p>

<p align="center">
  <a href="https://alexrabbit.github.io/stremio/configure.html"><strong>→ Open Configure</strong></a>
</p>

---

## Users: start here

1. Open **[alexrabbit.github.io/stremio/configure.html](https://alexrabbit.github.io/stremio/configure.html)**
2. **New ID** → create a channel → paste a [Taste of Cinema](https://www.tasteofcinema.com/) URL → Import
3. Pink **Install in Stremio** button
4. **Discover → Channel** → your lists

No `run.bat`. No Python. Just the GitHub Pages link.

---

## Repo owner: first-time setup

If configure shows **404** or **cannot reach API**, you need two one-time deploys:

| Step | What | Guide |
|------|------|--------|
| 1 | GitHub Pages (UI) | Settings → Pages → **GitHub Actions** → push `main` |
| 2 | Render (shared API) | [render.yaml](render.yaml) Blueprint + set `BASE_URL` |
| 3 | Link them | Repo variable `PUBLIC_API_URL` → re-run Pages workflow |

**Full checklist:** [docs/DEPLOY.md](docs/DEPLOY.md)

---

## Features

- Taste of Cinema import with **multi-page** scraping (`/1/`, `/2/`, …)
- Discover filters: `-by release date`, `-Directors`, `-90s`, genres
- Sample **[BackupExample.json](BackupExample.json)** — 230 channels, 2000+ movies

---

## Tests

```bash
PYTHONPATH=packages python -m pytest tests/ -q
```

---

MIT · [Deploy docs](docs/DEPLOY.md)
