/* Lemmata project UI (S06, Obsidian-style). Plain JS, no build step, no inline scripts, no innerHTML.
   Talks to the JSON API of wiki/architecture/data-model.md section 12, or reads an embedded snapshot
   (exported report) and becomes read-only. Everything the user sees is derived in the browser from that API.
   Sections: 1 core, 2 hub controls, 3 model (Items), 4 sentences, 5 graph, 6 pages, 7 shell, 8 boot. */
'use strict';
const PRODUCT = 'Lemmata';
const SNAP = (function () {
  const el = document.getElementById('lemmata-snapshot');
  if (!el) return null;
  try { return JSON.parse(el.textContent); } catch (e) { return null; }
})();
const READONLY = !!SNAP;
/* API base: /p/<pid>/ -> /p/<pid>/api/ (served by a hub); anything else -> /api/ (single-project mode). */
/* EMBED: set by a host that shows this app inside its own frame (the VS Code extension's tab). The host supplies the
   project id, answers fetch() itself, and opens links and files: { pid, open(url), openFile(repo, path, line) }. */
const EMBED = (!SNAP && typeof window !== 'undefined' && window.LEMMATA_EMBED) || null;
const PID = EMBED ? String(EMBED.pid) : (function () { const m = location.pathname.match(/^\/p\/([^/]+)\//); return m ? decodeURIComponent(m[1]) : null; })();
const goTo = url => { if (EMBED) EMBED.open(url); else location.href = url; };
/* a file's place, with a link that opens it in the host's editor when there is one */
function capLoc(n, text, line) {
  const cap = h('div', { class: 'cap' }, text);
  if (EMBED && n && n.loc && n.loc.path) cap.append(' ', h('a', { class: 'ghl', href: '#', title: 'Open this file in the editor', onclick: ev => { ev.preventDefault(); EMBED.openFile(n.repo, n.loc.path, line || n.loc.line || 1); } }, 'Open in editor'));
  return cap;
}
const API_BASE = PID ? '/p/' + encodeURIComponent(PID) + '/api/' : '/api/';
const apiUrl = path => path.startsWith('/api/') ? API_BASE + path.slice(5) : path;
let HUB_ON = false;   // true when /api/hub/status answers and the page is under /p/<pid>/
const UIKEY = 'lemmata.ui.' + (PID || 'local:' + location.port);

/* append() that ignores null/false and flattens arrays, so render code can pass optional pieces */
(function () { const ap = Element.prototype.append; Element.prototype.append = function (...k) { ap.apply(this, k.flat(Infinity).filter(x => x != null && x !== false)); }; })();
/* ---------- tiny DOM helper ---------- */
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) for (const k in attrs) {
    const v = attrs[k];
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'text') el.textContent = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
const basename = p => (p || '').split('/').pop();
const dirname = p => { const i = (p || '').lastIndexOf('/'); return i < 0 ? '' : p.slice(0, i); };
function plural(n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); }
const mono = t => h('span', { class: 'mono' }, t);
const trunc = (s, n) => { s = String(s == null ? '' : s); return s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s; };
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function lsGet(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }
function lsSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } }

/* ---------- API ---------- */
async function apiGet(path) {
  if (SNAP) return snapGet(path);
  const r = await fetch(apiUrl(path), { cache: 'no-store' });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error((j.error && j.error.message) || ('HTTP ' + r.status)); e.status = r.status; throw e; }
  return j;
}
async function apiPost(path, body) {
  if (SNAP) throw new Error('Read-only snapshot');
  const r = await fetch(apiUrl(path), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error((j.error && j.error.message) || ('HTTP ' + r.status)); e.status = r.status; throw e; }
  return j;
}
function snapGet(path) {
  const u = new URL(path, 'http://x/');
  const p = u.pathname.replace('/api/', ''), q = u.searchParams;
  if (p === 'analyze') {
    const a = SNAP.analyses[q.get('group') + '|' + q.get('node')];
    return a ? a : Promise.reject(new Error('This snapshot did not keep the reason for that one.'));
  }
  if (p === 'file') {
    const segs = SNAP.files[q.get('repo') + '|' + q.get('path')];
    const a = +(q.get('start') || 1), b = q.get('end') ? +q.get('end') : a + 400;
    if (!segs) return Promise.reject(new Error('File content is not stored in this snapshot'));
    for (const s of segs) {
      const e = s.start + s.lines.length - 1;
      if (a <= e && b >= s.start) {
        const from = Math.max(a, s.start), to = Math.min(b, e);
        return { start: from, lines: s.lines.slice(from - s.start, to - s.start + 1), binary: false, total: null };
      }
    }
    return Promise.reject(new Error('Those lines are not stored in this snapshot'));
  }
  if (p === 'events') return SNAP.events;
  if (SNAP[p]) return SNAP[p];
  return Promise.reject(new Error('Not available in a snapshot'));
}

/* ---------- strings (one place, so a Korean version can follow) ---------- */
const T = {
  checkNames: {
    main_appendix_mismatch: 'Numbers that differ between text and appendix',
    reference_unmatched: 'References that could not be matched',
    undefined_cite: 'Cited things that do not exist',
    uncited_reference: 'References nobody cites',
    unreferenced_float: 'Figures and tables never mentioned',
    undefined_ref: 'Links to things that do not exist',
    untraced_number: 'Numbers not found in any result file',
    figure_without_provenance: 'Figures with no known source',
  },
  checkOrder: ['main_appendix_mismatch', 'reference_unmatched', 'undefined_cite', 'uncited_reference', 'unreferenced_float', 'undefined_ref', 'untraced_number', 'figure_without_provenance'],
  checkChip: { main_appendix_mismatch: ['≠', 'Differs'], reference_unmatched: ['?', 'Could not be matched'], untraced_number: ['∅', 'Not traced'] },
  notRun: { 'no paper repo': 'no paper connected', 'no paper': 'no paper connected', 'no \\appendix found': 'no appendix found' },
  intro: [
    ['Lemmata keeps track of what your paper claims and what backs it.', 'It reads your paper and the code and results behind it. Claims shows the core message, each claim under it, and the proof, table, result file and script behind each one.'],
    ['When something changes, it tells you what it affects.', 'Change a setting or a script and Lemmata lists the tables, figures and sections that may no longer match. You don\'t have to watch it. Open it when you need it.'],
    ['You decide what is fine.', 'For each change, choose Looks fine, Needs fixing or Ignore. When you are happy, press "Mark everything as looked at" and Lemmata counts from there.'],
  ],
};

/* ---------- time words ---------- */
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const dayOf = d => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
function dayDiff(t) { const d = new Date(t); if (isNaN(d)) return null; return Math.round((dayOf(new Date()) - dayOf(d)) / 86400000); }
function dmon(t) { return (+t.slice(8, 10)) + ' ' + MON[(+t.slice(5, 7)) - 1]; }
function relTime(t) {
  if (!t) return '';
  const d = new Date(t); if (isNaN(d)) return '';
  const diff = (Date.now() - d) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.round(diff / 60) + ' min ago';
  const n = dayDiff(t);
  if (n <= 0) return 'today ' + t.slice(11, 16);
  if (n === 1) return 'yesterday';
  if (n <= 14) return n + ' days ago';
  return dmon(t) + (new Date().getFullYear() !== +t.slice(0, 4) ? ' ' + t.slice(0, 4) : '');
}
function absTime(t) { return t ? dmon(t) + (new Date().getFullYear() !== +t.slice(0, 4) ? ' ' + t.slice(0, 4) : '') + ', ' + t.slice(11, 16) : ''; }
function dayHeader(t) { const n = dayDiff(t); return n <= 0 ? 'Today' : n === 1 ? 'Yesterday' : dmon(t); }
function lastChecked(t) { if (!t) return ''; const n = dayDiff(t); return n <= 0 ? 'today ' + t.slice(11, 16) : absTime(t); }
function agoText(t) {
  if (!t) return 'never';
  const d = (Date.now() - Date.parse(t)) / 1000;
  if (isNaN(d)) return String(t);
  if (d < 90) return 'just now';
  if (d < 3600) return Math.round(d / 60) + ' min ago';
  if (d < 86400) return Math.round(d / 3600) + ' h ago';
  return Math.round(d / 86400) + ' days ago';
}

/* ---------- status vocabulary (words + glyphs from the S06 spec, section 1.4) ---------- */
const ST = {
  ok: { glyph: '✓', word: 'Up to date', cls: 'ok', rank: 0, say: 'up to date' },
  look: { glyph: '↻', word: 'Needs a second look', cls: 'look', rank: 3, say: 'needs a second look' },
  fine: { glyph: '✓✓', word: 'Looks fine', cls: 'fine', rank: 1, say: 'looks fine' },
  fix: { glyph: '✕', word: 'Needs fixing', cls: 'fix', rank: 4, say: 'needs fixing' },
  ign: { glyph: '–', word: 'Ignored', cls: 'ign', rank: 2, say: 'ignored' },
};
/* S18 state: a bracket tag plus a 6px dot (drawn by CSS from the class). The word carries the meaning; the old glyph is not shown. */
const tagWord = w => '[' + String(w).toLowerCase() + ']';
function chip(st, extra) { const s = ST[st]; return h('span', { class: 'chip ' + s.cls }, tagWord(s.word), extra ? ' ' + extra : null); }
function plainChip(glyph, word, cls) { return h('span', { class: 'chip ' + (cls || 'plain') }, tagWord(word)); }
const STATE_TO_ST = { reviewed: 'fine', needs_fixing: 'fix', ignored: 'ign', unreviewed: 'look' };

/* ---------- toast / modal / tooltip ---------- */
let toastTimer = null;
function toast(msg, action) {
  const old = $('#toast'); if (old) old.remove();
  const t = h('div', { id: 'toast', role: 'status' }, msg, action ? h('button', { class: 'linkbtn', onclick: () => { t.remove(); action.fn(); } }, action.label) : null);
  document.body.append(t);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.remove(), 4500);
}
function modal(title, body, buttons, opts) {
  opts = opts || {};
  const prevFocus = document.activeElement;
  const close = () => { scrim.remove(); document.removeEventListener('keydown', onKey, true); if (prevFocus && prevFocus.focus) prevFocus.focus(); };
  const acts = h('div', { class: 'acts' }, buttons.map(b => h('button', { class: 'btn' + (b.primary ? ' primary' : ''), onclick: () => { if (b.keep !== true) close(); if (b.fn) b.fn(close); } }, b.label)));
  const scrim = h('div', { class: 'scrim', onclick: ev => { if (ev.target === scrim) close(); } },
    h('div', { class: 'modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': title, style: opts.width ? { width: opts.width + 'px' } : null }, h('h3', null, title), body, acts));
  function onKey(ev) {
    if (ev.key === 'Escape') { ev.stopPropagation(); close(); }
    if (ev.key === 'Tab') {
      const f = $$('button, input, textarea', scrim).filter(x => !x.disabled); if (!f.length) return;
      const i = f.indexOf(document.activeElement);
      if (ev.shiftKey && i <= 0) { ev.preventDefault(); f[f.length - 1].focus(); }
      else if (!ev.shiftKey && i === f.length - 1) { ev.preventDefault(); f[0].focus(); }
    }
  }
  document.addEventListener('keydown', onKey, true);
  document.body.append(scrim);
  const first = scrim.querySelector('input, textarea') || acts.querySelector('button:not(.primary)') || acts.querySelector('button');
  if (first) first.focus();
  return close;
}
function tip(el, textFn) {
  let t = null;
  const hide = () => { if (t) { t.remove(); t = null; } };
  const move = ev => { if (t) { t.style.left = Math.min(ev.clientX + 12, innerWidth - 380) + 'px'; t.style.top = (ev.clientY + 14) + 'px'; } };
  const show = ev => { hide(); t = h('div', { class: 'tip' }, typeof textFn === 'function' ? textFn() : textFn); document.body.append(t); move(ev); };
  el.addEventListener('mouseenter', show); el.addEventListener('mousemove', move); el.addEventListener('mouseleave', hide);
}

/* ---------- file access (read-only /api/file) ---------- */
const fileCache = new Map();
async function getLines(repo, path, start, end) {
  const key = [repo, path, start, end].join('|');
  if (fileCache.has(key)) return fileCache.get(key);
  const q = '/api/file?repo=' + encodeURIComponent(repo) + '&path=' + encodeURIComponent(path) + '&start=' + start + (end ? '&end=' + end : '');
  const p = Promise.resolve().then(() => apiGet(q));
  fileCache.set(key, p);
  p.catch(() => fileCache.delete(key));
  return p;
}
function codeBlock(lines, start, hl, opts) {
  opts = opts || {};
  const hlset = new Set(hl || []);
  return h('div', { class: 'code', tabindex: '0', role: 'region', 'aria-label': opts.label || 'Source lines' },
    lines.map((t, i) => {
      const n = start + i;
      return h('div', { class: 'ln' + (hlset.has(n) ? ' hl' : '') }, h('span', { class: 'n' }, String(n)), t || ' ');
    }));
}
function diffBlock(unified) {
  const rows = String(unified || '').split('\n');
  if (rows.length && rows[rows.length - 1] === '') rows.pop();
  return h('div', { class: 'code', tabindex: '0', role: 'region', 'aria-label': 'What changed in this file' }, rows.map(t => {
    let c = 'ln', sign = ' ', body = t;
    if (t.startsWith('---') || t.startsWith('+++')) return null;
    if (t.startsWith('@@')) return h('div', { class: 'ln hunk' }, h('span', { class: 'n' }, ''), '⋯');
    if (false) c += ' hunk';
    else if (t.startsWith('+')) { c += ' add'; sign = '+'; body = t.slice(1); }
    else if (t.startsWith('-')) { c += ' del'; sign = '−'; body = t.slice(1); }
    else body = t.slice(1);
    const isHdr = c.includes('hunk');
    return h('div', { class: c }, h('span', { class: 'n' }, isHdr ? '' : sign), isHdr ? t : body || ' ');
  }));
}

/* ---------- state ---------- */
const S = {
  project: null, graph: null, events: null, findings: null, alarms: null, checkpoints: null, triage: null,
  loading: true, error: null,
  tabs: [], active: -1, nav: [], navPos: -1,
  leftOpen: true, rightOpen: true, leftW: 260, rightW: 300,
  chFilter: 'all', histFilter: 'all', onlyLook: false, treeOpen: {}, query: '',
  sel: null,            // Item id selected in the graph / focused for the right sidebar
  gf: { sections: true, floats: true, shared: true, refs: false, files: false, code: true, runs: true, results: true, settings: true, unused: false, onlyChanged: false, mode: 'whole', depth: 2, expanded: [] },
  openWhy: {}, noteOpen: {}, doneCards: {}, listView: false, localDepth: 1, checkSec: {},
  an: {},               // analyses cache  gid|node -> analyze response
};
const M = {};   // derived model (section 3)
const IX = {};  // node-level indexes

/* ======================================================================
   2. HUB MODE. Everything that only exists under /p/<pid>/ is in this block.
   To change what the hub shows (paper source, upload, sync), edit hubControls()
   and the functions below it; nothing else in this file knows about hub mode.
   ====================================================================== */
