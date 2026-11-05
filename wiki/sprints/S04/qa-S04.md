---
type: qa-report
owner_agent: qa
status: draft
sources:
  - "S04-brief.md (contract)"
  - "../../architecture/threat-model.md (CTO must-fix M1-M11, QA checklist section 7)"
  - "handoff-pipeline-eng-hub.md, handoff-pipeline-eng-mcp.md, handoff-web-eng.md (claims verified here, not taken as facts)"
  - "code on branch s04-hub-remote @ a965b20: app/src/lemmata/hub/*.py, server.py, mcp.py, engine/tree.py, web/hub/hub.js; app/tests/fake_github.py"
  - "../S02/qa-S02-localhost-demo.md (golden set, section 2)"
last_reviewed: 2026-11-05
---
# QA report: S04 hub, GitHub sign-in, MCP (branch `s04-hub-remote`, commit a965b20)

## Verdict: **block**
The hub works end to end on Linux with the fake GitHub: pairing, device flow, repo list, clone, zip upload, checkpoint, alarm after a second upload, sync, and an alarm after an upstream commit. It worked over raw HTTP, in Chromium, and through the official MCP SDK client and `claude mcp list`. All 85 unit tests pass. Single-project `lemmata demo` still matches the S02 golden set. Most attack attempts failed: no token leak, no path escape, no zip escape, and no CSRF or DNS-rebinding route.

I am blocking because one CTO must-fix item fails (**M9**) and three are only partly done (**M3, M6, M8**). There is also one new DoS defect (**D2**: an unauthenticated memory blow-up through a negative `Content-Length`). Each fix is small. After them, ship with caveats, plus the Mac-only checks in section 6. Merging to main still needs Juhyeong's approval.

## 1. Tests
- `PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_*.py'`: **85 tests OK** in 15.9 s, Python 3.13.18 and git 2.43.0. Only ResourceWarnings are printed.

## 2. End to end over HTTP (real `lemmata hub serve`, temp data dir `/tmp/qa-s04/data`, `app/tests/fake_github.py` as GitHub)
| Step | Result |
|---|---|
| `GET /api/hub/status` unauthenticated | 200, `authenticated:false`, no owner/user leaked |
| 5 wrong codes, then the right code | 5x 403 `bad_code`; `pairing.json` `wrong:5`; right code afterwards → 403 (locked) |
| expired code (`expires` set in the past) | 403; `hub pair-code` mints a new code |
| right code (lower case, with Origin) | 200, 43-char token, `dev_…`; cookie `HttpOnly; SameSite=Strict; Path=/`; reuse of the code → 403 (one-time) |
| `hub devices` / `hub revoke` | listed; a revoked token → 401 |
| device flow start/poll → approve | `pending` then `ok`; `github.json` 0600; owner `alice` saved |
| second account (`bob`) signs in | 403 `not_owner`, `github.json` not written; denied → `denied`; expired → `expired` |
| repos, `?q=evil` | sorted by pushed_at, filtered |
| create project `alice/tiny-transformer` (sample code repo at K2) | 201 `tiny-transformer-831d` |
| upload zip v1 (sample paper P2, single top folder, stripped) | `{"version":1, files:6}` |
| checkpoint `cp1` | 0 groups |
| upload zip v2 (appendix lr 3e-4 → 1e-3) | `version 2`; group `ev:commit:paper:d5cf62b…`, cause "Overleaf upload …", changed `tex:app:hparams` |
| push K3 (lr change in `configs/default.yaml`) to the fake repo; `POST …/sync` | `changed:true`; group `ev:commit:code:0d9f787…` with downstream `run:code/train_main` (1), `file:code/results/table2.csv` (2), `tex:tab:main` (3), which matches golden A1; second sync `changed:false` |

