<p align="center">
  <img src="web/static/logo.svg" width="96" alt="Channel Organizer logo">
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

Export and import your own backup JSON from the configure page anytime.

---

## Features

- Taste of Cinema import with multi-page scraping
- Discover filters: `-by release date`, `-Directors`, `-90s`, genres
- Personal channels backed by a shared API

---

## Developers

```bash
PYTHONPATH=packages python -m pytest tests/ -q
```

Local UI: `run.bat` → http://127.0.0.1:7010/configure

---

MIT