let HUBINFO = null;   // {kind:'zip'|'github'|'other', repo, subdir, last_sync}
const HUB_PLAIN = { paper_repo_not_found: 'That repository was not found, or your GitHub sign-in cannot see it.', paper_subdir_missing: 'That folder does not exist in the repository.', not_signed_in: 'Sign in to GitHub on the Projects page first.', paper_is_github: 'This project\'s paper comes from GitHub, so a zip cannot replace it.', paper_branch_not_found: 'That branch was not found.', paper_too_large: 'That paper is too large.' };
function paperStatusText() {
  if (!HUBINFO) return '';
  const k = HUBINFO.kind, t = HUBINFO.last_sync ? ' ✓ synced ' + agoText(HUBINFO.last_sync) : '';
  if (k === 'github') return HUBINFO.subdir ? 'Paper: folder ' + HUBINFO.subdir + '/ in your code repo' + t : 'Paper: GitHub repo' + t;
  if (k === 'zip') return 'Paper: zip — upload new version';
  return 'Paper: old setting — connect a paper repo';
}
/* hubControls() -> { menu: [ {label, hint, fn} ], status: string, sync: fn|null }. Hub mode only; empty otherwise. */
function hubControls() {
  if (!HUB_ON || READONLY) return { menu: [], status: '', sync: null };
  const kind = HUBINFO && HUBINFO.kind;
  const menu = EMBED ? [] : [{ label: '← Projects', hint: 'Back to your list of projects', fn: () => { location.href = '/'; } }];
  menu.push({ label: paperStatusText() || 'Paper', hint: kind === 'zip' ? 'Click to upload' : '', fn: kind === 'zip' ? () => { const i = $('#zip-in'); if (i) i.click(); } : null });
  if (kind === 'zip') menu.push({ label: 'Upload paper as zip', hint: 'Replaces the paper with a new zip', fn: () => { const i = $('#zip-in'); if (i) i.click(); } });
  menu.push({ label: 'Connect paper repo…', hint: 'Read the paper from GitHub', fn: connectPaperRepo });
  return { menu, status: paperStatusText(), sync: hubSync, zipInput: kind !== 'github' };
}
function connectPaperRepo() {
  const repo = h('input', { type: 'text', placeholder: 'owner/name or https://github.com/owner/name', 'aria-label': 'Paper repository', autocomplete: 'off', spellcheck: 'false' });
  const sub = h('input', { type: 'text', placeholder: 'Folder inside the repo (optional), e.g. paper', 'aria-label': 'Folder (optional)', autocomplete: 'off' });
  const err = h('div', { class: 'warn-note hidden', role: 'alert' });
  modal('Connect paper repo', h('div', null,
    h('p', null, 'Lemmata reads your LaTeX paper from GitHub, the same way it reads your code. The paper can be its own repo, or a folder inside your code repo.'), repo, h('div', { style: { height: '8px' } }), sub, err),
    [{ label: 'Cancel' }, { label: 'Connect', primary: true, keep: true, fn: async close => {
      let r = repo.value.trim().replace(/^https?:\/\/github\.com\//, '').replace(/\.git$/, '').replace(/\/+$/, '');
      if (!/^[\w.-]+\/[\w.-]+$/.test(r)) { err.textContent = 'Type the repository as owner/name.'; err.classList.remove('hidden'); return; }
      const body = { kind: 'github', repo: r }; if (sub.value.trim()) body.subdir = sub.value.trim().replace(/^\/+|\/+$/g, '');
      err.classList.add('hidden');
      try { await hubJson('POST', '/api/hub/projects/' + encodeURIComponent(PID) + '/paper-source', body); close(); await loadAll(); await loadHubInfo(); toast('Paper now comes from GitHub. Lemmata read it.'); }
      catch (e) { err.textContent = HUB_PLAIN[e.code] || e.message; err.classList.remove('hidden'); }
    } }], { width: 480 });
}
async function loadHubInfo() {
  if (!HUB_ON || !PID) return;
  try {
    const pl = await fetch('/api/hub/projects', { cache: 'no-store' }).then(r => r.json());
    const p = (pl.projects || []).find(x => x.id === PID);
    const ps = (p && p.paper_source) || { kind: 'zip' };
    HUBINFO = { kind: ps.kind === 'github' ? 'github' : ps.kind === 'zip' ? 'zip' : 'other', repo: ps.repo || null, subdir: ps.subdir || null, last_sync: p ? p.last_sync : null };
  } catch (e) { /* keep the previous info */ }
  if (S.project) { renderStatus(); renderShellExtras(); }
}
async function hubSync() {
  setBusy('Reading your files…');
  try {
    const r = await hubPost('/api/hub/projects/' + encodeURIComponent(PID) + '/sync', null, 'application/json');
    await loadAll();
    const c = r.code ? r.code.changed : r.changed, pp = r.paper && r.paper.changed;
    if (r.paper && r.paper.error) toast('Your paper could not be pulled: ' + String(r.paper.error).slice(0, 160));
    else toast(c || pp ? 'Synced. New changes were found.' : 'Already up to date.');
    await loadHubInfo();
  } catch (e) { toast('Sync failed. ' + e.message); }
  setBusy(null);
}
async function hubUpload(ev) {
  const f = ev.target.files[0]; if (!f) return;
  setBusy('Uploading your paper…');
  try {
    const r = await hubPost('/api/hub/projects/' + encodeURIComponent(PID) + '/paper', f, 'application/zip');
    await loadAll();
    toast('Paper uploaded (version ' + r.version + '). Lemmata read it again.');
    await loadHubInfo();
  } catch (e) { toast('Upload failed. ' + (HUB_PLAIN[e.code] || e.message)); }
  setBusy(null);
}
async function hubJson(method, path, body) {
  const r = await fetch(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { const er = j.error; const e = new Error((er && er.message) || (typeof er === 'string' ? er : '') || ('HTTP ' + r.status)); e.code = er && (er.code || (typeof er === 'string' ? er : '')); throw e; }
  return j;
}
async function hubPost(path, body, type) {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': type }, body: body == null ? '{}' : body });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { const er = j.error; const e = new Error((er && er.message) || (typeof er === 'string' ? er : '') || ('HTTP ' + r.status)); e.code = er && (er.code || (typeof er === 'string' ? er : '')); throw e; }
  return j;
}
async function detectHub() {
  if (READONLY || !PID) return;
  try { const r = await fetch('/api/hub/status', { cache: 'no-store' }); HUB_ON = r.ok; } catch (e) { HUB_ON = false; }
  if (HUB_ON) { loadHubInfo(); setInterval(loadHubInfo, 60000); }
}
/* end of hub-mode block */

/* sync for everyone: hub mode pulls from GitHub, single-project mode checks the files again */
async function syncNow() {
  if (READONLY) return;
  const hc = hubControls();
  if (hc.sync) return hc.sync();
  setBusy('Reading your files…');
  try { await apiPost('/api/scan', {}); await loadAll(); toast('Read your files again.'); }
  catch (e) { toast(e.status === 409 ? 'Lemmata is already checking your files. Try again in a moment.' : 'Something broke on our side. Your files and marks are unchanged.', { label: 'Details', fn: () => modal('Details', h('p', { class: 'mono' }, e.message), [{ label: 'Close', primary: true }]) }); }
  setBusy(null);
}
let BUSY = null;
function setBusy(msg) { BUSY = msg; renderStatus(); }

/* ======================================================================
   3. MODEL. Items are derived in the browser (spec section 1).
   ====================================================================== */
const PAPER = new Set(['thesis', 'rq', 'section', 'figure', 'table', 'equation']);
const FILEK = new Set(['asset', 'result', 'run', 'code', 'config', 'data', 'doc']);
const PROPK = new Set(['includes', 'generated_by', 'traces_to', 'produced_by', 'executes', 'reads', 'imports', 'value_match']);
const STRUCT = new Set(['contains', 'answers', 'refs']);
const KIND_WORD = { thesis: 'Main claim', rq: 'Research question', section: 'Section', figure: 'Figure', table: 'Table', equation: 'Equation', reference: 'Reference', code: 'Shared code', data: 'Shared data' };
const KIND_GLYPH = { thesis: '◆', rq: '?', section: '§', figure: '▣', table: '▦', equation: '∑', code: '{ }', data: '{ }', reference: '[ ]' };
/* colour by type: every kind of thing has its own layer colour (DESIGN.md --layer-*). Settings and data files use the code colour with a dashed border. */
const TYPES = {
  thesis: { word: 'Main claim', v: 'thesis', glyph: '◆' }, question: { word: 'Research question', v: 'question', glyph: '?' }, section: { word: 'Section', v: 'section', glyph: '§' },
  paper: { word: 'Figure, table or equation', v: 'paper', glyph: '▣' }, result: { word: 'Result file', v: 'result', glyph: '▤' }, code: { word: 'Code', v: 'code', glyph: '{ }' },
  run: { word: 'Run', v: 'run', glyph: '▶' }, reference: { word: 'Reference', v: 'reference', glyph: '[ ]' }, setting: { word: 'Settings and data', v: 'code', glyph: '≣', dash: true },
};
const TYPE_ORDER = ['thesis', 'question', 'section', 'paper', 'result', 'code', 'run', 'reference', 'setting'];
const PAPER_GLYPH = { figure: '▣', table: '▦', equation: '∑' };
function typeOfFile(kind) { return kind === 'result' || kind === 'asset' ? 'result' : kind === 'code' ? 'code' : kind === 'run' ? 'run' : 'setting'; }
function typeOfItem(it) {
  if (it.shared) return typeOfFile(it.node.kind);
  return it.kind === 'thesis' ? 'thesis' : it.kind === 'rq' ? 'question' : it.kind === 'section' ? 'section' : it.kind === 'reference' ? 'reference' : 'paper';
}
const TCOL = {};
const TYPE_TOKEN = { thesis: '--accent-dark', question: '--accent-vivid', section: '--accent', paper: '--accent-vivid', result: '--accent-dark', code: '--accent-light', run: '--accent-light', reference: '--muted' };
function tcol(t) { let c = TCOL[t]; if (!c) { const v = TYPES[t].v; c = TCOL[t] = { s: css(TYPE_TOKEN[v] || '--accent-vivid'), t: css('--accent-pale'), dash: !!TYPES[t].dash }; } return c; }
const tdot = t => h('span', { class: 'tdot t-' + t, 'aria-hidden': 'true' });
const FILE_WORD = { asset: 'A figure file', result: 'A result file', run: 'A run', code: 'A script', config: 'A settings file', data: 'A data file', doc: 'A document' };
const EV_GROUPS = [['Results and figures', ['result', 'asset']], ['Scripts', ['code']], ['Runs', ['run']], ['Settings', ['config']], ['Data', ['data', 'doc']]];

function edgeProp(e) {
  if (!PROPK.has(e.kind)) return false;
  if (e.kind === 'value_match') return e.status === 'approved';
  return e.status === 'detected' || e.status === 'approved';
}
function rebuildIndex() {
  const g = S.graph || { nodes: [], edges: [] };
  IX.node = new Map(g.nodes.map(n => [n.id, n]));
  IX.pout = new Map(); IX.pin = new Map();
  const add = (m, k, e) => { let a = m.get(k); if (!a) m.set(k, a = []); a.push(e); };
  for (const e of g.edges) if (edgeProp(e)) { add(IX.pout, e.from, e); add(IX.pin, e.to, e); }
  IX.alarm = new Map();
  if (S.alarms) for (const grp of S.alarms.groups) {
    for (const c of grp.changed) add(IX.alarm, c.node_id, { group: grp, role: 'changed', entry: c });
    for (const d of grp.downstream) add(IX.alarm, d.node_id, { group: grp, role: 'downstream', entry: d });
  }
  IX.hasCp = !!(S.alarms && S.alarms.checkpoint);
  IX.repoRole = Object.fromEntries(((S.project && S.project.repos) || []).map(r => [r.id, r.role]));
  IX.groupById = new Map(((S.alarms && S.alarms.groups) || []).map(x => [x.id, x]));
  buildModel();
}
function triageEntry(type, id) { const e = S.triage && S.triage.entries && S.triage.entries[type + ':' + id]; return e || null; }
function effState(type, id) {
  const e = triageEntry(type, id);
  if (!e) return { state: 'unreviewed', outdated: false, entry: null };
  return { state: e.effective_state || e.state, outdated: !!e.outdated, entry: e };
}
function nodeFlag(id) {   // s(x) in spec 1.4
  const t = effState('node', id), inAl = IX.alarm.has(id);
  if (t.state === 'needs_fixing') return 'fix';
  if (t.state === 'unreviewed' && (inAl || t.outdated)) return 'look';
  if (t.state === 'reviewed' && inAl) return 'fine';
  if (t.state === 'ignored' && inAl) return 'ign';
  return null;
}
const numParts = s => String(s == null ? '' : s).split('.').map(p => /^\d+$/.test(p) ? [0, +p] : [1, p.toLowerCase()]);
function cmpNum(a, b) {
  const A = numParts(a), B = numParts(b);
  for (let i = 0; i < Math.max(A.length, B.length); i++) {
    const x = A[i], y = B[i];
    if (!x) return -1; if (!y) return 1;
    if (x[0] !== y[0]) return x[0] - y[0];
    if (x[1] !== y[1]) return x[1] < y[1] ? -1 : 1;
  }
  return 0;
}
function tidyCaption(s) { return String(s || '').replace(/\s+/g, ' ').replace(/[.:]\s*$/, '').trim(); }
function itemTitle(n) {
  const a = n.attrs || {}, cap = tidyCaption(a.caption || n.detail);
  switch (n.kind) {
    case 'thesis': return 'Main claim';
    case 'rq': { const d = (n.detail || a.text || '').replace(/^RQ\s?\d+\s*[:.]?\s*/i, ''); return n.name + (d ? ' — ' + trunc(d, 90) : ''); }
    case 'section': {
      const word = a.in_appendix ? 'Appendix' : 'Section', ttl = a.title || n.detail || '';
      return (a.number ? word + ' ' + a.number : word) + (ttl ? ' — ' + ttl : '');
    }
    case 'figure': return 'Figure ' + (a.number || '') + (cap ? ' — ' + trunc(cap, 80) : '');
    case 'table': return 'Table ' + (a.number || '') + (cap ? ' — ' + trunc(cap, 80) : '');
    case 'equation': return 'Equation ' + (a.number || '');
    case 'reference': return n.name.replace(/^\[|\]$/g, '') + (a.title || n.detail ? ' — ' + trunc(a.title || n.detail, 70) : '');
    default: return n.name;
  }
}
function shortTitle(n) {   // used on graph labels and tree rows
  const a = n.attrs || {};
  switch (n.kind) {
    case 'thesis': return 'Main claim';
    case 'rq': return n.name;
    case 'section': return (a.in_appendix ? 'Appendix ' : '§') + (a.number || '') + ' ' + (a.title || n.detail || '');
    case 'figure': case 'table': { const cap = tidyCaption(a.caption || n.detail); return (n.kind === 'figure' ? 'Figure ' : 'Table ') + (a.number || '') + (cap ? ' · ' + cap : ''); }
    case 'equation': return 'Equation ' + (a.number || '');
    default: return n.name;
  }
}
function pathOf(n) { return (n.loc && n.loc.path) || n.name; }
function refKind(ref) {   // README "Fig. 5" -> {kind, number}
  const m = /^\s*(fig(?:ure)?s?|tab(?:le)?s?|app(?:endix)?|sec(?:tion)?|§)\.?\s*([A-Za-z]?[\d.]*[A-Za-z]?)/i.exec(ref || '');
  if (!m) return null;
  const w = m[1].toLowerCase();
  const kind = w.startsWith('fig') ? 'figure' : w.startsWith('tab') ? 'table' : 'section';
  return { kind, number: m[2].replace(/\.$/, ''), app: w.startsWith('app') };
}

function buildModel() {
  const nodes = (S.graph && S.graph.nodes) || [], edges = (S.graph && S.graph.edges) || [];
  M.items = []; M.byId = new Map(); M.itemsOf = new Map(); M.paperId = new Map(); M.readmeOnly = []; M.unused = []; M.noPaper = false;
  M.parent = new Map(); M.iedges = []; M.nbOut = new Map(); M.nbIn = new Map();
  const addTo = (m, k, v) => { let a = m.get(k); if (!a) m.set(k, a = []); a.push(v); };
  const mk = (n, o) => {
    const it = Object.assign({ id: n.id, node: n, nodes: [n.id], kind: n.kind, shared: false, ref: false, ev: [], sharedUse: [], users: [], finds: [], status: 'ok', links: 0, imp: 0, r: 16 }, o || {});
    it.title = it.title || itemTitle(n); it.short = it.short || shortTitle(n);
    it.kindWord = it.kindWord || KIND_WORD[it.kind] || it.kind;
    M.items.push(it); M.byId.set(it.id, it); return it;
  };
  /* 1. paper-facing Items */
  const paperNodes = nodes.filter(n => PAPER.has(n.kind));
  M.noPaper = paperNodes.length === 0;
  for (const n of paperNodes) { const it = mk(n); M.paperId.set(n.id, it.id); addTo(M.itemsOf, n.id, it.id); }
  for (const n of nodes.filter(x => x.kind === 'item')) {   // README placeholders merge into the Figure/Table/Appendix with the same number
    const rk = refKind(n.attrs && n.attrs.paper_ref); let hit = null;
    if (rk) hit = paperNodes.find(p => p.kind === rk.kind && String((p.attrs || {}).number) === rk.number && (rk.kind !== 'section' || !rk.app || !!(p.attrs || {}).in_appendix));
    if (hit) { const it = M.byId.get(hit.id); it.nodes.push(n.id); M.paperId.set(n.id, it.id); addTo(M.itemsOf, n.id, it.id); }
    else if (M.noPaper && rk) {   // code-only project: README rows are all there is, so they become Items
      const word = rk.kind === 'figure' ? 'Figure' : rk.kind === 'table' ? 'Table' : (rk.app ? 'Appendix' : 'Section');
      const it = mk(n, { kind: rk.kind, title: word + ' ' + rk.number + ' (from your README)', short: word + ' ' + rk.number, readme: true });
      M.paperId.set(n.id, it.id); addTo(M.itemsOf, n.id, it.id);
    } else M.readmeOnly.push(n);
  }
  for (const n of nodes.filter(x => x.kind === 'reference')) { const it = mk(n, { ref: true }); addTo(M.itemsOf, n.id, it.id); M.paperId.set(n.id, it.id); }
  const paperItems = M.items.filter(i => !i.ref);
  /* 2. who depends on which file: reach along propagating edges, from every Item's paper node */
  const reach = new Map();
  for (const it of paperItems) {
    const dist = new Map(); const q = [];
    for (const s of it.nodes) { dist.set(s, 0); q.push(s); }
    while (q.length) {
      const cur = q.shift();
      for (const e of IX.pout.get(cur) || []) {
        const t = IX.node.get(e.to);
        if (!t || dist.has(e.to) || PAPER.has(t.kind) || t.kind === 'reference' || t.kind === 'item') continue;
        dist.set(e.to, dist.get(cur) + 1); q.push(e.to);
      }
    }
    for (const [nid, d] of dist) if (d > 0) { let m = reach.get(nid); if (!m) reach.set(nid, m = new Map()); m.set(it.id, d); }
  }
  const evOwner = new Map(), evDist = new Map(), sharedNodes = new Map();
  for (const [nid, m] of reach) {
    if (m.size === 1) { const [iid, d] = [...m][0]; evOwner.set(nid, iid); evDist.set(nid, d); }
    else sharedNodes.set(nid, [...m.keys()]);
  }
  const fileNodes = nodes.filter(n => FILEK.has(n.kind));
  let changed = true;
  while (changed) {   // |F| = 0: inherit from a node it depends on
    changed = false;
    for (const n of fileNodes) {
      if (evOwner.has(n.id) || sharedNodes.has(n.id)) continue;
      for (const e of IX.pout.get(n.id) || []) {
        if (evOwner.has(e.to)) { evOwner.set(n.id, evOwner.get(e.to)); evDist.set(n.id, (evDist.get(e.to) || 1) + 1); changed = true; break; }
      }
    }
  }
  for (const [nid, iid] of evOwner) { const it = M.byId.get(iid); it.ev.push({ id: nid, dist: evDist.get(nid) }); addTo(M.itemsOf, nid, iid); }
  for (const it of paperItems) it.ev.sort((a, b) => a.dist - b.dist || (a.id < b.id ? -1 : 1));
  for (const [nid, users] of sharedNodes) {
    const n = IX.node.get(nid), sk = (n.kind === 'code' || n.kind === 'config' || n.kind === 'run') ? 'code' : 'data';
    const it = mk(n, { shared: true, kind: sk, kindWord: KIND_WORD[sk], title: n.kind === 'run' ? n.name : pathOf(n), short: n.kind === 'run' ? n.name : basename(pathOf(n)), users });
    addTo(M.itemsOf, nid, it.id);
    for (const u of users) M.byId.get(u).sharedUse.push(it.id);
  }
  M.unused = fileNodes.filter(n => !evOwner.has(n.id) && !sharedNodes.has(n.id));
  /* 3. Item-level links */
  const seen = new Set();
  const addLink = (a, b, rel) => { const k = a + '|' + b + '|' + rel; if (a === b || seen.has(k)) return; seen.add(k); M.iedges.push({ a, b, rel }); addTo(M.nbOut, a, { id: b, rel }); addTo(M.nbIn, b, { id: a, rel }); };
  for (const e of edges) {
    if (e.status === 'rejected') continue;
    const a = M.paperId.get(e.from), b = M.paperId.get(e.to);
    if (STRUCT.has(e.kind) && a && b) { addLink(a, b, e.kind); if (e.kind === 'contains' && !M.parent.has(b)) M.parent.set(b, a); }
    else if (e.kind === 'cites' && a && b) addLink(a, b, 'cites');
  }
  for (const it of M.items) if (it.shared) for (const u of it.users) addLink(u, it.id, 'uses');
  /* importance / size (spec 1.5) */
  for (const it of M.items) {
    const nb = new Set();
    for (const x of (M.nbOut.get(it.id) || []).concat(M.nbIn.get(it.id) || [])) if (!M.byId.get(x.id).ref) nb.add(x.id);
    it.links = it.ref ? (M.nbIn.get(it.id) || []).length : nb.size;
    it.imp = it.links + 0.5 * it.ev.length;
  }
  const imax = Math.max(1, ...M.items.filter(i => !i.ref).map(i => i.imp));
  for (const it of M.items) {
    let r = Math.max(16, 16 + 32 * Math.sqrt(it.imp / imax));
    if (it.kind === 'thesis') r = Math.max(36, r);
    if (it.shared) r = Math.max(12, 0.75 * r);
    if (it.ref) r = Math.max(12, 0.6 * r);
    it.r = Math.round(r);
  }
  M.rank = M.items.filter(i => !i.ref).sort((a, b) => b.imp - a.imp || (a.title < b.title ? -1 : 1)).map(i => i.id);
  M.findsByItem = new Map();
  for (const f of (S.findings && S.findings.findings) || []) {
    const hit = new Set();
    for (const nid of f.nodes || []) for (const iid of M.itemsOf.get(nid) || []) hit.add(iid);
    for (const iid of hit) addTo(M.findsByItem, iid, f);
  }
  computeStatuses();
  buildCards();
}
function itemNodeIds(it) { return it.shared ? [it.id] : it.nodes.concat(it.ev.map(e => e.id)); }
function computeStatuses() {
  for (const it of M.items) {
    const flags = [];
    for (const x of itemNodeIds(it)) { const f = nodeFlag(x); if (f) flags.push(f); }
    it.finds = M.findsByItem.get(it.id) || [];
    for (const f of it.finds) {
      const st = effState('finding', f.id).state;
      if (f.severity === 'warning') { if (st === 'unreviewed') flags.push('look'); else if (st === 'needs_fixing') flags.push('fix'); }
    }
    it.status = flags.includes('fix') ? 'fix' : flags.includes('look') ? 'look' : flags.includes('fine') ? 'fine' : flags.includes('ign') ? 'ign' : 'ok';
  }
  M.looked = M.items.filter(i => !i.ref && (i.status === 'look' || i.status === 'fix')).length;
  if (M.cards) M.todo = M.cards.filter(c => c.targets.some(t => effState(t.type, t.id).state === 'unreviewed')).length;
}
function itemTargets(it) {
  const out = [];
  for (const x of itemNodeIds(it)) if (IX.alarm.has(x) || effState('node', x).outdated) out.push({ type: 'node', id: x });
  for (const f of it.finds) if (f.severity === 'warning') out.push({ type: 'finding', id: f.id });
  if (!out.length) out.push({ type: 'node', id: it.nodes[0] });
  return out;
}
const worst = list => list.reduce((a, s) => (ST[s].rank > ST[a].rank ? s : a), 'ok');

/* naming for anything that has an id */
function itemFor(nodeId) { const a = M.itemsOf.get(nodeId); return a && a.length ? M.byId.get(a[0]) : null; }
function nameOf(nodeId, opts) {
  const n = IX.node.get(nodeId); if (!n) return nodeId;
  if (n.kind === 'run') return (opts && opts.bare ? '' : 'the run ') + n.name.replace(/^run\s+/, '');
  if (PAPER.has(n.kind) || n.kind === 'reference') { const it = M.byId.get(M.paperId.get(nodeId)); return it ? it.title : n.name; }
  return pathOf(n);
}
function kindLabel(it) {   // "Table in Section 5"
  if (it.shared) return it.kindWord;
  const par = M.parent.get(it.id), p = par && M.byId.get(par);
  const inSec = p && p.kind === 'section' ? ' in ' + (p.node.attrs.in_appendix ? 'Appendix ' : 'Section ') + (p.node.attrs.number || '') : '';
  switch (it.kind) {
    case 'figure': case 'table': case 'equation': return it.kindWord + (inSec || '');
    case 'section': return (it.node.attrs && it.node.attrs.in_appendix ? 'Appendix' : 'Section') + ' of your paper';
    default: return it.kindWord;
  }
}
function repoWord(repoId) { return IX.repoRole[repoId] === 'paper' ? 'paper' : 'code'; }
function itemSort(a, b) {
  const A = a.node.attrs || {}, B = b.node.attrs || {};
  const aa = A.in_appendix ? 1 : 0, bb = B.in_appendix ? 1 : 0;
  if (aa !== bb) return aa - bb;
  if (A.number != null && B.number != null && a.kind === b.kind) { const c = cmpNum(A.number, B.number); if (c) return c; }
  const la = (a.node.loc && a.node.loc.line) || 0, lb = (b.node.loc && b.node.loc.line) || 0;
  return (a.node.loc && b.node.loc && a.node.loc.path === b.node.loc.path ? la - lb : 0) || (a.title < b.title ? -1 : 1);
}
function neighboursOf(id, depth) {   // Item ids within `depth` hops (undirected)
  const seen = new Map([[id, 0]]), q = [id];
  while (q.length) {
    const c = q.shift(), d = seen.get(c); if (d >= depth) continue;
    for (const x of (M.nbOut.get(c) || []).concat(M.nbIn.get(c) || [])) {
      const it = M.byId.get(x.id); if (!it || (it.ref && !S.gf.refs)) continue;
      if (!seen.has(x.id)) { seen.set(x.id, d + 1); q.push(x.id); }
    }
  }
  return seen;
}

/* ======================================================================
   4. SENTENCES, CARDS, ACTIONS
   ====================================================================== */
const lead = it => it.title.split(' — ')[0];
function fmtVal(v) {
  v = String(v == null ? '' : v).trim().replace(/^["']|["']$/g, '');
  return v.replace(/^(-?\d+)\.0+(e[-+]?\d+)$/i, '$1$2');
}
function humanKey(k) { return String(k).split('.').pop().replace(/[_-]+/g, ' ').trim(); }
function keyChanges(an) {
  const d = an && an.diffs && an.diffs[0]; if (!d || d.binary) return null;
  const rm = new Map(), ad = new Map(), re = /^([-+])\s*"?([A-Za-z_][\w.\-]*)"?\s*[:=]\s*(.*?),?\s*$/;
  for (const line of String(d.unified).split('\n')) {
    if (line.startsWith('---') || line.startsWith('+++')) continue;
    const m = re.exec(line); if (!m) continue;
    (m[1] === '-' ? rm : ad).set(m[2], fmtVal(m[3]));
  }
  const out = [];
  for (const [k, v] of ad) if (!rm.has(k) || rm.get(k) !== v) out.push({ key: humanKey(k), old: rm.get(k), now: v });
  for (const [k, v] of rm) if (!ad.has(k)) out.push({ key: humanKey(k), old: v, now: null });
  return out;
}
function analysisKey(gid, nid) { return gid + '|' + nid; }
async function ensureAnalysis(gid, nid) {
  const k = analysisKey(gid, nid);
  if (S.an[k]) return S.an[k];
  try { const a = await apiGet('/api/analyze?group=' + encodeURIComponent(gid) + '&node=' + encodeURIComponent(nid)); S.an[k] = a; return a; }
  catch (e) { S.an[k] = { failed: e.message }; return S.an[k]; }
}
function causeInfo(g) {
  const c = g.cause || {}, rw = repoWord(c.repo);
  const changed = (g.changed || []).map(x => ({ n: IX.node.get(x.node_id), x })).filter(o => o.n);
  const paper = changed.filter(o => PAPER.has(o.n.kind) || o.n.kind === 'item');
  const files = changed.filter(o => !(PAPER.has(o.n.kind) || o.n.kind === 'item'));
  const rem = g.removed || [];
  let pieces;
  if (c.kind === 'run') pieces = ['A run finished: ', mono((c.subject || '').replace(/^run\s+/, '').split(':')[0] || c.event_id)];
  else if (c.kind === 'worktree') pieces = ['You have changes in ' + rw + ' that are not saved to git yet'];
  else if (c.kind === 'snapshot') pieces = ['Your ' + rw + ' files differ from when you last looked'];
  else if (c.kind === 'diverged') pieces = ['The history of your ' + rw + ' was rewritten since you last looked, so everything there is listed here.'];
  else if (files.length === 0 && paper.length) {
    if (paper.length === 1) { const it = M.byId.get(M.paperId.get(paper[0].n.id)); pieces = ['You edited ', it ? it.title : paper[0].n.name, ' in your paper (', mono(pathOf(paper[0].n)), ')']; }
    else pieces = ['You edited ' + plural(paper.length, 'place') + ' in your paper'];
  } else if (files.length === 1 && !paper.length) {
    const f = files[0], p = pathOf(f.n);
    if (f.x.change === 'added') pieces = ['You added ', mono(p)];
    else if (f.n.kind === 'config') {
      const an = S.an[analysisKey(g.id, f.n.id)], kc = keyChanges(an);
      if (kc && kc.length === 1 && kc[0].old != null && kc[0].now != null) pieces = ['You changed ', mono(p), ' (' + kc[0].key + ' ' + kc[0].old + ' → ' + kc[0].now + ')'];
      else if (kc && kc.length > 1) pieces = ['You changed ' + plural(kc.length, 'setting') + ' in ', mono(p)];
      else pieces = ['You changed ', mono(p)];
    } else if (f.n.kind === 'code') pieces = ['You edited ', mono(p)];
    else pieces = ['Your file ', mono(p), ' changed'];
  } else if (files.length + paper.length > 0) {
    const names = files.slice(0, 2).map(o => basename(pathOf(o.n)));
    const more = files.length - names.length;
    pieces = files.length ? ['You edited ' + plural(files.length, 'file') + ' in ' + rw + ' (' + names.join(', ') + (more > 0 ? ' and ' + more + ' more' : '') + ')'] : ['You edited ' + plural(paper.length, 'place') + ' in your paper'];
    if (files.length && paper.length) pieces.push(' and ' + plural(paper.length, 'place') + ' in your paper');
  } else if (rem.length) pieces = ['You removed ', mono(rem[0].path || rem[0].name || rem[0].node_id)];
  else pieces = ['You changed ', mono((c.files || [])[0] || 'a file')];
  return { pieces, time: relTime(c.time), abs: absTime(c.time), short: c.kind === 'commit' ? c.short : null, subject: c.subject };
}
function causeLine(g) {
  const ci = causeInfo(g);
  return h('span', { class: 'cause' }, ci.pieces, h('span', { class: 'muted', title: ci.abs }, ' · ' + ci.time),
    ci.short ? h('span', { class: 'muted' }, ' · commit ') : null,
    ci.short ? h('button', { class: 'hash mono', title: 'Click to copy the commit id', onclick: ev => { ev.stopPropagation(); copyText(ci.short); } }, ci.short) : null);
}
function copyText(t) {
  const done = () => toast('Copied.');
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done, () => toast('Could not copy. Select it and press Ctrl+C.'));
  else toast('Could not copy. Select it and press Ctrl+C.');
}
function ago(t) { return relTime(t); }

function buildCards() {
  M.cards = [];
  const groups = (S.alarms && S.alarms.groups) || [];
  for (const g of groups) {
    const nodes = g.changed.map(c => ({ id: c.node_id, role: 'changed', entry: c })).concat(g.downstream.map(d => ({ id: d.node_id, role: 'downstream', entry: d })));
    const items = new Map();
    for (const nd of nodes) for (const iid of M.itemsOf.get(nd.id) || []) items.set(iid, M.byId.get(iid));
    const list = [...items.values()].sort((a, b) => b.imp - a.imp || (a.title < b.title ? -1 : 1));
    // consequence: Items first, then the files and runs on the way
    const things = [], seenItem = new Set();
    for (const d of g.downstream) {
      const iid = M.paperId.get(d.node_id);
      if (iid && !seenItem.has(iid)) { seenItem.add(iid); things.push({ it: M.byId.get(iid), imp: M.byId.get(iid).imp, depth: d.depth }); }
    }
    things.sort((a, b) => b.imp - a.imp);
    const ev = [];
    for (const d of g.downstream) {
      if (M.paperId.has(d.node_id)) continue;
      const n = IX.node.get(d.node_id); if (!n) continue;
      let sfx = '';
      if (d.output_identical === true) sfx = 'not regenerated yet'; else if (d.output_identical === false) sfx = 'regenerated, content differs';
      ev.push({ id: d.node_id, name: nameOf(d.node_id), sfx, depth: d.depth });
    }
    ev.sort((a, b) => a.depth - b.depth);
    const targets = nodes.map(n => ({ type: 'node', id: n.id }));
    M.cards.push({ g, id: g.id, time: g.cause.time, nodes, items: list, itemsDown: things.map(t => t.it), ev, targets, count: things.length + ev.length });
  }
  M.todo = M.cards.filter(c => c.targets.some(t => effState(t.type, t.id).state === 'unreviewed')).length;
  M.cards.sort((a, b) => (a.time < b.time ? 1 : a.time > b.time ? -1 : 0));
}
function cardState(c) {
  const sts = c.targets.map(t => effState(t.type, t.id));
  const looked = sts.filter(s => s.state !== 'unreviewed').length;
  let key;
  if (sts.some(s => s.state === 'needs_fixing')) key = 'fix';
  else if (looked === 0) key = 'look';
  else if (looked < sts.length) key = 'partial';
  else if (sts.every(s => s.state === 'ignored')) key = 'ign';
  else key = 'fine';
  return { key, looked, total: sts.length };
}
function consequenceLine(c) {
  if (!c.count) return h('div', { class: 'conseq muted' }, 'Nothing else rests on this yet.');
  const bits = [];
  c.itemsDown.forEach(it => bits.push(h('b', null, lead(it))));
  c.ev.forEach(e => bits.push([e.name.startsWith('the run') ? e.name : mono(e.name), e.sfx ? h('span', { class: 'muted' }, ' (' + e.sfx + ')') : null]));
  const shown = bits.slice(0, 5), more = bits.length - shown.length;
  const out = [];
  shown.forEach((b, i) => { if (i) out.push(', '); out.push(b); });
  return h('div', { class: 'conseq' }, plural(c.count, 'thing') + (c.count === 1 ? ' may' : ' may') + ' need a second look: ', out, more > 0 ? ' and ' + more + ' more' : '');
}

/* ----- triage / checkpoint / link actions ----- */
function dedupe(ts) { const s = new Set(); return ts.filter(t => { const k = t.type + ':' + t.id; if (s.has(k)) return false; s.add(k); return true; }); }
async function setTriageMany(targets, state, note, quiet) {
  if (READONLY) return;
  targets = dedupe(targets);
  try {
    for (const t of targets) {
      const r = await apiPost('/api/triage', { target_type: t.type, target_id: t.id, state, note: note == null ? '' : note });
      const en = r.entry; if (!en.effective_state) { en.effective_state = en.state; en.outdated = false; }
      S.triage.entries[t.type + ':' + t.id] = en;
    }
    computeStatuses(); renderAll();
    if (!quiet) toast('Saved.');
  } catch (e) { toast('Something broke on our side. Your files and marks are unchanged.', { label: 'Details', fn: () => modal('Details', h('p', { class: 'mono' }, e.message), [{ label: 'Close', primary: true }]) }); await refreshTriage(); }
}
async function refreshTriage() { try { S.triage = await apiGet('/api/triage'); computeStatuses(); renderAll(); } catch (e) { /* ignore */ } }
function noteOf(targets) {
  for (const t of targets) { const e = triageEntry(t.type, t.id); if (e && e.note) return e.note; }
  return '';
}
async function createCheckpoint(note) {
  try {
    const r = await apiPost('/api/checkpoints', { note: note || '', at: null });
    S.alarms = r.alarms;
    const [cps, ev, pr, tri] = await Promise.all([apiGet('/api/checkpoints'), apiGet('/api/events'), apiGet('/api/project'), apiGet('/api/triage')]);
    S.checkpoints = cps; S.events = ev; S.project = pr; S.triage = tri;
    rebuildIndex(); renderAll();
    toast('Done. Last looked at: ' + lastChecked(r.checkpoint.created_at) + '.');
  } catch (e) { toast(e.status === 409 ? 'Lemmata is already checking your files. Try again in a moment.' : 'Something broke on our side. Your files and marks are unchanged.'); }
}
function markAllDialog() {
  if (READONLY) return;
  const note = h('input', { type: 'text', maxlength: '500', placeholder: 'Add a note to this mark (optional)', 'aria-label': 'Add a note to this mark (optional)' });
  modal('Mark everything as looked at?', h('div', null, h('p', null, 'Lemmata will start counting changes from now. Your notes and Looks fine / Needs fixing marks are kept. Earlier marks stay in History.'), note),
    [{ label: 'Cancel' }, { label: 'Mark everything as looked at', primary: true, fn: () => createCheckpoint(note.value) }], { width: 440 });
}
async function decideLink(edgeId, decision, doneMsg) {
  if (READONLY) return;
  try {
    await apiPost('/api/links/decide', { edge_id: edgeId, decision });
    await loadAll();
    if (doneMsg) toast(doneMsg);
  } catch (e) { toast('Something broke on our side. Your files and marks are unchanged.'); }
}

/* "Why?" block: the chain of what rests on what, in plain words, then the diff */
const CHAIN_PHRASE = { reads: 'reads', produced_by: 'is produced by', traces_to: 'is built from', includes: 'shows', generated_by: 'is made by', executes: 'runs', imports: 'imports', value_match: 'was linked by you to' };
const cap1 = s => (/^[^\s]*[\/.]/.test(s) ? s : s.charAt(0).toUpperCase() + s.slice(1));
function whyBlock(g, nodeId) {
  const box = h('div', { class: 'why-box' }, h('div', { class: 'muted' }, 'Loading the reason…'));
  ensureAnalysis(g.id, nodeId).then(an => {
    clear(box);
    if (an.failed) { box.append(h('div', { class: 'muted' }, 'The reason could not be loaded. ' + an.failed)); return; }
    const nodes = an.chain.nodes, eds = an.chain.edges;
    const steps = [h('li', null, h('span', { class: 'sw' }, cap1(nameOf(nodes[0])) + ' changed.'))];
    for (let i = 0; i < eds.length; i++) {
      const parts = eds[i].split('|'), from = parts[0], kind = parts[1], to = parts[2];
      const d = (g.downstream || []).find(x => x.node_id === nodes[i + 1]);
      let extra = null;
      if (d && d.output_identical === true) extra = 'It still has exactly the content it had when you last looked, so it may not have been regenerated yet.';
      if (d && d.output_identical === false) extra = 'It was regenerated and its content now differs.';
      steps.push(h('li', null, h('span', { class: 'sw' }, cap1(nameOf(from)) + ' ' + (CHAIN_PHRASE[kind] || 'depends on') + ' ' + nameOf(to) + '.'), extra ? h('div', { class: 'muted' }, extra) : null));
    }
    box.append(h('ol', { class: 'chain' }, steps));
    for (const df of an.diffs || []) {
      box.append(h('div', { class: 'diff-title' }, 'What changed in ', mono(df.path), ' since you last looked'));
      box.append(df.binary ? h('div', { class: 'muted' }, 'This is not a text file, so there is nothing to show line by line.') : diffBlock(df.unified));
      if (df.truncated) box.append(h('div', { class: 'muted' }, 'Only the first part of the change is shown.'));
    }
    box.append(h('details', { class: 'details' }, h('summary', null, 'Details'), h('div', { class: 'mono small' }, an.explanation || ''), h('div', { class: 'mono small muted' }, 'Change ' + g.id + ' · item ' + nodeId)));
  });
  return box;
}

/* ======================================================================
   5. GRAPH. Hand-written canvas + small force simulation (no library).
   ====================================================================== */
const RING = { thesis: 0, rq: 1, section: 2, figure: 3, table: 3, equation: 3, code: 4, data: 4, reference: 5, file: 6 };
const STATUS_COL = { look: '--amber-text', fix: '--red', fine: '--verify', ign: '--muted', ok: '--muted' };
function makeGraph(host, o) {
  o = o || {};
  const cv = h('canvas', { tabindex: o.mini ? '-1' : '0', role: 'img', 'aria-label': o.label || 'Graph of the items of your paper. Use the list view for a text version.' });
  const tipEl = o.mini ? null : h('div', { class: 'gtip hidden' });
  host.append(cv); if (tipEl) host.append(tipEl);
  const ctx = cv.getContext('2d');
  let W = 0, H = 0, dpr = Math.max(1, window.devicePixelRatio || 1);
  const V = { k: 1, tx: 0, ty: 0 };
  let nodes = [], edges = [], byId = new Map(), adj = new Map(), out = new Map(), inn = new Map();
  const pos = o.pos || new Map();
  let hover = null, sel = null, kfocus = null, alpha = 0, raf = 0, needFit = true, labelTop = new Set(), fadeSel = false, emphNid = null, animUntil = 0;
  let C = {};
  const COLMAP = { ink: '--text', paper: '--bg', surface: '--bg', border: '--border', 'border-strong': '--border-strong', muted: '--muted', verify: '--success', amber: '--warning', 'amber-text': '--text-secondary', red: '--error', up: '--accent-dark', 'down-stroke': '--accent-vivid', sunken: '--surface', 'amber-bg': '--surface', 'red-bg': '--surface', 'verify-bg': '--surface' };
  const readColours = () => { C = {}; for (const k in COLMAP) C[k] = css(COLMAP[k]); C.font = css('--font-sans'); C.mono = css('--font-mono'); };
  readColours();
  const widths = new Map();
  function tw(text, font) { const k = font + '|' + text; let w = widths.get(k); if (w == null) { ctx.font = font; w = ctx.measureText(text).width; widths.set(k, w); } return w; }

  function setData(spec) {
    readColours();
    const old = new Map(byId);
    nodes = []; edges = []; byId = new Map(); adj = new Map(); out = new Map(); inn = new Map();
    const ringCount = {}; spec.nodes.forEach(n => { const r = RING[n.kind] == null ? 6 : RING[n.kind]; ringCount[r] = (ringCount[r] || 0) + 1; });
    const ringIdx = {};
    spec.nodes.forEach(n => {
      const node = Object.assign({ x: 0, y: 0, vx: 0, vy: 0, pinned: false, hasPos: false }, n);
      const p = pos.get(n.id), prev = old.get(n.id);
      if (prev) { node.x = prev.x; node.y = prev.y; node.pinned = prev.pinned; node.hasPos = true; }
      else if (p) { node.x = p.x; node.y = p.y; node.pinned = true; node.hasPos = true; }
      nodes.push(node); byId.set(n.id, node);
    });
    spec.nodes.forEach(n => {
      const node = byId.get(n.id); if (node.hasPos || n.sat) return;
      const ring = RING[n.kind] == null ? 6 : RING[n.kind];
      const i = ringIdx[ring] = (ringIdx[ring] == null ? 0 : ringIdx[ring] + 1), cnt = ringCount[ring];
      const R = ring === 0 ? 0 : Math.max(ring * 125, cnt * 34 / (2 * Math.PI));
      const a = (2 * Math.PI * i) / cnt + ring * 0.7;
      node.x = Math.cos(a) * R; node.y = Math.sin(a) * R; node.hasPos = true;
    });
    // satellites start on the side of their parent that faces away from the middle, spread in a fan
    const kids = new Map();
    spec.nodes.forEach(n => { if (n.sat && !byId.get(n.id).hasPos) { let a = kids.get(n.parent); if (!a) kids.set(n.parent, a = []); a.push(byId.get(n.id)); } });
    const seedKids = pid => {
      const p = byId.get(pid), list = kids.get(pid); if (!p || !list) return;
      const out = Math.atan2(p.y, p.x) || 0, span = Math.min(2 * Math.PI, 0.55 * list.length + 0.6);
      list.forEach((k, i) => { const a = out + (list.length > 1 ? (i / (list.length - 1) - 0.5) * span : 0); k.x = p.x + Math.cos(a) * (p.r + 28); k.y = p.y + Math.sin(a) * (p.r + 28); k.hasPos = true; });
      list.forEach(k => seedKids(k.id));
    };
    for (const pid of [...kids.keys()]) if (!(byId.get(pid) || {}).sat) seedKids(pid);
    const sibs = new Map(); for (const e of spec.edges) if (e.sat) sibs.set(e.a, (sibs.get(e.a) || 0) + 1);
    for (const e of spec.edges) {
      const s = byId.get(e.a), t = byId.get(e.b); if (!s || !t) continue;
      const len = e.sat ? s.r + t.r + 26 + 2.4 * (sibs.get(e.a) || 0) : 76 + 0.7 * (s.r + t.r);
      edges.push({ a: e.a, b: e.b, s, t, len, rel: e.rel, sat: !!e.sat });
      for (const [m, k, v] of [[adj, e.a, e.b], [adj, e.b, e.a], [out, e.a, e.b], [inn, e.b, e.a]]) { let x = m.get(k); if (!x) m.set(k, x = new Set()); x.add(v); }
    }
    nodes.forEach(n => { n.deg = (adj.get(n.id) || new Set()).size || 1; });
    const real = nodes.filter(n => !n.sat).sort((a, b) => b.imp - a.imp);
    labelTop = new Set(real.slice(0, Math.min(o.mini ? 5 : 16, Math.max(o.mini ? 5 : 8, Math.ceil(0.2 * real.length)))).map(n => n.id));
    if (sel && !byId.has(sel)) sel = null;
    // only satellites came or went: keep every real item where it is and let just the satellites settle
    const realNow = nodes.filter(n => !n.sat), realOld = [...old.values()].filter(n => !n.sat);
    const soft = old.size > 0 && realNow.length === realOld.length && realNow.every(n => old.has(n.id) && !old.get(n.id).sat);
    const now = performance.now();
    for (const n of nodes) if (old.size && !old.has(n.id) && n.sat) { n.born = now; animUntil = now + 300; }
    if (soft) { const keep = realNow.map(n => [n, n.pinned]); keep.forEach(([n]) => { n.pinned = true; }); settle(90, 0.6); keep.forEach(([n, pn]) => { n.pinned = pn; }); }
    else settle(old.size ? 140 : 300, old.size ? 0.7 : 1);
    if (!old.size) needFit = true;
    request();
  }
  function hashStr(s) { let x = 0; for (let i = 0; i < s.length; i++) x = (x * 31 + s.charCodeAt(i)) >>> 0; return x; }
  function step(a) {
    for (const e of edges) {
      const s = e.s, t = e.t; let dx = t.x - s.x, dy = t.y - s.y; const d = Math.hypot(dx, dy) || 1e-6;
      const f = (d - e.len) / d * a * 0.4, bias = s.deg / (s.deg + t.deg);
      if (!t.pinned) { t.vx -= dx * f * bias; t.vy -= dy * f * bias; }
      if (!s.pinned) { s.vx += dx * f * (1 - bias); s.vy += dy * f * (1 - bias); }
    }
    const n = nodes.length;
    for (let i = 0; i < n; i++) {
      const A = nodes[i];
      for (let j = i + 1; j < n; j++) {
        const B = nodes[j]; let dx = B.x - A.x, dy = B.y - A.y, d2 = dx * dx + dy * dy;
        if (d2 < 1e-4) { dx = (i % 7) - 3 + 0.5; dy = (j % 5) - 2 + 0.5; d2 = dx * dx + dy * dy; }
        if (d2 > 90000) continue;
        const d = Math.sqrt(d2), sA = 120 + 12 * A.r, sB = 120 + 12 * B.r, dd = Math.max(d2, 900);
        if (!A.pinned) { A.vx -= dx * sB * a / dd; A.vy -= dy * sB * a / dd; }
        if (!B.pinned) { B.vx += dx * sA * a / dd; B.vy += dy * sA * a / dd; }
        const sep = A.r + B.r + 16;
        if (d < sep) {
          const p = (sep - d) / d * 0.5 * 0.9;
          if (!A.pinned) { A.x -= dx * p; A.y -= dy * p; }
          if (!B.pinned) { B.x += dx * p; B.y += dy * p; }
        }
      }
    }
    for (const q of nodes) {
      if (q.pinned || q.drag) { q.vx = q.vy = 0; continue; }
      q.vx -= q.x * 0.035 * a; q.vy -= q.y * 0.035 * a;
      q.vx *= 0.6; q.vy *= 0.6; q.x += q.vx; q.y += q.vy;
    }
  }
  function settle(ticks, a0) { let a = a0; for (let i = 0; i < ticks; i++) { step(a); a *= 0.9772; } }
  function animate() {
    raf = 0;
    if (alpha > 0.004) { step(alpha); alpha *= 0.94; request(true); }
    draw();
    if (performance.now() < animUntil) request(true);
  }
  function request(anim) { if (!raf) raf = requestAnimationFrame(animate); }
  function reheat(a) { alpha = Math.max(alpha, a); request(); }

  function resize() {
    const r = host.getBoundingClientRect(); const w = Math.round(r.width), hh = Math.round(r.height);
    if (!w || !hh) return;
    dpr = Math.max(1, window.devicePixelRatio || 1);
    if (w !== W || hh !== H || cv.width !== Math.round(w * dpr)) { W = w; H = hh; cv.width = Math.round(w * dpr); cv.height = Math.round(hh * dpr); cv.style.width = w + 'px'; cv.style.height = hh + 'px'; if (needFit) fit(); }
    request();
  }
  function fit(pad) {
    if (!W || !nodes.length) return;
    pad = pad == null ? (o.mini ? 14 : 40) : pad;
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (const n of nodes) { x0 = Math.min(x0, n.x - n.r); x1 = Math.max(x1, n.x + n.r); y0 = Math.min(y0, n.y - n.r); y1 = Math.max(y1, n.y + n.r); }
    const bw = Math.max(1, x1 - x0), bh = Math.max(1, y1 - y0 + (o.mini ? 0 : 30));
    V.k = Math.max(0.25, Math.min((W - 2 * pad) / bw, (H - 2 * pad - (o.mini ? 24 : 80)) / bh, o.mini ? 1 : 1.25));
    V.tx = W / 2 - ((x0 + x1) / 2) * V.k; V.ty = (H - (o.mini ? 24 : 70)) / 2 - ((y0 + y1) / 2) * V.k + (o.mini ? 0 : -8);
    needFit = false; request();
  }
  function zoomAt(f, cx, cy) {
    const k2 = Math.max(0.25, Math.min(4, V.k * f)); f = k2 / V.k;
    V.tx = cx - (cx - V.tx) * f; V.ty = cy - (cy - V.ty) * f; V.k = k2; request();
  }
  const toWorld = (sx, sy) => ({ x: (sx - V.tx) / V.k, y: (sy - V.ty) / V.k });
  function hit(sx, sy) {
    const w = toWorld(sx, sy); let best = null, bd = 1e9;
    for (const n of nodes) {
      const rr = Math.max(n.r, 9 / V.k) + 3 / V.k, d = Math.hypot(n.x - w.x, n.y - w.y);
      if (d <= rr && d - n.r < bd) { best = n; bd = d - n.r; }
    }
    return best;
  }
  function nbSet(f) { const s = new Set([f]); (adj.get(f) || new Set()).forEach(x => s.add(x)); return s; }
  function selSet() {   // the selected item, what touches it, its satellites and what those touch
    if (!sel || !fadeSel || o.mini || !byId.has(sel)) return null;
    const s = nbSet(sel);
    for (const n of nodes) if (n.sat && s.has(n.id)) (adj.get(n.id) || new Set()).forEach(x => s.add(x));
    return s;
  }
  function focusSet() {   // everything outside this set is faded
    const hs = hover ? nbSet(hover) : null, ss = selSet();
    if (hs && ss) { ss.forEach(x => hs.add(x)); return hs; }
    return hs || ss;
  }
  const BADGE = { look: '↻', fix: '✕', fine: '✓', ign: '–' };
  function ringOf(n, q, ctx2) {   // status is only ever a ring or a badge, never the fill: type owns the colour
    const st = n.status, k = n.sat ? 0.6 : 1;
    ctx2.setLineDash([]);
    const ring = (gap, w, col, dash) => { ctx2.beginPath(); ctx2.arc(q.x, q.y, q.r + gap, 0, 6.2832); ctx2.lineWidth = w; ctx2.strokeStyle = col; ctx2.setLineDash(dash || []); ctx2.stroke(); ctx2.setLineDash([]); };
    if (st === 'look') ring(4.5 * k + 1, 3 * k + 0.4, C.amber, [6 * k + 1, 4 * k]);
    else if (st === 'fix') { ring(4.5 * k + 1, 3 * k + 0.4, C.red); if (!n.sat) ring(8.5, 1.2, C.red); }
    else if (st === 'ign') ring(4, 1.2, C.muted, [1.5, 3]);
  }
  function draw() {
    if (!W) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
    const dimS = focusSet(), f = hover || sel, now = performance.now();
    const P = n => {   // satellites grow out of their parent
      if (!n.born) return n;
      const t = (now - n.born) / 260; if (t >= 1) { n.born = 0; return n; }
      const e = 1 - Math.pow(1 - Math.max(0, t), 3), p = byId.get(n.parent) || n;
      return { x: p.x + (n.x - p.x) * e, y: p.y + (n.y - p.y) * e, r: n.r * (0.35 + 0.65 * e), a: e };
    };
    ctx.save(); ctx.translate(V.tx, V.ty); ctx.scale(V.k, V.k);
    for (const e of edges) {
      const touch = f && (e.a === f || e.b === f), sp = P(e.s), tp = P(e.t), lit = dimS && dimS.has(e.a) && dimS.has(e.b);
      ctx.beginPath(); ctx.moveTo(sp.x, sp.y); ctx.lineTo(tp.x, tp.y);
      if (e.sat && fadeSel && lit) { ctx.globalAlpha = 0.9 * (tp.a || 1); ctx.lineWidth = 1.7 / V.k; ctx.strokeStyle = C.up; ctx.setLineDash([]); }
      else if (touch && !e.sat) {
        ctx.globalAlpha = 1; ctx.lineWidth = 2 / V.k;
        if (e.a === f) { ctx.strokeStyle = C.up; ctx.setLineDash([]); } else { ctx.strokeStyle = C['down-stroke']; ctx.setLineDash([6 / V.k, 4 / V.k]); }
      } else { ctx.globalAlpha = dimS ? (lit ? 0.4 : 0.06) : (e.sat ? 0.3 : 0.4); ctx.lineWidth = 1 / V.k; ctx.strokeStyle = C['border-strong']; ctx.setLineDash(e.sat ? [3 / V.k, 3 / V.k] : []); }
      ctx.stroke();
    }
    ctx.setLineDash([]); ctx.globalAlpha = 1;
    for (const n of nodes) {
      const q = P(n);
      let a = 1;
      if (dimS && !dimS.has(n.id)) a = 0.15; else if (!dimS && o.dimOk && n.status === 'ok' && !n.sat) a = 0.35;
      ctx.globalAlpha = a * (q.a || 1);
      ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, 6.2832); ctx.fillStyle = n.tint || C.sunken; ctx.fill();
      ctx.lineWidth = n.sat ? 1.8 : 2.2; ctx.strokeStyle = n.col || C['border-strong']; ctx.setLineDash(n.dash ? [4, 3] : []); ctx.stroke(); ctx.setLineDash([]);
      ringOf(n, q, ctx);
      const emph = emphNid && (n.nid === emphNid || n.id === emphNid);
      if (sel === n.id || emph) { ctx.beginPath(); ctx.arc(q.x, q.y, q.r + (n.status === 'fix' || n.status === 'look' ? 9 : 5) * (n.sat ? 0.8 : 1), 0, 6.2832); ctx.lineWidth = emph && n.sat ? 2.6 : 3; ctx.strokeStyle = C.ink; ctx.stroke(); }
      if (kfocus === n.id) { ctx.beginPath(); ctx.arc(q.x, q.y, q.r + 8, 0, 6.2832); ctx.lineWidth = 2; ctx.strokeStyle = C.ink; ctx.setLineDash([3, 3]); ctx.stroke(); ctx.setLineDash([]); }
      if (n.glyph && (!n.sat || q.r >= 9)) {
        ctx.fillStyle = C.ink; ctx.font = '600 ' + Math.round(n.sat ? 10 : Math.max(10, Math.min(q.r * 0.85, 26))) + 'px ' + C.mono; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(n.glyph, q.x, q.y + 1);
      }
      if (!n.sat && n.status && n.status !== 'ok') {
        const bx = q.x + q.r * 0.72, by = q.y - q.r * 0.72, br = Math.max(8, Math.min(11, q.r * 0.45)), sc = C[STATUS_COL[n.status].slice(2)];
        ctx.beginPath(); ctx.arc(bx, by, br, 0, 6.2832); ctx.fillStyle = C.surface; ctx.fill(); ctx.lineWidth = 1.2; ctx.strokeStyle = sc; ctx.stroke();
        ctx.fillStyle = sc; ctx.font = '700 ' + Math.round(br * 1.1) + 'px ' + C.font; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(BADGE[n.status] || '', bx, by + 0.5);
      }
      if (n.pinned && !n.sat) { ctx.beginPath(); ctx.arc(q.x - q.r * 0.72, q.y - q.r * 0.72, 3, 0, 6.2832); ctx.fillStyle = C.ink; ctx.fill(); }
    }
    ctx.restore(); ctx.globalAlpha = 1;
    drawLabels(dimS || (sel && !o.mini ? nbSet(sel) : null), dimS);
  }
  function drawLabels(fs, dimS) {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    const placed = [], circles = nodes.map(n => ({ id: n.id, x: n.x * V.k + V.tx, y: n.y * V.k + V.ty, r: n.r * V.k }));
    const cand = [];
    const real = nodes.filter(n => !n.sat);
    for (const n of real) {
      let pr = 9;
      if (hover === n.id || sel === n.id || (emphNid && n.id === emphNid)) pr = 0;
      else if (fs && fs.has(n.id)) pr = 1;
      else if (dimS) continue;
      else if (n.status !== 'ok') pr = 2;
      else if (labelTop.has(n.id)) pr = 3;
      else if (n.r * V.k >= 9) pr = 5;
      else continue;
      if (o.mini && pr > 1 && pr !== 3) continue;
      cand.push({ n, pr });
    }
    const have = new Set(cand.map(c => c.n.id));
    for (const n of nodes) if (n.sat && !have.has(n.id)) {
      const em = emphNid && n.nid === emphNid;
      if (hover === n.id || em) cand.push({ n, pr: 0 }); else if (fadeSel && dimS && dimS.has(n.id) && !n.born) cand.push({ n, pr: 1 });
    }
    cand.sort((a, b) => a.pr - b.pr || b.n.imp - a.n.imp);
    const hits = (r, self) => {
      if (r.x < 2 || r.y < 2 || r.x + r.w > W - 2 || r.y + r.h > H - 2) return true;
      for (const p of placed) if (r.x < p.x + p.w + 2 && r.x + r.w + 2 > p.x && r.y < p.y + p.h + 2 && r.y + r.h + 2 > p.y) return true;
      for (const c of circles) { if (c.id === self) continue; const cx = Math.max(r.x, Math.min(c.x, r.x + r.w)), cy = Math.max(r.y, Math.min(c.y, r.y + r.h)); if ((cx - c.x) ** 2 + (cy - c.y) ** 2 < c.r * c.r) return true; }
      return false;
    };
    for (const { n, pr } of cand) {
      const full = trunc(n.sat ? n.label : (n.short || n.title), o.mini ? 18 : 26), variants = [[full, 1]];
      if (!n.sat && full.includes(' · ')) variants.push([full.split(' · ')[0], 1]);
      if (!n.sat && n.status !== 'ok' && pr <= 2 && !o.mini) { variants.push([full, 0]); if (full.includes(' · ')) variants.push([full.split(' · ')[0], 0]); }
      let title = full, w = 0, hh = 0, pos2 = null;
      for (const [v, withS] of variants) {
        title = v;
        const px = o.mini || n.sat ? 11 : (n.r < 20 ? 12 : 13), font = (pr === 0 ? '600 ' : '') + px + 'px ' + C.font;
        const flag = withS && !n.sat && n.status !== 'ok' && !o.mini && pr <= 2;
        const sline = flag ? ST[n.status].glyph + ' ' + ST[n.status].say : null;
        w = Math.max(tw(v, font), sline ? tw(sline, '11px ' + C.font) : 0); hh = px + 3 + (sline ? 14 : 0);
        const sx = n.x * V.k + V.tx, sy = n.y * V.k + V.ty, rr = n.r * V.k;
        const tries = [[sx - w / 2, sy + rr + 3], [sx + rr + 10, sy - hh / 2], [sx - rr - 10 - w, sy - hh / 2], [sx - w / 2, sy - rr - 3 - hh]];
        if (fadeSel && sel === n.id) tries.unshift(tries.pop());   // satellites fan outwards, so keep the item's own label on the inner side
        for (const t of tries) { const r = { x: t[0], y: t[1], w, h: hh }; if (!hits(r, n.id)) { pos2 = r; break; } }
        if (pos2) { n._px = px; n._font = font; n._sline = sline; break; }
        if (v === variants[variants.length - 1][0] && withS === variants[variants.length - 1][1] && pr <= 2) { pos2 = { x: Math.max(2, Math.min(W - w - 2, tries[0][0])), y: Math.min(tries[0][1], H - hh - 2), w, h: hh }; n._px = px; n._font = font; n._sline = sline; }
      }
      if (!pos2) continue;
      const fpx = n._px, font = n._font, sline = n._sline;
      placed.push(pos2);
      ctx.globalAlpha = 1; ctx.lineJoin = 'round';
      const cx = pos2.x + w / 2;
      ctx.textAlign = 'center';
      ctx.font = font; ctx.lineWidth = 3; ctx.strokeStyle = C.paper; ctx.strokeText(title, cx, pos2.y); ctx.fillStyle = C.ink; ctx.fillText(title, cx, pos2.y);
      if (sline) { ctx.font = '600 11px ' + C.font; ctx.strokeText(sline, cx, pos2.y + fpx + 3); ctx.fillStyle = C[STATUS_COL[n.status].slice(2)]; ctx.fillText(sline, cx, pos2.y + fpx + 3); }
    }
    ctx.textAlign = 'left';
  }

  /* ----- interaction ----- */
  let drag = null, moved = false;
  const evPos = ev => { const r = cv.getBoundingClientRect(); return { x: ev.clientX - r.left, y: ev.clientY - r.top }; };
  cv.addEventListener('mousedown', ev => {
    if (ev.button !== 0) return;
    const p = evPos(ev), n = hit(p.x, p.y); moved = false;
    if (n && !o.mini) { drag = { type: 'node', n, sx: p.x, sy: p.y }; n.drag = true; }
    else drag = { type: 'pan', sx: p.x, sy: p.y, tx: V.tx, ty: V.ty, n };
    cv.focus({ preventScroll: true });
  });
  const onMove = ev => {
    if (!cv.isConnected) return;
    const p = evPos(ev);
    if (drag) {
      if (Math.hypot(p.x - drag.sx, p.y - drag.sy) > 3) moved = true;
      if (moved) {
        if (drag.type === 'node') { const w = toWorld(p.x, p.y); drag.n.x = w.x; drag.n.y = w.y; drag.n.pinned = true; reheat(0.25); }
        else { V.tx = drag.tx + p.x - drag.sx; V.ty = drag.ty + p.y - drag.sy; request(); }
        hideTip();
      }
      return;
    }
    const r = cv.getBoundingClientRect();
    if (p.x < 0 || p.y < 0 || p.x > r.width || p.y > r.height) { if (hover) { hover = null; cv.style.cursor = ''; hideTip(); request(); if (o.onHover) o.onHover(null); } return; }
    const n = hit(p.x, p.y), id = n ? n.id : null;
    cv.style.cursor = n ? 'pointer' : 'grab';
    if (id !== hover) { hover = id; request(); if (o.onHover && !(n && n.sat)) o.onHover(id); }
    if (n) showTip(n, p); else hideTip();
  };
  const onUp = ev => {
    if (!drag) return;
    const d = drag; drag = null; if (d.n) d.n.drag = false;
    if (!moved) {
      if (d.n) { if (d.n.sat) { if (o.onClickSat) o.onClickSat(d.n); } else { sel = d.n.id; kfocus = null; if (o.onClick) o.onClick(d.n.id, ev); request(); } }
      else if (!o.mini) { sel = null; if (o.onClick) o.onClick(null, ev); request(); }
    } else if (d.type === 'node') { pos.set(d.n.id, { x: d.n.x, y: d.n.y }); if (o.onPin) o.onPin(pos); }
  };
  window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp);
  cv.addEventListener('dblclick', ev => { const p = evPos(ev), n = hit(p.x, p.y); if (n && o.onOpen) o.onOpen(n); });
  cv.addEventListener('wheel', ev => { if (o.mini) return; ev.preventDefault(); const p = evPos(ev); zoomAt(ev.deltaY < 0 ? 1.12 : 1 / 1.12, p.x, p.y); }, { passive: false });
  cv.addEventListener('keydown', ev => {
    if (o.mini) return;
    const order = nodes.filter(n => !n.sat).sort((a, b) => b.imp - a.imp).map(n => n.id);
    if (ev.key === 'Tab') {
      const i = order.indexOf(kfocus), j = i + (ev.shiftKey ? -1 : 1);
      if (j >= 0 && j < order.length) { ev.preventDefault(); kfocus = order[j]; hover = null; request(); if (o.onFocus) o.onFocus(kfocus); }
    } else if (ev.key === 'Enter' && kfocus) { sel = kfocus; if (o.onClick) o.onClick(kfocus, ev); request(); }
    else if (ev.key === 'Escape') { sel = null; kfocus = null; if (o.onClick) o.onClick(null, ev); request(); }
    else if (ev.key.startsWith('Arrow')) {
      ev.preventDefault();
      const from = byId.get(kfocus || sel); if (!from) { kfocus = order[0]; request(); return; }
      const dx = ev.key === 'ArrowRight' ? 1 : ev.key === 'ArrowLeft' ? -1 : 0, dy = ev.key === 'ArrowDown' ? 1 : ev.key === 'ArrowUp' ? -1 : 0;
      let best = null, bs = 1e9;
      for (const id of adj.get(from.id) || []) { const n = byId.get(id); if (!n || n.sat) continue; const vx = n.x - from.x, vy = n.y - from.y, dot = (vx * dx + vy * dy) / (Math.hypot(vx, vy) || 1); if (dot > 0.3) { const sc = Math.hypot(vx, vy) / dot; if (sc < bs) { bs = sc; best = n; } } }
      if (best) { kfocus = best.id; request(); if (o.onFocus) o.onFocus(kfocus); }
    }
  });
  cv.addEventListener('mouseleave', () => { if (!drag && hover) { hover = null; hideTip(); request(); if (o.onHover) o.onHover(null); } });
  function showTip(n, p) {
    if (!tipEl || !o.tooltip) return;
    clear(tipEl).append(o.tooltip(n)); tipEl.classList.remove('hidden');
    tipEl.style.left = Math.min(p.x + 14, W - 270) + 'px'; tipEl.style.top = Math.min(p.y + 16, H - 90) + 'px';
  }
  function hideTip() { if (tipEl) tipEl.classList.add('hidden'); }
  const ro = new ResizeObserver(() => resize()); ro.observe(host);
  return {
    setData, fit: () => { fit(); }, resize, redraw: request,
    zoomBy: f => zoomAt(f, W / 2, H / 2),
    setSelected(id, fade) { sel = id; fadeSel = !!fade && !!id; request(); },
    setEmph(nid) { emphNid = nid || null; request(); },
    reveal(id) {   // nudge the view so the item and its satellites are on screen
      const n = byId.get(id); if (!n || !W) return;
      let x0 = n.x - n.r, x1 = n.x + n.r, y0 = n.y - n.r, y1 = n.y + n.r;
      for (const m of nodes) if (m.sat) { x0 = Math.min(x0, m.x - m.r - 40); x1 = Math.max(x1, m.x + m.r + 40); y0 = Math.min(y0, m.y - m.r - 22); y1 = Math.max(y1, m.y + m.r + 22); }
      const pad = 16, bot = H - 96; let dx = 0, dy = 0;
      const sx0 = x0 * V.k + V.tx, sx1 = x1 * V.k + V.tx, sy0 = y0 * V.k + V.ty, sy1 = y1 * V.k + V.ty;
      if (sx0 < pad) dx = pad - sx0; else if (sx1 > W - pad) dx = W - pad - sx1;
      if (sy0 < pad) dy = pad - sy0; else if (sy1 > bot) dy = bot - sy1;
      if (sx1 - sx0 > W - 2 * pad) dx = (W - (sx0 + sx1)) / 2;
      if (dx || dy) { V.tx += dx; V.ty += dy; request(); }
    },
    rearrange() { pos.clear(); nodes.forEach(n => { n.pinned = false; }); if (o.onPin) o.onPin(pos); nodes.forEach(n => { n.x *= 0.3; n.y *= 0.3; }); settle(300, 1); fit(); },
    focusOn(id) { const n = byId.get(id); if (n && W) { V.tx = W / 2 - n.x * V.k; V.ty = H / 2 - n.y * V.k; sel = id; request(); } },
    visible: () => nodes.filter(n => !n.sat).map(n => n.id),
    patch(spec) { for (const s of spec) { const n = byId.get(s.id); if (n) { n.status = s.status; n.short = s.short; n.title = s.title; n.item = s.item || n.item; } } request(); },
    dimOnly(v) { o.dimOk = v; request(); },
    hl(id) { hover = id; request(); },
    destroy() { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); ro.disconnect(); if (raf) cancelAnimationFrame(raf); },
  };
}

