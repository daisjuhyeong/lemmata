/* Lemmata research views (S07): Claim map, Timeline, Experiments, Tasks, Ask. Loaded after app.js and uses its helpers
   (h, clear, doc, sec, apiGet, apiPost, openTab, openNode, toast, modal, plainChip, mono, trunc, absTime, dmon, S, IX).
   Everything shown here comes from /api/claims, /api/timeline, /api/ledger, /api/tasks, /api/digest and /api/ask.
   No inline scripts, no innerHTML. */
'use strict';
const RX = { tree: null, view: 'tree', sel: null, t: 1, playing: null, claims: null, timeline: null, ledger: null, tasks: null, loaded: false, error: null, open: {}, filter: 'all', tlFilter: 'all', exFilter: 'all',
  ask: { q: '', busy: false, res: null, history: [] }, hub: null, digest: null };
const RX_TABS = { claims: ['◆', 'Claims'], timeline: ['⚑', 'Timeline'], experiments: ['▦', 'Experiments'], tasks: ['☑', 'Tasks'], ask: ['?', 'Ask'] };
const RX_VIEW_TAB = { claims: 'claims', inbox: 'changes', timeline: 'timeline', ask: 'ask' };
const RX_STATUS = { supported: ['✓', 'Supported', 'fine'], partial: ['◐', 'Partly supported', 'look'], unsupported: ['✕', 'Not supported', 'fix'] };
const RX_KIND = { contribution: 'Contribution', question: 'Research question', theorem: 'Theorem', lemma: 'Lemma', proposition: 'Proposition', corollary: 'Corollary', claim: 'Claim', core: 'Core message' };

