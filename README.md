<p align="center">
  <img src="web/static/logo.svg" width="96" alt="Stremio Watchlist Maker logo">
</p>

<h1 align="center">🎬 Stremio Watchlist Maker</h1>
<p align="center"><strong>Movie channels in Stremio — configure in the browser, watch in Discover.</strong></p>

<p align="center">
  <a href="https://alexrabbit.github.io/Stremio-Watchlist-Maker/configure.html"><strong>→ Open Configure</strong></a>
</p>

---

## Users

1. Open **[alexrabbit.github.io/Stremio-Watchlist-Maker/configure.html](https://alexrabbit.github.io/Stremio-Watchlist-Maker/configure.html)**
2. **New ID** → create a channel → import a list URL (e.g. [Taste of Cinema](https://www.tasteofcinema.com/))
3. **Install in Stremio** (pink button)
4. **Discover → Channel** → your lists

### Try the sample backup

1. Download **[BackupExample.json](BackupExample.json)** from this repo
2. Open [configure](https://alexrabbit.github.io/Stremio-Watchlist-Maker/configure.html) → **New ID**
3. **Import backup** → select the file (large — imports in batches)

Export and import your own backups anytime from the configure page.

---

## Features

- Taste of Cinema import with multi-page scraping
- Discover filters: `-by release date`, `-Directors`, `-90s`, genres
- Sample **[BackupExample.json](BackupExample.json)** — 230 channels, 2000+ movies

---

## Developers

```bash
PYTHONPATH=packages python -m pytest tests/ -q
```

Local UI: `run.bat` → http://127.0.0.1:7010/configure

---

MIT