/* ======================================================================
   6. PAGES (centre)
   ====================================================================== */
function menuPop(anchor, entries, opts) {
  const old = $('#menu'); if (old) { old.remove(); if (old._anchor === anchor) return; }
  opts = opts || {};
  const r = anchor.getBoundingClientRect();
  const m = h('div', { id: 'menu', class: 'menu', role: 'menu' }, entries.map(e => {
    if (e.sep) return h('div', { class: 'msep' });
    if (e.head) return h('div', { class: 'mhead' }, e.head);
    const cls = 'mitem' + (e.disabled ? ' off' : '');
    const inner = [h('span', null, e.label), e.hint ? h('span', { class: 'mhint' }, e.hint) : null];
    if (e.href) return h('a', { class: cls, role: 'menuitem', href: e.href, download: e.download ? '' : null, onclick: () => m.remove() }, inner);
    return h('button', { class: cls, role: 'menuitem', disabled: e.disabled || !e.fn, onclick: () => { m.remove(); if (e.fn) e.fn(); } }, inner);
  }));
  m._anchor = anchor;
  document.body.append(m);
  const mw = m.offsetWidth, mh = m.offsetHeight;
  let left = opts.right ? r.right - mw : r.left, top = opts.up ? r.top - mh - 4 : r.bottom + 4;
  if (opts.side) { left = r.right + 6; top = Math.max(8, r.bottom - mh); }
  m.style.left = Math.max(8, Math.min(left, innerWidth - mw - 8)) + 'px'; m.style.top = Math.max(8, Math.min(top, innerHeight - mh - 8)) + 'px';
  const off = ev => { if (!m.contains(ev.target) && ev.target !== anchor) { m.remove(); document.removeEventListener('mousedown', off, true); } };
  setTimeout(() => document.addEventListener('mousedown', off, true), 0);
  const first = m.querySelector('button:not(:disabled), a'); if (first) first.focus();
  m.addEventListener('keydown', ev => { if (ev.key === 'Escape') { m.remove(); anchor.focus(); } });
}
const doc = (...kids) => h('div', { class: 'doc' }, kids);
function sec(title, id, ...kids) {
  S.outline.push({ id, label: title });
  return h('section', { class: 'dsec', id: 'sec-' + id }, h('h3', null, title), kids);
}
function emptyState(glyph, title, sub, actions) {
  return h('div', { class: 'empty-state' }, h('div', { class: 'big' }, glyph), h('div', { class: 'et' }, title), sub ? h('div', { class: 'muted' }, sub) : null, actions ? h('div', { class: 'acts' }, actions) : null);
}
function itemLink(it, cls) {
  return h('button', { class: 'ilink ' + (cls || ''), onclick: ev => openItem(it.id, ev.metaKey || ev.ctrlKey), title: ST[it.status].word }, h('span', { class: 'sg ' + it.status, 'aria-hidden': 'true' }, ST[it.status].glyph), ' ', it.title);
}
function triageButtons(targets, cur, key, opts) {
  opts = opts || {};
  const noteOpen = !!S.noteOpen[key];
  const b = (state, label) => h('button', { class: 'btn s-' + state, 'aria-pressed': String(cur === state), disabled: READONLY, title: READONLY ? 'Read-only snapshot' : null, 'data-triage': state,
    onclick: () => {
      if (state === 'needs_fixing' && cur !== state) { S.noteOpen[key] = true; renderPage(true); setTimeout(() => { const i = $('#note-' + CSS.escape(key)); if (i) i.focus(); }, 0); return; }
      setTriageMany(targets, cur === state ? 'unreviewed' : state, noteOf(targets));
    } }, label);
  return h('div', { class: 'tri-wrap' },
    h('div', { class: 'tri' }, b('reviewed', 'Looks fine'), b('needs_fixing', 'Needs fixing'), b('ignored', 'Ignore')),
    noteOpen ? h('div', { class: 'noterow' },
      h('input', { type: 'text', id: 'note-' + key, maxlength: '2000', placeholder: 'Add a note (optional)', 'aria-label': 'Add a note (optional)', value: noteOf(targets), onkeydown: ev => { if (ev.key === 'Enter') ev.target.nextSibling.click(); } }),
      h('button', { class: 'btn primary', onclick: ev => { const v = ev.target.previousSibling.value; S.noteOpen[key] = false; setTriageMany(targets, 'needs_fixing', v); } }, 'Save'),
      h('button', { class: 'btn', onclick: () => { S.noteOpen[key] = false; renderPage(true); } }, 'Cancel')) : null);
}