**Browser (Chromium 153 via Playwright, 1280x800), screenshots in `/tmp/qa-s04/shots/`:** I paired with a wrong code and then the right one (02-04), then ran the device flow with the code shown (05) and auto-advanced after approval. Next: the projects list (06), New project (07) with the repo search, the zip attached (08), Create, and the project UI under `/p/tiny-transformer-48d7/` (09). The top bar shows Projects, Sync now, Upload paper zip, and Checkpoint. I set the checkpoint from the UI (10-11). After "Upload paper zip" with v2, the toast read "Paper version 2 uploaded · rescanned" and App. B was flagged (12). After a new upstream commit ("batch size 256"), "Sync now" gave 5 items to recheck, the code group appeared (13), and I returned to Projects (14). The repo description `<img src=x onerror=…>` rendered as text (0 `<img>` in the list).
Console under `/p/<pid>/`: **no errors**. On the hub pages I saw: the expected CSP block of the fake avatar URL (x3), the 403 from the deliberate wrong code, and one 401 on first load (D11).

## 3. MCP
- Raw JSON-RPC on `/mcp` gave these results. `initialize` echoes 2025-06-18 and 2024-11-05 and maps an unknown version to 2025-06-18; serverInfo is `lemmata 0.1.0` and capabilities are `{tools:{}}`. `notifications/initialized` → **202**, empty body. `ping` OK. `tools/list` → **9 tools**: 7 with `readOnlyHint:true`, while `set_triage` and `sync` have `readOnlyHint:false, destructiveHint:false, idempotentHint:true`. `GET /mcp` → 405. Batch → 400/-32600. Parse error → 400/-32700. A 70 KB body → 413. `text/plain` → 400. Unknown tool → -32602.
- Auth results:
  - no Authorization → 401
  - Basic auth → 401
  - cookie only, or cookie plus a good Origin → **401**
  - bad Bearer → 401
  - Bearer with `Origin: http://evil.example`, `http://127.0.0.1:8888`, or `null` → **403**
  - Bearer with `Origin: http://localhost:18765` → 200
  - `Host: evil.example` → 403
- Each tool on the created project returned `structuredContent`:
  - `list_projects`: OK
  - `project_status`: works by pid; a name or repo matching two projects gives an `isError` that lists the pids
  - `alarms`: A1/A2 with file:line
  - `explain`: works with and without `group`
  - `findings`: works with and without `check`
  - `node`: works by id and by label "Table 2"
  - `search`: OK
  - `set_triage`: the note became "… [by VS Code QA]"; a bad state gives `isError`
  - `sync`: reported "nothing new"
- **Official SDK** `@modelcontextprotocol/sdk` 1.32.2, `StreamableHTTPClientTransport`, token from `lemmata hub token`: connect (protocol 2025-06-18), listTools (9, with annotations), callTool alarms (2 groups), search, ping. With no token or a bad token the client fails cleanly with 401. **`claude` CLI 2.1.318** (temp HOME): `claude mcp add --scope user --transport http …` then `claude mcp list` → `lemmata … (HTTP) - √ Connected`.

