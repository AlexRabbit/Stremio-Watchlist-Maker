# Deploy Channel Organizer

The **configure page** (`web/`) can live on GitHub Pages. The **addon API** (manifest, catalog, import) must run on a machine Stremio can reach.

---

## Option A — Local only (default)

1. Run `run.bat` (Windows) or `python main.py`
2. Open `http://127.0.0.1:7010/configure`
3. Install addon: `http://127.0.0.1:7010/{userId}/manifest.json`

Stremio on the same PC can use `127.0.0.1` directly.

---

## Option B — GitHub Pages (configure UI only)

Pages hosts the static configure UI. Imports still hit your Python server.

### Steps

1. **Push this repo to GitHub** (public or private)

2. **Enable Pages**  
   GitHub → **Settings → Pages** → Source: **GitHub Actions**  
   (or deploy branch `gh-pages` from `/web`)

3. **Workflow** (already included): `.github/workflows/pages.yml`  
   On push to `main`, it publishes the `web/` folder.

4. **Point the UI at your backend**  
   Edit `web/static/configure.js` — set the API base near the top:
   ```javascript
   const DEFAULT_API = "https://your-tunnel-or-vps.example";
   ```
   Or use the configure page query param if supported: `?api=https://...`

5. **Your Pages URL** will look like:
   ```
   https://YOUR_USERNAME.github.io/stremio/configure.html
   ```

6. **Install manifest from your server**, not Pages:
   ```
   https://your-api.example/{userId}/manifest.json
   ```

### What Pages cannot do

- Serve `manifest.json` (needs dynamic user catalogs)
- Run imports / SQLite / background workers
- Proxy Stremio catalog requests

---

## Option C — Remote backend (VPS / cloud)

1. Deploy the Python app to Fly.io, Railway, a VPS, etc.
2. Set environment variables:
   ```env
   HOST=0.0.0.0
   PORT=7010
   BASE_URL=https://your-domain.example
   API_TOKEN=generate-a-long-random-token
   CORS_ORIGINS=https://YOUR_USERNAME.github.io
   ```
3. Put HTTPS in front (Caddy, nginx, or platform TLS)
4. Install: `https://your-domain.example/{userId}/manifest.json`

**Security:** Never expose port 7010 without `API_TOKEN` on a public IP. See [SECURITY.md](SECURITY.md).

---

## Option D — Tunnel for testing

```bash
ngrok http 7010
```

1. Set `BASE_URL` in `.env` to the ngrok HTTPS URL
2. Restart the server
3. Install manifest: `https://xxxx.ngrok-free.app/{userId}/manifest.json`
4. Optional: host configure UI on Pages pointing at the ngrok URL

---

## Stremio install deep link

Encode your manifest URL:

```
stremio:///addons?addon=https%3A%2F%2Fyour-host%2F{userId}%2Fmanifest.json
```

On Windows, `stremio://127.0.0.1:7010/...` may strip the port — use the `addons?addon=` form instead.

---

## Checklist before going public

- [ ] `.env` is **not** committed (see `.gitignore`)
- [ ] `logs/` and `data/*.db` are **not** committed
- [ ] `API_TOKEN` set on any internet-facing deploy
- [ ] `BASE_URL` matches your public HTTPS URL
- [ ] Run tests: `PYTHONPATH=packages python -m pytest tests/ -q`