/* ---------- Changes ---------- */
function cpDate() { const cp = S.alarms && S.alarms.checkpoint; return cp ? dmon(cp.created_at) : null; }
function pageChanges() {
  const cp = S.alarms && S.alarms.checkpoint;
  const root = doc(h('h1', { class: 'ptitle' }, 'What changed since you last looked'));
  if (S.loading) { root.append(h('div', { class: 'muted' }, 'Reading your paper and code…'), [1, 2, 3].map(() => h('div', { class: 'skelcard' }))); return root; }
  if (!cp) {
    root.append(emptyState('○', 'You haven\'t set a starting point yet.', 'Lemmata needs to know when you last felt sure about your paper. It will then list everything that changes after that.',
      [h('button', { class: 'btn primary', disabled: READONLY, onclick: () => createCheckpoint('') }, 'Start tracking from now')]));
    return root;
  }
  const full = (S.checkpoints && S.checkpoints.checkpoints || []).find(c => c.id === cp.id) || cp;
  root.append(h('div', { class: 'subline' }, h('span', null, 'Last looked at: ' + lastChecked(cp.created_at)), cp.note ? h('span', { class: 'muted' }, ' · note "' + cp.note + '"') : null,
    h('button', { class: 'btn', disabled: READONLY, title: READONLY ? 'Read-only snapshot' : null, onclick: markAllDialog }, 'Mark everything as looked at')));
  const cards = M.cards, nChecks = (S.findings && S.findings.findings || []).length;
  if (!cards.length) {
    root.append(emptyState('✓', 'Nothing has changed since ' + absTime(cp.created_at) + '.', 'Everything Lemmata knows about is as you left it.',
      [h('button', { class: 'linkbtn', onclick: () => openTab('checks') }, 'See your checks (' + nChecks + ')'), h('button', { class: 'linkbtn', onclick: () => openTab('graph') }, 'Open the graph')]));
    return root;
  }
  root.append(h('div', { class: 'summary' },
    h('button', { class: 'linkbtn', onclick: () => $('.card') && $('.card').scrollIntoView({ block: 'start' }) }, plural(cards.length, 'change')), ' · ',
    h('button', { class: 'linkbtn', onclick: () => { S.chFilter = 'look'; renderPage(true); } }, plural(M.todo, 'thing') + ' still to look at'), ' · ',
    h('button', { class: 'linkbtn', onclick: () => openTab('checks') }, plural(nChecks, 'check') + ' about your paper')));
  const counts = { all: cards.length, look: 0, fix: 0, fine: 0, ign: 0 };
  cards.forEach(c => { const k = cardState(c).key; counts[k === 'partial' ? 'look' : k]++; });
  const chips = [['all', 'All'], ['look', 'Not looked at'], ['fix', 'Needs fixing'], ['fine', 'Looks fine'], ['ign', 'Ignored']];
  root.append(h('div', { class: 'fchips', role: 'group', 'aria-label': 'Filter changes' }, chips.map(([k, l]) => h('button', { class: 'fchip', 'aria-pressed': String(S.chFilter === k), onclick: () => { S.chFilter = k; renderPage(true); } }, l + ' ', h('span', { class: 'n' }, counts[k])))));
  let lastDay = null, shown = 0;
  for (const c of cards) {
    const k = cardState(c).key, kk = k === 'partial' ? 'look' : k;
    if (S.chFilter !== 'all' && kk !== S.chFilter) continue;
    const day = dayHeader(c.time);
    if (day !== lastDay) { root.append(h('div', { class: 'dayhead' }, day)); lastDay = day; }
    root.append(cardEl(c)); shown++;
  }
  if (!shown) root.append(h('div', { class: 'muted pad-t' }, 'No changes match this filter.'));
  return root;
}
function cardEl(c) {
  const st = cardState(c), g = c.g;
  const label = st.key === 'partial' ? plainChip('↻', 'Partly looked at (' + st.looked + ' of ' + st.total + ')', 'look') : chip(st.key);
  const done = (st.key === 'fine' || st.key === 'ign' || st.key === 'fix') && !S.openCard[c.id];
  if (done) {
    return h('article', { class: 'card done', 'data-card': c.id }, h('div', { class: 'cardline' }, label, causeLine(g),
      h('button', { class: 'linkbtn', onclick: () => { S.openCard[c.id] = true; renderPage(true); } }, 'Show'),
      h('button', { class: 'linkbtn', disabled: READONLY, onclick: () => setTriageMany(c.targets, 'unreviewed', noteOf(c.targets)) }, 'Undo')));
  }
  const primary = (c.itemsDown[0] || c.items[0]);
  const whyKey = 'card:' + c.id, whyNode = pickWhyNode(c);
  const flag = (g.flags || []).find(f => f.code === 'message_claims_no_change');
  const rows = [];
  const changedRows = c.nodes.filter(n => n.role === 'changed');
  for (const n of changedRows) rows.push(h('div', { class: 'arow' }, plainChip('•', 'Changed'), ' ', PAPER.has((IX.node.get(n.id) || {}).kind) ? nameOf(n.id) : mono(nameOf(n.id))));
  for (const it of c.itemsDown.concat(c.items.filter(i => !c.itemsDown.includes(i) && !c.nodes.some(n => n.role === 'changed' && M.itemsOf.get(n.id) && M.itemsOf.get(n.id).includes(i.id) && !it_isPaperNode(n.id))))) {
    if (changedRows.some(n => M.paperId.get(n.id) === it.id)) continue;
    const evs = c.ev.filter(e => (M.itemsOf.get(e.id) || []).includes(it.id));
        rows.push(h('div', { class: 'arow' }, chip(it.status), ' ', h('button', { class: 'ilink', onclick: ev => openItem(it.id, ev.metaKey || ev.ctrlKey) }, it.title), h('span', { class: 'muted' }, '  ' + kindLabelShort(it)),
      evs.length ? h('div', { class: 'aev muted' }, evs.map((e, i) => h('span', null, i ? ' · ' : '', e.name.startsWith('the run') ? e.name : mono(e.name), e.sfx ? ' (' + e.sfx + ')' : ''))) : null));
  }
  const openBtn = !primary ? null : (c.itemsDown.length + c.items.length > 1 && new Set(c.itemsDown.concat(c.items)).size > 1)
    ? h('button', { class: 'btn', onclick: ev => menuPop(ev.currentTarget, [...new Set(c.itemsDown.concat(c.items))].map(it => ({ label: it.title, fn: () => openItem(it.id) })), { right: true }) }, 'Open items ▾')
    : h('button', { class: 'btn', onclick: ev => openItem(primary.id, ev.metaKey || ev.ctrlKey) }, 'Open ' + lead(primary));
  return h('article', { class: 'card st-' + st.key, 'data-card': c.id },
    h('div', { class: 'cardhead' }, label, h('div', { class: 'cause-line' }, causeLine(g))),
    consequenceLine(c),
    h('div', { class: 'alist' }, rows),
    flag ? h('div', { class: 'flag' }, '⚑ The commit message says "' + flag.phrase + '", but content changed in ' + plural((g.cause.files || []).length || g.changed.length, 'file') + '.') : null,
    S.openWhy[whyKey] ? whyBlock(g, whyNode) : null,
    h('div', { class: 'btnrow' },
      h('button', { class: 'btn', 'aria-expanded': String(!!S.openWhy[whyKey]), onclick: () => { S.openWhy[whyKey] = !S.openWhy[whyKey]; renderPage(true); } }, 'Why?'),
      triageButtons(c.targets, st.key === 'fine' ? 'reviewed' : st.key === 'fix' ? 'needs_fixing' : st.key === 'ign' ? 'ignored' : null, c.id),
      h('span', { class: 'grow' }), openBtn));
}
const it_isPaperNode = id => M.paperId.has(id);
function kindLabelShort(it) { const k = kindLabel(it); const m = /\b(in .*)$/.exec(k); return m ? m[1].replace(/^in /, '') : k; }
function pickWhyNode(c) {
  const d = c.g.downstream.find(x => M.paperId.has(x.node_id)); if (d) return d.node_id;
  if (c.g.downstream.length) return c.g.downstream[c.g.downstream.length - 1].node_id;
  return c.g.changed[0] ? c.g.changed[0].node_id : '';
}