## 4. CTO must-fix items
| # | Item | Result | Evidence (attack attempted) |
|---|---|---|---|
| M1 | Confine engine file access | **pass** | Planted real symlinks in a hub clone (`real_leak.tex/.yaml -> ../../../hub/github.json`, `real_hubdir -> ../../../hub`, `passwd.csv -> /etc/passwd`). Uploaded a paper with `\input{../../../hub/secret}`, `\input{../../<other pid>/paper/zz_other}`, `\input{../code/real_leak}`, an absolute `\input{/tmp/…}`, and `\input{../paper/../../../hub/secret}`. Then rescanned and read every `/p/<pid>/api/*` GET, including export, `/api/file`, and `/api/raw`, plus `..`, `%2e%2e` and `.git/config` paths, static `/p/<pid>/../..`, and MCP findings/search/node/explain. Sentinels, token, and `/etc/passwd` content appeared nowhere (`leakscan.py`: "LEAKS: none"). |
| M2 | Origin/Host/CSRF | **pass** | Cookie POST/DELETE with no Origin, `http://127.0.0.1:8888`, `https://127.0.0.1:18765`, `null`, or evil → 403. Correct Origin → 200. Bearer with no Origin → 200; Bearer with evil Origin → 403. Cookie `text/plain` → 400; multipart to the zip route → 400. Host evil, missing, or `127.0.0.1.nip.io` → 403. No `Access-Control-*` headers; OPTIONS → 501. |
| M3 | Bind + Funnel | **partial** | A fake `tailscale` CLI (status reports 192.0.2.2) made the hub bind only `127.0.0.1` and `192.0.2.2`. A connection *from* 192.0.2.2 (non-Tailscale) was closed with 0 bytes, while loopback and 127.0.0.2 were served. `peer_ok` table correct, including `100.63.255.255`/`100.128.0.1` (false) and v4-mapped addresses. With fake `funnel status` "Funnel on … 18766", serve exits 1. **Gaps:** no retry until Tailscale has an address (D6), and `Tailscale-Funnel-Request` is not dropped (request → 200). |
| M4 | Token never in argv/logs/config | **pass** | The git wrapper logged every argv: the token and the base64 header appear in 0 lines. The header travels only as `GIT_CONFIG_KEY_0=http.<github_web>/.extraHeader`. A `ps` sampler during a 1 s-delayed fetch (68 samples with git running) found 0 hits. `.git/config` holds no token. `grep -r` of the data dir finds the token only in `hub/github.json`; stdout log 0 hits. Failed clones (bad branch, missing repo) return scrubbed stderr with no token. |
| M5 | Hardened git | **pass (with a note)** | clone/fetch/merge/add/commit argv carry `core.hooksPath=/dev/null`, `core.symlinks=false`, `protocol.allow=never` + `protocol.https.allow=always` (+http only under `LEMMATA_GIT_ALLOW_HTTP=1` with a loopback github_web), `http.followRedirects=false`, `credential.helper=`, `submodule.recurse=false`, `core.fsmonitor=false`. The env carries `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_TERMINAL_PROMPT=0`, `GIT_LFS_SKIP_SMUDGE=1`, `GIT_OPTIONAL_LOCKS=0`, `GIT_ASKPASS=/bin/false`, and `--template=<empty dir>`, `--no-recurse-submodules`, `--`. The attack repo (symlinks, `.lfsconfig` to a foreign URL, `.gitmodules` `file:///etc`, `.gitattributes filter=lfs`) cloned with symlinks as plain files, no `sub/`, and no hooks dir. This box's `/etc/gitconfig` has a `git-lfs` filter with `required=true`, and it was correctly ignored. `core.protectHFS/NTFS` are not passed explicitly; they rely on git defaults (see section 6). Engine reads (`run_git`) are not hardened (D10). |
| M6 | Zip ingest | **partial** | **Rejected** with 400 and nothing written outside the temp dir (`find -newer` check): `../../x`, `a/../../../../../tmp/x`, `/tmp/x`, `C:/x`, symlink, FIFO, `.git/hooks/post-commit`, `.GIT/config`, `proj/.git/config`, `.git/` dir entry, `Main.tex`+`main.tex`, backslash, `..`, 5,001 files, a non-zip, the encrypted flag, a 10.4 MB → 10 GB bomb, and 600 x 1 MB. Bodies stream to `tmp/` (0600). A missing Content-Length → 411; over 100 MB → 413 before reading. **Gaps:** `.git./config`, `GIT~1/config`, and `.git /config` pass the check and fail later in `git add`, which leaves the paper half-replaced (D3). `.g\u200cit/` and an NFC+NFD `café.tex` duplicate are accepted (D8). There is no 50 MB per-file cap. A lying-header bomb is stopped, but as a 500 rather than a 400 (D7). |
| M7 | Hub pages XSS + CSP | **pass (deviations)** | No `innerHTML`/`insertAdjacentHTML`/`eval` in `hub.js` or `app.js`. The repo description `<img onerror>` and the project name `<script>` render as text. CSP and nosniff are on all hub responses, but the CSP adds `style-src 'unsafe-inline'` and `img-src data:` and lacks `form-action 'self'` (D12). |
| M8 | MCP output + write tools | **partial** | Annotations are correct. Text output is cleaned: ESC and BEL are stripped, a 3,000-char injected line is cut to about 200 chars, `</user-file-quote>` is neutralised, and the data-not-instructions notice is present. **Gaps (D4):** the notice comes at the *end*, not at the start. Triage has no structured `by`: UI writes record nothing, and MCP appends the user-chosen device *name* to the note text. `structuredContent` still carries raw `\x1b`/`\x07` from repo text. |
| M9 | Setup line `--scope user` + warning | **FAIL** | `lemmata hub token --device X` prints `claude mcp add --transport http lemmata http://vm:18765/mcp --header "Authorization: Bearer …"`. It has no `--scope user` and no warning against `--scope project` (`hub/cli.py:115`). The MCP handoff's doc line is correct; the CLI is not. |
| M10 | Files at rest | **pass (Linux)** | `~/Lemmata`, `hub/`, `projects/*`, `tmp/`, `trash/`, `empty-template/` are 700. `config.json`, `tokens.json`, `github.json`, `pairing.json`, and `project.json` are 600. Writes use mkstemp+fchmod+replace, the serve umask is 077, and codes are compared with `hmac.compare_digest`. `hub.log` is created by launchd, so Mac only. |
| M11 | Input validation | **pass (deviations)** | 400 for `../hub`, `a/..`, `--upload-pack=…`, `alice/x y`, `.git` suffix, and a non-string repo. Branch values `-uhelp`, `--upload-pack=…`, `../../x`, `a..b`, and a newline → 400. pid `..%2fhub` and upper-case → 404. Nothing touched `/tmp/qa-pwn*`. **Deviations (D9):** `-x/y`, `a/.`, and owner/name over 39/100 chars reach git (502 "not found"), though only as a URL after `--`, so they are not exploitable. The pid regex is `^[a-z0-9-]{1,64}$`, not `…-[0-9a-f]{4}$`. github_api/web cannot be set over HTTP or by `hub config` flags. |