function rxTrack(event, extra) {
  if (!HUB_ON || READONLY) return;
  fetch('/api/hub/events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.assign({ event, project: PID }, extra || {})) }).catch(() => { });
}
async function rxLoad() {
  if (READONLY && !(SNAP && SNAP.claims)) { RX.loaded = true; RX.error = 'This snapshot was made without the research views.'; return; }
  try {
    const [claims, timeline, ledger, tasks, tree] = await Promise.all(['claims', 'timeline', 'ledger', 'tasks', 'tree'].map(p => apiGet('/api/' + p)));
    Object.assign(RX, { claims, timeline, ledger, tasks, tree, loaded: true, error: null });
  } catch (e) { RX.loaded = true; RX.error = e.status === 501 ? 'Not available on sample data.' : e.message; }
}
async function rxRefresh(render) { await rxLoad(); if (render !== false) { renderLeft(); renderPage(true); renderStatus(); } }
function rxChip(st) { const s = RX_STATUS[st]; return plainChip(s[0], s[1], s[2]); }
function rxWhere(loc, repo) {
  if (!loc || !loc.path) return null;
  return h('button', { class: 'linkbtn mono small', title: 'Show these lines', onclick: () => rxShowLines(repo || 'paper', loc) }, loc.path + (loc.line ? ':' + loc.line : ''));
}
async function rxShowLines(repo, loc) {
  const a = Math.max(1, (loc.line || 1) - 2), b = (loc.end_line || loc.line || 1) + 2;
  let body;
  try { const r = await apiGet('/api/file?repo=' + encodeURIComponent(repo) + '&path=' + encodeURIComponent(loc.path) + '&start=' + a + '&end=' + Math.min(b, a + 60)); const hl = []; for (let i = loc.line || 1; i <= (loc.end_line || loc.line || 1); i++) hl.push(i); body = codeBlock(r.lines, r.start, hl); }
  catch (e) { body = h('p', { class: 'muted' }, 'Could not read those lines: ' + e.message); }
  modal(loc.path + ':' + loc.line, body, [{ label: 'Close', primary: true }]);
}
function rxNotReady(title) {
  if (!RX.loaded) return doc(h('h1', { class: 'ptitle' }, title), h('p', { class: 'muted' }, 'Reading your project…'));
  if (RX.error) return doc(h('h1', { class: 'ptitle' }, title), emptyState('!', 'Not available', RX.error, [h('button', { class: 'btn', onclick: () => rxRefresh() }, 'Try again')]));
  return null;
}
function rxNodeBtn(nid, label) {
  const n = IX.node && IX.node.get(nid);
  return h('button', { class: 'linkbtn', onclick: () => openNode(nid), title: n ? pathOf(n) : '' }, label || (n ? shortTitle(n) : nid));
}
async function rxPost(path, body, okMsg) {
  try {
    const r = await apiPost(path, body); if (okMsg) toast(okMsg);
    if (path.startsWith('/api/claims')) { RX.digest = null; try { const [t, l, tr] = await Promise.all(['timeline', 'ledger', 'tree'].map(p => apiGet('/api/' + p))); RX.timeline = t; RX.ledger = l; RX.tree = tr; } catch (e) { /* the old tree stays */ } }
    else RX.digest = null;
    return r;
  }
  catch (e) { toast(e.message || 'That did not work.'); return null; }
}

/* ---------- Claim map ---------- */
function rxChain(s) {
  const ch = s.chain || {};
  const parts = [];
  const add = (ids, word) => { if (ids && ids.length) parts.push(h('span', { class: 'ch-part' }, h('span', { class: 'muted' }, word + ' '), ids.slice(0, 3).map((id, i) => [i ? ', ' : null, rxNodeBtn(id, basename((IX.node.get(id) || { name: id }).name))]), ids.length > 3 ? ' +' + (ids.length - 3) : null)); };
  add(ch.results, 'file'); add(ch.code, 'made by'); add(ch.runs, 'run'); add(ch.settings, 'settings');
  if (!parts.length) return null;
  return h('div', { class: 'rx-chain' }, parts.map((p, i) => [i ? h('span', { class: 'arrow', 'aria-hidden': 'true' }, ' ← ') : null, p]));
}
function rxSupportRow(c, s) {
  const key = s.node_id || s.name;
  const rel = { proof: 'Proof', assumes: 'Assumes', uses: 'Uses', evidence: 'Evidence', 'stated as': 'Stated as' }[s.relation] || s.relation;
  const suggested = s.how === 'suggested';
  const name = s.node_id ? rxNodeBtn(s.node_id, s.name) : (s.claim_id ? h('button', { class: 'linkbtn', onclick: () => { RX.open[s.claim_id] = true; renderPage(true); setTimeout(() => { const el = document.getElementById('cl-' + s.claim_id.replace(/[^\w]/g, '_')); if (el) el.scrollIntoView({ block: 'center' }); }, 30); } }, s.name) : h('b', null, s.name));
  return h('div', { class: 'rx-sup' + (suggested ? ' sug' : '') },
    h('div', { class: 'rx-sup-h' },
      h('span', { class: 'rx-rel' }, suggested ? 'Suggested' : rel), name,
      s.detail ? h('span', { class: 'muted' }, ' · ' + trunc(s.detail, 90)) : null, h('span', { class: 'grow' }), rxWhere(s.loc),
      suggested ? [h('button', { class: 'btn sm primary', disabled: READONLY, onclick: async () => { const r = await rxPost('/api/claims/link', { id: c.id, target: key, on: true }); if (r) { RX.claims = r; rxTrack('claim_linked'); renderPage(true); renderLeft(); } } }, 'Yes, this backs it'),
        h('button', { class: 'btn sm', disabled: READONLY, onclick: async () => { const r = await rxPost('/api/claims/link', { id: c.id, target: key, on: false }); if (r) { RX.claims = r; renderPage(true); } } }, 'No')]
        : (s.how === 'manual' || s.node_id) && !READONLY ? h('button', { class: 'linkbtn small', title: 'Remove this link', onclick: async () => { const r = await rxPost('/api/claims/link', { id: c.id, target: key, on: false }); if (r) { RX.claims = r; renderPage(true); renderLeft(); } } }, 'Unlink') : null),
    rxChain(s),
    !suggested && s.relation === 'evidence' && s.traced === false ? h('div', { class: 'rx-warn' }, 'Not traced to a result file or script. If the numbers were typed by hand, say where they come from (a “% source: code:results/file.csv” comment above the table).') : null,
    s.stale ? h('div', { class: 'rx-warn' }, '↻ Recheck: ' + s.stale) : null);
}
function rxLinkDialog(c) {
  const input = h('input', { type: 'search', placeholder: 'Table, figure, section or file name', 'aria-label': 'Search' });
  const list = h('div', { class: 'rx-pick' });
  const have = new Set(c.support.map(s => s.node_id));
  const cand = S.graph.nodes.filter(n => ['figure', 'table', 'section', 'result', 'code', 'run', 'data'].includes(n.kind) && !have.has(n.id));
  let m;
  const paint = () => {
    const q = input.value.toLowerCase().split(/\s+/).filter(Boolean);
    const rows = cand.filter(n => q.every(w => (n.name + ' ' + (n.detail || '') + ' ' + pathOf(n)).toLowerCase().includes(w))).slice(0, 30);
    clear(list).append(rows.length ? rows.map(n => h('button', { class: 'rx-pickrow', onclick: async () => { const r = await rxPost('/api/claims/link', { id: c.id, target: n.id, on: true }); if (r) { RX.claims = r; rxTrack('claim_linked'); } m(); renderPage(true); renderLeft(); } },
      h('b', null, n.name), ' ', h('span', { class: 'muted' }, trunc(n.detail || pathOf(n), 80)))) : h('div', { class: 'muted' }, 'Nothing matches.'));
  };
  input.addEventListener('input', paint);
  m = modal('What backs “' + c.label + '”?', h('div', null, input, list), [{ label: 'Cancel' }]);
  paint(); setTimeout(() => input.focus(), 30);
}
function rxEditDialog(c) {
  const ta = h('textarea', { rows: '4', 'aria-label': 'Claim text', class: 'rx-ta' }); ta.value = c.text;
  const note = h('textarea', { rows: '2', 'aria-label': 'Note', class: 'rx-ta', placeholder: 'Note to yourself (optional): a caveat, a condition, what would falsify it' }); note.value = c.note || '';
  modal('Edit ' + c.label, h('div', null, h('p', { class: 'muted' }, 'Say the claim in your own words. The paper is not changed.'), ta, note), [{ label: 'Cancel' },
    { label: 'Save', primary: true, fn: async () => { const r = await rxPost('/api/claims', { id: c.id, text: ta.value, note: note.value }); if (r) { RX.claims = r; renderPage(true); } } }]);
}
function rxClaimCard(c) {
  const open = RX.open[c.id] != null ? RX.open[c.id] : (c.status !== 'supported' || !!c.recheck || c.state === 'proposed');
  const real = c.support.filter(s => s.how !== 'suggested'), sug = c.support.filter(s => s.how === 'suggested');
  const setState = async st => { const r = await rxPost('/api/claims', { id: c.id, state: st }); if (r) { RX.claims = r; if (st !== 'proposed') rxTrack(st === 'confirmed' ? 'claim_confirmed' : 'claim_rejected'); renderPage(true); renderLeft(); } };
  return h('article', { class: 'card rx-claim st-' + c.status + (c.state === 'rejected' ? ' rejected' : ''), id: 'cl-' + c.id.replace(/[^\w]/g, '_') },
    h('button', { class: 'rx-claim-h', 'aria-expanded': String(open), onclick: () => { RX.open[c.id] = !open; renderPage(true); } },
      h('span', { class: 'caret' }, open ? '▾' : '▸'), h('span', { class: 'rx-label' }, c.label), rxChip(c.status),
      c.recheck ? plainChip('↻', 'Recheck', 'look') : null, c.state === 'proposed' ? plainChip('✎', 'Draft', 'proposed') : null, c.manual ? plainChip('+', 'Yours', 'plain') : null,
      h('span', { class: 'grow' }), h('span', { class: 'muted small' }, RX_KIND[c.kind] || '')),
    h('div', { class: 'rx-text serif' }, c.text),
    open ? h('div', { class: 'rx-body' },
      c.loc ? h('div', { class: 'muted small' }, 'In the paper: ', rxWhere(c.loc)) : null,
      c.recheck ? h('div', { class: 'rx-warn' }, '↻ Something behind this claim changed: ' + c.recheck) : null,
      c.issues.map(i => h('div', { class: 'rx-warn' }, '! ' + i)),
      real.length ? real.map(s => rxSupportRow(c, s)) : h('div', { class: 'rx-none' }, c.formal ? 'No proof found. If the proof is elsewhere, write “Proof of Theorem~\\ref{…}” at its start so Lemmata can connect it.' : 'Nothing backs this claim yet. Link the table, figure, section or result file that shows it.'),
      sug.map(s => rxSupportRow(c, s)),
      c.note ? h('div', { class: 'rx-note' }, h('b', null, 'Your note: '), c.note) : null,
      READONLY ? null : h('div', { class: 'btnrow' },
        c.state !== 'confirmed' ? h('button', { class: 'btn primary', onclick: () => setState('confirmed') }, 'Yes, this is a claim of the paper') : h('button', { class: 'btn', onclick: () => setState('proposed') }, 'Back to draft'),
        h('button', { class: 'btn', onclick: () => rxLinkDialog(c) }, 'Link evidence…'),
        h('button', { class: 'btn', onclick: () => rxEditDialog(c) }, 'Edit wording / note'),
        h('span', { class: 'grow' }),
        c.manual ? h('button', { class: 'linkbtn', onclick: async () => { const r = await rxPost('/api/claims/remove', { id: c.id }); if (r) { RX.claims = r; renderPage(true); renderLeft(); } } }, 'Delete')
          : c.state !== 'rejected' ? h('button', { class: 'linkbtn', onclick: () => setState('rejected') }, 'Not a claim') : h('button', { class: 'linkbtn', onclick: () => setState('proposed') }, 'Bring back'))) : null);
}
function rxAddClaimBox(root) {
  if (READONLY) return;
  const ta = h('textarea', { rows: '2', class: 'rx-ta', placeholder: 'One sentence', 'aria-label': 'New claim' });
  root.append(h('details', { class: 'details' }, h('summary', null, '+ Add a claim'), ta, h('div', { class: 'btnrow' }, h('button', { class: 'btn', onclick: async () => { if (!ta.value.trim()) return; const r = await rxPost('/api/claims/add', { text: ta.value }); if (r) { RX.claims = r; renderPage(true); renderLeft(); } } }, 'Add'))));
}
function pageClaims() {
  const nr = rxNotReady('Claims'); if (nr) return nr;
  S.outline = [];
  const d = RX.claims, cc = d.counts;
  const seg = h('div', { class: 'rx-seg', role: 'group', 'aria-label': 'View' }, [['tree', 'Tree'], ['list', 'List']].map(([k, l]) => h('button', { 'aria-pressed': String(RX.view === k), onclick: () => { RX.view = k; renderPage(true); } }, l)));
  const root = doc(h('div', { class: 'row' }, h('h1', { class: 'ptitle grow' }, 'Claims'), seg,
    h('button', { class: 'btn', title: 'Watch the tree grow', onclick: () => { RX.t = 0; openTab('timeline'); setTimeout(rxPlay, 300); } }, '▶ Growth'),
    READONLY ? null : h('a', { class: 'btn', href: apiUrl('/api/claims.md'), title: 'Download claims.md to commit to your repository' }, '↓ .md')));
  if (!d.has_paper) root.append(emptyState('◆', 'No paper connected', 'Connect a paper repository or upload the LaTeX source as a zip from the project menu (⋯).'));
  if (RX.view === 'tree' && RX.tree) {
    root.append(rxTree({ scrub: false }));
    const c = RX.sel && d.claims.find(x => x.id === RX.sel);
    if (c) { RX.open[c.id] = true; root.append(rxClaimCard(c)); }
    else if (RX.sel === 'core' && d.core) root.append(rxCoreCard(d.core));
    else if (RX.sel && IX.node && IX.node.get(RX.sel)) root.append(rxEvidenceCard(RX.sel));
    rxAddClaimBox(root);
    return root;
  }
  if (d.core) root.append(rxCoreCard(d.core));
  const live = d.claims.filter(c => c.state !== 'rejected'), gone = d.claims.filter(c => c.state === 'rejected');
  const F = RX.filter;
  const pass = c => F === 'all' || (F === 'draft' ? c.state === 'proposed' : F === 'recheck' ? !!c.recheck : c.status === F);
  const chips = [['all', 'All', live.length], ['unsupported', 'Not supported', cc.unsupported], ['partial', 'Partly', cc.partial], ['supported', 'Supported', cc.supported], ['recheck', 'Recheck', cc.recheck], ['draft', 'Drafts to confirm', cc.proposed]];
  root.append(h('div', { class: 'fchips' }, chips.map(([k, l, n]) => h('button', { class: 'fchip', 'aria-pressed': String(F === k), onclick: () => { RX.filter = k; renderPage(true); } }, l + ' ', h('span', { class: 'n' }, n)))));
  const groups = [['What the paper contributes', c => c.kind === 'contribution' || c.kind === 'claim'], ['Questions it asks', c => c.kind === 'question'], ['Formal statements', c => !!c.formal]];
  for (const [title, fn] of groups) {
    const list = live.filter(fn).filter(pass);
    if (!live.filter(fn).length) continue;
    root.append(sec(title, title.split(' ')[0].toLowerCase(), list.length ? list.map(rxClaimCard) : h('div', { class: 'muted' }, 'None with this filter.')));
  }
  rxAddClaimBox(root);
  if (gone.length) root.append(h('details', { class: 'details' }, h('summary', null, 'Not claims (' + gone.length + ')'), gone.map(rxClaimCard)));
  return root;
}
function rxCoreCard(core) {
  const cc = RX.claims.counts;
  const full = h('details', { class: 'details' }, h('summary', null, 'Abstract'), h('div', { class: 'serif' }, core.abstract || ''));
  return h('section', { class: 'rx-core st-' + core.status },
    h('div', { class: 'rx-core-h' }, h('span', { class: 'rx-label' }, 'Core message'), rxChip(core.status), core.recheck ? plainChip('↻', 'Recheck', 'look') : null, h('span', { class: 'grow' }),
      READONLY ? null : h('button', { class: 'linkbtn small', onclick: () => rxEditDialog(core) }, 'Reword'), rxWhere(core.loc)),
    h('div', { class: 'rx-core-t serif' }, core.text),
    h('div', { class: 'rx-meter', role: 'img', 'aria-label': cc.supported + ' supported, ' + cc.partial + ' partly, ' + cc.unsupported + ' not supported' },
      cc.total ? [['supported', cc.supported], ['partial', cc.partial], ['unsupported', cc.unsupported]].filter(x => x[1]).map(([k, n]) => h('span', { class: 'seg ' + k, style: 'flex:' + n }, String(n))) : null),
    core.abstract ? full : null);
}

/* ---------- Research tree: crown = what the paper says, roots = what backs it ---------- */
const SVGNS = 'http://www.w3.org/2000/svg';
function sv(tag, attrs, ...kids) {
  const el = document.createElementNS(SVGNS, tag);
  for (const k in (attrs || {})) { const v = attrs[k]; if (v == null || v === false) continue; if (k === 'onclick') el.addEventListener('click', v); else el.setAttribute(k, v); }
  const add = c => { if (c == null || c === false) return; if (Array.isArray(c)) c.forEach(add); else el.append(c.nodeType ? c : document.createTextNode(String(c))); };
  kids.forEach(add); return el;
}
const RX_GLYPH = { proof: '∎', assumption: '◇', definition: '◇', condition: '◇', hypothesis: '◇', table: '▦', figure: '◔', section: '§', equation: '∑', item: '•', result: '▤', asset: '◔', data: '⛁', code: '{}', config: '⚙', run: '▶', missing: '?' };
const RX_KINDWORD = { proof: 'Proof', assumption: 'Assumption', definition: 'Definition', table: 'Table', figure: 'Figure', section: 'Section', result: 'Result file', asset: 'Figure file', data: 'Data', code: 'Script', config: 'Settings', run: 'Run', missing: 'Nothing backs this yet' };
function rxTreeLayout(T) {
  const N = new Map(T.nodes.map(n => [n.id, n]));
  const claims = T.nodes.filter(n => n.layer === 'claim'), roots = T.nodes.filter(n => n.layer === 'root');
  const kids = new Map(); claims.forEach(c => { const p = c.parent || 'core'; if (!kids.has(p)) kids.set(p, []); kids.get(p).push(c.id); });
  const CW = 96, TOP = 132, DY = 86, P = {};
  let slot = 0, maxDepth = 1;
  const place = (id, depth) => {   // tidy tree: leaves take the next slot, a parent sits over the middle of its children
    const ch = kids.get(id) || []; maxDepth = Math.max(maxDepth, depth);
    if (!ch.length) { P[id] = { x: slot++ * CW, y: TOP + depth * DY }; return; }
    ch.forEach(c => place(c, depth + 1));
    P[id] = { x: (P[ch[0]].x + P[ch[ch.length - 1]].x) / 2, y: TOP + depth * DY };
  };
  place('core', 0);
  claims.forEach(c => { if (!P[c.id]) P[c.id] = { x: slot++ * CW, y: TOP + DY }; });
  const ground = TOP + maxDepth * DY + 62;
  const up = new Map(); T.edges.forEach(e => { if (N.has(e.to) && N.get(e.to).layer === 'root') { if (!up.has(e.to)) up.set(e.to, []); up.get(e.to).push(e.from); } });
  const pics = T.nodes.some(n => n.img), GAP = pics ? 92 : 78;
  for (let b = 1; b <= 4; b++) {   // roots in bands by kind, each under the middle of what it supports
    const band = roots.filter(r => r.band === b); if (!band.length) continue;
    band.forEach(r => { const ps = (up.get(r.id) || []).filter(p => P[p]); r._want = ps.length ? ps.reduce((a, p) => a + P[p].x, 0) / ps.length : 0; });
    band.sort((a, c) => a._want - c._want || (a.id < c.id ? -1 : 1));
    let prev = -Infinity; band.forEach(r => { const x = Math.max(r._want, prev + GAP); P[r.id] = { x, y: ground + 58 + (b - 1) * (pics ? 88 : 74) }; prev = x; });
    const shift = band.reduce((a, r) => a + (r._want - P[r.id].x), 0) / band.length; band.forEach(r => { P[r.id].x += shift; });
  }
  let minX = Infinity, maxX = -Infinity, maxY = 0;
  for (const id in P) { minX = Math.min(minX, P[id].x); maxX = Math.max(maxX, P[id].x); maxY = Math.max(maxY, P[id].y); }
  const coreW = 620, pad = 64;
  const lo = Math.min(minX, P.core.x - coreW / 2), hi = Math.max(maxX, P.core.x + coreW / 2);
  for (const id in P) P[id].x += pad - lo;
  return { P, N, W: hi - lo + pad * 2, H: maxY + 58, ground, coreW };
}
function rxTree(opts) {
  const T = RX.tree, L = rxTreeLayout(T), { P, N } = L;
  const wrap = h('div', { class: 'rx-treewrap' });
  const svg = sv('svg', { viewBox: '0 0 ' + L.W + ' ' + L.H, class: 'rx-tree', role: 'img', 'aria-label': 'Research tree: the core message at the top, the claims under it, and the evidence behind them as roots' });
  svg.style.minWidth = Math.round(L.W * 0.66) + 'px';
  const nRoots = new Map(); T.edges.forEach(e => { if (e.kind === 'support' && e.how !== 'suggested') nRoots.set(e.from, (nRoots.get(e.from) || 0) + 1); });
  // soil, ground line, crown glow
  svg.append(sv('rect', { x: 0, y: L.ground, width: L.W, height: L.H - L.ground, class: 'soil' }), sv('line', { x1: 0, x2: L.W, y1: L.ground, y2: L.ground, class: 'ground' }),
    sv('text', { x: 10, y: L.ground - 8, class: 'bandlab' }, 'Paper'), sv('text', { x: 10, y: L.ground + 16, class: 'bandlab' }, 'Evidence'));
  const gE = sv('g'), gN = sv('g'); svg.append(gE, gN);
  const els = new Map(), edgeEls = [];
  const curve = (a, b, viaGround) => {
    if (viaGround) { const gx = a.x + (b.x - a.x) * 0.25; return 'M' + a.x + ',' + a.y + ' C' + a.x + ',' + (L.ground - 4) + ' ' + gx + ',' + (L.ground - 14) + ' ' + gx + ',' + L.ground + ' S' + b.x + ',' + (b.y - 34) + ' ' + b.x + ',' + b.y; }
    const my = (a.y + b.y) / 2; return 'M' + a.x + ',' + a.y + ' C' + a.x + ',' + my + ' ' + b.x + ',' + my + ' ' + b.x + ',' + b.y;
  };
  for (const e of T.edges) {
    const a = P[e.from], b = P[e.to]; if (!a || !b) continue;
    const to = N.get(e.to), fromRoot = N.get(e.from) && N.get(e.from).layer === 'root';
    let cls = 'e e-' + e.kind + (e.how === 'suggested' ? ' sug' : '') + (e.stale ? ' stale' : ''), w = 1.6, d;
    if (e.kind === 'branch') { cls += ' st-' + to.status; w = 3 + Math.min(6, (nRoots.get(e.to) || 0) * 1.5 + (kidsCount(T, e.to)) * 1.5); d = curve(a, b); }
    else if (e.kind === 'uses') { const mx = (a.x + b.x) / 2, my = Math.min(a.y, b.y) - 30; d = 'M' + a.x + ',' + a.y + ' Q' + mx + ',' + my + ' ' + b.x + ',' + b.y; }
    else d = curve(a, b, !fromRoot);
    const p = sv('path', { d, class: cls, 'stroke-width': w, fill: 'none' }); gE.append(p); edgeEls.push({ e, el: p });
  }
  // nodes
  const half = r => 'M0,' + (-r) + ' A' + r + ',' + r + ' 0 0,0 0,' + r + ' Z';
  for (const n of T.nodes) {
    const p = P[n.id]; if (!p) continue;
    const g = sv('g', { class: 'n n-' + n.layer + (n.status ? ' st-' + n.status : '') + (n.state === 'proposed' ? ' draft' : '') + (RX.sel === n.id ? ' sel' : ''), transform: 'translate(' + p.x + ',' + p.y + ')', tabindex: '0' });
    const inner = sv('g', { class: 'sprout' }); g.append(inner);
    if (n.layer === 'core') {
      const fo = sv('foreignObject', { x: -L.coreW / 2, y: -118, width: L.coreW, height: 96 });
      fo.append(h('div', { class: 'rx-coretext serif', title: READONLY ? '' : 'Click to reword' }, n.title || 'No core message found. Click to write it.'));
      inner.append(fo, sv('circle', { r: 13, class: 'dot' }), n.status === 'partial' ? sv('path', { d: half(13), class: 'halfdot' }) : null, n.recheck ? sv('circle', { r: 18, class: 'ring' }) : null);
    } else if (n.layer === 'claim') {
      const r = n.depth > 1 ? 11 : 14;
      inner.append(sv('circle', { r: r + 9, class: 'hit' }), n.recheck ? sv('circle', { r: r + 5, class: 'ring' }) : null, n.formal ? sv('rect', { x: -r, y: -r, width: 2 * r, height: 2 * r, rx: 3, class: 'dot' }) : sv('circle', { r, class: 'dot' }),
        n.status === 'partial' ? (n.formal ? sv('rect', { x: -r, y: -r, width: r, height: 2 * r, class: 'halfdot' }) : sv('path', { d: half(r), class: 'halfdot' })) : null,
        sv('text', { x: r + 7, y: 4, class: 'lab side' }, n.short + (n.state === 'proposed' ? ' ✎' : '')), n.recheck ? sv('text', { x: -r - 14, y: -r + 4, class: 'badge' }, '↻') : null,
        sv('title', null, n.label + ' — ' + RX_STATUS[n.status][1] + (n.recheck ? ', recheck' : '') + (n.state === 'proposed' ? ' (draft)' : '') + '\n' + n.title));
    } else {
      const miss = n.kind === 'missing', pic = n.img && !READONLY;
      if (pic) {   // the figure itself
        const im = sv('image', { x: -32, y: -23, width: 64, height: 46, href: apiUrl('/api/thumb?node=' + encodeURIComponent(n.node_id)), preserveAspectRatio: 'xMidYMid meet' });
        im.addEventListener('error', () => { im.replaceWith(sv('text', { y: 4.5, class: 'glyph' }, RX_GLYPH[n.kind])); });
        inner.append(sv('rect', { x: -34, y: -25, width: 68, height: 50, rx: 3, class: 'box pic' + (n.traced === false ? ' untraced' : '') }), im, sv('text', { y: 37, class: 'lab' }, n.short));
      } else inner.append(sv('rect', { x: -15, y: -12, width: 30, height: 24, rx: n.band === 1 ? 12 : 4, class: 'box' + (miss ? ' miss' : '') + (n.traced === false && !miss ? ' untraced' : '') }),
        sv('text', { y: 4.5, class: 'glyph' }, RX_GLYPH[n.kind] || '•'), sv('text', { y: 26, class: 'lab' + (n.band > 1 ? ' hov' : '') }, miss ? '' : n.short));
      inner.append(n.shared > 1 ? sv('text', { x: pic ? 38 : 19, y: pic ? -18 : -8, class: 'badge' }, '×' + n.shared) : null,
        n.caveat ? sv('g', { transform: 'translate(' + (pic ? -34 : -15) + ',' + (pic ? -25 : -12) + ')' }, sv('circle', { r: 7, class: 'cav' }), sv('text', { y: 3.5, class: 'cavt' }, '!')) : null,
        sv('title', null, (RX_KINDWORD[n.kind] || n.kind) + (miss ? '' : ': ' + n.title) + (n.traced === false && !miss ? '\nNot traced to a result file or script' : '')));
    }
    const pick = () => {
      if (n.layer === 'root') { if (n.node_id) { RX.sel = RX.sel === n.id ? null : n.id; if (!opts.scrub) renderPage(true); else { RX.view = 'tree'; openTab('claims'); } } else if (n.loc) rxShowLines('paper', n.loc); else if (n.kind === 'missing') { const cid = n.id.slice(8); RX.sel = cid; const c = RX.claims.claims.find(x => x.id === cid); if (c && !READONLY) rxLinkDialog(c); renderPage(true); } return; }
      RX.sel = RX.sel === n.id ? null : n.id; if (!opts.scrub) renderPage(true); else { RX.view = 'tree'; openTab('claims'); }
    };
    g.addEventListener('click', pick); g.addEventListener('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); pick(); } });
    g.addEventListener('mouseenter', () => focus(n.id)); g.addEventListener('mouseleave', () => focus(null)); g.addEventListener('focus', () => focus(n.id)); g.addEventListener('blur', () => focus(null));
    gN.append(g); els.set(n.id, g);
  }
  // hover: light up everything a node rests on and everything that rests on it
  const dn = new Map(), upm = new Map(); T.edges.forEach(e => { (dn.get(e.from) || dn.set(e.from, []).get(e.from)).push(e.to); (upm.get(e.to) || upm.set(e.to, []).get(e.to)).push(e.from); });
  const reach = (id, m) => { const seen = new Set([id]), q = [id]; while (q.length) for (const x of (m.get(q.pop()) || [])) if (!seen.has(x)) { seen.add(x); q.push(x); } return seen; };
  function focus(id) {
    svg.classList.toggle('focus', !!id);
    const on = id ? new Set([...reach(id, dn), ...reach(id, upm)]) : null;
    els.forEach((el, k) => el.classList.toggle('on', !!on && on.has(k)));
    edgeEls.forEach(({ e, el }) => el.classList.toggle('on', !!on && on.has(e.from) && on.has(e.to)));
  }
  wrap.append(svg);
  // time: positions never move; pieces only appear
  const t0 = T.span ? Date.parse(T.span.start) : 0, t1 = T.span ? Date.parse(T.span.end) : 0;
  const born = new Map(T.nodes.map(n => [n.id, n.born ? Date.parse(n.born) : null]));
  const firstUse = new Map(); T.edges.forEach(e => { const b = born.get(e.from); if (b != null && born.get(e.to) == null && N.get(e.to).layer === 'root') firstUse.set(e.to, Math.min(firstUse.get(e.to) || Infinity, b)); });
  const bornOf = id => born.get(id) != null ? born.get(id) : (firstUse.get(id) != null ? firstUse.get(id) : null);
  function setTime(frac) {
    const now = t0 + (t1 - t0) * frac + 1; let shown = 0;
    els.forEach((el, id) => { const b = bornOf(id); const hide = frac < 1 && b != null && b > now; el.classList.toggle('unborn', hide); if (!hide) shown++; });
    edgeEls.forEach(({ e, el }) => { const hide = frac < 1 && [e.from, e.to].some(id => { const b = bornOf(id); return b != null && b > now; }); el.classList.toggle('unborn', hide); });
    return { now, shown };
  }
  if (opts.scrub && T.span && t1 > t0) wrap.append(rxScrubber(T, t0, t1, setTime));
  else setTime(1);
  wrap.append(rxLegend(T));
  return wrap;
}
/* One figure, table or file: the picture, what it is for, whether it is connected to the repository, and your caveat. */
function rxEvidenceCard(nodeId, onChange) {
  const box = h('article', { class: 'card rx-ev' }, h('div', { class: 'muted' }, '…'));
  apiGet('/api/evidence?node=' + encodeURIComponent(nodeId)).then(d => paint(d)).catch(e => { clear(box).append(h('div', { class: 'muted' }, e.message)); });
  function paint(d) {
    const n = d.node, gh = x => x.github ? h('a', { class: 'ghl', href: x.github, target: '_blank', rel: 'noopener noreferrer', title: 'Open on GitHub at the commit Lemmata read' }, '↗ GitHub') : null;
    const row = x => h('div', { class: 'rx-ev-row' }, h('span', { class: 'lg-g' }, RX_GLYPH[x.kind] || '•'), rxNodeBtn(x.node_id, x.name), gh(x),
      x.last ? h('span', { class: 'muted small mono' }, ' ' + x.last.short + ' · ' + dmon(x.last.time)) : null);
    let pic = null;
    if (d.image && !READONLY) { const src = apiUrl('/api/thumb?node=' + encodeURIComponent(nodeId)); pic = h('a', { href: src, target: '_blank', rel: 'noopener noreferrer', class: 'rx-ev-pic' }, h('img', { src, alt: n.name, onerror: ev => { ev.target.closest('a').replaceWith(h('div', { class: 'rx-ev-nopic muted' }, 'No preview')); } })); }
    else if (d.table) pic = h('div', { class: 'rx-ev-tablewrap' }, h('table', { class: 'tbl rx-ev-table' }, h('tbody', null, d.table.map((r, i) => h('tr', null, r.map(c => h(i ? 'td' : 'th', null, c)))))));
    const cav = h('textarea', { rows: '2', class: 'rx-ta', 'aria-label': 'Caveat', placeholder: 'Caveat: what a reader must keep in mind' }); cav.value = d.note.caveat || '';
    const pur = h('textarea', { rows: '2', class: 'rx-ta', 'aria-label': 'Meant to show', placeholder: 'Meant to show: the one thing this is in the paper for' }); pur.value = d.note.purpose || '';
    const linked = d.connected;
    clear(box).append(
      h('div', { class: 'rx-ev-h' }, h('span', { class: 'rx-label' }, n.name), linked ? plainChip('✓', 'Connected', 'fine') : plainChip('✕', 'Not connected', 'fix'),
        d.stale ? plainChip('↻', 'Out of date', 'look') : null, d.note.caveat ? plainChip('!', 'Caveat', 'look') : null, h('span', { class: 'grow' }),
        d.self ? gh(d.self) : null, rxWhere(n.loc, n.repo), h('button', { class: 'linkbtn small', onclick: () => openNode(nodeId) }, 'Open')),
      h('div', { class: 'rx-ev-b' }, pic, h('div', { class: 'rx-ev-r' },
        d.caption ? h('div', { class: 'serif rx-ev-cap' }, d.caption) : null,
        d.backs.length ? h('div', { class: 'rx-ev-backs' }, d.backs.map(b => h('button', { class: 'chip-btn st-' + b.status, title: b.text, onclick: () => { RX.sel = b.id; RX.view = 'tree'; openTab('claims'); renderPage(true); } }, '◆ ' + b.label))) : h('div', { class: 'muted small' }, 'Backs no claim yet.'),
        d.chain.length ? h('div', { class: 'rx-ev-chain' }, d.chain.map(row))
          : !linked ? h('div', { class: 'rx-warn' }, d.typed_by_hand || n.kind === 'table' ? 'No result file found behind it. Put “% source: code:results/file.csv” above it in the LaTeX.' : 'No script or result file found that makes it.') : null,
        d.stale ? h('div', { class: 'rx-warn' }, '↻ ' + d.stale.newer.map(x => x.name).join(', ') + ' changed after ' + d.stale.file + ' was written.') : null,
        READONLY ? [d.note.purpose ? h('div', { class: 'rx-note' }, h('b', null, 'Meant to show: '), d.note.purpose) : null, d.note.caveat ? h('div', { class: 'rx-note' }, h('b', null, 'Caveat: '), d.note.caveat) : null]
          : [pur, cav, h('div', { class: 'btnrow' }, h('button', { class: 'btn', onclick: async () => {
            const r = await rxPost('/api/note', { node: nodeId, caveat: cav.value, purpose: pur.value }, 'Saved.');
            if (r) { try { RX.tree = await apiGet('/api/tree'); } catch (e) { /* keep */ } if (onChange) onChange(); else renderPage(true); }
          } }, 'Save'))])));
  }
  return box;
}
function kidsCount(T, id) { return T.nodes.filter(n => n.parent === id).length; }
function rxLegend(T) {
  const has = f => T.nodes.some(f), hasE = f => T.edges.some(f);
  const dot = cls => { const s = sv('svg', { viewBox: '-10 -10 20 20', width: 14, height: 14, class: 'rx-tree mini' }); s.append(sv('g', { class: 'n n-claim ' + cls }, sv('circle', { r: 7, class: 'dot' }), cls.includes('partial') ? sv('path', { d: 'M0,-7 A7,7 0 0,0 0,7 Z', class: 'halfdot' }) : null)); return s; };
  const items = [
    has(n => n.status === 'supported') ? [dot('st-supported'), 'Supported'] : null, has(n => n.status === 'partial') ? [dot('st-partial'), 'Partly'] : null,
    has(n => n.status === 'unsupported') ? [dot('st-unsupported'), 'Not supported'] : null, has(n => n.recheck) ? [h('span', { class: 'lg-ring' }, '↻'), 'Recheck'] : null,
    has(n => n.formal) ? [h('span', { class: 'lg-g' }, '□'), 'Theorem / lemma'] : null, hasE(e => e.how === 'suggested') ? [h('span', { class: 'lg-g' }, '┄'), 'Suggested'] : null,
    has(n => n.kind === 'missing') ? [h('span', { class: 'lg-g' }, '?'), 'Missing'] : null, has(n => n.state === 'proposed' && n.layer === 'claim') ? [h('span', { class: 'lg-g' }, '✎'), 'Draft'] : null,
  ].filter(Boolean);
  const kinds = [...new Set(T.nodes.filter(n => n.layer === 'root' && n.kind !== 'missing').map(n => n.kind))];
  return h('div', { class: 'rx-legend' }, items.map(([g, l]) => h('span', null, g, ' ' + l)), kinds.map(k => h('span', null, h('span', { class: 'lg-g' }, RX_GLYPH[k] || '•'), ' ' + (RX_KINDWORD[k] || k))));
}
function rxScrubber(T, t0, t1, setTime) {
  const range = h('input', { type: 'range', min: '0', max: '1000', value: String(Math.round(RX.t * 1000)), 'aria-label': 'Time', class: 'rx-range' });
  const date = h('span', { class: 'rx-date mono' }), cap = h('span', { class: 'rx-cap' }), play = h('button', { class: 'btn rx-play', 'aria-label': 'Play' }, '▶');
  const strip = sv('svg', { viewBox: '0 0 1000 14', preserveAspectRatio: 'none', class: 'rx-marks' });
  const marks = (T.marks || []).map(m => ({ m, f: (Date.parse(m.time) - t0) / (t1 - t0) })).filter(x => x.f >= 0 && x.f <= 1);
  marks.forEach(({ m, f }) => { const l = sv('line', { x1: f * 1000, x2: f * 1000, y1: m.decision ? 0 : 6, y2: 14, class: m.decision ? 'dec' : '' }, sv('title', null, dmon(m.time) + ' · ' + m.title + ': ' + m.summary)); l.addEventListener('click', () => apply(f)); strip.append(l); });
  function apply(f) {
    RX.t = Math.max(0, Math.min(1, f)); range.value = String(Math.round(RX.t * 1000));
    const r = setTime(RX.t); const d = new Date(r.now);
    date.textContent = d.getDate() + ' ' + MON[d.getMonth()] + ' ' + d.getFullYear();
    const last = marks.filter(x => x.f <= RX.t + 1e-6).pop();
    clear(cap).append(last ? [last.m.decision ? h('b', null, '◆ ') : null, last.m.title, h('span', { class: 'muted' }, ' · ' + trunc(last.m.summary, 70))] : '');
  }
  range.addEventListener('input', () => { rxStop(); apply(+range.value / 1000); });
  rxPlay = () => {
    rxStop(); if (RX.t >= 1) RX.t = 0; play.textContent = '❚❚';
    const stops = [...new Set(marks.map(x => x.f).concat([1]))].filter(f => f > RX.t + 1e-6).sort((a, b) => a - b);   // step from event to event
    let i = 0; apply(RX.t);
    RX.playing = setInterval(() => { if (!document.body.contains(range) || i >= stops.length) { rxStop(); play.textContent = '▶'; return; } apply(stops[i++]); }, 900);
  };
  play.addEventListener('click', () => { if (RX.playing) { rxStop(); play.textContent = '▶'; } else rxPlay(); });
  const step = dir => { rxStop(); const fs = marks.map(x => x.f).concat([0, 1]).sort((a, b) => a - b); const nx = dir > 0 ? fs.find(f => f > RX.t + 1e-6) : fs.filter(f => f < RX.t - 1e-6).pop(); if (nx != null) apply(nx); };
  const bar = h('div', { class: 'rx-scrub' }, play, h('button', { class: 'btn', 'aria-label': 'Previous step', onclick: () => step(-1) }, '‹'), h('button', { class: 'btn', 'aria-label': 'Next step', onclick: () => step(1) }, '›'),
    h('div', { class: 'rx-track' }, range, strip), date);
  setTimeout(() => apply(RX.t), 0);
  return h('div', null, bar, h('div', { class: 'rx-capline' }, cap));
}
let rxPlay = () => { };
function rxStop() { if (RX.playing) { clearInterval(RX.playing); RX.playing = null; } }

/* ---------- Timeline ---------- */
function pageTimeline() {
  const nr = rxNotReady('Timeline'); if (nr) return nr;
  S.outline = [];
  const tl = RX.timeline, F = RX.tlFilter;
  const root = doc(h('h1', { class: 'ptitle' }, 'Timeline'));
  if (RX.tree && RX.tree.nodes.length) {
    root.append(rxTree({ scrub: true }));
    if (RX.tree.undated) root.append(h('div', { class: 'muted small' }, RX.tree.dated ? 'Pieces without a date in git are shown from the start.' : 'No dates found in git for this tree.'));
  }
  const host = root; const stepsBox = h('details', { class: 'details' }, h('summary', null, 'Steps (' + tl.steps.length + ')'));
  root.append(stepsBox);
  const label = id => { const c = RX.claims && (RX.claims.claims.find(x => x.id === id) || (RX.claims.core && RX.claims.core.id === id && RX.claims.core)); return c ? c.label : id; };
  const steps = tl.steps.filter(s => F === 'all' || (F === 'decisions' ? s.decision : F === 'claims' ? s.affects.length : s.role === F)).slice().reverse();
  stepsBox.open = !!RX.stepsOpen; stepsBox.addEventListener('toggle', () => { RX.stepsOpen = stepsBox.open; });
  stepsBox.append(h('div', { class: 'fchips' }, [['all', 'All', tl.steps.length], ['decisions', 'Decisions', tl.decisions], ['claims', 'Touching a claim', tl.steps.filter(s => s.affects.length).length], ['code', 'Code', null], ['paper', 'Paper', null]]
    .map(([k, l, n]) => h('button', { class: 'fchip', 'aria-pressed': String(F === k), onclick: () => { RX.tlFilter = k; renderPage(true); } }, l, n != null ? [' ', h('span', { class: 'n' }, n)] : null))));
  if (!steps.length) return stepsBox.append(h('div', { class: 'muted' }, tl.steps.length ? 'Nothing with this filter.' : 'No commits yet.')), root;
  let month = null;
  for (const s of steps) {
    const mk = s.day.slice(0, 7);
    if (mk !== month) { month = mk; stepsBox.append(h('div', { class: 'dayhead' }, MON[+mk.slice(5, 7) - 1] + ' ' + mk.slice(0, 4))); }
    const open = !!RX.open['tl:' + s.id];
    stepsBox.append(h('article', { class: 'rx-step' + (s.decision ? ' decision' : '') },
      h('div', { class: 'rx-step-d mono' }, dmon(s.day)),
      h('div', { class: 'rx-step-dot', 'aria-hidden': 'true' }, s.decision ? '◆' : '·'),
      h('div', { class: 'rx-step-b' },
        h('button', { class: 'rx-step-h', 'aria-expanded': String(open), onclick: () => { RX.open['tl:' + s.id] = !open; renderPage(true); } },
          h('b', null, s.title), s.decision ? plainChip('◆', 'Decision', 'proposed') : null, h('span', { class: 'muted' }, ' ' + (s.role === 'paper' ? 'paper' : 'code') + ' · ' + plural(s.commits.length, 'commit')),
          s.after_checkpoint ? h('span', { class: 'tag' }, 'Since you last looked') : null),
        h('div', { class: 'rx-step-s' }, s.summary),
        s.affects.length ? h('div', { class: 'small' }, h('span', { class: 'muted' }, 'Touches what backs: '), s.affects.map((id, i) => [i ? ', ' : null, h('button', { class: 'linkbtn', onclick: () => { RX.open[id] = true; RX.filter = 'all'; openTab('claims'); } }, label(id))])) : null,
        open ? h('ul', { class: 'rx-commits' }, s.commits.map(c => h('li', null, mono(c.short), ' ', c.subject, h('span', { class: 'muted' }, ' · ' + plural(c.files, 'file') + ' · ' + absTime(c.time))))) : null)));
  }
  return root;
}

/* ---------- Experiments (ledger) ---------- */
function pageExperiments() {
  const nr = rxNotReady('Experiments'); if (nr) return nr;
  S.outline = [];
  const L = RX.ledger, F = RX.exFilter, c = L.counts;
  const root = doc(h('h1', { class: 'ptitle' }, 'Experiments'),
    h('p', { class: 'muted' }, 'Result files, what made them, and what relies on them.'));
  root.append(h('div', { class: 'fchips' }, [['all', 'All', L.rows.length], ['stale', 'Out of date', c.stale], ['unknown', 'No known source', c.unknown], ['current', 'Current', c.current]].map(([k, l, n]) =>
    h('button', { class: 'fchip', 'aria-pressed': String(F === k), onclick: () => { RX.exFilter = k; renderPage(true); } }, l + ' ', h('span', { class: 'n' }, n)))));
  const rows = L.rows.filter(r => F === 'all' || r.status === F);
  if (!L.rows.length) return root.append(emptyState('▦', 'No result files found', 'Lemmata looks for files in folders named results, outputs, figures, tables, plots or logs, and for run records in runs/*.json.')), root;
  const stChip = r => r.status === 'stale' ? plainChip('↻', 'Out of date', 'look') : r.status === 'current' ? plainChip('✓', 'Current', 'fine') : plainChip('?', 'No known source', 'ign');
  for (const r of rows) {
    root.append(h('article', { class: 'card rx-ex st-' + r.status },
      h('div', { class: 'rx-ex-h' }, h('button', { class: 'linkbtn', 'aria-expanded': String(RX.exSel === r.node_id), onclick: () => { RX.exSel = RX.exSel === r.node_id ? null : r.node_id; renderPage(true); } }, h('b', null, r.name)), stChip(r), h('span', { class: 'grow' }), r.made ? h('span', { class: 'muted small' }, 'written ' + absTime(r.made.time) + ' · ', mono(r.made.short)) : null),
      h('dl', { class: 'rx-dl' },
        r.code.length || r.runs.length ? [h('dt', null, 'Made by'), h('dd', null, r.runs.map(x => [rxNodeBtn(x.node_id, x.name), x.command ? h('span', { class: 'muted mono small' }, ' ' + trunc(x.command, 70)) : null, ' ']), r.code.map((x, i) => [i || r.runs.length ? ', ' : null, rxNodeBtn(x.node_id, x.name)]))] : [h('dt', null, 'Made by'), h('dd', { class: 'muted' }, 'Unknown. No script writes a file with this name.')],
        r.settings.length ? [h('dt', null, 'Settings'), h('dd', null, r.settings.map((x, i) => [i ? ', ' : null, rxNodeBtn(x.node_id, x.name)]))] : null,
        h('dt', null, 'Used in'), h('dd', null, r.used_by.length ? r.used_by.map((x, i) => [i ? ', ' : null, rxNodeBtn(x.node_id, x.name)]) : h('span', { class: 'muted' }, 'Nothing in the paper.')),
        r.claims.length ? [h('dt', null, 'Backs'), h('dd', null, r.claims.map((x, i) => [i ? ', ' : null, h('button', { class: 'linkbtn', onclick: () => { RX.open[x.id] = true; RX.filter = 'all'; openTab('claims'); } }, x.label)]))] : null),
      RX.exSel === r.node_id ? rxEvidenceCard(r.node_id) : null,
      r.newer.length ? h('div', { class: 'rx-warn' }, '↻ Changed after this file was written: ', r.newer.slice(0, 3).map((x, i) => [i ? '; ' : null, h('b', null, x.name), ' on ' + dmon(x.time) + ' (“' + trunc(x.subject || '', 60) + '”)']), '. Rerun it, or check that the change does not affect the output.') : null));
  }
  if (!rows.length) root.append(h('div', { class: 'muted' }, 'None with this filter.'));
  return root;
}

/* ---------- Tasks (feedback) ---------- */
function rxTaskCard(t) {
  const done = t.state !== 'open';
  const set = async body => { const r = await rxPost('/api/tasks', Object.assign({ id: t.id }, body)); if (r) { RX.tasks = r; if (body.state === 'done') rxTrack('task_done'); renderPage(true); renderLeft(); } };
  return h('article', { class: 'card rx-task' + (done ? ' done' : '') },
    h('div', { class: 'rx-task-h' },
      h('input', { type: 'checkbox', checked: t.state === 'done', disabled: READONLY, 'aria-label': 'Done', onchange: ev => set({ state: ev.target.checked ? 'done' : 'open' }) }),
      h('div', { class: 'grow' }, h('div', { class: 'rx-task-t' }, t.text), h('div', { class: 'muted small' }, (t.source || 'Feedback') + ' · ' + dmon(t.created))),
      !READONLY && t.state === 'open' ? h('button', { class: 'linkbtn small', onclick: () => set({ state: 'dropped' }) }, 'Drop') : t.state === 'dropped' ? plainChip('–', 'Dropped', 'ign') : null),
    t.targets.length || t.claims.length ? h('div', { class: 'rx-task-l' }, h('span', { class: 'muted' }, 'About: '),
      t.targets.map((x, i) => [i ? ', ' : null, rxNodeBtn(x.node_id, x.name), !READONLY ? h('button', { class: 'xbtn', title: 'Not about this', 'aria-label': 'Remove ' + x.name, onclick: () => set({ remove_target: x.node_id }) }, '×') : null]),
      t.claims.map((x, i) => [i || t.targets.length ? ', ' : null, h('button', { class: 'linkbtn', onclick: () => { RX.open[x.id] = true; RX.filter = 'all'; openTab('claims'); } }, x.label)]))
      : h('div', { class: 'rx-task-l muted' }, 'Lemmata could not tell what this is about. Name a table, figure, section, theorem or file in the feedback, or link one.'),
    !done && t.also_check && t.also_check.length ? h('div', { class: 'rx-task-l' }, h('span', { class: 'muted' }, 'When you change that, also recheck: '), t.also_check.slice(0, 8).map((x, i) => [i ? ', ' : null, rxNodeBtn(x.node_id, x.name)])) : null);
}
function pageTasks() {
  const nr = rxNotReady('Tasks'); if (nr) return nr;
  S.outline = [];
  const T2 = RX.tasks;
  const root = doc(h('h1', { class: 'ptitle' }, 'Tasks'),
    h('p', { class: 'muted' }, 'Paste feedback. Lemmata turns it into linked tasks.'));
  if (!READONLY) {
    const ta = h('textarea', { rows: '5', class: 'rx-ta', id: 'fb-text', 'aria-label': 'Feedback', placeholder: 'One point per line, for example:\n- Table 2 should include a second baseline\n- The proof of Theorem 1 does not use Assumption 2\n- Rerun evaluate.py with a longer window' });
    const src = h('input', { type: 'text', id: 'fb-source', 'aria-label': 'Where it came from', placeholder: 'Where it came from, e.g. Advisor meeting 10 Nov' });
    root.append(h('div', { class: 'card' }, ta, h('div', { class: 'btnrow' }, src, h('button', { class: 'btn primary', id: 'fb-add', onclick: async () => {
      if (!ta.value.trim()) return;
      const r = await rxPost('/api/feedback', { text: ta.value, source: src.value.trim() || null });
      if (r) { RX.tasks = r; rxTrack('feedback_added'); renderPage(true); renderLeft(); }
    } }, 'Make tasks'))));
  }
  const open = T2.tasks.filter(t => t.state === 'open'), rest = T2.tasks.filter(t => t.state !== 'open');
  root.append(sec('Open (' + open.length + ')', 'open', open.length ? open.map(rxTaskCard) : h('div', { class: 'muted' }, T2.tasks.length ? 'Everything is done.' : 'No feedback yet.')));
  if (rest.length) root.append(h('details', { class: 'details' }, h('summary', null, 'Done and dropped (' + rest.length + ')'), rest.map(rxTaskCard)));
  // weekly digest
  if (!READONLY) root.append(sec('Weekly digest', 'digest', rxDigestBox()));
  return root;
}
function rxDigestBox() {
  const box = h('div', { class: 'card' });
  const paint = () => {
    clear(box);
    if (!RX.digest) { box.append(h('p', { class: 'muted' }, 'Loading…')); return; }
    box.append(h('pre', { class: 'rx-digest' }, RX.digest.text),
      h('div', { class: 'btnrow' }, h('button', { class: 'btn', onclick: () => copyText(RX.digest.text) }, 'Copy')));
    if (HUB_ON && RX.hub) {
      const d = RX.hub.digest || {};
      const url = h('input', { type: 'text', 'aria-label': 'Slack webhook URL', placeholder: d.configured ? 'A Slack webhook is saved. Paste a new one to replace it.' : 'https://hooks.slack.com/services/…' });
      const post = async body => { try { const r = await fetch('/api/hub/projects/' + encodeURIComponent(PID) + '/digest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); const j = await r.json(); if (!r.ok) throw new Error(j.error.message); RX.hub.digest = j; paint(); return true; } catch (e) { toast(e.message); return false; } };
      box.append(h('div', { class: 'rx-digest-s' },
        h('p', { class: 'muted' }, 'Send this to a Slack channel every Monday morning. Create an “incoming webhook” in Slack and paste its URL. Lemmata contacts hooks.slack.com and nothing else.'),
        h('div', { class: 'btnrow' }, url, h('button', { class: 'btn', onclick: async () => { if (url.value.trim() && await post({ webhook: url.value.trim(), enabled: true })) toast('Saved. The digest goes out on Mondays.'); } }, 'Save'),
          d.configured ? h('button', { class: 'btn', onclick: async () => { try { const r = await fetch('/api/hub/projects/' + encodeURIComponent(PID) + '/digest/send', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); const j = await r.json(); if (!r.ok) throw new Error(j.error.message); rxTrack('digest_sent'); toast('Sent to Slack.'); } catch (e) { toast(e.message); } } }, 'Send now') : null,
          d.configured ? h('button', { class: 'linkbtn', onclick: () => post({ webhook: '', enabled: false }) }, 'Stop and forget the webhook') : null),
        d.configured ? h('div', { class: 'muted small' }, (d.enabled ? 'On. ' : 'Off. ') + (d.last_sent ? 'Last sent ' + absTime(d.last_sent) + '.' : 'Not sent yet.')) : null));
    }
  };
  paint();
  if (!RX.digest) apiGet('/api/digest').then(d => { RX.digest = d; paint(); }).catch(e => { clear(box).append(h('p', { class: 'muted' }, e.message)); });
  return box;
}

/* ---------- Ask ---------- */
const RX_EXAMPLES = ['Which claims are not supported?', 'Which results are out of date?', 'What decisions were made recently?', 'What are my open tasks?'];
function rxAnswerCard(a) {
  const go = a.type === 'claim' ? () => { RX.open[a.id] = true; RX.filter = 'all'; openTab('claims'); } : a.type === 'step' ? () => openTab('timeline') : a.type === 'task' ? () => openTab('tasks')
    : a.type === 'check' ? () => { S.focusFinding = a.id; openTab('checks'); } : () => openNode(a.id);
  return h('article', { class: 'card rx-ans' },
    h('div', { class: 'rx-ans-h' }, h('button', { class: 'linkbtn', onclick: go }, h('b', null, a.title)), a.status ? rxChip(a.status) : null, a.recheck ? plainChip('↻', 'Recheck', 'look') : null,
      h('span', { class: 'grow' }), h('span', { class: 'muted small' }, { claim: 'Claim', item: 'In the paper', result: 'Result file', step: 'Timeline', task: 'Task', impact: 'Impact', check: 'Check' }[a.type] || '')),
    a.text ? h('div', null, a.text) : null,
    a.support && a.support.length ? h('ul', { class: 'rx-ans-l' }, a.support.map(s => h('li', { class: s.how === 'suggested' ? 'muted' : '' }, (s.how === 'suggested' ? 'suggested: ' : s.relation + ': '), s.node_id ? rxNodeBtn(s.node_id, s.name) : s.name, s.how !== 'suggested' && s.traced === false ? h('span', { class: 'muted' }, ' (not traced)') : null))) : (a.type === 'claim' ? h('div', { class: 'muted' }, 'Nothing backs it yet.') : null),
    a.issues && a.issues.length ? a.issues.map(i => h('div', { class: 'rx-warn' }, '! ' + i)) : null,
    a.nodes && a.nodes.length ? h('div', { class: 'small' }, a.nodes.map((n, i) => [i ? ', ' : null, rxNodeBtn(n)])) : null,
    a.used_by && a.used_by.length ? h('div', { class: 'muted small' }, 'Used in: ' + a.used_by.join(', ')) : null,
    a.targets && a.targets.length ? h('div', { class: 'muted small' }, 'About: ' + a.targets.join(', ')) : null);
}
function pageAsk() {
  S.outline = [];
  const A = RX.ask;
  const input = h('input', { type: 'search', id: 'ask-q', value: A.q, placeholder: 'Ask about this project', 'aria-label': 'Question' });
  const run = async q => {
    q = (q != null ? q : input.value).trim(); if (!q || A.busy) return;
    A.q = q; A.busy = true; renderPage(true);
    try { A.res = await apiPost('/api/ask', { question: q }); rxTrack('ask'); } catch (e) { A.res = { error: e.status === 501 ? 'Not available on sample data.' : e.message }; }
    A.busy = false; renderPage(true);
  };
  input.addEventListener('keydown', ev => { if (ev.key === 'Enter') run(); });
  const root = doc(h('h1', { class: 'ptitle' }, 'Ask'),
    h('p', { class: 'muted' }, 'Looks things up in your paper and repository. Rules, not an AI model.'),
    h('div', { class: 'rx-askbar' }, input, h('button', { class: 'btn primary', id: 'ask-go', disabled: A.busy || READONLY, onclick: () => run() }, A.busy ? 'Looking…' : 'Ask')),
    h('div', { class: 'rx-ex-q' }, RX_EXAMPLES.concat(['What depends on ' + (basename(((S.graph.nodes.find(n => n.kind === 'code') || {}).name) || 'train.py')) + '?']).map(q => h('button', { class: 'fchip', onclick: () => run(q) }, q))));
  if (A.res && A.res.error) root.append(h('div', { class: 'rx-warn' }, A.res.error));
  else if (A.res) {
    root.append(h('div', { class: 'evg' }, A.res.answers.length ? plural(A.res.answers.length, 'result') + ' for “' + A.res.question + '”' : 'Nothing found for “' + A.res.question + '”'));
    if (!A.res.answers.length) root.append(h('p', { class: 'muted' }, 'Try naming a table, figure, theorem or file, or use one of the examples above.'));
    A.res.answers.forEach(a => root.append(rxAnswerCard(a)));
    root.append(h('div', { class: 'card rx-claude' }, h('b', null, 'Want reasoning, not lookup?'),
      h('p', { class: 'muted' }, 'Lemmata does not send your work to an AI model. If you use Claude Code, connect it to Lemmata (Account → create a token on the Projects page) and paste this. It runs on your own plan and reads the same evidence, with file and line for every statement.'),
      h('pre', { class: 'rx-digest' }, A.res.claude_prompt), h('div', { class: 'btnrow' }, h('button', { class: 'btn', onclick: () => copyText(A.res.claude_prompt) }, 'Copy prompt'))));
  }
  setTimeout(() => { const el = document.getElementById('ask-q'); if (el && !A.res && !typing(document.activeElement)) el.focus(); }, 30);
  return root;
}

/* ---------- wiring into the shell ---------- */
const RX_PAGES = { claims: pageClaims, timeline: pageTimeline, experiments: pageExperiments, tasks: pageTasks, ask: pageAsk };
function rxNavRows() {
  const cc = RX.claims && RX.claims.counts, lc = RX.ledger && RX.ledger.counts, tc = RX.tasks && RX.tasks.counts;
  const act = k => { const t = S.tabs[S.active]; return !!t && t.k === k; };
  return [
    navRow('Claims', '◆', () => openTab('claims'), cc ? (cc.unsupported + cc.partial) || null : null, act('claims')),
    navRow('Timeline', '⚑', () => openTab('timeline'), null, act('timeline')),
    navRow('Experiments', '▦', () => openTab('experiments'), lc ? lc.stale || null : null, act('experiments')),
    navRow('Tasks', '☑', () => openTab('tasks'), tc ? tc.open || null : null, act('tasks')),
    navRow('Ask', '?', () => openTab('ask'), null, act('ask')),
  ];
}
/* First visit to a project: open on the start view chosen on the Projects page (or assigned for the comparison). */
async function rxStartView() {
  if (!HUB_ON || READONLY) return;
  try {
    const st = await (await fetch('/api/hub/status', { cache: 'no-store' })).json();
    const p = await (await fetch('/api/hub/projects/' + encodeURIComponent(PID), { cache: 'no-store' })).json();
    RX.hub = p && p.id ? p : null;
    const tab = RX_VIEW_TAB[st.start_view];
    const key = 'lemmata.startview.' + PID;
    if (tab && !lsGet(key, false)) { lsSet(key, st.start_view); openTab(tab); }
  } catch (e) { /* the default tabs stay */ }
}
function rxUsefulBar() {   // one question, once per project: was the view you opened on useful?
  if (!HUB_ON || READONLY || lsGet('lemmata.useful.' + PID, false)) return;
  const t = S.tabs[S.active]; if (!t) return;
  setTimeout(() => {
    if (lsGet('lemmata.useful.' + PID, false) || document.querySelector('.scrim')) return;
    const bar = h('div', { class: 'rx-useful', role: 'status' }, 'Is this view helping you understand the project? ',
      h('button', { class: 'btn sm', onclick: () => { lsSet('lemmata.useful.' + PID, 'yes'); rxTrack('useful_yes', { view: (S.tabs[S.active] || {}).k }); bar.remove(); toast('Thanks.'); } }, 'Yes'),
      h('button', { class: 'btn sm', onclick: () => { lsSet('lemmata.useful.' + PID, 'no'); rxTrack('useful_no', { view: (S.tabs[S.active] || {}).k }); bar.remove(); toast('Thanks. Try another view from the left.'); } }, 'Not really'),
      h('button', { class: 'xbtn', 'aria-label': 'Dismiss', onclick: () => { lsSet('lemmata.useful.' + PID, 'dismissed'); bar.remove(); } }, '×'));
    document.body.append(bar);
  }, 90000);
}