/* ---------- Item page ---------- */
function relevantEvents(it) {
  const ids = new Set(itemNodeIds(it)), evPaths = it.ev.map(e => { const n = IX.node.get(e.id); return n ? n.repo + '|' + pathOf(n) : ''; });
  if (it.shared) { const n = it.node; evPaths.push(n.repo + '|' + pathOf(n)); }
  const out = [];
  for (const ev of (S.events && S.events.events) || []) {
    let hit = false;
    if (ev.changed_nodes) hit = ev.changed_nodes.some(n => ids.has(n));
    if (!hit && (!ev.changed_nodes || !ev.after_checkpoint)) hit = (ev.files || []).some(f => evPaths.includes(ev.repo + '|' + f.path));
    if (hit) out.push(ev);
  }
  return out.sort((a, b) => (a.time < b.time ? 1 : -1));
}
function eventPieces(ev) {
  const g = IX.groupById.get(ev.id); if (g) return causeInfo(g).pieces;
  const rw = repoWord(ev.repo);
  if (ev.kind === 'run') return ['A run finished: ', mono(ev.id.split('/').pop())];
  if (ev.kind === 'worktree') return ['You have changes in ' + rw + ' that are not saved to git yet'];
  if (ev.kind === 'snapshot') return ['Your ' + rw + ' files differ from when you last looked'];
  if (ev.kind === 'diverged') return ['The history of your ' + rw + ' was rewritten since you last looked'];
  const fs = ev.files || [];
  if (fs.length === 1) {
    const f = fs[0], n = IX.node.get('file:' + ev.repo + '/' + f.path);
    if (f.status === 'A') return ['You added ', mono(f.path)];
    if (f.status === 'D') return ['You removed ', mono(f.path)];
    if (rw === 'paper' && /\.(tex|bib)$/.test(f.path)) return ['You edited your paper (', mono(f.path), ')'];
    if (n && n.kind === 'config') return ['You changed ', mono(f.path)];
    if (n && (n.kind === 'result' || n.kind === 'data')) return ['Your file ', mono(f.path), ' changed'];
    return ['You edited ', mono(f.path)];
  }
  return ['You edited ' + fs.length + ' files in ' + rw];
}
function eventLine(ev, opts) {
  opts = opts || {};
  return h('div', { class: 'evline' }, h('span', { class: 'eg', 'aria-hidden': 'true' }, ev.kind === 'run' ? '▲' : ev.kind === 'commit' ? '●' : '◌'),
    h('div', { class: 'evtx' }, h('span', null, eventPieces(ev)), h('span', { class: 'muted', title: absTime(ev.time) }, ' · ' + (opts.clock ? ev.time.slice(11, 16) : relTime(ev.time))), ev.kind === 'commit' ? h('span', { class: 'muted' }, ' · commit ', h('span', { class: 'mono' }, ev.short)) : null,
      opts.subject && ev.subject ? h('div', { class: 'muted quote' }, '“' + ev.subject + '”') : null));
}
function whatThis(it) {
  const P = [];
  const nodes = it.ev.map(e => IX.node.get(e.id)).filter(Boolean);
  const direct = it.nodes.flatMap(n => IX.pout.get(n) || []);
  const first = (arr, f) => arr.find(f);
  const resE = first(direct, e => e.kind === 'traces_to'), resN = resE ? IX.node.get(resE.to) : first(nodes, n => n.kind === 'result' || n.kind === 'data');
  const runN = first(nodes, n => n.kind === 'run');
  let scriptN = null;
  const gen = first(direct, e => e.kind === 'generated_by'); if (gen) scriptN = IX.node.get(gen.to);
  if (!scriptN && resN) { const pe = (IX.pout.get(resN.id) || []).find(e => e.kind === 'produced_by' && (IX.node.get(e.to) || {}).kind === 'code'); if (pe) scriptN = IX.node.get(pe.to); }
  if (!scriptN && runN) { const ex = (IX.pout.get(runN.id) || []).find(e => e.kind === 'executes'); if (ex) scriptN = IX.node.get(ex.to); }
  if (!scriptN) scriptN = first(nodes, n => n.kind === 'code') || null;
  const assetN = first(nodes, n => n.kind === 'asset');
  const par = M.parent.get(it.id), p = par && M.byId.get(par);
  const where = p && p.kind === 'section' ? ' in ' + lead(p) : '';
  const A = x => mono(pathOf(x));
  switch (it.kind) {
    case 'table':
      P.push('A table' + where + '. ');
      if (resN) { P.push('It is built from ', A(resN)); if (scriptN) { P.push(', produced by ', A(scriptN)); if (runN) P.push(' on ', nameOf(runN.id)); } P.push('.'); }
      else P.push('It is not linked to a result file yet.');
      break;
    case 'figure':
      P.push('A figure' + where + '. ');
      if ((it.node.attrs || {}).manual) P.push('You said it is drawn by hand.');
      else if (scriptN) { P.push('It is made by ', A(scriptN)); if (resN) P.push(' from ', A(resN)); P.push('.'); }
      else if (assetN) P.push('It shows ', A(assetN), '. Lemmata does not know what makes it yet.');
      else P.push('Lemmata does not know where it comes from yet.');
      break;
    case 'equation': P.push('An equation' + where + '.'); break;
    case 'section': {
      const k = (M.nbOut.get(it.id) || []).filter(x => x.rel === 'contains' && ['figure', 'table', 'equation'].includes(M.byId.get(x.id).kind)).length;
      P.push((it.node.attrs.in_appendix ? 'Appendix ' : 'Section ') + (it.node.attrs.number || '') + ' of your paper. It contains ' + plural(k, 'figure, table or equation', 'figures, tables or equations') + '.'); break;
    }
    case 'thesis': {
      const rq = (M.nbOut.get(it.id) || []).filter(x => M.byId.get(x.id).kind === 'rq').length, sc = (M.nbOut.get(it.id) || []).filter(x => M.byId.get(x.id).kind === 'section').length;
      P.push('The abstract of your paper. ' + plural(rq, 'research question') + ' and ' + plural(sc, 'section') + ' rest under it.'); break;
    }
    case 'rq': {
      const ss = (M.nbOut.get(it.id) || []).filter(x => x.rel === 'answers').map(x => lead(M.byId.get(x.id)));
      P.push('A research question your paper states.' + (ss.length ? ' It is discussed in ' + ss.join(', ') + '.' : '')); break;
    }
    case 'reference': {
      const ss = (M.nbIn.get(it.id) || []).map(x => lead(M.byId.get(x.id)));
      P.push('A cited work.' + (ss.length ? ' Cited in ' + ss.join(', ') + '.' : ' Nothing cites it yet.')); break;
    }
    default:
      if (it.shared) P.push('A file that ' + it.users.length + ' parts of your paper rest on: ' + it.users.map(u => lead(M.byId.get(u))).join(', ') + '.');
      else P.push(it.kindWord + '.');
  }
  return P;
}
function nodeNote(nid) {   // "changed 2 days ago · commit 2836100" / "not changed"
  const al = IX.alarm.get(nid);
  if (!al) return 'not changed';
  const ch = al.find(a => a.role === 'changed');
  if (ch) { const c = ch.group.cause; return 'changed ' + relTime(c.time) + (c.short && c.kind === 'commit' ? ' · commit ' + c.short : ''); }
  const d = al[0];
  if (d.entry.output_identical === true) return 'not regenerated yet';
  if (d.entry.output_identical === false) return 'regenerated, content differs';
  return 'may need a second look';
}
function evidenceRow(nid) {
  const n = IX.node.get(nid); if (!n) return null;
  const f = nodeFlag(nid), al = IX.alarm.get(nid), open = !!S.openEv[nid];
  const row = h('div', { class: 'evrow', 'data-ev': nid },
    h('button', { class: 'evhead', 'aria-expanded': String(open), onclick: () => { S.openEv[nid] = !S.openEv[nid]; renderPage(true); } },
      h('span', { class: 'caret' }, open ? '▾' : '▸'), tdot(typeOfFile(n.kind)), mono(n.kind === 'run' ? n.name.replace(/^run\s+/, '') : pathOf(n)), n.kind === 'run' ? h('span', { class: 'muted' }, ' run') : null,
      f ? chip(f) : null, h('span', { class: 'muted note' }, nodeNote(nid))),
    h('button', { class: 'linkbtn sm', onclick: () => copyText(pathOf(n)) }, 'Copy path'));
  if (open) {
    const body = h('div', { class: 'evbody' });
    const ch = al && al.find(a => a.role === 'changed');
    if (ch) { body.append(h('div', { class: 'muted' }, 'Loading what changed…')); ensureAnalysis(ch.group.id, nid).then(an => { clear(body); if (an.failed) body.append(h('div', { class: 'muted' }, 'The change could not be loaded. ' + an.failed)); else for (const df of an.diffs.filter(d => d.node_id === nid)) body.append(df.binary ? h('div', { class: 'muted' }, 'Not a text file.') : diffBlock(df.unified)); }); }
    else body.append(h('div', { class: 'muted' }, al ? 'This file has not changed itself. It may need a second look because something it rests on changed.' : 'Not changed since you last looked.'));
    row.append(body);
  }
  return row;
}
function pageItem(it) {
  S.outline = [];
  const root = doc();
  const st = ST[it.status];
  root.append(h('div', { class: 'ititle' },
    h('h1', { class: 'ptitle' }, tdot(typeOfItem(it)), it.title),
    h('div', { class: 'imeta' }, h('span', { class: 'muted' }, kindLabel(it)), chip(it.status), it.finds.length ? plainChip('!', plural(it.finds.length, 'check')) : null,
      h('span', { class: 'grow' }), h('button', { class: 'btn', onclick: () => { S.gf.mode = 'around'; S.sel = it.id; openTab('graph'); } }, 'Open graph around this item'))));
  // why it needs attention
  if (it.status !== 'ok') {
    const targets = itemTargets(it), groups = [];
    for (const nid of itemNodeIds(it)) for (const a of IX.alarm.get(nid) || []) if (!groups.includes(a.group)) groups.push(a.group);
    const whyKey = 'item:' + it.id, g0 = groups[0];
    const ch = g0 && g0.changed[0];
    let sentence;
    if (it.status === 'look') {
      if (g0) {
        const ev0 = it.ev.map(e => e.id).filter(id => (IX.alarm.get(id) || []).some(a => a.role === 'downstream' && a.entry.output_identical === true))[0];
        sentence = h('span', null, 'Something this item rests on changed ' + relTime(g0.cause.time) + ': ' + lcFirst(textOf(causeInfo(g0).pieces)) + '. ' + (ev0 ? cap1(nameOf(ev0)) + ' has not been regenerated yet.' : ''));
      } else { const fnd = it.finds.find(f => f.severity === 'warning' && effState('finding', f.id).state === 'unreviewed') || it.finds[0]; sentence = h('span', null, 'A check found something here. ', fnd ? h('button', { class: 'linkbtn', onclick: () => { S.focusFinding = fnd.id; openTab('checks'); } }, 'See the check') : null); }
    } else if (it.status === 'fix') {
      const e = targets.map(t => triageEntry(t.type, t.id)).find(x => x && x.state === 'needs_fixing');
      sentence = h('span', null, 'You marked this as needing a fix' + (e ? ' on ' + dmon(e.updated_at) : '') + '.' + (noteOf(targets) ? ' Your note: “' + noteOf(targets) + '”' : ''));
    } else if (it.status === 'fine') {
      const e = targets.map(t => triageEntry(t.type, t.id)).find(x => x && x.state === 'reviewed');
      sentence = h('span', null, 'You marked this as looking fine' + (e ? ' on ' + dmon(e.updated_at) : '') + '.');
    } else sentence = h('span', null, 'You chose to ignore this item.');
    const cur = { look: null, fix: 'needs_fixing', fine: 'reviewed', ign: 'ignored' }[it.status];
    const outdated = itemNodeIds(it).some(x => effState('node', x).outdated);
    root.append(h('div', { class: 'attn ' + it.status },
      h('div', { class: 'atx' }, h('span', { class: 'sg ' + it.status }, st.glyph), ' ', sentence, outdated ? h('div', { class: 'muted' }, 'It changed again since you marked it, so Lemmata asks you to look again.') : null),
      g0 && S.openWhy[whyKey] ? whyBlock(g0, it.nodes.find(n => (IX.alarm.get(n) || []).some(a => a.group === g0)) || itemNodeIds(it).find(n => (IX.alarm.get(n) || []).some(a => a.group === g0))) : null,
      h('div', { class: 'btnrow' }, g0 ? h('button', { class: 'btn', 'aria-expanded': String(!!S.openWhy[whyKey]), onclick: () => { S.openWhy[whyKey] = !S.openWhy[whyKey]; renderPage(true); } }, 'Why?') : null,
        triageButtons(targets, cur, it.id))));
  }
  root.append(sec('What this is', 'what', h('p', { class: 'what' }, whatThis(it))));
  // evidence
  const evBody = [];
  if (it.shared) {
    evBody.push(h('div', { class: 'evgroup' }, h('div', { class: 'evg' }, 'Used by'), it.users.map(u => h('div', { class: 'evrow' }, itemLink(M.byId.get(u))))));
    const r = evidenceRow(it.id); if (r) evBody.push(h('div', { class: 'evgroup' }, h('div', { class: 'evg' }, 'This file'), r));
  } else {
    for (const [name, kinds] of EV_GROUPS) {
      const rows = it.ev.filter(e => kinds.includes((IX.node.get(e.id) || {}).kind)).map(e => evidenceRow(e.id)).filter(Boolean);
      if (rows.length) evBody.push(h('div', { class: 'evgroup' }, h('div', { class: 'evg' }, name), rows));
    }
    if (it.sharedUse.length) evBody.push(h('div', { class: 'evgroup' }, h('div', { class: 'evg' }, 'Shared with other items'), it.sharedUse.map(sid => {
      const s = M.byId.get(sid); const others = s.users.filter(u => u !== it.id).map(u => lead(M.byId.get(u)));
      return h('div', { class: 'evrow' }, h('button', { class: 'evhead', onclick: () => openItem(sid) }, h('span', { class: 'caret' }, '↗'), tdot(typeOfItem(s)), mono(s.title), h('span', { class: 'muted note' }, 'also used by ' + (others.join(', ') || 'nothing else'))));
    })));
  }
  if (!evBody.length) {
    evBody.push(h('div', { class: 'muted' }, 'Nothing behind this item yet. If it comes from a result file or script, add a note in the LaTeX source like % source: results/table2.csv.'));
    evBody.push(h('button', { class: 'linkbtn', onclick: () => { S.showExample = !S.showExample; renderPage(true); } }, S.showExample ? 'Hide example' : 'Show example'));
    if (S.showExample) evBody.push(h('div', { class: 'code' }, h('div', { class: 'ln' }, h('span', { class: 'n' }, '1'), '\\begin{table}'), h('div', { class: 'ln' }, h('span', { class: 'n' }, '2'), '% source: code:results/table2.csv'), h('div', { class: 'ln' }, h('span', { class: 'n' }, '3'), '\\caption{Main results}')));
  }
  root.append(sec('Behind this item', 'evidence', evBody));
  // where it appears
  const n = it.node;
  if (!it.shared && n.loc && n.loc.path && !it.readme) {
    const box = h('div', null, h('div', { class: 'muted' }, 'Loading…'));
    const line = n.loc.line, end = Math.min(n.loc.end_line || line, line + 11);
    if (line) getLines(n.repo, n.loc.path, line, end).then(r => { clear(box); box.append(capLoc(n, n.loc.path + ' line ' + line, line), codeBlock(r.lines, r.start, [line], { label: 'Your paper source' })); })
      .catch(() => { clear(box); box.append(capLoc(n, n.loc.path + (line ? ' line ' + line : ''), line), (n.attrs || {}).caption ? h('div', { class: 'quote' }, 'Caption: “' + n.attrs.caption + '”') : h('div', { class: 'muted' }, 'The text is not available here.')); });
    else clear(box).append(capLoc(n, mono(n.loc.path)));
    root.append(sec('In your paper', 'paper', box));
  }
  // checks
  if (it.finds.length) root.append(sec('Checks about this item', 'checks', it.finds.map(f => h('div', { class: 'chk' }, h('div', null, findingSentence(f)), h('button', { class: 'linkbtn', onclick: () => { S.focusFinding = f.id; openTab('checks'); } }, 'Open evidence')))));
  // history
  const evs = relevantEvents(it);
  root.append(sec('History', 'history', evs.length ? evs.slice(0, 12).map(e => eventLine(e)) : h('div', { class: 'muted' }, 'Nothing has changed here since the start.')));
  // notes
  const targets = itemTargets(it), cur = noteOf(targets);
  const ta = h('textarea', { rows: '3', maxlength: '2000', 'aria-label': 'Your note', placeholder: 'Your note', disabled: READONLY }); ta.value = cur;
  const earlier = targets.flatMap(t => ((triageEntry(t.type, t.id) || {}).history || []).filter(x => x.note).map(x => x)).sort((a, b) => (a.at < b.at ? 1 : -1));
  root.append(sec('Notes', 'notes', ta,
    h('div', { class: 'btnrow' }, h('button', { class: 'btn', disabled: READONLY, onclick: () => { const t0 = targets[0]; const ent = triageEntry(t0.type, t0.id); setTriageMany(targets, ent ? ent.state : 'unreviewed', ta.value); } }, 'Save note')),
    earlier.length > 1 ? h('details', { class: 'details' }, h('summary', null, 'Earlier notes'), earlier.slice(1, 8).map(x => h('div', { class: 'muted' }, absTime(x.at) + ' — ' + x.note))) : null));
  return root;
}
const lcFirst = s => s.charAt(0).toLowerCase() + s.slice(1);
function textOf(pieces) { return pieces.map(p => (p && p.nodeType ? p.textContent : String(p))).join(''); }

/* ---------- Evidence page (files and runs that are not Items) ---------- */
function pageEvidence(nid) {
  S.outline = [];
  const n = IX.node.get(nid), root = doc();
  if (!n) return root.append(h('div', { class: 'muted' }, 'This file is not part of the project any more.')), root;
  const rn = n.kind === 'run' ? n.name.replace(/^run\s+/, '') : pathOf(n);
  root.append(h('h1', { class: 'ptitle mono-title' }, rn));
  if (EMBED && n.loc && n.loc.path) root.append(capLoc(n, mono(n.loc.path)));
  const users = (M.itemsOf.get(nid) || []).map(i => M.byId.get(i));
  root.append(h('p', { class: 'what' }, (FILE_WORD[n.kind] || 'A file') + (n.kind === 'item' ? ' listed in your README' : ' in your ' + (repoWord(n.repo) === 'paper' ? 'paper' : 'code')) + '. ' + (users.length ? 'It is used by ' + users.map(u => lead(u)).join(', ') + '.' : n.kind === 'item' ? 'It was listed in your README, but no figure or table in the paper has that number.' : 'It is not used by anything in the paper yet.')));
  if (users.length) root.append(sec('Used by', 'used', users.map(u => h('div', { class: 'evrow' }, itemLink(u)))));
  const r = evidenceRow(nid); if (r) { S.openEv[nid] = S.openEv[nid] !== false; root.append(sec('This file', 'file', r)); }
  return root;
}

