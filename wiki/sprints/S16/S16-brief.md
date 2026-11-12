---
type: task-card
owner_agent: lead
status: built, not yet QA-verified
sources:
  - "founder messages in chat, 2026-11-12 13:39 and 13:41 KST: 'can i access the visuals such as the reviews, the tree map in VS code?'; 'Yes build it so that I can access it from VS code. Plan first.'; plan approved 13:42 ('Proceed')"
  - "app/src/lemmata/hub/routes.py and server.py: the hub sends frame-ancestors 'none', so its pages cannot be framed; static files of web/ are served from the hub root"
  - "code: vscode/src/tab.ts, vscode/src/core/embed.ts, vscode/media/embed.js, vscode/src/core/client.ts (raw), vscode/src/extension.ts; app/src/lemmata/web/app.js (EMBED hook); tests vscode/test/unit/embed.test.ts, vscode/test/e2e/tab.test.ts"
last_reviewed: 2026-11-12
---
# S16 brief: the Lemmata pages in a VS Code tab

## What was built
- **A tab that shows the hub's own web app** (extension 0.3.0). The extension fetches app.js, research.js, app.css and KaTeX from the hub, builds one page (fonts inlined) and shows it in a webview. No second copy of Review, Claims or Experiments exists.
- **A request bridge.** The webview's policy allows no network at all. `media/embed.js` replaces `fetch`; each request goes to the extension as a message, is checked by `allowedRequest` (this project's API plus status, project list, this project's hub actions, the event counter) and is sent to the hub with the stored token. The token never enters the page. Because the extension makes the calls, the tab works over Remote-SSH through the same tunnel as the rest.
- **Web app hook** (`window.LEMMATA_EMBED`, 12 lines in app.js): project id from the host, no "Projects" menu entry, export goes through the host, "Open in editor" links on file places.
- **Links.** File places open in the editor beside the tab; `.md` opens as a document; pictures open in an editor tab; export asks where to save; web links open in the browser.
- Commands: Open Lemmata (in a tab), Open Review, Open Claims tree, Open Experiments; a button on the panel.

## Decisions taken without the founder (to confirm)
- The hub's `frame-ancestors 'none'` was kept; nothing in the hub's security settings changed.
- The page may not delete the project or reach device, token or user routes, even though the token could.
- Inside the tab the app keeps its 1024 px minimum and scrolls sideways in a narrow column.
- Pages are fetched once per window and kept until reconnect; a hub update shows after the tab is reopened.

## Not built
- Runs logged in S15 are still not shown on the Experiments page or the Claims tree.
- The tab does not follow the VS Code colour theme (it keeps Lemmata's colours).
- Paper zip upload from the tab goes through the bridge but was not tried.

## Verified
- 162 Python tests, 56 extension unit tests (6 new), 10 integration tests pass.
- 6 end-to-end tests pass: the real `LemmataTab` code with a headless Chrome page as the webview and a real hub. They cover: Claims tree drawn from real data with no network request from the page; Review and Experiments opened in the same tab; a hoped conclusion typed in the tab saved on the hub; requests for other projects, devices and project deletion refused; the token absent from the page; Open in editor, claims.md and web links; a plain message when the hub is unreachable.
- **Not verified:** not run inside a real VS Code window, so webview behaviour that differs from Chrome (message timing, fonts, focus, `retainContextWhenHidden`) is untested. Not run on mcd_extension or over Remote-SSH. Figure thumbnails go through the bridge but the sample project showed none to check. QA has not reviewed.
