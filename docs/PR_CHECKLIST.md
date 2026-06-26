# After merging this PR — one GitHub variable to set

1. **GitHub** → repo **Settings** → **Secrets and variables** → **Actions** → **Variables**
2. Add or update:

| Variable | Value |
|----------|--------|
| `PUBLIC_API_URL` | Your public API base URL (HTTPS, no trailing slash) |

Get the live URL from the VPS tunnel (see deploy log on server):

```bash
docker logs stremio-channel-organizer-tunnel-1 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1
```

Or use your own domain if nginx is configured.

3. **Actions** → **GitHub Pages** → **Run workflow**
4. Open https://alexrabbit.github.io/stremio/configure.html and test **Import backup**

Do **not** commit numeric host addresses or tunnel tokens to the repo.