/* ---------- Checks ---------- */
function findingSentence(f) {
  const d = f.details || {}, tail = f.id.indexOf('/') >= 0 ? f.id.slice(f.id.indexOf('/') + 1) : f.id;
  const itl = () => { const it = f.nodes && f.nodes.length ? M.byId.get(M.paperId.get(f.nodes[0])) : null; return it ? lead(it) : 'This item'; };
  switch (f.check) {
    case 'reference_unmatched': { const n = IX.node.get('ref:' + tail); const t = n ? ((n.attrs || {}).title || n.detail) : ''; return 'The reference "' + t + '" (' + tail + ') could not be matched in OpenAlex or Crossref. Check its title, year or DOI.'; }
    case 'main_appendix_mismatch': return cap1(humanKey(d.name || tail)) + ' differs: the main text says ' + fmtVal(d.main_value) + ' and the appendix says ' + fmtVal(d.appendix_value) + '.';
    case 'uncited_reference': return tail + ' is in your bibliography but nothing cites it.';
    case 'unreferenced_float': { const it = itl(); return (f.evidence || []).some(e => e.role === 'begin') ? it + ' has no label, so it cannot be mentioned in the text.' : it + ' is never mentioned in the text.'; }
    case 'undefined_ref': return 'The text refers to "' + tail + '", but nothing in the paper has that name.';
    case 'undefined_cite': return 'The text cites "' + tail + '", which is not in your bibliography.';
    case 'untraced_number': return 'The number ' + tail.split('#').pop() + ' in ' + itl() + ' was not found in any of your result files.';
    case 'figure_without_provenance': return itl() + ' has no script or note saying where it comes from.';
    default: return f.message;
  }
}
function findingCard(f) {
  const st = effState('finding', f.id), s = STATE_TO_ST[st.state] || 'look';
  const cc = T.checkChip[f.check];
  const its = [...new Set((f.nodes || []).map(n => M.paperId.get(n)).filter(Boolean))].map(i => M.byId.get(i));
  const cur = st.state === 'unreviewed' ? null : st.state;
  const e = st.entry;
  return h('article', { class: 'card fcard' + (S.focusFinding === f.id ? ' focus' : ''), id: 'f-' + f.id.replace(/[^\w]/g, '_') },
    h('div', { class: 'cardhead' }, chip(s), cc ? plainChip(cc[0], cc[1], 'look') : null, f.severity === 'info' ? h('span', { class: 'muted' }, 'for your information') : null),
    h('div', { class: 'fsent' }, findingSentence(f)),
    h('div', { class: 'fev' }, (f.evidence || []).slice(0, 4).map(ev => h('div', { class: 'fevr' }, mono(ev.path + ' line ' + ev.line), h('span', { class: 'quote' }, ' — “' + trunc(ev.text, 110) + '”')))),
    its.length ? h('div', { class: 'fits muted' }, 'Concerns: ', its.map((it, i) => [i ? ', ' : '', h('button', { class: 'linkbtn', onclick: ev => openItem(it.id, ev.metaKey || ev.ctrlKey) }, lead(it))])) : null,
    e && e.note ? h('div', { class: 'muted' }, 'Your note: “' + e.note + '”') : null,
    triageButtons([{ type: 'finding', id: f.id }], cur, 'f:' + f.id));
}
function edgeSentence(e) {
  const from = M.byId.get(M.paperId.get(e.from)), path = nameOf(e.to);
  const pairs = [], re = /([\w.\-]+):\s*paper\s+([^,;]+),\s*config\s+([^;]+)/g; let m;
  while ((m = re.exec(e.reason || ''))) pairs.push({ k: humanKey(m[1]), p: m[2].trim(), c: m[3].trim() });
  const who = from ? lead(from) : 'Your paper';
  if (!pairs.length) return who + ' and ' + path + ' seem to describe the same settings. Should Lemmata treat them as the same?';
  const p0 = pairs[0];
  return who + ' mentions ' + p0.k + ' ' + p0.p + ', and ' + path + ' sets ' + p0.k + ' to ' + p0.c + '.' + (pairs.length > 1 ? ' It also lines up ' + pairs.slice(1).map(p => p.k + ' (' + p.p + ')').join(', ') + '.' : '') + ' Should Lemmata treat them as the same setting?';
}
function pageChecks() {
  S.outline = [];
  const root = doc(h('h1', { class: 'ptitle' }, 'Checks'), h('p', { class: 'muted' }, 'Things Lemmata found by reading your paper and code. A check is a suggestion to look, not a verdict.'));
  const fs = (S.findings && S.findings.findings) || [], checks = (S.findings && S.findings.checks) || [];
  const notRun = checks.filter(c => c.status !== 'ran');
  const sts = f => STATE_TO_ST[effState('finding', f.id).state] || 'look';
  const counts = { all: fs.length, look: 0, fine: 0, fix: 0, ign: 0 }; fs.forEach(f => counts[sts(f)]++);
  const chips = [['all', 'All'], ['look', 'Needs a second look'], ['fine', 'Looks fine'], ['fix', 'Needs fixing'], ['ign', 'Ignored']];
  root.append(h('div', { class: 'fchips' }, chips.map(([k, l]) => h('button', { class: 'fchip', 'aria-pressed': String((S.ckFilter || 'all') === k), onclick: () => { S.ckFilter = k; renderPage(true); } }, l + ' ', h('span', { class: 'n' }, counts[k]))),
    notRun.length ? h('span', { class: 'fchip static' }, 'Not checked ', h('span', { class: 'n' }, notRun.length)) : null));
  const byCheck = new Map(); fs.forEach(f => { if (!byCheck.has(f.check)) byCheck.set(f.check, []); byCheck.get(f.check).push(f); });
  for (const key of T.checkOrder) {
    const meta = checks.find(c => c.check === key), list = (byCheck.get(key) || []).filter(f => (S.ckFilter || 'all') === 'all' || sts(f) === S.ckFilter);
    const open = S.checkSec[key] != null ? S.checkSec[key] : list.length > 0;
    root.append(h('section', { class: 'csec' },
      h('button', { class: 'csh', 'aria-expanded': String(open), onclick: () => { S.checkSec[key] = !open; renderPage(true); } }, h('span', { class: 'caret' }, open ? '▾' : '▸'), h('span', { class: 'cname' }, T.checkNames[key]), h('span', { class: 'cn' }, list.length)),
      open ? h('div', { class: 'cbody' },
        meta && meta.status !== 'ran' ? h('div', { class: 'muted' }, plainChip('–', 'Not checked', 'ign'), ' ' + (T.notRun[meta.note] ? 'No paper connected' : 'Not checked: ' + (T.notRun[meta.note] || meta.note || 'it could not run'))) : null,
        list.length ? list.map(findingCard) : (meta && meta.status === 'ran' ? h('div', { class: 'muted' }, 'Nothing found.') : null)) : null));
  }
  // suggested links
  const links = ((S.graph && S.graph.edges) || []).filter(e => e.kind === 'value_match');
  const open = links.filter(e => e.status === 'proposed'), done = links.filter(e => e.status === 'approved'), hidden = links.filter(e => e.status === 'rejected');
  const linkRow = e => {
    const rows = [h('div', { class: 'fsent' }, edgeSentence(e))];
    const to = nameOf(e.to), from = M.byId.get(M.paperId.get(e.from));
    if (e.status === 'proposed') rows.push(h('div', { class: 'btnrow' }, plainChip('+', 'Suggested', 'proposed'), h('span', { class: 'grow' }),
      h('button', { class: 'btn primary', disabled: READONLY, onclick: () => decideLink(e.id, 'approved', 'Linked. ' + (from ? lead(from) : 'Your paper') + ' now rests on ' + to + '.') }, 'Yes, link them'),
      h('button', { class: 'btn', disabled: READONLY, onclick: () => decideLink(e.id, 'rejected') }, 'No, don\'t suggest this')));
    else if (e.status === 'approved') rows.push(h('div', { class: 'btnrow' }, plainChip('✓', 'Linked', 'fine'), h('span', { class: 'grow' }), h('button', { class: 'btn', disabled: READONLY, onclick: () => decideLink(e.id, 'proposed') }, 'Undo')));
    else rows.push(h('div', { class: 'btnrow' }, h('button', { class: 'btn', disabled: READONLY, onclick: () => decideLink(e.id, 'proposed') }, 'Bring back')));
    return h('article', { class: 'card fcard' }, rows);
  };
  root.append(h('section', { class: 'csec', id: 'suggested' }, h('div', { class: 'csh static' }, h('span', { class: 'cname' }, 'Suggested links'), h('span', { class: 'cn' }, open.length)),
    h('div', { class: 'cbody' }, h('p', { class: 'muted' }, 'Lemmata noticed matches between your paper and your files. Nothing is linked until you say so.'),
      open.length ? open.map(linkRow) : h('div', { class: 'muted' }, 'No suggestions right now.'),
      done.length ? [h('div', { class: 'evg' }, 'Linked by you'), done.map(linkRow)] : null,
      hidden.length ? h('details', { class: 'details' }, h('summary', null, 'Hidden suggestions (' + hidden.length + ')'), hidden.map(linkRow)) : null)));
  return root;
}

/* ---------- History ---------- */
function weekStart(t) { const d = new Date(t.slice(0, 10) + 'T00:00:00'); d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); const p = n => String(n).padStart(2, '0'); return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()); }
function pageHistory(opts) {
  opts = opts || {};
  S.outline = [];
  const root = doc(h('h1', { class: 'ptitle' }, 'History'));
  const evs = ((S.events && S.events.events) || []).slice();
  const cp = S.alarms && S.alarms.checkpoint, cpT = cp ? Date.parse(cp.created_at) : null;
  const F = S.histFilter;
  root.append(h('div', { class: 'fchips' }, [['all', 'All'], ['code', 'Code'], ['paper', 'Paper'], ['runs', 'Runs']].map(([k, l]) => h('button', { class: 'fchip', 'aria-pressed': String(F === k), onclick: () => { S.histFilter = k; renderPage(true); } }, l))));
  const rows = evs.filter(e => F === 'all' || (F === 'runs' ? e.kind === 'run' : F === 'paper' ? repoWord(e.repo) === 'paper' && e.kind !== 'run' : repoWord(e.repo) === 'code' && e.kind !== 'run')).map(e => ({ t: Date.parse(e.time), ev: e }));
  const marks = ((S.checkpoints && S.checkpoints.checkpoints) || []).filter(c => !(cp && c.id === cp.id)).map(c => ({ t: Date.parse(c.created_at), mark: c }));
  const all = rows.concat(F === 'all' ? marks : []);
  if (cp && F === 'all') all.push({ t: cpT + 0.5, rule: cp });
  all.sort((a, b) => b.t - a.t);
  if (!all.length) return root.append(h('div', { class: 'muted' }, 'No history yet.')), root;
  let lastDay = null;
  for (const r of all) {
    const iso = r.ev ? r.ev.time : r.mark ? r.mark.created_at : r.rule.created_at;
    if (r.rule) { root.append(h('div', { class: 'cprule' }, h('span', null, 'Last looked at: ' + absTime(cp.created_at)))); continue; }
    const day = opts.weekly ? 'Week of ' + dmon(weekStart(iso)) : dayHeader(iso);
    if (day !== lastDay) { root.append(h('div', { class: 'dayhead' }, opts.weekly ? day : day === 'Today' || day === 'Yesterday' ? day : dmon(iso) + (dayDiff(iso) > 300 ? ' ' + iso.slice(0, 4) : ''))); lastDay = day; }
    if (r.mark) root.append(h('div', { class: 'evline' }, h('span', { class: 'eg', 'aria-hidden': 'true' }, '⚑'), h('div', { class: 'evtx' }, 'You marked everything as looked at', r.mark.note ? h('span', { class: 'muted' }, ' · “' + r.mark.note + '”') : null, h('span', { class: 'muted' }, ' · ' + absTime(r.mark.created_at)))));
    else root.append(h('div', { class: 'hrow' }, eventLine(r.ev, { subject: true, clock: true }), h('span', { class: 'muted rw' }, repoWord(r.ev.repo)), cpT != null ? h('span', { class: 'tag' }, r.t > cpT ? 'Since then' : 'Before') : null));
  }
  return root;
}

