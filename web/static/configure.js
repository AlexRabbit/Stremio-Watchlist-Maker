(() => {
  const RAW_API = "__CHANNEL_ORGANIZER_API__";
  const RAW_TOKEN = "__CONFIGURE_API_TOKEN__";
  const DEV_MODE = new URLSearchParams(window.location.search).has("dev");
  const ON_GITHUB_PAGES = /\.github\.io$/i.test(window.location.hostname);

  function isPlaceholder(value) {
    return typeof value === "string" && /^__[A-Z0-9_]+__$/.test(value);
  }

  const CONFIGURE_API_TOKEN = isPlaceholder(RAW_TOKEN) ? "" : RAW_TOKEN;

  function metaApi() {
    const raw = document.querySelector('meta[name="channel-organizer-api"]')?.content?.trim() || "";
    return isPlaceholder(raw) ? "" : raw.replace(/\/$/, "");
  }

  function apiBase() {
    const fromQuery = new URLSearchParams(window.location.search).get("api");
    if (fromQuery && (!ON_GITHUB_PAGES || DEV_MODE)) {
      return fromQuery.replace(/\/$/, "");
    }
    if (DEV_MODE) {
      return (localStorage.getItem("playlist_api_base") || "http://127.0.0.1:7010").replace(/\/$/, "");
    }
    const baked = metaApi();
    if (baked) return baked;
    if (!isPlaceholder(RAW_API)) return RAW_API.replace(/\/$/, "");
    if (ON_GITHUB_PAGES) return "";
    return window.location.origin;
  }

  let BASE = apiBase();
  const params = new URLSearchParams(window.location.search);
  const pathUserId = (() => {
    const parts = window.location.pathname.split("/").filter(Boolean);
    if (parts.length === 2 && parts[1] === "configure" && /^[a-zA-Z0-9]{8,64}$/.test(parts[0])) {
      return parts[0];
    }
    return null;
  })();
  let userId = pathUserId || params.get("user") || localStorage.getItem("playlist_user_id") || "";
  let activePlaylistId = null;
  let itemsSkip = 0;
  let itemsTotal = 0;
  let fileContent = null;
  let pollTimer = null;

  const $ = (id) => document.getElementById(id);

  function bindClick(id, handler) {
    const el = $(id);
    if (el) el.addEventListener("click", handler);
  }

  function showToast(msg, ms = 7000) {
    const el = $("install-toast");
    if (!el) return;
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => { el.hidden = true; }, ms);
  }

  function toStremioInstallUrl(manifestHttpUrl) {
    try {
      const u = new URL(manifestHttpUrl);
      if (u.protocol === "https:") {
        return `stremio://${u.host}${u.pathname}${u.search}`;
      }
    } catch (_) { /* fall through */ }
    return `stremio:///addons?addon=${encodeURIComponent(manifestHttpUrl)}`;
  }

  function openStremioInstall(manifestHttpUrl) {
    const stremioUrl = toStremioInstallUrl(manifestHttpUrl);
    const iframe = document.createElement("iframe");
    iframe.setAttribute("aria-hidden", "true");
    iframe.style.cssText = "display:none;width:0;height:0;border:0";
    iframe.src = stremioUrl;
    document.body.appendChild(iframe);
    setTimeout(() => iframe.remove(), 3000);
  }

  function saveApiBase(url) {
    BASE = url.replace(/\/$/, "");
    localStorage.setItem("playlist_api_base", BASE);
    const input = $("api-server");
    if (input) input.value = BASE;
    if (userId) saveUser(userId);
  }

  function setupProductionUi() {
    if (!ON_GITHUB_PAGES || DEV_MODE) return;
    document.body.classList.add("deploy-private");
    const row = $("api-server-row");
    if (row) row.hidden = true;
  }

  function setupApiServerUi() {
    if (!DEV_MODE) return;
    const row = $("api-server-row");
    const input = $("api-server");
    if (row) row.hidden = false;
    if (input) input.value = BASE;
    bindClick("btn-save-api", async () => {
      const url = ($("api-server")?.value || "").trim() || "http://127.0.0.1:7010";
      saveApiBase(url);
      try {
        await api("/api/health");
        showToast("Connected to API");
        await ensureUser();
        await loadPlaylists();
      } catch (e) {
        showToast(`Cannot reach API (${e.message})`, 12000);
      }
    });
  }

  function saveUser(id) {
    userId = id;
    localStorage.setItem("playlist_user_id", id);
    const userInput = $("user-id");
    if (userInput) userInput.value = id;
    const url = new URL(window.location.href);
    url.searchParams.set("user", id);
    history.replaceState({}, "", url);
    const addonUrl = $("addon-url");
    if (addonUrl) addonUrl.value = `${BASE}/${id}/manifest.json`;
  }

  async function api(path, opts = {}) {
    const timeoutMs = opts.timeoutMs ?? 180000;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const { timeoutMs: _drop, ...fetchOpts } = opts;
    const authHeaders = CONFIGURE_API_TOKEN
      ? { Authorization: `Bearer ${CONFIGURE_API_TOKEN}` }
      : {};
    try {
      const res = await fetch(`${BASE}${path}`, {
        headers: { "Content-Type": "application/json", ...authHeaders, ...fetchOpts.headers },
        signal: controller.signal,
        ...fetchOpts,
      });
      const text = await res.text();
      if (!res.ok) {
        let msg = text;
        try {
          const j = JSON.parse(text);
          msg = j.error || j.message || j.description || text;
        } catch (_) { /* raw */ }
        throw new Error(msg || `HTTP ${res.status}`);
      }
      return text ? JSON.parse(text) : {};
    } catch (err) {
      if (err.name === "AbortError") {
        throw new Error("Request timed out — large backups import in batches automatically; try again.");
      }
      if (err.message === "Failed to fetch") {
        throw new Error("Cannot reach the API (offline, CORS, or HTTPS certificate). Check that the backend is running.");
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  async function importBackupData(data) {
    const playlists = Array.isArray(data.playlists) ? data.playlists : [];
    if (!playlists.length) {
      throw new Error("Backup has no playlists");
    }
    const chunkSize = 4;
    let importedItems = 0;
    let playlistsCreated = 0;
    let itemsSkipped = 0;
    for (let i = 0; i < playlists.length; i += chunkSize) {
      const chunk = playlists.slice(i, i + chunkSize);
      const end = Math.min(i + chunkSize, playlists.length);
      showToast(`Importing playlists ${i + 1}–${end} of ${playlists.length}…`, 5000);
      const res = await api(`/api/users/${userId}/import-backup`, {
        method: "POST",
        body: JSON.stringify({
          schema_version: data.schema_version,
          playlists: chunk,
        }),
        timeoutMs: 300000,
      });
      importedItems += res.imported_items || 0;
      playlistsCreated += res.playlists_created || 0;
      itemsSkipped += res.items_skipped || 0;
    }
    return { imported_items: importedItems, playlists_created: playlistsCreated, items_skipped: itemsSkipped };
  }

  async function ensureUser() {
    if (pathUserId) {
      saveUser(pathUserId);
      return userId;
    }
    if (!userId) {
      const data = await api("/api/users", { method: "POST", body: "{}" });
      saveUser(data.user_id);
    } else {
      saveUser(userId);
    }
    if (!userId) {
      throw new Error("Could not create a user ID — try New ID again.");
    }
    return userId;
  }

  async function requireUserId() {
    if (userId) return userId;
    return ensureUser();
  }

  async function loadPlaylists() {
    if (!userId) return;
    const data = await api(`/api/users/${userId}/playlists`);
    const ul = $("playlist-list");
    if (!ul) return;
    ul.innerHTML = "";
    (data.playlists || []).forEach((pl) => {
      const li = document.createElement("li");
      li.dataset.id = pl.id;
      li.innerHTML = `<span><strong>${escapeHtml(pl.name)}</strong><div class="meta">${pl.sort_by} · ${pl.sort_order}</div></span><span>→</span>`;
      li.onclick = () => selectPlaylist(pl);
      if (pl.id === activePlaylistId) li.classList.add("active");
      ul.appendChild(li);
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  async function selectPlaylist(pl) {
    activePlaylistId = pl.id;
    const detail = $("detail-panel");
    if (detail) detail.hidden = false;
    const title = $("detail-title");
    if (title) title.textContent = pl.name;
    const detailSort = $("detail-sort");
    const playlistSort = $("playlist-sort");
    if (detailSort && playlistSort) {
      detailSort.innerHTML = playlistSort.innerHTML;
      detailSort.value = pl.sort_by;
    }
    const detailOrder = $("detail-order");
    if (detailOrder) detailOrder.value = pl.sort_order;
    itemsSkip = 0;
    await loadPlaylists();
    await loadItems(true);
  }

  async function loadItems(reset = false) {
    if (!activePlaylistId) return;
    if (reset) {
      itemsSkip = 0;
      const grid = $("items-grid");
      if (grid) grid.innerHTML = "";
    }
    const data = await api(`/api/playlists/${activePlaylistId}/items?skip=${itemsSkip}&limit=40`);
    itemsTotal = data.total;
    const count = $("items-count");
    if (count) count.textContent = `(${data.total})`;
    const grid = $("items-grid");
    if (!grid) return;
    (data.items || []).forEach((item) => grid.appendChild(renderItem(item)));
    itemsSkip += (data.items || []).length;
    const more = $("btn-load-more");
    if (more) more.hidden = itemsSkip >= itemsTotal;
  }

  function renderItem(item) {
    const card = document.createElement("article");
    card.className = "item-card";
    card.role = "listitem";
    const poster = `https://images.metahub.space/poster/medium/${item.imdb_id}/img`;
    card.innerHTML = `
      <img src="${poster}" alt="" loading="lazy" decoding="async" onerror="this.style.background='#ddd'">
      <div class="info"><strong>${escapeHtml(item.title)}</strong><br>${item.year || ""}</div>
      <button type="button">Remove</button>`;
    card.querySelector("button").onclick = async () => {
      try {
        await api(`/api/items/${item.id}`, { method: "DELETE" });
        card.remove();
      } catch (err) {
        showToast(`Remove failed: ${err.message}`);
      }
    };
    return card;
  }

  async function pollJob(jobId) {
    const el = $("job-status");
    if (el) el.hidden = false;
    clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      try {
        const job = await api(`/api/jobs/${jobId}`);
        if (el) {
          el.textContent = `Import: ${job.status} — ${job.processed}/${job.total} processed, ${job.matched} matched`;
        }
        if (job.status === "completed" || job.status === "failed") {
          clearInterval(pollTimer);
          await loadItems(true);
          showToast("Import done. Metadata enrichment runs automatically in the background.");
        }
      } catch (err) {
        clearInterval(pollTimer);
        showToast(`Import status error: ${err.message}`);
      }
    }, 2000);
  }

  async function startImport(type, payload) {
    if (!activePlaylistId) {
      showToast("Select a channel first.");
      return;
    }
    try {
      const job = await api(`/api/playlists/${activePlaylistId}/import`, {
        method: "POST",
        body: JSON.stringify({ type, payload, user_id: userId }),
      });
      await pollJob(job.job_id);
    } catch (err) {
      showToast(`Import failed: ${err.message}`);
    }
  }

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab, .tab-panel").forEach((el) => el.classList.remove("active"));
      tab.classList.add("active");
      const panel = $(`tab-${tab.dataset.tab}`);
      if (panel) panel.classList.add("active");
    });
  });

  bindClick("btn-new-user", async () => {
    try {
      const data = await api("/api/users", { method: "POST", body: "{}" });
      saveUser(data.user_id);
      activePlaylistId = null;
      const detail = $("detail-panel");
      if (detail) detail.hidden = true;
      await loadPlaylists();
    } catch (err) {
      showToast(`New user failed: ${err.message}`);
    }
  });

  bindClick("btn-copy-install", () => {
    const url = $("addon-url")?.value;
    if (!url) return;
    navigator.clipboard.writeText(url);
    showToast("Addon URL copied.");
  });

  bindClick("btn-install-stremio", async () => {
    const manifestUrl = $("addon-url")?.value;
    if (!manifestUrl) {
      showToast("Create a User ID first.");
      return;
    }
    try {
      await navigator.clipboard.writeText(manifestUrl);
    } catch (_) { /* optional */ }
    openStremioInstall(manifestUrl);
    showToast("Opening Stremio… If it doesn't open, Addons → paste the copied URL.");
  });

  bindClick("btn-copy-url", () => {
    navigator.clipboard.writeText(window.location.href);
    showToast("Link copied.");
  });

  bindClick("btn-create-playlist", async () => {
    const name = ($("playlist-name")?.value || "").trim();
    if (!name) {
      showToast("Enter a channel name.");
      return;
    }
    try {
      await requireUserId();
      await api(`/api/users/${userId}/playlists`, {
        method: "POST",
        body: JSON.stringify({
          name,
          sort_by: $("playlist-sort")?.value || "position",
          sort_order: $("playlist-order")?.value || "asc",
          content_type: "channel",
        }),
      });
      if ($("playlist-name")) $("playlist-name").value = "";
      await loadPlaylists();
      showToast(`Channel "${name}" created.`);
    } catch (err) {
      showToast(`Create failed: ${err.message}`);
    }
  });

  bindClick("btn-apply-sort", async () => {
    if (!activePlaylistId) return;
    try {
      await api(`/api/playlists/${activePlaylistId}`, {
        method: "PATCH",
        body: JSON.stringify({
          sort_by: $("detail-sort")?.value,
          sort_order: $("detail-order")?.value,
        }),
      });
      await loadPlaylists();
      await loadItems(true);
    } catch (err) {
      showToast(`Sort failed: ${err.message}`);
    }
  });

  bindClick("btn-delete-playlist", async () => {
    if (!activePlaylistId) return;
    if (!confirm("Delete this channel and all movies?")) return;
    try {
      await api(`/api/playlists/${activePlaylistId}`, { method: "DELETE" });
      activePlaylistId = null;
      const detail = $("detail-panel");
      if (detail) detail.hidden = true;
      await loadPlaylists();
    } catch (err) {
      showToast(`Delete failed: ${err.message}`);
    }
  });

  bindClick("btn-import-url", () => startImport("url", ($("import-url")?.value || "").trim()));
  bindClick("btn-import-bulk", () => startImport("bulk", $("import-bulk")?.value || ""));
  bindClick("btn-import-file", () => {
    if (!fileContent) return;
    startImport("file", JSON.stringify(fileContent));
  });

  const importFile = $("import-file");
  if (importFile) {
    importFile.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      fileContent = { content: await file.text(), filename: file.name };
      const btn = $("btn-import-file");
      if (btn) btn.disabled = false;
    });
  }

  bindClick("btn-add-single", async () => {
    if (!activePlaylistId) {
      showToast("Select a channel first.");
      return;
    }
    const title = ($("single-title")?.value || "").trim();
    const year = $("single-year")?.value ? parseInt($("single-year").value, 10) : null;
    const body = title.startsWith("tt") ? { imdb_id: title } : { title, year };
    try {
      await api(`/api/playlists/${activePlaylistId}/items`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      if ($("single-title")) $("single-title").value = "";
      if ($("single-year")) $("single-year").value = "";
      await loadItems(true);
    } catch (err) {
      showToast(`Add failed: ${err.message}`);
    }
  });

  bindClick("btn-load-more", () => loadItems(false));

  bindClick("btn-export", async () => {
    try {
      await requireUserId();
      const data = await api(`/api/users/${userId}/export`);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `channels-backup-${userId}.json`;
      a.click();
    } catch (err) {
      showToast(`Export failed: ${err.message}`);
    }
  });

  const importBackup = $("import-backup");
  if (importBackup) {
    importBackup.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        await requireUserId();
        const data = JSON.parse(await file.text());
        const res = await importBackupData(data);
        showToast(
          `Imported ${res.imported_items} movies in ${res.playlists_created} channels` +
            (res.items_skipped ? ` (${res.items_skipped} skipped)` : ""),
          10000,
        );
        await loadPlaylists();
      } catch (err) {
        showToast(`Backup import failed: ${err.message}`, 12000);
      } finally {
        e.target.value = "";
      }
    });
  }

  setupProductionUi();
  setupApiServerUi();

  (async () => {
    try {
      await ensureUser();
    } catch (err) {
      const hint = DEV_MODE
        ? "Cannot reach API — check the server field above or run run.bat locally."
        : "Cannot reach the API. Try again in a moment, or hard-refresh this page (Ctrl+F5).";
      showToast(hint, 12000);
      console.error("API error:", BASE, err);
      return;
    }
    try {
      await loadPlaylists();
    } catch (err) {
      showToast(`Could not load channels: ${err.message}`);
      console.error(err);
    }
  })();
})();