## 5. Defects (ranked)
1. **D1 (M9, blocking).** The setup line lacks `--scope user` and the warning. Repro: `lemmata hub token --device "VS Code"`. Fix: change the print in `hub/cli.py:115` and add one warning line.
2. **D2 (medium, new, unauthenticated DoS).** A negative `Content-Length` bypasses the 64 KB cap. `server.Handler._body` (server.py:258-263) and `HubHandler._mcp` (routes.py:172-177) check only `n > MAX_BODY`, and `rfile.read(-1)` then reads to EOF into memory. Repro: `POST /api/hub/pair` (public) with `Content-Type: application/json`, `Content-Length: -1`, then stream 200 MB. Hub RSS went from 39 MB to 246 MB, and it answers 400 only after EOF. Reachable by any tailnet peer or local process. Fix: reject `n < 0` with 400. A socket read timeout is also advisable.
3. **D3 (medium).** An upload that `git add` rejects leaves `paper/` half-replaced. Repro: a zip with `main.tex`, `new_file.tex`, and `.git./config` (or `GIT~1/config`, `.git /config`) → 502 `git add failed: invalid path`. The working tree is replaced, nothing is committed, there is no rescan, and `git status` shows `D .gitattributes`, `M main.tex`, `?? new_file.tex`, `?? ".git /"`. On macOS (`core.protectHFS` on) `.g\u200cit/…` will take the same path. Fix: reject NTFS/HFS `.git` aliases in `safe_extract`, and stage into a fresh index or restore the tree on failure.
4. **D4 (M8 partial).** The notice should come first. Add a structured `by` (`ui:<device_id>` / `mcp:<device_id>`) on triage writes and show it in the UI. Clean `structuredContent` strings too. Repro: `POST /p/<pid>/api/triage` with a cookie and see that the entry has no `by`. MCP `findings` on a line with ESC returns the raw `\u001b` in `structuredContent.findings[0].evidence[0].text`.
5. **D5 (medium, product).** Hub projects never do the online reference lookup. `Manager.app()` builds `Engine(root)` offline, and there is no hub setting for it. Repro: `GET /p/<pid>/api/findings` shows check `reference_unmatched` as `status: "ran"`, `count 0`, with the note "6 not checked". The MVP's reference-existence check is silently inert in hub mode, and "ran" overstates what happened. Needs a decision from Juhyeong and the lead (opt-in per hub).
6. **D6 (M3 partial).** There is no retry for a Tailscale address at start, and no Funnel-header drop. Repro: run `lemmata hub serve` with Tailscale not yet up. It prints "listening on loopback only" and never binds the Tailscale IP. Under launchd at boot this race makes the hub unreachable from the MacBook until a restart. Also, `GET /api/hub/projects` with `Tailscale-Funnel-Request: ?1` → 200.
7. **D7 (low).** Some bad inputs give 500s with server paths. A zip with a file `a` and `a/b.tex` → 500 `FileExistsError: … /tmp/qa-s04/data/tmp/up-…/a`. A lying-size zip → 500 `BadZipFile`. Clone errors echo the absolute data path. These should be 400 with a short message.
8. **D8 (low, M6).** No NFC/zero-width normalisation and no 50 MB per-file cap. Repro: a zip with NFC and NFD `café.tex` → 200 (3 files). On APFS one silently overwrites the other.
9. **D9 (low, M11).** `code_repo` `-x/y` and `a/.` are not rejected with 400. The regex lacks the `{1,39}`/`{1,100}` bounds.
10. **D10 (low, residual).** Engine `run_git`/`cat-file` (`engine/tree.py:11-19, 213-216`) use the user's system and global git config inside hub clones. Today that means the git-lfs filter from `/etc/gitconfig`. No repo-supplied program runs (I confirmed `subprocess` in `engine/` is git only, with no TeX or BibTeX), but this should get the M5 env (`GIT_CONFIG_NOSYSTEM`, `GIT_CONFIG_GLOBAL=/dev/null`) in hub mode.
11. **D11 (low, UX).** In a fresh browser on a hub that already has any paired device, `status.paired` is hub-wide, so `hub.js` shows Projects, gets a 401, and then shows the pairing page (one console 401). `pairedOf()` should use `authenticated`.
12. **D12 (low).** CSP deviations listed under M7. `PUT /mcp` and `OPTIONS` return stdlib 501 HTML without the CSP header.
13. **D13 (info).** On `not_owner`, the other account's new OAuth token is dropped but not revoked at GitHub.
14. **D14 (info).** The demo golden set passes 10/10 findings with exact file:line, 2 proposed links, A1 (downstream depths 1/2/3) and A2. The code SHAs are now K3 `0d9f787` (S02 table: `2836100`). Paper SHAs are unchanged (P3 `02c7676`). Update the SHAs when `golden.json` is written.