/* ---------- Graph tab ---------- */
const GR = { host: null, g: null, sig: '', pos: new Map(), el: null };
function graphSpec(opts) {
  opts = opts || {};
  const gf = S.gf, nodes = [], edges = [], ids = new Set();
  const show = it => {
    if (it.ref) return gf.refs;
    if (it.shared) return gf.shared;
    if (it.kind === 'thesis' || it.kind === 'rq') return true;
    if (it.kind === 'section') return gf.sections;
    return gf.floats;
  };
  let allowed = null;
  if (opts.local) allowed = neighboursOf(opts.local, opts.depth);
  else if (gf.mode === 'around' && S.sel && M.byId.has(S.sel)) allowed = neighboursOf(S.sel, gf.depth);
  const mkNode = (it, scale) => { const ty = typeOfItem(it), c = tcol(ty); return { id: it.id, item: it, type: ty, r: Math.max(opts.local ? 9 : 12, it.r * scale), kind: it.kind, status: it.status, imp: it.imp, title: it.title, short: it.short, tint: c.t, col: c.s, dash: c.dash, glyph: it.shared ? TYPES[ty].glyph : (PAPER_GLYPH[it.kind] || TYPES[ty].glyph) }; };
  for (const it of M.items) {
    if (allowed ? !allowed.has(it.id) : !show(it)) continue;
    nodes.push(mkNode(it, opts.local ? 0.62 : 1)); ids.add(it.id);
  }
  for (const e of M.iedges) if (ids.has(e.a) && ids.has(e.b)) edges.push({ a: e.a, b: e.b, rel: e.rel });
  if (!opts.local) {
    const cats = { code: gf.code, run: gf.runs, result: gf.results, asset: gf.results, data: gf.results, doc: gf.results, config: gf.settings };
    const satFor = (nid, parent) => {
      const n = IX.node.get(nid), si = M.byId.get(nid), ty = typeOfFile(n.kind), c = tcol(ty);
      return { id: 'sat:' + nid + '@' + parent, sat: true, parent, r: 11, kind: 'file', type: ty, status: (si && si.shared ? si.status : nodeFlag(nid)) || 'ok', imp: 0, label: n.kind === 'run' ? n.name.replace(/^run\s+/, '') : basename(pathOf(n)), title: pathOf(n), nid, tint: c.t, col: c.s, dash: c.dash, glyph: TYPES[ty].glyph };
    };
    const evItem = S.ev.item && ids.has(S.ev.item) ? M.byId.get(S.ev.item) : null;
    const made = new Map();   // file node id -> satellite id, for the opened item
    const addSat = (nid, parent) => { const sat = satFor(nid, parent); nodes.push(sat); edges.push({ a: parent, b: sat.id, sat: true }); return sat; };
    for (const it of M.items) {
      if (!ids.has(it.id) || it.ref) continue;
      const open = it === evItem;
      if (!(gf.files || open) || (it.shared && !open)) continue;
      let owned = it.shared ? evDeps(it.id).map(d => d.id) : it.ev.map(e => e.id).concat(open ? it.sharedUse.filter(sid => !ids.has(sid)) : []);
      let more = 0;
      if (open && owned.length > MAXSAT) {   // too many to read on a canvas: things to look at first, then results/runs/settings, then scripts; the sidebar lists them all
        const must = new Set([S.ev.row].concat(S.ev.trail || [])), rank = id => { const f = nodeFlag(id); return (must.has(id) ? -2 : 0) + (f === 'look' || f === 'fix' ? -1 : 0) + (IX.node.get(id).kind === 'code' ? 0.5 : 0); };
        const sorted = owned.map((id, i) => [id, rank(id), i]).sort((a, b) => a[1] - b[1] || a[2] - b[2]);
        owned = sorted.slice(0, MAXSAT).map(x => x[0]); more = sorted.length - MAXSAT;
      }
      if (more) { const mid = 'sat:more@' + it.id; nodes.push({ id: mid, sat: true, more: true, parent: it.id, r: 11, kind: 'file', type: 'code', status: 'ok', imp: 0, label: '+' + more + ' more', title: more + ' more files behind this item', nid: null, tint: css('--surface'), col: css('--border-strong'), glyph: '…' }); edges.push({ a: it.id, b: mid, sat: true }); }
      for (const nid of owned) { const n = IX.node.get(nid); if (!n || (!open && !cats[n.kind])) continue; const sat = addSat(nid, it.id); if (open) made.set(nid, sat.id); }
    }
    if (evItem) for (const t of S.ev.trail || []) {   // a satellite is open too: show what it rests on
      if (!made.has(t)) break;
      const fs = made.get(t);
      for (const d of evDeps(t)) {
        if (made.has(d.id)) { if (made.get(d.id) !== fs) edges.push({ a: fs, b: made.get(d.id), sat: true }); continue; }
        const sat = satFor(d.id, fs); nodes.push(sat); edges.push({ a: fs, b: sat.id, sat: true }); made.set(d.id, sat.id);
      }
    }
    if (gf.unused && !allowed) {
      for (const n of M.unused.slice(0, 60)) nodes.push({ id: 'sat:u:' + n.id, sat: true, parent: null, r: 8, kind: 'file', type: typeOfFile(n.kind), status: 'ok', imp: 0, label: basename(pathOf(n)), title: pathOf(n), nid: n.id, tint: css('--surface'), col: css('--border-strong'), glyph: '' });
    }
  }
  return { nodes, edges };
}
function evDeps(nid) {   // files and runs this file rests on
  const out = [], seen = new Set();
  for (const e of IX.pout.get(nid) || []) { const n = IX.node.get(e.to); if (n && FILEK.has(n.kind) && !seen.has(n.id)) { seen.add(n.id); out.push({ id: n.id, kind: e.kind }); } }
  return out;
}
function itemTip(n) {
  if (n.more) return h('div', null, h('b', null, n.title), h('div', { class: 'muted' }, 'Click to open the item and see them all.'));
  if (n.sat) return h('div', null, h('b', { class: 'mono' }, n.title), h('div', { class: 'muted' }, (n.nid && IX.node.get(n.nid) ? FILE_WORD[IX.node.get(n.nid).kind] || 'A file' : 'A file') + ' · ' + ST[n.status].say), h('div', { class: 'muted' }, 'Click to see what it rests on. Double-click to open it.'));
  const it = n.item;
  return h('div', null, h('div', { class: 'tt' }, it.title), h('div', { class: 'muted' }, kindLabel(it)), h('div', { class: 'ttr' }, chip(it.status)), h('div', { class: 'muted' }, plural(it.links, 'connection')),
    !it.ref && !it.shared && it.ev.length ? h('div', { class: 'muted' }, 'Click to see its supporting evidence. Double-click to open it.') : null);
}
function ensureGraph() {
  if (GR.el) return;
  GR.host = h('div', { class: 'ghost' });
  GR.pos = new Map(lsGet(UIKEY + '.pos', []).map(p => [p[0], { x: p[1], y: p[2] }]));
  GR.g = makeGraph(GR.host, {
    pos: GR.pos, dimOk: false, tooltip: itemTip,
    onClick: id => { if (id) evOpen(id); else evClose(); },
    onHover: id => { if (S.ev.item) return; S.hoverItem = id; clearTimeout(GR.ht); GR.ht = setTimeout(renderRight, 70); },
    onClickSat: n => { if (n.more) openItem(n.parent); else evSat(n); },
    onOpen: n => { if (n.sat) { if (n.nid) openNode(n.nid); } else openItem(n.id); },
    onPin: p => lsSet(UIKEY + '.pos', [...p].map(([k, v]) => [k, Math.round(v.x), Math.round(v.y)])),
  });
  GR.el = h('div', { class: 'gview' });
}
function syncGraph() {
  if (!GR.g) return;
  const spec = graphSpec(), sig = JSON.stringify([spec.nodes.map(n => n.id), spec.edges.length, S.gf.mode, S.gf.depth, S.gf.mode === 'around' ? S.sel : '']);
  GR.g.dimOnly(S.gf.onlyChanged);
  if (sig !== GR.sig) { GR.sig = sig; GR.g.setData(spec); } else GR.g.patch(spec.nodes);
  GR.g.setSelected(S.ev.item || S.sel, !!S.ev.item);
  GR.g.setEmph(S.ev.row);
}
function pageGraph() {
  ensureGraph();
  const gf = S.gf, tb = h('div', { class: 'gtools' },
    h('input', { type: 'search', id: 'gfind', placeholder: 'Find an item', 'aria-label': 'Find an item', oninput: ev => gFind(ev.target.value), onkeydown: ev => { if (ev.key === 'Enter') gFind(ev.target.value, true); } }),
    h('div', { class: 'seg' }, h('button', { class: 'btn', 'aria-pressed': String(gf.mode === 'whole'), onclick: () => { gf.mode = 'whole'; persistUI(); renderPage(); } }, 'Whole paper'),
      h('button', { class: 'btn', 'aria-pressed': String(gf.mode === 'around'), title: S.sel ? null : 'Pick an item first', onclick: () => { if (!S.sel) { toast('Click an item first, then choose Around this item.'); return; } gf.mode = 'around'; persistUI(); renderPage(); } }, 'Around this item')),
    gf.mode === 'around' ? h('label', { class: 'depth' }, 'Depth ', h('input', { type: 'range', min: '1', max: '3', value: String(gf.depth), 'aria-label': 'How many steps away to show', oninput: ev => { gf.depth = +ev.target.value; ev.target.nextSibling.textContent = gf.depth; persistUI(); syncGraph(); } }), h('span', null, String(gf.depth))) : null,
    h('button', { class: 'btn', id: 'btn-filters', 'aria-haspopup': 'true', onclick: ev => filtersPop(ev.currentTarget) }, 'Filters'),
    h('button', { class: 'btn', 'aria-pressed': String(S.listView), onclick: () => { S.listView = !S.listView; renderPage(); } }, 'List view'),
    h('button', { class: 'btn', onclick: () => GR.g.rearrange() }, 'Re-arrange'),
    h('span', { class: 'grow' }),
    h('button', { class: 'btn', 'aria-label': 'Zoom out', onclick: () => GR.g.zoomBy(1 / 1.25) }, '−'), h('button', { class: 'btn', 'aria-label': 'Zoom in', onclick: () => GR.g.zoomBy(1.25) }, '+'),
    h('button', { class: 'btn', onclick: () => GR.g.fit() }, 'Fit'));
  const legend = h('div', { class: 'glegend' },
    h('div', { class: 'lgrow' }, h('span', { class: 'lgh' }, 'What it is'), TYPE_ORDER.map(t => h('span', { class: 'lg' }, h('span', { class: 'sw t-' + t }), TYPES[t].word))),
    h('div', { class: 'lgrow' }, h('span', { class: 'lgh' }, 'Status'),
      h('span', { class: 'lg look' }, h('span', { class: 'rs look' }), '↻ Needs a second look'), h('span', { class: 'lg fix' }, h('span', { class: 'rs fix' }), '✕ Needs fixing'),
      h('span', { class: 'lg fine' }, '✓ Looks fine'), h('span', { class: 'lg ok' }, 'No ring = up to date')),
    h('div', { class: 'muted' }, 'Click an item to see the evidence it rests on (blue lines). Double-click to open it. Circle size = how many things connect to it.'));
  const wrap = h('div', { class: 'gpage' }, tb);
  if (S.listView) wrap.append(graphList());
  else {
    GR.el.replaceChildren(GR.host, legend);
    wrap.append(GR.el);
    if (!M.items.filter(i => !i.ref).length) GR.el.append(h('div', { class: 'gmsg' }, 'There is nothing to draw yet. Lemmata draws your paper\'s figures, tables and sections once it has read a paper or a README.'));
  }
  return wrap;
}
/* ---------- click an item: show its supporting evidence ---------- */
function evSync(reveal) {
  GR.sig = ''; syncGraph();
  if (reveal && GR.g && S.ev.item) GR.g.reveal(S.ev.item);
  renderRight();
}
function evOpen(id) {
  if (S.gf.mode !== 'around') S.sel = id;
  S.ev = { item: id, file: null, row: null, trail: [] };
  evSync(true);
}
function evClose() {
  if (!S.ev.item && !S.sel) return;
  if (S.gf.mode !== 'around') S.sel = null;
  S.ev = { item: null, file: null, row: null, trail: [] };
  evSync();
}
function evSat(n) {
  if (!n.nid || !S.ev.item) return;
  const pn = String(n.parent || '').startsWith('sat:') ? String(n.parent).slice(4, String(n.parent).indexOf('@')) : null;
  const i = pn ? S.ev.trail.indexOf(pn) : -1;
  S.ev.trail = (i >= 0 ? S.ev.trail.slice(0, i + 1) : []).concat(n.nid);
  S.ev.file = n.nid; S.ev.row = n.nid;
  evSync(true);
}
const MAXSAT = 14;
const EV_GROUP = { result: ['results', 'Results'], code: ['code', 'Code'], run: ['runs', 'Runs'], setting: ['settings', 'Settings and data'] };
function whyLine(nid, si) {
  const n = IX.node.get(nid); if (!n) return '';
  const outs = IX.pout.get(nid) || [], ins = IX.pin.get(nid) || [], parts = [];
  const bareName = id => { const m = IX.node.get(id); return m ? (m.kind === 'run' ? m.name.replace(/^run\s+/, '') : basename(pathOf(m))) : id; };
  const OUTP = { produced_by: 'made by', generated_by: 'made by', traces_to: 'built from', executes: 'runs', reads: 'reads', imports: 'imports', value_match: 'linked by you to', includes: 'shows' };
  const INP = { executes: 'run by', reads: 'read by', imports: 'imported by', produced_by: 'makes', generated_by: 'makes', includes: 'shown in', traces_to: 'feeds', value_match: 'linked by you to' };
  for (const e of outs.slice(0, 3)) {
    const t = IX.node.get(e.to); if (!t || PAPER.has(t.kind)) continue;
    if ((e.kind === 'produced_by' || e.kind === 'generated_by') && t.kind === 'run') {
      const ex = (IX.pout.get(t.id) || []).find(x => x.kind === 'executes');
      parts.push('made by ' + (ex ? bareName(ex.to) + ' on run ' : 'run ') + bareName(t.id));
    } else parts.push((OUTP[e.kind] || 'uses') + ' ' + (t.kind === 'run' ? 'run ' : '') + bareName(t.id));
    if (parts.length >= 3) break;
  }
  for (let i = parts.length - 1; i >= 0; i--) if (parts.some(q => q.startsWith(parts[i] + ' on run '))) parts.splice(i, 1);
  parts.splice(2);
  if (!parts.length) for (const e of ins) {
    const f = IX.node.get(e.from); if (!f) continue;
    parts.push((INP[e.kind] || 'used by') + ' ' + (PAPER.has(f.kind) ? (M.byId.get(M.paperId.get(f.id)) || { short: f.name }).short : (f.kind === 'run' ? 'run ' : '') + bareName(f.id)));
    if (parts.length >= 1) break;
  }
  let t = parts.join('; ');
  if (si && si.users && si.users.length) t = (t ? t + '; ' : '') + 'also behind ' + si.users.map(u => M.byId.get(u).short).slice(0, 2).join(' and ') + (si.users.length > 2 ? ' and ' + (si.users.length - 2) + ' more' : '');
  if (nodeFlag(nid) === 'look' || nodeFlag(nid) === 'fix') { const note = nodeNote(nid); if (note && note !== 'not changed') t += (t ? '; ' : '') + note; }
  return t ? trunc(t.charAt(0).toUpperCase() + t.slice(1), 120) : 'Behind this item';
}
function evEntries(ownerId) {
  const g = { papers: [], results: [], code: [], runs: [], settings: [] };
  const it = M.byId.get(ownerId), fileOwner = !it || it.shared;
  const pushFile = nid => {
    const n = IX.node.get(nid); if (!n) return;
    const si = M.byId.get(nid), sh = si && si.shared ? si : null, ty = typeOfFile(n.kind);
    g[EV_GROUP[ty][0]].push({ id: nid, type: ty, name: n.kind === 'run' ? n.name.replace(/^run\s+/, '') : basename(pathOf(n)), full: pathOf(n), status: (sh ? sh.status : nodeFlag(nid)) || 'ok', why: whyLine(nid, sh), run: n.kind === 'run' });
  };
  if (!fileOwner) {
    for (const e of it.ev) pushFile(e.id);
    for (const sid of it.sharedUse) pushFile(sid);
    const m = new Map();
    for (const x of M.nbOut.get(it.id) || []) { const o = M.byId.get(x.id); if (!o || o.ref || o.shared) continue; const e = m.get(x.id) || { o, rels: [] }; const w = REL_OUT[x.rel]; if (!e.rels.includes(w)) e.rels.push(w); m.set(x.id, e); }
    for (const { o, rels } of m.values()) g.papers.push({ id: o.id, item: o, type: typeOfItem(o), name: o.short || o.title, full: o.title, status: o.status, why: 'This item ' + rels.join(' and ') + ' it' });
  } else {
    for (const d of evDeps(ownerId)) pushFile(d.id);
    const owner = M.byId.get(ownerId);
    const users = owner && owner.shared ? owner.users.map(u => M.byId.get(u)) : [M.byId.get(S.ev.item)];
    for (const o of users) if (o) g.papers.push({ id: o.id, item: o, type: typeOfItem(o), name: o.short || o.title, full: o.title, status: o.status, why: 'This file is part of the evidence for it' });
  }
  return g;
}
function evPreview(id) {
  const box = h('div', { class: 'epre' });
  const o = M.byId.get(id), n = IX.node.get(id);
  if (o && !o.shared) {
    box.append(h('div', { class: 'epre-h' }, tdot(typeOfItem(o)), h('b', null, o.title)), h('div', { class: 'muted' }, kindLabel(o) + ' · ' + ST[o.status].say));
    return box;
  }
  if (!n) return box;
  box.append(h('div', { class: 'epre-h' }, tdot(typeOfFile(n.kind)), h('b', { class: 'mono' }, n.kind === 'run' ? n.name.replace(/^run\s+/, '') : pathOf(n))));
  const body = h('div', null, h('div', { class: 'muted' }, 'Loading…')); box.append(body);
  const al = IX.alarm.get(id), ch = al && al.find(a => a.role === 'changed');
  const head = () => {
    if (n.kind === 'run' && (n.attrs || {}).command) return clear(body).append(h('div', { class: 'cap' }, 'Command'), h('div', { class: 'code' }, h('div', { class: 'ln' }, h('span', { class: 'n' }, '$'), n.attrs.command)));
    if (!(n.loc && n.loc.path)) return clear(body).append(h('div', { class: 'muted' }, 'No preview for this.'));
    getLines(n.repo, n.loc.path, 1, 14).then(r => { clear(body).append(capLoc(n, 'Start of the file', 1), codeBlock(r.lines, r.start, [], { label: 'Start of the file' })); })
      .catch(() => { clear(body).append(h('div', { class: 'muted' }, 'No preview for this kind of file.')); });
  };
  if (ch) ensureAnalysis(ch.group.id, id).then(an => {
    const df = !an.failed && an.diffs.find(d => d.node_id === id && !d.binary);
    if (df) clear(body).append(h('div', { class: 'cap' }, 'What changed'), diffBlock(df.unified)); else head();
  }); else head();
  return box;
}
function renderEvidenceSide(box, it) {
  const fileId = S.ev.file && IX.node.has(S.ev.file) ? S.ev.file : null;
  const fn = fileId ? IX.node.get(fileId) : null, fsh = fileId ? M.byId.get(fileId) : null;
  const ownerId = fileId || it.id;
  const st = fileId ? ((fsh && fsh.shared ? fsh.status : nodeFlag(fileId)) || 'ok') : it.status;
  const title = fileId ? (fn.kind === 'run' ? 'Run ' + fn.name.replace(/^run\s+/, '') : pathOf(fn)) : it.title;
  box.append(h('div', { class: 'rtitle' },
    h('div', { class: 'esub' }, 'Supporting evidence'),
    h('div', { class: 'rt-line' }, tdot(fileId ? typeOfFile(fn.kind) : typeOfItem(it)), h('div', { class: 'serif rt' }, title)), chip(st),
    h('div', { class: 'btnrow' },
      h('button', { class: 'btn sm', onclick: () => { if (fileId) openNode(fileId); else openItem(it.id); } }, 'Open full page'),
      fileId ? h('button', { class: 'btn sm', onclick: () => { S.ev.file = null; S.ev.trail = []; S.ev.row = null; evSync(); } }, 'Back to ' + trunc(it.short || it.title, 22)) : null,
      h('button', { class: 'btn sm', onclick: () => evClose() }, 'Close'))));
  if (it.ref) { box.append(h('div', { class: 'rempty' }, 'This is a reference. Open its page to see where it is cited.')); return; }
  if (S.ev.row) box.append(h('div', { class: 'rpad' }, evPreview(S.ev.row),
    S.ev.row !== ownerId && IX.node.has(S.ev.row) ? h('div', { class: 'btnrow' }, h('button', { class: 'btn sm', onclick: () => openNode(S.ev.row) }, 'Open this file'), h('button', { class: 'btn sm', onclick: () => copyText(pathOf(IX.node.get(S.ev.row))) }, 'Copy path')) : null));
  const g = evEntries(ownerId), groups = [['papers', 'Paper items it rests on'], ['results', 'Results'], ['code', 'Code'], ['runs', 'Runs'], ['settings', 'Settings and data']];
  let any = false;
  for (const [k, label] of groups) {
    const list = g[k]; if (!list.length) continue; any = true;
    const lab = fileId && k === 'papers' ? 'Paper items it supports' : label;
    box.append(h('section', { class: 'egrp' }, h('div', { class: 'eh' }, lab, h('span', { class: 'rc' }, list.length)),
      list.map(e => h('button', { class: 'erow' + (S.ev.row === e.id ? ' on' : ''), title: e.full, 'aria-pressed': String(S.ev.row === e.id),
        onclick: () => { S.ev.row = e.id; if (GR.g) GR.g.setEmph(e.id); renderRight(); } },
        tdot(e.type), h('span', { class: 'ename' + (e.item ? '' : ' mono') }, e.name), h('span', { class: 'est ' + e.status }, ST[e.status].glyph + ' ' + ST[e.status].word), h('span', { class: 'ewhy' }, e.why)))));
  }
  if (!any) box.append(h('div', { class: 'rempty' }, fileId ? 'Nothing else behind this file.' : 'Nothing behind this item yet. If it comes from a result file or script, add a note in the LaTeX source like % source: results/table2.csv.'));
  box.append(h('div', { class: 'rempty small' }, 'Click an empty spot or press Esc to close. Double-click an item to open its page.'));
}
function afterGraphAttach() { if (S.listView || !GR.g) return; syncGraph(); GR.g.resize(); }
function gFind(q, enter) {
  q = q.trim().toLowerCase(); if (!q || !GR.g) return;
  const it = M.items.find(i => i.title.toLowerCase().includes(q) && GR.g.visible().includes(i.id));
  if (it && enter) { GR.g.focusOn(it.id); S.sel = it.id; renderRight(); }
  else if (it) GR.g.focusOn(it.id);
}
function filtersPop(anchor) {
  const gf = S.gf;
  const cb = (key, label, sub) => h('label', { class: 'fcb' + (sub ? ' sub' : '') }, h('input', { type: 'checkbox', checked: gf[key] ? '' : null, onchange: ev => { gf[key] = ev.target.checked; persistUI(); GR.sig = ''; syncGraph(); if (key === 'files') filtersPop(anchor), filtersPop(anchor); } }), ' ' + label);
  const m = h('div', { id: 'menu', class: 'menu fpop', role: 'dialog', 'aria-label': 'Filters' },
    h('div', { class: 'mhead' }, 'Show'), cb('sections', 'Sections'), cb('floats', 'Figures, tables and equations'), cb('shared', 'Shared code and data'), cb('refs', 'References'),
    cb('files', 'Files behind items'), gf.files ? [cb('code', 'Code', true), cb('runs', 'Runs', true), cb('results', 'Results and data', true), cb('settings', 'Settings', true)] : null,
    cb('unused', 'Files not used by the paper'),
    h('div', { class: 'msep' }), cb('onlyChanged', 'Only things that changed'));
  const old = $('#menu'); if (old) { old.remove(); if (old.classList.contains('fpop') && old._anchor === anchor && !m._again) { return; } }
  m._anchor = anchor; document.body.append(m);
  const r = anchor.getBoundingClientRect(); m.style.left = Math.min(r.left, innerWidth - 300) + 'px'; m.style.top = (r.bottom + 4) + 'px';
  const off = ev => { if (!m.contains(ev.target) && ev.target !== anchor) { m.remove(); document.removeEventListener('mousedown', off, true); } };
  setTimeout(() => document.addEventListener('mousedown', off, true), 0);
}
function graphList() {
  const rows = M.items.filter(i => !i.ref || S.gf.refs);
  const key = S.listSort || 'imp';
  rows.sort((a, b) => key === 'title' ? (a.title < b.title ? -1 : 1) : key === 'status' ? ST[b.status].rank - ST[a.status].rank : b.links - a.links);
  const th = (k, l) => h('th', { scope: 'col' }, h('button', { class: 'linkbtn', onclick: () => { S.listSort = k; renderPage(true); } }, l));
  return h('div', { class: 'glist' }, h('table', { class: 'tbl' }, h('thead', null, h('tr', null, th('title', 'Item'), h('th', { scope: 'col' }, 'Kind'), th('status', 'Status'), th('imp', 'Connections'))),
    h('tbody', null, rows.map(i => h('tr', null, h('td', null, h('button', { class: 'linkbtn', onclick: ev => openItem(i.id, ev.metaKey || ev.ctrlKey) }, i.title)), h('td', null, kindLabel(i)), h('td', null, chip(i.status)), h('td', { class: 'mono' }, i.links))))));
}

/* ======================================================================
   7. SHELL: ribbon, explorer, tabs, right sidebar, status bar, palette, intro
   ====================================================================== */
Object.assign(S, { outline: [], openCard: {}, openEv: {}, hoverItem: null, ckFilter: 'all', focusFinding: null, showExample: false, listSort: 'imp', ev: { item: null, file: null, row: null, trail: [] } });
function persistUI() {
  lsSet(UIKEY, { tabs: S.tabs.map(t => ({ k: t.k, id: t.id })), active: S.active, leftOpen: S.leftOpen, rightOpen: S.rightOpen, leftW: S.leftW, rightW: S.rightW, gf: S.gf, treeOpen: S.treeOpen });
}
function restoreUI() {
  const u = lsGet(UIKEY, null);
  if (u) {
    Object.assign(S, { leftOpen: u.leftOpen !== false, rightOpen: u.rightOpen !== false, leftW: u.leftW || 260, rightW: u.rightW || 300, treeOpen: u.treeOpen || {} });
    if (u.gf) { Object.assign(S.gf, u.gf); S.hadGf = true; }
    S.tabs = (u.tabs || []).filter(t => ['changes', 'graph', 'item', 'node', 'checks', 'history', 'digest', 'review', 'claims', 'timeline', 'experiments', 'setup', 'tasks', 'ask', 'notation'].includes(t.k)); S.active = u.active != null ? u.active : 0;
  }
  if (!S.tabs.length) { S.tabs = [{ k: 'claims' }]; S.active = 0; }
  if (S.active >= S.tabs.length || S.active < 0) S.active = 0;
}
function pruneTabs() {
  const keep = S.tabs.filter(t => (t.k === 'item' ? M.byId.has(t.id) : t.k === 'node' ? IX.node.has(t.id) : true));
  if (keep.length !== S.tabs.length) { const cur = S.tabs[S.active]; S.tabs = keep.length ? keep : [{ k: 'changes' }]; S.active = Math.max(0, S.tabs.indexOf(cur)); }
}
const tabKey = t => t.k + (t.id ? '|' + t.id : '');
function tabTitle(t) {
  switch (t.k) {
    case 'changes': { const d = cpDate(); return d ? 'Changes since ' + d : 'Changes'; }
    case 'graph': return 'Graph'; case 'checks': return 'Checks'; case 'history': return 'History'; case 'digest': return 'Digest';
    case 'review': case 'claims': case 'timeline': case 'experiments': case 'setup': case 'tasks': case 'ask': case 'notation': return RX_TABS[t.k][1];
    case 'item': { const it = M.byId.get(t.id); return it ? trunc(it.short || it.title, 24) : 'Item'; }
    case 'node': { const n = IX.node.get(t.id); return n ? trunc(basename(pathOf(n)), 24) : 'File'; }
  }
  return '';
}
const TAB_GLYPH = { digest: '',  changes: '◔', graph: '◉', checks: '!', history: '⚑', item: '▤', node: '{ }', review: '◎', claims: '◆', timeline: '⚑', experiments: '▦', setup: '⊞', tasks: '☑', ask: '?', notation: '𝑥' };
function openTab(k, id, opts) {
  opts = opts || {};
  const key = tabKey({ k, id });
  let i = S.tabs.findIndex(t => tabKey(t) === key);
  if (i < 0) {
    if (opts.replace && S.active >= 0 && S.tabs[S.active] && ['item', 'node'].includes(S.tabs[S.active].k)) { S.tabs[S.active] = { k, id }; i = S.active; }
    else {
      S.tabs.push({ k, id });
      if (S.tabs.length > 8) { const act = S.tabs[S.tabs.length - 1]; const cand = S.tabs.filter(t => t !== act).sort((a, b) => (a.used || 0) - (b.used || 0))[0]; S.tabs.splice(S.tabs.indexOf(cand), 1); }
      i = S.tabs.findIndex(t => tabKey(t) === key);
    }
  }
  activate(i);
}
function openItem(id, newTab) {
  const it = M.byId.get(id); if (!it) return;
  S.sel = id; openTab('item', id, { replace: !newTab });
}
function openNode(nid) {
  const it = itemFor(nid);
  if (it) { S.openEv[nid] = true; openItem(it.id, false); setTimeout(() => { const el = $('[data-ev="' + CSS.escape(nid) + '"]'); if (el) el.scrollIntoView({ block: 'center' }); }, 30); }
  else openTab('node', nid, { replace: true });
}
function activate(i, noNav) {
  S.active = i; const t = S.tabs[i]; t.used = Date.now();
  if (t.k === 'item') S.sel = t.id;
  if (!noNav) { S.nav = S.nav.slice(0, S.navPos + 1); S.nav.push(tabKey(t)); S.navPos = S.nav.length - 1; }
  persistUI(); if (!noNav) window.scrollTo(0, 0); renderAll();
}
function navGo(d) {
  const p = S.navPos + d; if (p < 0 || p >= S.nav.length) return;
  S.navPos = p; const key = S.nav[p]; const i = S.tabs.findIndex(t => tabKey(t) === key);
  if (i >= 0) activate(i, true); else { const [k, id] = key.split('|'); S.tabs.push({ k, id }); activate(S.tabs.length - 1, true); }
}

/* ---------- shell DOM (S18): band, one column, footer ---------- */
/* The four top-level pages. Every other page belongs to one of them (shown as active) and is reached from a link on that page or from the footer. */
const NAV = [['claims', 'Claims'], ['experiments', 'Experiments'], ['setup', 'Setup'], ['digest', 'Digest'], ['review', 'Review']];
const NAV_OF = { claims: 'claims', timeline: 'claims', notation: 'claims', graph: 'claims', item: 'claims', node: 'claims', experiments: 'experiments', setup: 'setup', digest: 'digest', tasks: 'digest', history: 'digest', ask: 'digest', review: 'review', changes: 'review', checks: 'review' };
const navShort = l => l.slice(0, 1);
function buildShell() {
  const app = $('#app');
  app.append(
    h('header', { id: 'band' }, h('h1', { class: 'bt' }, PRODUCT), h('p', { class: 'bsub', id: 'bsub' }, ''), h('nav', { id: 'topnav', role: 'tablist', 'aria-label': 'Main' })),
    h('div', { id: 'banner', class: 'hidden', role: 'alert' }),
    h('main', { id: 'page', tabindex: '-1' }),
    h('footer', { id: 'status' }),
    h('div', { id: 'extras' }));
}
function renderShellExtras() {
  const ex = clear($('#extras'));
  const hc = hubControls();
  if (HUB_ON && !READONLY && hc.zipInput) ex.append(h('input', { type: 'file', id: 'zip-in', accept: '.zip,application/zip', class: 'hidden', 'aria-label': 'Paper zip', onchange: hubUpload }));
}
function projectMenu(anchor) {
  const hc = hubControls();
  const es = [{ head: S.project ? S.project.name : PRODUCT }];
  if (!READONLY) es.push({ label: 'Export report (HTML)', hint: 'A single file you can share', href: apiUrl('/api/export'), download: true });
  es.push({ label: 'Sync now', fn: () => syncNow(), disabled: READONLY });
  if (hc.menu.length) { es.push({ sep: true }); hc.menu.forEach(m => es.push(m)); }
  es.push({ sep: true }, { label: 'Show "How Lemmata works"', fn: () => intro(true) });
  menuPop(anchor, es, { up: true });
}

/* ---------- left sidebar ---------- */
const sgl = st => h('span', { class: 'sg ' + st, 'aria-hidden': 'true' }, ST[st].glyph);
function activeIs(k, id) { const t = S.tabs[S.active]; return !!t && t.k === k && (id == null || t.id === id); }
function usedByText(nid) {
  const its = (M.itemsOf.get(nid) || []).map(i => M.byId.get(i));
  if (!its.length) return 'Not used by the paper';
  if (its[0].shared) return 'Shared by ' + its[0].users.map(u => lead(M.byId.get(u))).slice(0, 3).join(' and ');
  return 'Part of ' + lead(its[0]);
}
function renderLeft() { }   // S18: no sidebar; the counts that lived here are in the nav and the footer

/* ---------- tab bar, page ---------- */
function renderTabbar() {
  const bar = clear($('#topnav')); if (!bar) return;
  const t = S.tabs[S.active], cur = t ? NAV_OF[t.k] : null;
  const badge = k => k === 'claims' ? ((RX.claims && RX.claims.counts && RX.claims.counts.stages) ? (RX.claims.counts.stages.testing + RX.claims.counts.stages.refuted) || 0 : 0)
    : k === 'experiments' ? (RX.experiments ? RX.experiments.counts.attention + RX.experiments.counts.untested : 0) : k === 'setup' ? (RX.setup ? RX.setup.counts.checks : 0) : k === 'review' ? M.todo || 0 : (RX.tasks && RX.tasks.counts ? RX.tasks.counts.open || 0 : 0);
  NAV.forEach(([k, label]) => {
    const on = k === cur, n = badge(k);
    bar.append(h('button', { class: 'navtab' + (on ? ' on' : ''), role: 'tab', 'aria-selected': String(on), 'aria-label': label + (n ? ', ' + n + ' to look at' : ''), title: label, onclick: () => openTab(k) },
      h('span', { class: 'navl', 'data-full': label }, label), n ? h('span', { class: 'navn' }, ' ' + n) : null));
  });
  fitTabs();
  const sub = $('#bsub'); if (sub) sub.textContent = S.project ? S.project.name : '';
}
function renderPage(keepScroll) {
  const pg = $('#page'), st = window.scrollY, t = S.tabs[S.active];
  if (!t) return;
  if (GR.el && GR.el.parentNode) GR.el.parentNode.removeChild(GR.el);
  clear(pg); pg.className = t.k === 'graph' ? 'graph' : t.k === 'setup' ? 'wide' : '';
  S.outline = [];
  let el;
  if (S.error && !S.graph.nodes.length) el = doc(emptyState('!', 'Can\'t reach Lemmata.', 'The local server isn\'t answering. Check that Lemmata is still running, then try again.', [h('button', { class: 'btn primary', onclick: () => loadAll() }, 'Try again')]));
  else if (t.k === 'changes') el = pageChanges();
  else if (t.k === 'graph') el = pageGraph();
  else if (t.k === 'item') { const it = M.byId.get(t.id); el = it ? pageItem(it) : doc(h('div', { class: 'muted' }, 'This item is not in the project any more.')); }
  else if (t.k === 'node') el = pageEvidence(t.id);
  else if (t.k === 'checks') el = pageChecks();
  else if (t.k === 'history') el = pageHistory();
  else if (RX_PAGES[t.k]) el = RX_PAGES[t.k]();
  pg.append(el);
  if (t.k === 'item' || t.k === 'graph') pg.append(h('aside', { id: 'right', 'aria-label': 'Links for the open item' }));
  if (S.navPos > 0 && !NAV.some(n => n[0] === t.k)) pg.prepend(h('button', { class: 'linkbtn backlink', onclick: () => navGo(-1) }, '← Back'));
  if (t.k === 'graph') afterGraphAttach();
  if (keepScroll) window.scrollTo(0, st);
  else if (t.k === 'checks' && S.focusFinding) { const f = $('#f-' + S.focusFinding.replace(/[^\w]/g, '_')); if (f) f.scrollIntoView({ block: 'center' }); }
  renderOutlineSoon();
}
let outT = 0; function renderOutlineSoon() { cancelAnimationFrame(outT); outT = requestAnimationFrame(renderRight); }

