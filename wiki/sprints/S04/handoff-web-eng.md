---
type: handoff
owner_agent: web-eng
status: draft
sources:
  - "S04-brief.md"
  - "../../design/DESIGN.md"
  - "../../design/screens/desktop-launcher.md"
last_reviewed: 2026-11-05
---
# S04 handoff: web-eng (hub pages, API base, Tauri connect)

## Delivered
- `app/src/lemmata/web/hub/` (index.html, hub.css, hub.js): pair (8-char code), GitHub device flow (large code, Copy with non-secure-context fallback, Open GitHub target=_blank, polling at `interval`, denied/expired Retry, avatar+login, Sign out), projects list, New project (repo search, zip drop or file button, progress, opens `/p/<pid>/`). No innerHTML, no inline script/handlers; inline styles only through `el.style` (CSP-safe).
- `web/app.js`: `API_BASE` from `location.pathname`, `apiUrl()` used for fetch, export href, raw img. Under `/p/<pid>/` with `/api/hub/status` reachable: "← Projects", "Sync now", "Upload paper zip" ("Paper version N uploaded · rescanned"). Single-project mode unchanged (no hub probe at `/`). `app.css`: narrow-window tweak for the extra buttons.
- `desktop/`: launcher "Lemmata server" block (URL prefilled and remembered in `server.json`), probe then navigate, File > Connect to Server... / Disconnect, auto-reconnect on launch, unreachable banner (Retry / Use locally), `on_navigation` (only hub origin, loopback and local pages stay; others open in the browser) and `on_new_window` (target=_blank opens in the default browser). Remote page gets no capability. tokio features `net`, `io-util` added. `cargo build --offline` is warning-free.
- `app/tests/mock_hub.py` (mock hub with CSP header and a fixture-engine proxy for `/p/<pid>/api`).

## Verified (Playwright, Chromium)
Mock hub and real `lemmata hub serve` with `tests/fake_github.py`: pair (wrong then right code), device flow, repo search, create with zip, open project UI under `/p/<pid>/` (all API calls under `/p/<pid>/api/`), upload toast, Sync now, Projects row counts, sign out. Mock only: denied/expired. Screenshots `app/docs/screens/s04-*.png`. 85 existing tests pass.

## Findings and gaps
- Real `GET /api/hub/status` shape: `{paired, user, github_connected, ...}`; hub.js accepts that and the brief-style `github.user`. Real `POST /api/hub/projects` returns the bare project (brief says `{project}`); hub.js accepts both.
- CSP: app.js is fine under the hub CSP; vendored `cytoscape.min.js` triggers one "Applying inline style" violation (graph still renders). Add `style-src 'self' 'unsafe-inline'` or accept the console noise.
- POST without an `Origin` header gets 403 "origin not allowed" from the hub (browsers send it; scripted clients must).
- Tauri not run on a Mac: the navigation guard, new-window handler, probe and menus compile but are untested at runtime; launcher checked only with a stubbed `__TAURI__`. The server block sits below the fold at 720x520 (scrolls).
- Hub GitHub avatars need https://avatars.githubusercontent.com (allowed by the CSP).
- Not done: delete project, DESIGN.md/desktop-launcher.md screen specs for the new UI (designer task).