## 6. Only the Macs can verify
- **Tailscale:** real `tailscale status --json` parsing (IPv4+IPv6 binds, MagicDNS short and full names in the Host allow-list), real `tailscale funnel status` text, the start-at-login race (D6), a MacBook → mini connection over the tailnet, and the Tailscale ACL from threat model section 6.
- **launchd:** `hub install`/`uninstall`, the plist, `hub.log` creation mode (launchd creates it; the dir is 0700) and its content, KeepAlive restarts, PATH.
- **APFS and Apple Git:** case-insensitive and normalization-insensitive behaviour (D3, D8), the `core.protectHFS` default, the Apple Git version against 2.39.4/2.45.1 (N8), and `ps` env visibility on macOS.
- **Real GitHub:** device flow with client id `Ov23lij3uNF6pctpA6yH` (this box's proxy blocks it), `/user/repos` pagination, a private clone and fetch with the scoped header, and avatars under the CSP.
- **Tauri:** Connect to server, remembered URL, auto-reconnect, the unreachable banner (Retry / Use locally), the navigation guard and new-window handler, File menu items, WebKit cookie persistence for `http://<magicdns>:8765`, and the Copy button.
- **Claude Code in VS Code** against `http://dais-juhyeongs-mac-mini:8765/mcp` with a real prompt (the five prompts in the MCP handoff), including how it treats the 401 without `WWW-Authenticate`.

## 7. Artefacts
Scripts are in `/tmp/qa-s04/scripts/` (fake GitHub runner, git argv wrapper `/tmp/qa-s04/gitwrap/git`, ps sampler, leak scan, MCP raw/tools, zip and bomb generators, Playwright flows, SDK client `/tmp/qa-s04/mcpscript/client.mjs`). Malicious zips are in `/tmp/qa-s04/zips/` and screenshots in `/tmp/qa-s04/shots/`. All servers I started were stopped.

## Re-test 2026-11-05 (uncommitted fixes on `s04-hub-remote`, after the round-1 handoff updates)
Scope: blocking and partial items (M3, M6, M8, M9) and D2, D3, D6, D7, D8, D9, D11, D12, plus the full test suite and one quick end-to-end pass. I re-ran the round-1 scripts and zips from `/tmp/qa-s04/` on a fresh data dir (`/tmp/qa-s04/data-r2`) against the fake GitHub.

### Updated verdict: **ship with caveats**
No must-fix item fails, and every defect I re-tested is fixed. Two caveats remain, and each is either a one-line fix or needs a CTO acceptance:
- **M8:** the UI does not display triage `by`. The value is stored.
- **CSP:** the CSP still has the M7 deviations.

Two further points need a decision from Juhyeong before merge: the new per-project `online_refs` toggle sends bibliography titles and DOIs to OpenAlex and Crossref, which is a use of user data. Merging to main also needs his approval. The Mac-only list in section 6 still applies.

### Results
- **Tests:** 95/95 OK (was 85).
- **End to end (HTTP):**
  - pairing: 5 wrong codes lock the code (right code then 403); an expired code → 403; the right code → 200 with the cookie set
  - device flow → `ok`; create `tiny-transformer-5d7e`; zip v1; checkpoint; zip v2 → group `ev:commit:paper:1182e28…` (changed `tex:app:hparams`)
  - push K3 + sync → `changed:true` and the code group with downstream run → table2.csv → `tex:tab:main`
- **MCP SDK client** (1.32.2, Streamable HTTP, token from `hub token`): connect, 9 tools, alarms (2 groups), search, ping. No token or a bad token → 401.
- **Golden set** (`lemmata demo`): 10/10 findings with file:line, 2 proposed links, 8 checks `ran` (single-project mode is unchanged by the D5 status change).
- **Token:** found in 0 of 236 git argv lines; the only file holding it is `hub/github.json`.

### Must-fix table (re-test)
| # | Round 1 | Re-test | Evidence |
|---|---|---|---|
| M1 | pass | pass (not re-attacked; unchanged) | — |
| M2 | pass | pass | Also for the new `PATCH /api/hub/projects/<pid>`: cookie without Origin → 403; with a good Origin → 200; a bad value → 400 |
| M3 | partial | **pass** | Started the hub with no `tailscale`, then a fake CLI appeared. Within 15 s: "Tailscale is up; now also listening on 192.0.2.2". Host `qa-mini.tail1234.ts.net` → 200 (allow-list refreshed). A peer from 192.0.2.2 to the late-bound socket is closed with 0 bytes. `Tailscale-Funnel-Request: ?1` → 403, also on the public `/api/hub/status` |
| M4 | pass | pass | Token in 0 of 236 argv lines; clone env has the scoped `GIT_CONFIG_KEY_0`; clone errors are masked (`<data>/projects/…`) |
| M5 | pass | pass | Engine `status`, `log` and `ls-files` now run with `GIT_CONFIG_NOSYSTEM=1` and `GIT_CONFIG_GLOBAL=/dev/null` in hub mode (D10, 52/52 calls) |
| M6 | partial | **pass** | All 27 malicious zips: 25 → 400 `bad_zip`, including the round-1 accepts `.g‌it/` ("invisible formatting characters"), NFC/NFD `café.tex` (duplicate), `.git./`, `GIT~1/`, `.git /` (".git folder"), file/folder clash, and the lying-size bomb. The two benign ones (exec bit, `.gitmodules`) → 200. A 60 MB single file → 400 "larger than 50 MB". Nothing written outside the data dir (`find -newer`); `tmp/` empty; `/tmp/qa_*pwn*` absent |
| M7 | pass (deviations) | pass (deviations unchanged) | CSP is still `style-src 'unsafe-inline'`, `img-src data:`, with no `form-action 'self'`. The CTO should accept this or tighten it |
| M8 | partial | **pass except UI display** | The notice is now the first line of every tool's text. `structuredContent` is cleaned: the injected evidence has no ESC/BEL. Triage stores `by` in the entry and in its history: MCP writes `mcp:dev_d456cacd`, UI writes `ui:dev_207b0447`. **Gap:** `app.js` does not show `by` (threat model: "the UI shows it") |
| M9 | **FAIL** | **pass** | `hub token` prints `claude mcp add --scope user --transport http …` plus the warning "never in a project's .mcp.json or a repo" |
| M10 | pass | pass (not re-tested beyond the fresh dir; same code) | — |
| M11 | pass (deviations) | **pass** | `-x/y`, `a/.`, a 40-char owner, a 101-char name, and `alice/-uhelp` → 400; `--upload-pack=x` branch → 400 |

### Defects re-tested
| Defect | Result | Evidence |
|---|---|---|
| D2 negative Content-Length DoS | **fixed** | `Content-Length: -1` on public `/api/hub/pair` and on `/mcp` → 400 before any read; hub RSS stayed at 31.4 MB. `abc`, `+5` and ` 1e3` → 400 |
| D3 half-replaced paper | **fixed** | The aliases are rejected up front. With `git commit-tree` forced to fail through the wrapper → 502, and the paper file list, HEAD (`704e040`) and the md5 of `main.tex` are unchanged, `git status` is clean, and `tmp/` is empty |
| D5 inert reference check (re-checked in passing) | **fixed** | Hub `reference_unmatched` is now `not_checked`, "6 of 6 entries unchecked (online lookup is off)", and there is an opt-in `online_refs` per project. Needs Juhyeong's approval (user data to OpenAlex/Crossref) |
| D6 Tailscale late start + Funnel header | **fixed** | See M3 |
| D7 500s with paths | **fixed** | The file/folder clash and the lying bomb → 400. Clone errors show `<data>/…` instead of the absolute path |
| D8 NFC / zero-width / per-file cap | **fixed** | See M6 |
| D9 code_repo regex | **fixed** | See M11 |
| D11 fresh-browser 401 | **fixed** | In a fresh Chromium context on a hub with paired devices, the pairing page shows directly with 0 console errors (`/tmp/qa-s04/shots/r2-01-…png`) |
| D12 stdlib 501 HTML | **fixed (methods)** | PUT, OPTIONS, TRACE and PATCH on `/mcp`, and PUT on `/api/hub/projects`, → 405 JSON with CSP and nosniff. The CSP deviations remain (M7) |

All servers I started for the re-test are stopped: the hub on 18765, the late-Tailscale hub on 18766, the fake GitHub, and the demo.