/* ---------- right sidebar ---------- */
const REL_OUT = { contains: 'contains', answers: 'is answered in', refs: 'refers to', cites: 'cites', uses: 'uses' };
const REL_IN = { contains: 'contains it', answers: 'asks what it answers', refs: 'refers to it', cites: 'cites it', uses: 'uses it' };
const EV_REL = { result: 'built from', asset: 'shows', code: 'made by', run: 'run', config: 'settings', data: 'data', doc: 'document' };
function focusItem() {
  const t = S.tabs[S.active]; if (!t) return null;
  if (t.k === 'item') return M.byId.get(t.id);
  if (t.k === 'graph') return M.byId.get(S.hoverItem || S.sel) || null;
  return null;
}
function acc(title, count, body, key) {
  const open = S.treeOpen['r:' + key] !== false;
  return h('section', { class: 'racc' }, h('button', { class: 'rh', 'aria-expanded': String(open), onclick: () => { S.treeOpen['r:' + key] = !open; renderRight(); } }, h('span', { class: 'caret' }, open ? '▾' : '▸'), title, count != null ? h('span', { class: 'rc' }, count) : null), open ? h('div', { class: 'rb' }, body) : null);
}
function rrow(label, rel, st, onclick, hov, type) {
  return h('button', { class: 'rrow', onclick, onmouseenter: hov ? () => { if (RG.g) RG.g.hl(hov); } : null }, type ? tdot(type) : null, st ? sgl(st) : h('span', { class: 'sg ph' }), h('span', { class: 'rl' }, label), h('span', { class: 'rrel' }, rel));
}
function renderRight() {
  const rbox = $('#right'); if (!rbox) { if (RG.g) { RG.g.destroy(); RG.g = null; } return; }
  const box = clear(rbox);
  if (RG.g) { RG.g.destroy(); RG.g = null; }
  const tb = S.tabs[S.active];
  if (tb && tb.k === 'graph' && S.ev.item && M.byId.has(S.ev.item)) { renderEvidenceSide(box, M.byId.get(S.ev.item)); return; }
  const it = focusItem();
  if (!it) { box.append(h('div', { class: 'rempty' }, 'Open an item to see what it rests on and what rests on it.')); return; }
  box.append(h('div', { class: 'rtitle' }, h('div', { class: 'serif rt' }, it.title), chip(it.status)));
  const merge = (list, rels) => { const m = new Map(); for (const x of list) { if (M.byId.get(x.id).ref && !S.gf.refs) continue; const e = m.get(x.id) || { id: x.id, rels: [] }; const w = rels[x.rel]; if (!e.rels.includes(w)) e.rels.push(w); m.set(x.id, e); } return [...m.values()]; };
  const outs = merge(M.nbOut.get(it.id) || [], REL_OUT), ins = merge(M.nbIn.get(it.id) || [], REL_IN);
  const rest = [];
  if (!it.shared) for (const e of it.ev.slice(0, 7)) { const n = IX.node.get(e.id); if (!n) continue; rest.push(rrow(n.kind === 'run' ? n.name.replace(/^run\s+/, '') : pathOf(n), EV_REL[n.kind] || '', nodeFlag(e.id), () => openNode(e.id), null, typeOfFile(n.kind))); }
  if (!it.shared && it.ev.length > 7) rest.push(h('div', { class: 'muted rmore' }, 'and ' + (it.ev.length - 7) + ' more behind this item'));
  outs.slice(0, 10).forEach(x => { const o = M.byId.get(x.id); rest.push(rrow(o.short || o.title, x.rels.join(' · '), o.status !== 'ok' ? o.status : null, () => openItem(o.id), o.id, typeOfItem(o))); });
  if (outs.length > 10) rest.push(h('div', { class: 'muted rmore' }, 'and ' + (outs.length - 10) + ' more'));
  box.append(acc('Rests on', rest.length, rest.length ? rest : h('div', { class: 'muted' }, 'Nothing. This item stands on its own.'), 'rests'));
  const sup = ins.slice(0, 12).map(x => { const o = M.byId.get(x.id); return rrow(o.short || o.title, x.rels.join(' · '), o.status !== 'ok' ? o.status : null, () => openItem(o.id), o.id, typeOfItem(o)); });
  box.append(acc('Supports', ins.length, sup.length ? sup : h('div', { class: 'muted' }, 'Nothing else rests on this yet.'), 'supports'));
  const lg = h('div', { class: 'lghost' });
  box.append(acc('Local graph', null, [lg, h('div', { class: 'lgctl' }, h('button', { class: 'btn sm', 'aria-label': 'Fewer steps', disabled: S.localDepth <= 1, onclick: () => { S.localDepth--; renderRight(); } }, '−'), h('span', null, 'Depth ' + S.localDepth), h('button', { class: 'btn sm', 'aria-label': 'More steps', disabled: S.localDepth >= 3, onclick: () => { S.localDepth++; renderRight(); } }, '+'), h('span', { class: 'grow' }), h('button', { class: 'linkbtn', onclick: () => { S.gf.mode = 'around'; S.sel = it.id; openTab('graph'); } }, 'Open in Graph tab'))], 'local'));
  const evs = relevantEvents(it).slice(0, 5);
  box.append(acc('Recent changes', null, [evs.length ? evs.map(e => eventLine(e)) : h('div', { class: 'muted' }, 'Nothing has changed here since the start.'), h('button', { class: 'linkbtn', onclick: () => openTab('history') }, 'See all in History')], 'recent'));
  if (S.outline.length && activeIs('item')) box.append(acc('Outline', null, S.outline.map(o => h('button', { class: 'rrow', onclick: () => { const el = $('#sec-' + o.id); if (el) el.scrollIntoView({ block: 'start' }); } }, h('span', { class: 'rl' }, o.label))), 'outline'));
  // local graph canvas
  if (lg.isConnected && S.treeOpen['r:local'] !== false) {
    lg.style.height = '200px';
    const spec = graphSpec({ local: it.id, depth: S.localDepth });
    RG.g = makeGraph(lg, { mini: true, pos: new Map(), label: 'Local graph of the open item', onClick: id => { if (id) openItem(id, false); } });
    RG.g.setData(spec); RG.g.setSelected(it.id); RG.g.resize(); RG.g.fit();
  }
}
const RG = { g: null };

/* ---------- status bar ---------- */
function renderStatus() {
  const bar = clear($('#status')); if (!bar) return;
  const cp = S.alarms && S.alarms.checkpoint, hc = hubControls();
  const nChecks = ((S.findings && S.findings.findings) || []).length;
  const embed = !!window.LEMMATA_EMBED;
  const link = (label, fn, extra) => h('button', Object.assign({ class: 'linkbtn flink', onclick: fn }, extra || {}), label);
  const more = [link('Changes', () => openTab('changes')), link('Checks' + (nChecks ? ' (' + nChecks + ')' : ''), () => openTab('checks')), link('History', () => openTab('history')), link('Graph', () => openTab('graph')),
    link('Growth', () => openTab('timeline')), link('Notation', () => openTab('notation')), link('Tasks', () => openTab('tasks')), link('Ask', () => openTab('ask')), link('Search', () => quickSwitcher())];
  bar.append(h('div', { class: 'flinks' }, more, embed ? (window.LEMMATA_EMBED.site ? h('a', { class: 'flink', href: window.LEMMATA_EMBED.site, id: 'open-site' }, 'Open on website') : null) : [link('Project menu', ev => projectMenu(ev.currentTarget), { id: 'foot-menu' }), link('How Lemmata works', () => intro(true))]),
    h('div', { class: 'fstate' },
      h('button', { class: 'linkbtn flink', onclick: () => (READONLY ? openTab('changes') : markAllDialog()), title: 'Mark everything as looked at' }, 'Last looked at: ' + (cp ? lastChecked(cp.created_at) : 'not yet')),
      ' · ', plural(M.todo || 0, 'thing') + ' to look at',
      BUSY ? h('span', { role: 'status' }, ' · ' + BUSY) : !hc.status && S.project ? ' · Files read ' + agoText(S.project.scanned_at) : hc.status ? ' · ' + hc.status : null,
      READONLY ? null : [' · ', h('button', { class: 'linkbtn flink', disabled: !!BUSY, onclick: () => syncNow() }, 'Sync now')]));
}

/* ---------- palette / switcher / intro ---------- */
function fuzzy(q, s) {
  q = q.toLowerCase(); s = s.toLowerCase(); if (!q) return 1;
  let i = 0, score = 0, last = -2;
  for (let j = 0; j < s.length && i < q.length; j++) if (s[j] === q[i]) { score += (j === last + 1 ? 3 : 1) + (j === 0 || ' /-_.'.includes(s[j - 1]) ? 2 : 0); last = j; i++; }
  return i === q.length ? score : -1;
}
function listModal(placeholder, makeList, hint) {
  let sel = 0, list = [];
  const prev = document.activeElement;
  const input = h('input', { type: 'text', class: 'pinput', placeholder, 'aria-label': placeholder, autocomplete: 'off', spellcheck: 'false' });
  const ul = h('div', { class: 'plist', role: 'listbox' });
  const close = () => { scrim.remove(); if (prev && prev.focus) prev.focus(); };
  const draw = () => {
    list = makeList(input.value); sel = Math.min(sel, Math.max(0, list.length - 1)); clear(ul);
    list.slice(0, 8).forEach((r, i) => ul.append(h('div', { class: 'pitem' + (i === sel ? ' on' : '') + (r.disabled ? ' off' : ''), role: 'option', 'aria-selected': String(i === sel), onmouseenter: () => { sel = i; paint(); }, onclick: () => run(r) },
      r.st ? sgl(r.st) : null, h('span', { class: 'pl' }, r.label), r.disabled ? h('span', { class: 'prel' }, r.reason) : r.hint ? h('span', { class: 'prel' }, r.hint) : null)));
    if (!list.length) ul.append(h('div', { class: 'lempty' }, 'Nothing matches.'));
  };
  const paint = () => $$('.pitem', ul).forEach((e, i) => { e.classList.toggle('on', i === sel); e.setAttribute('aria-selected', String(i === sel)); });
  const run = r => { if (r.disabled) return; close(); r.run(); };
  input.addEventListener('input', () => { sel = 0; draw(); });
  input.addEventListener('keydown', ev => {
    if (ev.key === 'Escape') { ev.preventDefault(); close(); }
    else if (ev.key === 'ArrowDown') { ev.preventDefault(); sel = Math.min(Math.min(list.length, 8) - 1, sel + 1); paint(); }
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); sel = Math.max(0, sel - 1); paint(); }
    else if (ev.key === 'Enter') { ev.preventDefault(); if (list[sel]) run(list[sel]); }
  });
  const scrim = h('div', { class: 'scrim top', onclick: ev => { if (ev.target === scrim) close(); } }, h('div', { class: 'palette', role: 'dialog', 'aria-modal': 'true', 'aria-label': placeholder }, input, ul, hint ? h('div', { class: 'phint' }, hint) : null));
  document.body.append(scrim); draw(); input.focus();
}
function quickSwitcher() {
  listModal('Open an item or a file', q => {
    const rows = [];
    for (const it of M.items) { if (it.ref && !S.gf.refs && !q) continue; const s = fuzzy(q, it.title); if (s >= 0) rows.push({ s: s + 5, label: it.title, hint: kindLabel(it), st: it.status, run: () => openItem(it.id) }); }
    for (const n of S.graph.nodes) if (FILEK.has(n.kind)) { const s = fuzzy(q, pathOf(n)); if (s >= 0) rows.push({ s, label: pathOf(n), hint: usedByText(n.id), run: () => openNode(n.id) }); }
    return rows.sort((a, b) => b.s - a.s);
  }, '↑↓ to move · Enter to open · Esc to close');
}
function currentItemCmd(state) {
  const it = focusItem();
  return it && !it.shared ? () => setTriageMany(itemTargets(it), state, noteOf(itemTargets(it))) : null;
}
function palette() {
  const it = S.tabs[S.active] && S.tabs[S.active].k === 'item' ? M.byId.get(S.tabs[S.active].id) : null;
  const cmds = [
    { label: 'Go to Review', run: () => openTab('review') }, { label: 'Go to Claims', run: () => openTab('claims') }, { label: 'Go to Notation', run: () => openTab('notation') }, { label: 'Go to Timeline', run: () => openTab('timeline') }, { label: 'Go to Experiments', run: () => openTab('experiments') }, { label: 'Go to Setup (metrics, datasets, baselines)', run: () => openTab('setup') }, { label: 'Go to Tasks', run: () => openTab('tasks') }, { label: 'Ask about this project', run: () => openTab('ask') },
    { label: 'Go to Changes', run: () => openTab('changes') }, { label: 'Go to Graph', run: () => openTab('graph') }, { label: 'Go to Checks', run: () => openTab('checks') }, { label: 'Go to History', run: () => openTab('history') },
    { label: 'Open item…', hint: 'Ctrl+O', run: () => quickSwitcher() },
    { label: 'Mark everything as looked at', run: () => markAllDialog(), disabled: READONLY, reason: 'Read-only snapshot' },
    { label: 'Mark this item as Looks fine', run: () => setTriageMany(itemTargets(it), 'reviewed', noteOf(itemTargets(it))), disabled: !it || READONLY, reason: it ? 'Read-only snapshot' : 'No item open' },
    { label: 'Mark this item as Needs fixing', run: () => setTriageMany(itemTargets(it), 'needs_fixing', noteOf(itemTargets(it))), disabled: !it || READONLY, reason: it ? 'Read-only snapshot' : 'No item open' },
    { label: 'Ignore this item', run: () => setTriageMany(itemTargets(it), 'ignored', noteOf(itemTargets(it))), disabled: !it || READONLY, reason: it ? 'Read-only snapshot' : 'No item open' },
    { label: 'Sync now', run: () => syncNow(), disabled: READONLY, reason: 'Read-only snapshot' },
    { label: 'Show files behind items', run: () => { S.gf.files = true; persistUI(); GR.sig = ''; openTab('graph'); } },
    { label: 'Export report (HTML)', run: () => { goTo(apiUrl('/api/export')); }, disabled: READONLY, reason: 'Read-only snapshot' },
    { label: 'How Lemmata works', run: () => intro(true) },
  ];
  listModal('Type a command or an item', q => cmds.map(c => ({ ...c, s: fuzzy(q, c.label) })).filter(c => c.s >= 0).sort((a, b) => b.s - a.s), '↑↓ to move · Enter to run · Esc to close');
}
function intro(force) {
  if (!force && lsGet('lemmata.seen_intro', false)) return;
  let step = 0;
  const body = h('div', { class: 'intro' }), dots = h('div', { class: 'muted idots' });
  const acts = h('div', { class: 'acts' });
  const done = (go) => { lsSet('lemmata.seen_intro', true); scrim.remove(); document.removeEventListener('keydown', onKey, true); if (go) openTab('changes'); };
  const draw = () => {
    clear(body).append(h('h3', { class: 'serif' }, T.intro[step][0]), h('p', null, T.intro[step][1]));
    clear(dots).append(step + 1 + ' of 3');
    clear(acts).append(h('button', { class: 'linkbtn', onclick: () => done(false) }, 'Skip'), h('span', { class: 'grow' }),
      step ? h('button', { class: 'btn', onclick: () => { step--; draw(); } }, 'Back') : null,
      step < 2 ? h('button', { class: 'btn primary', onclick: () => { step++; draw(); } }, 'Next') : h('button', { class: 'btn primary', onclick: () => done(true) }, 'Show me what changed'));
  };
  const onKey = ev => { if (ev.key === 'Escape') done(false); };
  document.addEventListener('keydown', onKey, true);
  const scrim = h('div', { class: 'scrim' }, h('div', { class: 'modal introm', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'How Lemmata works' }, body, dots, acts));
  document.body.append(scrim); draw();
}

/* ---------- keys ---------- */
const typing = t => t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable);
let gSeq = 0;
document.addEventListener('keydown', ev => {
  const mod = ev.metaKey || ev.ctrlKey, k = ev.key;
  if (mod && !ev.altKey) {
    if ((k === 'p' || k === 'P') && !ev.shiftKey) { ev.preventDefault(); palette(); }
    else if (k === 'o' || k === 'O') { ev.preventDefault(); quickSwitcher(); }
    else if (k === '[') { ev.preventDefault(); navGo(-1); }
    else if (k === ']') { ev.preventDefault(); navGo(1); }
    return;
  }
  if (ev.altKey || typing(ev.target) || document.querySelector('.scrim')) return;
  const t = S.tabs[S.active], recent = Date.now() - gSeq < 900;
  if (k === 'Escape' && t && t.k === 'graph' && S.ev.item) { evClose(); return; }
  if (k === '/' && t && t.k === 'graph') { ev.preventDefault(); const f = $('#gfind'); if (f) f.focus(); }
  else if (k === '?') intro(true);
  else if (k === 'g') { if (recent) { gSeq = 0; openTab('graph'); } else gSeq = Date.now(); }
  else if (k === 'c' && recent) { gSeq = 0; openTab('changes'); }
});

/* ======================================================================
   8. BOOT
   ====================================================================== */
function renderAll() {
  renderLeft(); renderTabbar(); renderPage(true); renderStatus(); renderBanner();
  document.title = (S.project ? S.project.name + ' – ' : '') + PRODUCT;
}
function renderBanner() {
  const b = $('#banner'); if (!b) return; clear(b);
  const msg = READONLY ? 'Read-only snapshot from ' + dmon(SNAP.exported_at || '') + '. You can look around but not change anything.' : null;
  if (S.error && S.graph && S.graph.nodes.length) { b.classList.remove('hidden'); b.className = 'err'; b.append('Something broke on our side. Your files and marks are unchanged. ', h('button', { class: 'linkbtn', onclick: () => loadAll() }, 'Try again')); return; }
  if (msg) { b.classList.remove('hidden'); b.className = 'info'; b.append(msg); } else b.classList.add('hidden');
}
async function loadAll() {
  try {
    const [project, graph, events, findings, alarms, checkpoints, triage] = await Promise.all(
      ['project', 'graph', 'events', 'findings', 'alarms', 'checkpoints', 'triage'].map(p => apiGet('/api/' + p)));
    Object.assign(S, { project, graph, events, findings, alarms, checkpoints, triage, error: null, loading: false });
  } catch (e) {
    S.loading = false; S.error = e.message; if (!S.graph) S.graph = { nodes: [], edges: [] };
  }
  rebuildIndex(); pruneTabs();
  rxLoad().then(() => { renderLeft(); const t = S.tabs[S.active]; if (t && RX_PAGES[t.k]) renderPage(true); });
  if (!S.hadGf && !S.gfAuto) { S.gfAuto = true; if (M.items.filter(i => i.shared).length > 12) { S.gf.shared = false; GR.sig = ''; } }
  const first = !S.rendered; S.rendered = true;
  renderAll(); renderShellExtras();
  if (first) { persistUI(); }
  prefetchCauses();
}
async function prefetchCauses() {
  let any = false;
  for (const g of (S.alarms && S.alarms.groups) || []) {
    const cfg = g.changed.filter(c => (IX.node.get(c.node_id) || {}).kind === 'config');
    if (g.changed.length === 1 && cfg.length === 1 && !S.an[analysisKey(g.id, cfg[0].node_id)]) { await ensureAnalysis(g.id, cfg[0].node_id); any = true; }
  }
  if (any && S.tabs[S.active] && S.tabs[S.active].k === 'changes') renderPage(true);
  else if (any) renderRight();
}
let refreshBusy = false;
async function autoRefreshTick() {
  if (READONLY || refreshBusy || document.hidden || S.loading || !S.project) return;
  if (document.querySelector('.scrim') || typing(document.activeElement)) return;
  refreshBusy = true;
  try {
    const p = await apiGet('/api/project');
    if (p.scanned_at && p.scanned_at !== S.project.scanned_at) { await loadAll(); toast('Updated. Lemmata found new changes.'); }
  } catch (e) { /* server briefly busy: try again next tick */ }
  refreshBusy = false;
}
/* In VS Code the four tabs stay on one row: when they do not fit, the active one keeps its name and the others shorten to their first letter. */
function fitTabs() {
  const bar = $('#topnav'); if (!bar || !window.LEMMATA_EMBED) return;
  const inactive = bar.querySelectorAll('.navtab:not(.on) .navl');
  inactive.forEach(s => { s.textContent = s.dataset.full; });
  if (bar.scrollWidth > bar.clientWidth + 1) inactive.forEach(s => { s.textContent = navShort(s.dataset.full); });
}
/* In VS Code, arrow keys move between rows and Enter opens one, as in the file explorer (the Claims tree has its own keys). */
const ROW_KEYS = '.row-line button, .rx-x-main, button.rx-rv-r, button.rx-rv-b, button.rx-rv-check, .rrow';
function rowKeys() {
  if (!window.LEMMATA_EMBED) return;
  document.addEventListener('keydown', ev => {
    if (ev.key !== 'ArrowDown' && ev.key !== 'ArrowUp') return;
    const a = document.activeElement;
    if (!a || !a.matches || !a.matches(ROW_KEYS)) return;
    const all = Array.from(document.querySelectorAll(ROW_KEYS)).filter(e => e.offsetParent), nx = all[all.indexOf(a) + (ev.key === 'ArrowDown' ? 1 : -1)];
    if (nx) { ev.preventDefault(); nx.focus(); }
  });
}
function watchWidth() {   // the width modes themselves are CSS container queries; only the tab labels are measured
  if (!window.ResizeObserver) return;
  new ResizeObserver(() => fitTabs()).observe($('#app'));
}
function boot() {
  restoreUI();
  S.graph = { nodes: [], edges: [] }; rebuildIndex();
  buildShell();
  renderAll(); watchWidth(); rowKeys();
  detectHub().then(loadAll).then(() => {
    if (!READONLY) { setInterval(autoRefreshTick, 5000); document.addEventListener('visibilitychange', () => { if (!document.hidden) autoRefreshTick(); }); }
    if (HUB_ON) { lsSet('lemmata.seen_intro', true); rxStartView().then(rxUsefulBar); }   // the hub's own tutorial already explained Lemmata
    else intro(false);
  });
}
/* research.js is loaded after this file, so start once the whole document (both scripts) has been read. */
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
