/* Lemmata UI. Plain JS, no build step. Talks to the JSON API of data-model.md section 12,
   or reads an embedded snapshot (exported report) and becomes read-only. */
'use strict';
const PRODUCT = 'Lemmata';
const HUB = '.lemmata';
const SNAP = (function () {
  const el = document.getElementById('lemmata-snapshot');
  if (!el) return null;
  try { return JSON.parse(el.textContent); } catch (e) { return null; }
})();
const READONLY = !!SNAP;
/* API base: /p/<pid>/ -> /p/<pid>/api/ (served by a hub); anything else -> /api/ (single-project mode). */
const PID = (function () { const m = location.pathname.match(/^\/p\/([^/]+)\//); return m ? decodeURIComponent(m[1]) : null; })();
const API_BASE = PID ? '/p/' + encodeURIComponent(PID) + '/api/' : '/api/';
const apiUrl = path => path.startsWith('/api/') ? API_BASE + path.slice(5) : path;
let HUB_ON = false;   // true when /api/hub/status answers and the page is under /p/<pid>/

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
  for (const c of kids.flat()) {
    if (c == null || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}
const $ = (s, r) => (r || document).querySelector(s);
function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
const basename = p => (p || '').split('/').pop();
const dirname = p => { const i = (p || '').lastIndexOf('/'); return i < 0 ? '' : p.slice(0, i); };
const fmtTime = t => t ? t.replace('T', ' ').slice(0, 16) : '';
const fmtDate = t => t ? t.slice(0, 10) : '';
function plural(n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); }

/* ---------- API ---------- */
async function apiGet(path) {
  if (SNAP) return snapGet(path);
  const r = await fetch(apiUrl(path), { cache: 'no-store' });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((j.error && j.error.message) || ('HTTP ' + r.status));
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
    return a ? a : Promise.reject(new Error('No stored analysis in this snapshot'));
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

/* ---------- constants ---------- */
const STATUS = {
  confirmed: { icon: '✓', word: 'Confirmed' },
  recheck: { icon: '↻', word: 'Recheck' },
  reviewed: { icon: '✓✓', word: 'Reviewed' },
  needs_fixing: { icon: '✕', word: 'Needs fixing' },
  ignored: { icon: '–', word: 'Ignored' },
  lowconf: { icon: '?', word: 'Low confidence' },
  proposed: { icon: '+', word: 'Proposed' },
  unmatched: { icon: '?', word: 'Could not be matched' },
  mismatch: { icon: '≠', word: 'Mismatch' },
  nottraced: { icon: '∅', word: 'Not traced' },
};
function chip(kind, extra) {
  const s = STATUS[kind];
  return h('span', { class: 'chip ' + kind }, s.icon + ' ' + s.word, extra ? ' ' + extra : null);
}
const BANDS = [
  { layer: 0, name: 'Thesis', glyph: 'T', col: 'thesis' },
  { layer: 1, name: 'Questions', glyph: 'Q', col: 'question' },
  { layer: 2, name: 'Sections', glyph: '§', col: 'section' },
  { layer: 3, name: 'Paper items', glyph: 'F', col: 'paper' },
  { layer: 4, name: 'Repo results', glyph: '▤', col: 'result' },
  { layer: 5, name: 'Runs', glyph: '▶', col: 'run' },   /* contract: runs 5, code 6 (ADR-002 open question 2) */
  { layer: 6, name: 'Code', glyph: '{ }', col: 'code' },
];
const BAND_BY_LAYER = Object.fromEntries(BANDS.map(b => [b.layer, b]));
const REF_BAND = { layer: null, name: 'References', glyph: 'R', col: 'reference' };
const KIND_GLYPH = { thesis: 'T', rq: 'Q', section: '§', figure: 'F', table: 'T', equation: 'E', item: 'F', asset: '▤', result: '▤', run: '▶', code: '{ }', config: '{ }', data: '▤', doc: '¶', reference: 'R' };
const KIND_LABEL = { thesis: 'Thesis', rq: 'Question', section: 'Section', figure: 'Figure', table: 'Table', equation: 'Equation', item: 'Paper item', asset: 'Asset', result: 'Result file', run: 'Run', code: 'Code file', config: 'Config file', data: 'Data file', doc: 'Document', reference: 'Reference' };
function colorOf(layer) { const b = layer == null ? REF_BAND : BAND_BY_LAYER[layer]; return b ? b.col : 'section'; }
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const LINEAGE_KINDS = new Set(['includes', 'generated_by', 'traces_to', 'produced_by', 'executes', 'reads', 'imports', 'contains', 'answers']);
const EDGE_PHRASE = { reads: 'reads', produced_by: 'is produced by', traces_to: 'traces to', includes: 'includes', generated_by: 'is generated by', executes: 'runs', imports: 'imports', value_match: 'shares a value with', contains: 'contains', answers: 'is answered in', refs: 'refers to', cites: 'cites' };

/* ---------- state ---------- */
const S = {
  project: null, graph: null, events: null, findings: null, alarms: null, checkpoints: null, triage: null,
  tab: 'graph', sel: null, dir: 'both', showRefs: false, showAll: false, filter: 'all', query: '',
  collapsed: new Set(), groupInit: false, onlyRecheck: false, blast: null, selEvent: null,
  alarmFilter: 'all', openGroups: new Set(), alarmSel: null, analysis: null, findSel: null, fFilter: { kind: '', state: '', q: '' },
  linkFilter: 'all', linkSel: null, linkChecked: new Set(), zoomRange: false, outlineSel: null, showPicker: false,
  rightCollapsed: false, leftCollapsed: false, error: null, loading: true, fullPreview: false, rendered: false,
};
const IX = {};   // derived indexes

function rebuildIndex() {
  const g = S.graph || { nodes: [], edges: [] };
  IX.node = new Map(g.nodes.map(n => [n.id, n]));
  IX.edge = new Map(g.edges.map(e => [e.id, e]));
  IX.out = new Map(); IX.in = new Map(); IX.all = new Map();
  const add = (m, k, e) => { let a = m.get(k); if (!a) m.set(k, a = []); a.push(e); };
  for (const e of g.edges) {
    add(IX.out, e.from, e); add(IX.in, e.to, e); add(IX.all, e.from, e); if (e.to !== e.from) add(IX.all, e.to, e);
  }
  // alarms by node
  IX.alarm = new Map();
  if (S.alarms) for (const grp of S.alarms.groups) {
    for (const c of grp.changed) add(IX.alarm, c.node_id, { group: grp, role: 'changed', entry: c });
    for (const d of grp.downstream) add(IX.alarm, d.node_id, { group: grp, role: 'downstream', entry: d });
  }
  IX.removed = new Set();
  if (S.alarms) for (const grp of S.alarms.groups) for (const r of grp.removed || []) IX.removed.add(r.node_id);
  IX.findingsByNode = new Map();
  if (S.findings) for (const f of S.findings.findings) for (const n of f.nodes || []) add(IX.findingsByNode, n, f);
  IX.hasCp = !!(S.alarms && S.alarms.checkpoint);
}
function lineageEdgeOk(e) {
  if (e.status === 'rejected' || e.status === 'proposed') return false;
  if (e.kind === 'value_match') return e.status === 'approved';
  if (e.kind === 'cites') return S.showRefs;
  return LINEAGE_KINDS.has(e.kind);
}
function triageEntry(type, id) {
  const e = S.triage && S.triage.entries && S.triage.entries[type + ':' + id];
  if (!e) return null;
  // effective_state is computed by the server on read; keep it consistent after local updates
  return e;
}
function effState(type, id) {
  const e = triageEntry(type, id);
  if (!e) return { state: 'unreviewed', outdated: false, entry: null };
  return { state: e.effective_state || e.state, outdated: !!e.outdated, entry: e };
}
function nodeStatus(id) {
  const t = effState('node', id).state;
  if (t === 'needs_fixing' || t === 'reviewed' || t === 'ignored') return t;
  if (IX.alarm.has(id)) return 'recheck';
  return IX.hasCp ? 'confirmed' : 'none';
}
const STATUS_RANK = { needs_fixing: 5, recheck: 4, reviewed: 2, ignored: 1, confirmed: 0, none: 0 };
function nodeLabel(id) { const n = IX.node.get(id); return n ? n.name : id; }
function locStr(n) {
  const l = n.loc || {};
  if (!l.path) return n.repo;
  return l.path + (l.line ? ':' + l.line : '');
}
function layerName(n) { const b = n.layer == null ? REF_BAND : BAND_BY_LAYER[n.layer]; return b ? b.name : '?'; }
function lowConf(grp) { return (grp.flags || []).some(f => f.code === 'message_claims_no_change'); }

/* lineage over underlying nodes: up = what it rests on (follow from->to), down = what it supports */
function lineage(id) {
  const up = new Map(), down = new Map(), upE = new Set(), downE = new Set();
  const walk = (start, next, seen, eset) => {
    const q = [start];
    seen.set(start, 0);
    while (q.length) {
      const cur = q.shift();
      for (const e of (next === 'out' ? IX.out : IX.in).get(cur) || []) {
        if (!lineageEdgeOk(e)) continue;
        const nx = next === 'out' ? e.to : e.from;
        eset.add(e.id);
        if (!seen.has(nx)) { seen.set(nx, seen.get(cur) + 1); q.push(nx); }
      }
    }
    seen.delete(start);
  };
  walk(id, 'out', up, upE);
  walk(id, 'in', down, downE);
  return { up, down, upE, downE };
}

/* ---------- toast / modal ---------- */
let toastTimer = null;
function toast(msg, undo) {
  const old = $('#toast'); if (old) old.remove();
  const t = h('div', { id: 'toast', role: 'status' }, msg, undo ? h('button', { class: 'linkbtn', onclick: () => { t.remove(); undo(); } }, 'Undo') : null);
  document.body.append(t);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.remove(), 4000);
}
function modal(title, body, buttons) {
  const prevFocus = document.activeElement;
  const close = () => { scrim.remove(); document.removeEventListener('keydown', onKey, true); if (prevFocus && prevFocus.focus) prevFocus.focus(); };
  const acts = h('div', { class: 'acts' }, buttons.map(b => h('button', { class: 'btn' + (b.primary ? ' primary' : ''), onclick: () => { close(); if (b.fn) b.fn(); } }, b.label)));
  const scrim = h('div', { class: 'scrim', onclick: ev => { if (ev.target === scrim) close(); } },
    h('div', { class: 'modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': title }, h('h3', null, title), body, acts));
  function onKey(ev) {
    if (ev.key === 'Escape') { ev.stopPropagation(); close(); }
    if (ev.key === 'Tab') {
      const f = [...scrim.querySelectorAll('button')]; if (!f.length) return;
      const i = f.indexOf(document.activeElement);
      if (ev.shiftKey && i <= 0) { ev.preventDefault(); f[f.length - 1].focus(); }
      else if (!ev.shiftKey && i === f.length - 1) { ev.preventDefault(); f[0].focus(); }
    }
  }
  document.addEventListener('keydown', onKey, true);
  document.body.append(scrim);
  const safe = acts.querySelector('button:not(.primary)') || acts.querySelector('button');
  if (safe) safe.focus();
}
function tip(el, textFn) {
  let t = null;
  const show = ev => { hide(); t = h('div', { class: 'tip' }, typeof textFn === 'function' ? textFn() : textFn); document.body.append(t); move(ev); };
  const move = ev => { if (t) { t.style.left = Math.min(ev.clientX + 12, innerWidth - 380) + 'px'; t.style.top = (ev.clientY + 14) + 'px'; } };
  const hide = () => { if (t) { t.remove(); t = null; } };
  el.addEventListener('mouseenter', show); el.addEventListener('mousemove', move); el.addEventListener('mouseleave', hide);
}

/* ---------- file access ---------- */
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
      return h('div', { class: 'ln' + (hlset.has(n) ? ' hl' : '') },
        h('span', { class: 'n' }, String(n)), h('span', { class: 'w' }, hlset.has(n) ? (opts.word || '') : ''), t || ' ');
    }));
}
function diffBlock(unified) {
  const rows = String(unified || '').split('\n');
  if (rows.length && rows[rows.length - 1] === '') rows.pop();
  return h('div', { class: 'code', tabindex: '0', role: 'region', 'aria-label': 'Diff' }, rows.map(t => {
    let c = 'ln', sign = ' ', body = t;
    if (t.startsWith('@@') || t.startsWith('---') || t.startsWith('+++')) c += ' hunk';
    else if (t.startsWith('+')) { c += ' add'; sign = '+'; body = t.slice(1); }
    else if (t.startsWith('-')) { c += ' del'; sign = '−'; body = t.slice(1); }
    else body = t.slice(1);
    const isHdr = c.includes('hunk');
    return h('div', { class: c }, h('span', { class: 'n' }, isHdr ? '' : sign), h('span', { class: 'w' }), isHdr ? t : body || ' ');
  }));
}

/* ======================================================================
   GRAPH (Cytoscape, preset layout computed here)
   ====================================================================== */
const G = { userMoved: false, cy: null, items: new Map(), bands: [], groups: new Map(), groupOf: new Map(), measure: null, barCache: new Map(), tipEl: null, W: 1000 };
const NODE_H = 26, ROW_H = 36;

function textWidth(s) {
  if (!G.measure) { G.measure = document.createElement('canvas').getContext('2d'); }
  G.measure.font = '12px ' + css('--font-sans');
  return G.measure.measureText(s).width;
}
function computeGroups() {
  G.groups = new Map(); G.groupOf = new Map();
  const nodes = (S.graph && S.graph.nodes) || [];
  const perLayer = new Map();
  for (const n of nodes) perLayer.set(n.layer, (perLayer.get(n.layer) || 0) + 1);
  const buckets = new Map();
  for (const n of nodes) {
    if (n.layer == null || !['asset', 'result', 'code', 'config', 'data', 'doc'].includes(n.kind)) continue;
    const p = (n.loc && n.loc.path) || '';
    const big = perLayer.get(n.layer) > 40;
    const d = big ? (p.includes('/') ? p.split('/')[0] : '') : dirname(p);   // big layers group by top-level folder
    if (!d) continue;
    const k = 'grp:' + n.layer + ':' + n.repo + ':' + d;
    if (!buckets.has(k)) buckets.set(k, { id: k, layer: n.layer, repo: n.repo, dir: d, members: [] });
    buckets.get(k).members.push(n.id);
  }
  for (const [k, g] of buckets) if (g.members.length >= (perLayer.get(g.layer) > 40 ? 3 : 5)) {
    G.groups.set(k, g);
    for (const m of g.members) G.groupOf.set(m, k);
  }
  if (!S.groupInit) {
    S.groupInit = true;
    for (const [k, g] of G.groups) if (perLayer.get(g.layer) > 40) S.collapsed.add(k);
  }
}
function groupStatus(g) {
  let best = 'none';
  for (const m of g.members) { const s = nodeStatus(m); if (STATUS_RANK[s] > STATUS_RANK[best]) best = s; }
  return best;
}
function groupCounts(g) {
  const c = {};
  for (const m of g.members) { const s = nodeStatus(m); c[s] = (c[s] || 0) + 1; }
  return c;
}
function repOf(id) {
  const gid = G.groupOf.get(id);
  return gid && S.collapsed.has(gid) ? gid : id;
}
function barUri(w, status) {
  const col = { recheck: '#E3B25E', needs_fixing: '#B3261E', reviewed: '#2A7354' }[status];
  const key = w + status;
  if (G.barCache.has(key)) return G.barCache.get(key);
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + w + '" height="' + NODE_H + '">' +
    (col ? '<rect x="0" y="' + (NODE_H - 4) + '" width="' + w + '" height="4" fill="' + col + '"/>' : '') + '</svg>';
  const u = 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
  G.barCache.set(key, u);
  return u;
}
function stripeUri(w, status, colName) {
  const key = 's' + w + status + colName;
  if (G.barCache.has(key)) return G.barCache.get(key);
  const col = { recheck: '#E3B25E', needs_fixing: '#B3261E', reviewed: '#2A7354' }[status];
  const stripe = css('--layer-' + colName) || '#5B6478';
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + w + '" height="' + NODE_H + '">' +
    '<rect x="0" y="0" width="4" height="' + NODE_H + '" fill="' + stripe + '"/>' +
    (col ? '<rect x="0" y="' + (NODE_H - 4) + '" width="' + w + '" height="4" fill="' + col + '"/>' : '') + '</svg>';
  const u = 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
  G.barCache.set(key, u);
  return u;
}
function statusGlyph(s) { return s === 'recheck' ? '↻ ' : s === 'needs_fixing' ? '✕ ' : s === 'reviewed' ? '✓✓ ' : s === 'ignored' ? '– ' : ''; }

function buildItems() {
  computeGroups();
  const nodes = (S.graph && S.graph.nodes) || [];
  const items = new Map();   // id -> item
  const layers = new Map();  // layer -> [blocks]
  const byLayer = new Map();
  for (const n of nodes) {
    if (n.layer == null && !S.showRefs) continue;
    const L = n.layer == null ? 'ref' : n.layer;
    if (!byLayer.has(L)) byLayer.set(L, []);
    byLayer.get(L).push(n);
  }
  for (const [L, ns] of byLayer) {
    const blocks = [];
    const seenG = new Set();
    ns.sort((a, b) => ((a.repo + (a.loc && a.loc.path)) < (b.repo + (b.loc && b.loc.path)) ? -1 : 1) || (a.id < b.id ? -1 : 1));
    for (const n of ns) {
      const gid = G.groupOf.get(n.id);
      if (gid) {
        if (seenG.has(gid)) continue;
        seenG.add(gid);
        const g = G.groups.get(gid);
        const coll = S.collapsed.has(gid);
        const blk = { key: gid, items: [] };
        items.set(gid, { id: gid, group: g, layer: L, label: '', collapsed: coll });
        blk.items.push(gid);
        if (!coll) for (const m of g.members) { items.set(m, { id: m, node: IX.node.get(m), layer: L }); blk.items.push(m); }
        blocks.push(blk);
      } else {
        items.set(n.id, { id: n.id, node: n, layer: L });
        blocks.push({ key: n.id, items: [n.id] });
      }
    }
    layers.set(L, blocks);
  }
  return { items, layers };
}
function itemLabel(it) {
  if (it.group) {
    const g = it.group, c = groupCounts(g);
    const worst = groupStatus(g);
    const w = worst === 'recheck' || worst === 'needs_fixing' ? '  ' + statusGlyph(worst).trim() + ' ' + (c[worst] || 0) : '';
    return (it.collapsed ? '▸ ' : '▾ ') + g.dir + '/ (' + g.members.length + ')' + w;
  }
  const n = it.node;
  return (n.kind === 'section' ? '' : KIND_GLYPH[n.kind] + ' ') + statusGlyph(nodeStatus(n.id)) + n.name;
}
function layoutGraph(model) {
  const { items, layers } = model;
  for (const it of items.values()) {
    it.label = itemLabel(it);
    it.w = Math.round(Math.min(176, Math.max(60, textWidth(it.label) + 26)));
  }
  // neighbours between visible items
  const nb = new Map();
  for (const e of (S.graph && S.graph.edges) || []) {
    if (e.status === 'rejected' || e.kind === 'refs') continue;
    const a = repOf(e.from), b = repOf(e.to);
    if (a === b || !items.has(a) || !items.has(b)) continue;
    if (!nb.has(a)) nb.set(a, []); if (!nb.has(b)) nb.set(b, []);
    nb.get(a).push(b); nb.get(b).push(a);
  }
  const order = [...layers.keys()].filter(k => k !== 'ref').sort((a, b) => a - b);
  const rank = new Map();
  const setRanks = () => {
    for (const L of order) {
      let i = 0; const tot = layers.get(L).reduce((s, b) => s + b.items.length, 0) || 1;
      for (const b of layers.get(L)) for (const id of b.items) rank.set(id, (i++ + 0.5) / tot);
    }
  };
  setRanks();
  for (let sweep = 0; sweep < 4; sweep++) {
    const seq = sweep % 2 ? order.slice().reverse() : order;
    for (const L of seq) {
      const blocks = layers.get(L);
      const keyed = blocks.map((b, idx) => {
        let s = 0, c = 0;
        for (const id of b.items) for (const o of nb.get(id) || []) { if (items.get(o).layer !== L && rank.has(o)) { s += rank.get(o); c++; } }
        return { b, idx, bc: c ? s / c : null };
      });
      // blocks without neighbours keep their slot relative to the others
      const mean = i => keyed[i].bc == null ? (blocks.length ? (keyed[i].idx + 0.5) / blocks.length : 0.5) : keyed[i].bc;
      const order2 = keyed.map((k, i) => ({ k, v: mean(i) })).sort((x, y) => x.v - y.v || x.k.idx - y.k.idx);
      layers.set(L, order2.map(o => o.k.b));
    }
    setRanks();
  }
  // pick the row width W that gives the largest fit-to-view zoom
  const cw = ($('#cy') && $('#cy').clientWidth) || 800, chh = ($('#cy') && $('#cy').clientHeight) || 560;
  const natural = order.map(L => layers.get(L).reduce((s, b) => s + b.items.reduce((s2, id) => s2 + items.get(id).w + 12, 0), 0));
  const widest = Math.max(0, ...natural);
  const minW = Math.max(400, ...[...items.values()].map(i => i.w + 12));
  let best = null;
  for (let W = minW; W <= Math.max(minW, Math.min(1800, widest)) + 59; W += 60) {
    const r = packLayers(model, order, W);
    const z = Math.min((cw - 40) / r.totalW, (chh - 56) / r.H, 1.05);
    if (!best || z > best.z + 0.01) best = { z, W, r };
  }
  const r = best ? best.r : packLayers(model, order, minW);
  G.W = r.W; G.bands = r.bands; G.pos = r.pos; G.totalH = r.H; G.refHead = r.refHead;
}
function packLayers(model, order, W) {
  const { items, layers } = model;
  const bands = []; let y = 0; const pos = new Map();
  for (const L of order) {
    const flat = layers.get(L).flatMap(b => b.items);
    const rows = [[]]; let rw = 0;
    for (const id of flat) {
      const w = items.get(id).w + 12;
      if (rw + w > W && rows[rows.length - 1].length) { rows.push([]); rw = 0; }
      rows[rows.length - 1].push(id); rw += w;
    }
    const bh = Math.max(88, rows.length * ROW_H + 28);
    const top = y;
    rows.forEach((row, r) => {
      const tw = row.reduce((s, id) => s + items.get(id).w + 12, 0);
      let x = (W - tw) / 2;
      const cy = top + (bh - rows.length * ROW_H) / 2 + r * ROW_H + ROW_H / 2;
      for (const id of row) { const w = items.get(id).w; pos.set(id, { x: x + w / 2, y: cy }); x += w + 12; }
    });
    const cnt = ((S.graph && S.graph.nodes) || []).filter(n => n.layer === L).length;
    bands.push({ layer: L, top, h: bh, count: cnt, meta: BAND_BY_LAYER[L] || { name: 'Layer ' + L, glyph: '?', col: 'section' } });
    y += bh;
  }
  let totalW = W, refHead = null;
  if (layers.has('ref')) {
    const flat = layers.get('ref').flatMap(b => b.items);
    const perCol = Math.max(1, Math.floor((Math.max(y, 400) - 40) / ROW_H));
    const cols = Math.ceil(flat.length / perCol);
    const x0 = W + 90;
    flat.forEach((id, i) => { const c = Math.floor(i / perCol), r = i % perCol; pos.set(id, { x: x0 + c * 190 + items.get(id).w / 2, y: 44 + r * ROW_H }); });
    refHead = { x: x0 + (cols * 190 - 20) / 2, y: 12, w: 120 };
    totalW = x0 + cols * 190;
  }
  return { bands, pos, H: y, W, totalW, refHead };
}
function buildElements(model) {
  const els = [];
  const { items } = model;
  for (const it of items.values()) {
    const p = G.pos.get(it.id); if (!p) continue;
    const col = it.group ? colorOf(it.layer) : colorOf(it.node.layer);
    els.push({ group: 'nodes', data: { id: it.id, label: it.label, w: it.w, col, isGroup: !!it.group, status: 'none', bar: '' }, position: { x: p.x, y: p.y } });
  }
  if (G.refHead) els.push({ group: 'nodes', classes: 'colhead', data: { id: '__refhead', label: 'References', w: 120 }, position: { x: G.refHead.x, y: G.refHead.y }, selectable: false, grabbable: false });
  const seen = new Map();
  for (const e of (S.graph && S.graph.edges) || []) {
    if (e.status === 'rejected') continue;
    const a = repOf(e.from), b = repOf(e.to);
    if (a === b || !items.has(a) || !items.has(b)) continue;
    const k = a + '→' + b;
    let d = seen.get(k);
    if (!d) {
      d = { id: 'v:' + k, source: a, target: b, ids: [], proposed: true };
      seen.set(k, d); els.push({ group: 'edges', data: d });
    }
    d.ids.push(e.id);
    if (e.status !== 'proposed') d.proposed = false;
  }
  return els;
}
function cyStyle() {
  const ink = css('--ink'), border = css('--border-strong');
  const tint = {}; for (const c of ['thesis', 'question', 'section', 'reference', 'paper', 'result', 'code', 'run']) tint[c] = [css('--layer-' + c), css('--layer-' + c + '-t')];
  const st = [
    { selector: 'node', style: { shape: 'round-rectangle', width: 'data(w)', height: NODE_H, label: 'data(label)', 'text-valign': 'center', 'text-halign': 'center', 'font-size': 12, 'font-family': css('--font-sans'), color: ink, 'text-max-width': 150, 'text-wrap': 'ellipsis', 'border-width': 1, 'border-color': border, 'background-color': '#fff', 'text-margin-x': 2 } },
    { selector: 'node[?isGroup]', style: { 'border-style': 'dashed', 'border-width': 1.5, 'background-color': '#fff' } },
    { selector: 'node.colhead', style: { 'border-width': 0, 'background-opacity': 0, 'font-weight': 600, events: 'no' } },
    { selector: 'node[bar]', style: { 'background-image': 'data(bar)', 'background-fit': 'none', 'background-width': '100%', 'background-height': '100%', 'background-clip': 'node', 'background-position-x': '0%', 'background-position-y': '0%', 'background-repeat': 'no-repeat' } },
    { selector: 'node.up', style: { 'border-color': css('--up'), 'border-width': 2.5 } },
    { selector: 'node.down', style: { 'border-color': css('--down'), 'border-width': 2.5 } },
    { selector: 'node.sel', style: { 'border-color': ink, 'border-width': 3.5 } },
    { selector: 'node.blast', style: { 'border-color': css('--amber'), 'border-width': 3 } },
    { selector: 'node.dim', style: { opacity: 0.22 } },
    { selector: 'node.match', style: { 'border-color': ink, 'border-width': 2 } },
    { selector: 'edge', style: { display: 'none', width: 1, 'line-color': border, 'curve-style': 'bezier', 'control-point-step-size': 30, 'target-arrow-shape': 'none', 'target-arrow-color': border, 'arrow-scale': 0.8 } },
    { selector: 'edge.all', style: { display: 'element', opacity: 0.5 } },
    { selector: 'edge.eup', style: { display: 'element', opacity: 1, width: 2, 'line-color': css('--up'), 'target-arrow-color': css('--up'), 'target-arrow-shape': 'triangle', 'z-index': 9 } },
    { selector: 'edge.edown', style: { display: 'element', opacity: 1, width: 2, 'line-color': css('--down-stroke'), 'target-arrow-color': css('--down-stroke'), 'line-style': 'dashed', 'line-dash-pattern': [6, 4], 'target-arrow-shape': 'triangle', 'z-index': 9 } },
    { selector: 'edge.prop', style: { display: 'element', opacity: 1, width: 1.5, 'line-color': '#8C93A3', 'line-style': 'dotted', 'target-arrow-shape': 'none', label: 'Proposed', 'font-size': 10, color: css('--muted'), 'text-background-color': '#fff', 'text-background-opacity': 0.9, 'text-background-padding': 2, 'z-index': 8 } },
  ];
  return st;
}
function initCy() {
  const cy = cytoscape({ container: $('#cy'), elements: [], style: cyStyle(), layout: { name: 'preset' }, minZoom: 0.08, maxZoom: 3, boxSelectionEnabled: false, autoungrabify: true, selectionType: 'single' });
  G.cy = cy;
  cy.on('tap', 'node', ev => {
    const n = ev.target;
    if (n.hasClass('colhead')) return;
    if (n.data('isGroup')) { toggleGroup(n.id()); return; }
    selectNode(n.id(), { noCenter: true });
  });
  cy.on('tap', ev => { if (ev.target === cy && S.sel) clearSelection(); });
  cy.on('mouseover', 'node', ev => {
    const n = ev.target; if (n.hasClass('colhead')) return;
    const oe = ev.originalEvent; if (!oe) return;
    hideGraphTip();
    let text;
    if (n.data('isGroup')) { const g = G.groups.get(n.id()); text = g.dir + '/\n' + g.members.length + ' files · click to ' + (S.collapsed.has(n.id()) ? 'expand' : 'collapse'); }
    else { const x = IX.node.get(n.id()); const st = nodeStatus(x.id); text = x.name + '\n' + layerName(x) + ' · ' + locStr(x) + '\n' + (STATUS[st] ? STATUS[st].word : 'No checkpoint'); }
    G.tipEl = h('div', { class: 'tip' }, text); document.body.append(G.tipEl);
    G.tipEl.style.left = Math.min(oe.clientX + 12, innerWidth - 380) + 'px'; G.tipEl.style.top = (oe.clientY + 14) + 'px';
    $('#cy').style.cursor = 'pointer';
  });
  cy.on('mouseout', 'node', () => { hideGraphTip(); $('#cy').style.cursor = ''; });
  cy.on('viewport', syncBands);
  cy.on('dragpan', () => { G.userMoved = true; });
  $('#cy').addEventListener('wheel', () => { G.userMoved = true; }, { passive: true });
  cy.on('pan zoom', hideGraphTip);
}
function clearTips() { document.querySelectorAll('.tip').forEach(t => t.remove()); G.tipEl = null; }
function hideGraphTip() { if (G.tipEl) { G.tipEl.remove(); G.tipEl = null; } }

function rebuildGraph(opts) {
  opts = opts || {};
  if (!G.cy) return;
  const model = buildItems();
  G.model = model;
  layoutGraph(model);
  const els = buildElements(model);
  const cy = G.cy;
  cy.startBatch();
  cy.elements().remove();
  cy.add(els);
  cy.endBatch();
  buildBandDom();
  applyGraphState();
  if (opts.fit !== false) fitGraph(); else syncBands();
  const empty = !(S.graph && S.graph.nodes && S.graph.nodes.length);
  setGraphMsg(S.loading ? { t: 'Building graph…' } : S.error ? { t: 'The graph could not be drawn. ' + S.error, btn: ['Rescan', rescan] } :
    empty ? { t: 'The graph is empty. ' + PRODUCT + ' did not find a thesis, sections or results to connect.', btn: ['Back to scan', () => openPicker()] } : null);
}
function setGraphMsg(m) {
  let el = $('#gmsg');
  if (!m) { if (el) el.remove(); return; }
  if (!el) { el = h('div', { id: 'gmsg' }); $('#gview').append(el); }
  clear(el).append(h('div', null, m.t));
  if (m.btn) el.append(h('button', { class: 'btn', style: { marginTop: '8px' }, onclick: m.btn[1] }, m.btn[0]));
}
function fitGraph() {
  const cy = G.cy; if (!cy || !cy.nodes().length) return;
  G.userMoved = false;
  const bb = cy.nodes().not('.colhead').boundingBox();
  const cw = cy.width(), ch = cy.height();
  const topPad = 8, botPad = 44;
  const bw = Math.max(bb.w, 1), bh = Math.max(G.totalH || bb.h, 1);
  const z = Math.max(0.08, Math.min((cw - 40) / bw, (ch - topPad - botPad) / bh, 1.05));
  cy.zoom(z);
  cy.pan({ x: cw / 2 - z * (bb.x1 + bb.w / 2), y: topPad + (ch - topPad - botPad) / 2 - z * (bh / 2) });
  syncBands();
}
function buildBandDom() {
  const bg = clear($('#bandbg')), lb = clear($('#bandlabels'));
  G.bands.forEach((b, i) => {
    b.bgEl = h('div', { class: 'bgrow' + (i % 2 ? ' alt' : '') });
    b.lbEl = h('div', { class: 'blabel', style: { borderLeftColor: 'var(--layer-' + b.meta.col + ')' }, title: 'Shift+click to collapse or expand this band' },
      h('b', null, h('span', { class: 'glyph' }, b.meta.glyph), b.meta.name), h('span', null, String(b.count)));
    b.lbEl.addEventListener('click', ev => { if (ev.shiftKey) toggleBand(b.layer); });
    bg.append(b.bgEl); lb.append(b.lbEl);
  });
  syncBands();
}
function syncBands() {
  const cy = G.cy; if (!cy) return;
  const z = cy.zoom(), py = cy.pan().y;
  for (const b of G.bands) {
    if (!b.bgEl) continue;
    const top = py + b.top * z, hh = b.h * z;
    b.bgEl.style.top = top + 'px'; b.bgEl.style.height = hh + 'px';
    b.lbEl.style.top = top + 'px'; b.lbEl.style.height = Math.max(hh, 0) + 'px';
    b.lbEl.style.display = hh < 20 ? 'none' : '';
  }
}
function toggleGroup(gid) {
  if (S.collapsed.has(gid)) S.collapsed.delete(gid); else S.collapsed.add(gid);
  rebuildGraph({ fit: false });
}
function toggleBand(layer) {
  const ids = [...G.groups.values()].filter(g => g.layer === layer).map(g => g.id);
  if (!ids.length) return;
  const anyOpen = ids.some(i => !S.collapsed.has(i));
  for (const i of ids) anyOpen ? S.collapsed.add(i) : S.collapsed.delete(i);
  rebuildGraph({ fit: false });
}
function expandAll(on) {
  for (const g of G.groups.values()) on ? S.collapsed.delete(g.id) : S.collapsed.add(g.id);
  rebuildGraph();
}

function matchNode(n, q) {
  q = q.toLowerCase();
  return (n.name || '').toLowerCase().includes(q) || ((n.loc && n.loc.path) || '').toLowerCase().includes(q) || (n.detail || '').toLowerCase().includes(q) || n.id.toLowerCase().includes(q);
}
function filterMatch(id) {
  const st = nodeStatus(id);
  if (S.filter === 'recheck') return st === 'recheck';
  if (S.filter === 'needs_fixing') return st === 'needs_fixing';
  if (S.filter === 'proposed') return (IX.all.get(id) || []).some(e => e.status === 'proposed');
  return true;
}
function applyGraphState() {
  const cy = G.cy; if (!cy || !G.model) return;
  const L = S.sel && IX.node.has(S.sel) ? lineage(S.sel) : null;
  S.lin = L;
  const selRep = S.sel ? repOf(S.sel) : null;
  const q = S.query.trim();
  let matches = 0;
  const blast = S.blast ? new Set(S.blast.nodes) : null;
  cy.batch(() => {
    cy.nodes().forEach(nd => {
      if (nd.hasClass('colhead')) return;
      const it = G.model.items.get(nd.id()); if (!it) return;
      const members = it.group ? it.group.members : [it.id];
      const st = it.group ? groupStatus(it.group) : nodeStatus(it.id);
      nd.data('bar', STATUS_RANK[st] >= 1 && st !== 'confirmed' && st !== 'none' ? stripeUri(it.w, st, colorOf(it.group ? it.layer : it.node.layer)) : stripeUri(it.w, 'none', colorOf(it.group ? it.layer : it.node.layer)));
      nd.data('label', itemLabel(it));
      let cls = { sel: false, up: false, down: false, dim: false, match: false, blast: false };
      if (L) {
        const isSel = members.includes(S.sel);
        const inUp = S.dir !== 'down' && members.some(m => L.up.has(m));
        const inDown = S.dir !== 'up' && members.some(m => L.down.has(m));
        cls.sel = isSel; cls.up = !isSel && inUp; cls.down = !isSel && inDown && !inUp;
        cls.dim = !(isSel || inUp || inDown);
      } else if (q) {
        const m = members.some(id => matchNode(IX.node.get(id), q));
        cls.match = m; cls.dim = !m; if (m) matches++;
      } else if (blast) {
        const m = members.some(id => blast.has(id));
        cls.blast = m; cls.dim = !m;
      } else if (S.filter !== 'all') {
        cls.dim = !members.some(filterMatch);
      }
      if (L && blast && members.some(id => blast.has(id))) cls.blast = true;
      for (const k in cls) nd.toggleClass(k, cls[k]);
    });
    cy.edges().forEach(ed => {
      const ids = ed.data('ids');
      let c = '';
      if (L) {
        const up = S.dir !== 'down' && ids.some(i => L.upE.has(i));
        const dn = S.dir !== 'up' && ids.some(i => L.downE.has(i));
        const pr = ids.some(i => { const e = IX.edge.get(i); return e.status === 'proposed' && (e.from === S.sel || e.to === S.sel); });
        c = up ? 'eup' : dn ? 'edown' : pr ? 'prop' : '';
      } else if (ed.data('proposed') && (S.filter === 'all' || S.filter === 'proposed')) c = 'prop';
      else if (S.filter === 'proposed') c = '';
      else if (S.showAll) c = 'all';
      ed.toggleClass('eup', c === 'eup'); ed.toggleClass('edown', c === 'edown'); ed.toggleClass('prop', c === 'prop'); ed.toggleClass('all', c === 'all');
    });
  });
  // counter chip
  const cnt = $('#gcount');
  if (cnt) {
    clear(cnt);
    if (L) cnt.append(h('span', { class: 'chip plain' }, 'Rests on ' + L.up.size + ' · Supports ' + L.down.size));
    if (q) cnt.append(h('span', { class: 'chip plain' }, plural(matches, 'match', 'matches')));
  }
  const cb = $('#cpbanner'); if (cb) cb.classList.toggle('hidden', IX.hasCp || READONLY);
  const noMatch = q && matches === 0;
  const msg = $('#gmsg');
  if (noMatch && !msg) setGraphMsg({ t: 'No nodes match “' + q + '”.', btn: ['Clear filter', () => { $('#search').value = ''; setQuery(''); }] });
  else if (!noMatch && msg && msg.firstChild && msg.firstChild.textContent.startsWith('No nodes match')) setGraphMsg(null);
}
function setQuery(q) { S.query = q; applyGraphState(); }

function ensureVisible(id) {
  const gid = G.groupOf.get(id);
  if (gid && S.collapsed.has(gid)) { S.collapsed.delete(gid); return true; }
  const n = IX.node.get(id);
  if (n && n.layer == null && !S.showRefs) { S.showRefs = true; syncRefsButton(); return true; }
  return false;
}
function selectNode(id, opts) {
  opts = opts || {};
  if (!IX.node.has(id)) return;
  S.sel = id; S.blast = opts.keepBlast ? S.blast : null;
  if (!opts.keepBlast) { S.selEvent = null; renderTimeline(); }
  if (ensureVisible(id)) rebuildGraph({ fit: false }); else applyGraphState();
  if (!opts.noCenter && G.cy) {
    const nd = G.cy.getElementById(id);
    if (nd.nonempty()) G.cy.animate({ center: { eles: nd }, zoom: Math.max(G.cy.zoom(), 0.8) }, { duration: 150 });
  }
  S.rightCollapsed = false; layoutMain();
  renderDetail(); renderOutline(); syncBands();
}
function clearSelection() {
  S.sel = null; S.blast = null; S.selEvent = null;
  applyGraphState(); renderDetail(); renderOutline(); renderTimeline();
}
function showInGraph(id) { setTab('graph'); selectNode(id); }
function moveSel(dx, dy) {
  const cy = G.cy; if (!cy) return;
  const cur = S.sel && cy.getElementById(repOf(S.sel));
  if (!cur || cur.empty()) { const f = cy.nodes().not('.colhead').first(); if (f.nonempty() && !f.data('isGroup')) selectNode(f.id()); return; }
  const p = cur.position(); let best = null, bd = 1e12;
  cy.nodes().not('.colhead').forEach(n => {
    if (n.id() === cur.id() || n.data('isGroup')) return;
    const q = n.position(), ddx = q.x - p.x, ddy = q.y - p.y;
    if (dx && (Math.sign(ddx) !== dx || Math.abs(ddy) > ROW_H / 2)) return;
    if (dy && (Math.sign(ddy) !== dy || Math.abs(ddy) < ROW_H / 2)) return;
    const d = dx ? Math.abs(ddx) + Math.abs(ddy) * 5 : Math.abs(ddy) * 3 + Math.abs(ddx);
    if (d < bd) { bd = d; best = n; }
  });
  if (best) selectNode(best.id());
}

/* ======================================================================
   SHELL, TOPBAR, TRIAGE
   ====================================================================== */
const TABS = [['graph', 'Graph', 'G'], ['alarms', 'Alarms', 'A'], ['checks', 'Checks', 'C'], ['links', 'Links', 'L']];
function buildShell() {
  const app = clear($('#app'));
  app.append(
    h('header', { id: 'topbar', role: 'banner' }),
    h('div', { id: 'banner', class: 'hidden', role: 'alert' }),
    h('div', { id: 'main' },
      h('aside', { id: 'left', 'aria-label': 'Outline' }),
      h('main', { id: 'centre' },
        h('section', { id: 'v-graph', class: 'view', 'aria-label': 'Graph' },
          h('div', { id: 'gtools', class: 'toolbar' }),
          h('div', { id: 'cpbanner', class: 'hidden' }, 'Set a Last known good checkpoint on the timeline to see what to recheck.'),
          h('div', { id: 'gview' },
            h('div', { id: 'bandbg' }), h('div', { id: 'cy', role: 'application', 'aria-label': 'Dependency graph. Use the outline or search to pick a node; arrow keys move the selection.' }),
            h('div', { id: 'bandlabels' }),
            h('div', { id: 'gcount', 'aria-live': 'polite' }),
                  h('div', { id: 'legend' },
              h('span', { class: 'u' }, '▲ Rests on (blue, solid)'), h('span', { class: 'd' }, '▼ Supports (orange, dashed)'),
              h('span', null, '↻ Recheck'), h('span', null, '✕ Needs fixing'), h('span', null, '✓✓ Reviewed')))),
        h('section', { id: 'v-alarms', class: 'view', 'aria-label': 'Alarms' }),
        h('section', { id: 'v-checks', class: 'view', 'aria-label': 'Checks' }),
        h('section', { id: 'v-links', class: 'view', 'aria-label': 'Links' }),
        h('div', { id: 'tlstrip', class: 'hidden' }),
        h('section', { id: 'timeline', 'aria-label': 'Timeline' })),
      h('aside', { id: 'right', 'aria-label': 'Details' },
        h('div', { id: 'r-detail' }), h('div', { id: 'r-alarm', class: 'hidden' }), h('div', { id: 'r-check', class: 'hidden' }), h('div', { id: 'r-link', class: 'hidden' }))),
    h('div', { id: 'picker', class: 'hidden' }));
  buildGraphTools();
  initCy();
}
function buildGraphTools() {
  const t = clear($('#gtools'));
  const dirBtn = (v, label, tipText) => h('button', { class: 'btn sm', 'data-dir': v, 'aria-pressed': String(S.dir === v), title: tipText, onclick: () => setDir(v) }, label);
  t.append(
    h('input', { id: 'search', type: 'search', placeholder: 'Search nodes  /', 'aria-label': 'Search nodes', oninput: ev => setQuery(ev.target.value), onkeydown: ev => {
      if (ev.key === 'Enter') { const m = (S.graph.nodes || []).find(n => matchNode(n, S.query)); if (m) { selectNode(m.id); } }
      if (ev.key === 'Escape') { ev.target.value = ''; setQuery(''); ev.target.blur(); ev.stopPropagation(); } } }),
    h('label', { class: 'muted' }, 'Show: ', h('select', { id: 'filter', 'aria-label': 'Show', onchange: ev => { S.filter = ev.target.value; applyGraphState(); } },
      [['all', 'All'], ['recheck', 'Recheck only'], ['needs_fixing', 'Needs fixing'], ['proposed', 'Proposed links']].map(o => h('option', { value: o[0] }, o[1])))),
    h('span', { class: 'seg', role: 'group', 'aria-label': 'Lineage direction' },
      dirBtn('both', 'Both', 'Show what it rests on and what it supports (B)'), dirBtn('up', '▲ Rests on', 'Only what it rests on (U)'), dirBtn('down', '▼ Supports', 'Only what it supports (D)')),
    h('button', { class: 'btn sm', id: 'btn-refs', 'aria-pressed': 'false', onclick: () => { S.showRefs = !S.showRefs; syncRefsButton(); rebuildGraph(); } }, 'References'),
    h('button', { class: 'btn sm', id: 'btn-alledges', 'aria-pressed': 'false', onclick: () => { S.showAll = !S.showAll; $('#btn-alledges').setAttribute('aria-pressed', String(S.showAll)); applyGraphState(); } }, 'Show all edges'),
    h('button', { class: 'btn sm', onclick: () => expandAll(true) }, 'Expand all'),
    h('button', { class: 'btn sm', onclick: () => expandAll(false) }, 'Collapse all'),
    h('button', { class: 'btn sm', title: 'Fit  F', onclick: fitGraph }, 'Fit  F'),
    h('button', { class: 'btn sm', 'aria-label': 'Zoom out', onclick: () => zoomBy(1 / 1.3) }, '−'),
    h('button', { class: 'btn sm', 'aria-label': 'Zoom in', onclick: () => zoomBy(1.3) }, '+'));
}
function zoomBy(f) { G.userMoved = true; const cy = G.cy; cy.zoom({ level: cy.zoom() * f, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }); }
function syncRefsButton() { const b = $('#btn-refs'); if (b) b.setAttribute('aria-pressed', String(S.showRefs)); }
function setDir(v) {
  S.dir = v;
  document.querySelectorAll('[data-dir]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.dir === v)));
  applyGraphState(); renderDetail();
}

function setTab(tab) {
  clearTips();
  S.tab = tab; S.showPicker = false;
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === 'v-' + tab));
  $('#picker').classList.add('hidden');
  $('#timeline').classList.toggle('hidden', !(tab === 'graph' || tab === 'alarms'));
  if (!(tab === 'graph' || tab === 'alarms')) $('#tlstrip').classList.add('hidden');
  for (const id of ['detail', 'alarm', 'check', 'link']) $('#r-' + id).classList.toggle('hidden', !(id === { graph: 'detail', alarms: 'alarm', checks: 'check', links: 'link' }[tab]));
  layoutMain();
  renderTopbar();
  if (tab === 'graph' && G.cy) { G.cy.resize(); syncBands(); }
  if (tab === 'alarms') renderAlarms();
  if (tab === 'checks') renderChecks();
  if (tab === 'links') renderLinks();
  renderTimeline();
}
function layoutMain() {
  const m = $('#main'); if (!m) return;
  m.className = '';
  const t = S.tab;
  if (t === 'checks' || t === 'links') { m.classList.add('noleft'); m.classList.add((t === 'checks' ? S.findSel : S.linkSel) ? 'wideright' : 'nodetail'); }
  else { if (S.leftCollapsed) m.classList.add('noleft'); if (S.rightCollapsed) m.classList.add('noright'); }
  if (G.cy) setTimeout(() => { G.cy.resize(); if (!G.userMoved && S.tab === 'graph') fitGraph(); else syncBands(); renderTimeline(); }, 0);
}

function counts() {
  const alarmed = new Set();
  if (S.alarms) for (const g of S.alarms.groups) { for (const c of g.changed) alarmed.add(c.node_id); for (const d of g.downstream) alarmed.add(d.node_id); }
  let recheck = 0; for (const id of alarmed) if (nodeStatus(id) === 'recheck') recheck++;
  const openF = S.findings ? S.findings.findings.filter(f => effState('finding', f.id).state === 'unreviewed').length : 0;
  const prop = S.graph ? S.graph.edges.filter(e => e.status === 'proposed').length : 0;
  return { recheck, openF, prop, alarmed: alarmed.size };
}
function renderTopbar() {
  const tb = clear($('#topbar')); if (!S.project) return;
  const c = counts();
  const badge = (n, word) => h('span', { class: 'badge' + (n ? '' : ' zero'), 'aria-label': n + ' ' + word }, String(n));
  const cp = S.alarms && S.alarms.checkpoint;
  tb.append(...[
    HUB_ON ? h('a', { class: 'btn', id: 'btn-projects', href: '/', title: 'All projects' }, '← Projects') : null,
    h('span', { class: 'brand' }, PRODUCT), 
    h('button', { class: 'proj', title: 'Project and scan', onclick: () => openPicker() }, 'project: ', h('b', null, S.project.name)),
    h('div', { class: 'tabs', role: 'tablist' }, TABS.map(([id, label, key]) => h('button', { class: 'tab', role: 'tab', 'aria-selected': String(S.tab === id), title: label + '  ' + key, onclick: () => setTab(id) }, label,
      id === 'alarms' ? badge(c.recheck, 'to recheck') : id === 'checks' ? badge(c.openF, 'open findings') : id === 'links' ? badge(c.prop, 'proposed links') : null))),
    h('span', { class: 'grow' }),
    READONLY ? h('span', { class: 'chip outdated', title: 'Opened from an exported file' }, 'Read-only snapshot · exported ' + fmtTime(SNAP.exported_at)) :
      h('span', { class: 'scanst' }, 'scanned ' + fmtTime(S.project.scanned_at)),
    h('button', { class: 'btn', id: 'btn-cp', 'aria-haspopup': 'dialog', onclick: toggleCheckpointPanel, title: 'Your Last known good checkpoint' },
      'Checkpoint: ' + (cp ? cp.id.toUpperCase() : 'none'), ' ▾'),
    READONLY ? null : h('button', { class: 'btn', id: 'btn-rescan', onclick: rescan }, 'Rescan'),
    HUB_ON && !READONLY ? h('button', { class: 'btn', id: 'btn-sync', title: 'Pull the latest commits from GitHub and rescan', onclick: hubSync }, 'Sync now') : null,
    HUB_ON && !READONLY ? h('button', { class: 'btn', id: 'btn-upload', title: 'In Overleaf: Menu → Download → Source', onclick: () => $('#zip-in').click() }, 'Upload paper zip') : null,
    HUB_ON && !READONLY ? h('input', { type: 'file', id: 'zip-in', accept: '.zip,application/zip', class: 'hidden', 'aria-label': 'Paper zip', onchange: hubUpload }) : null,
    READONLY ? null : h('a', { class: 'btn', href: apiUrl('/api/export'), download: '', title: 'Saves a local HTML file you can share. It includes the evidence shown here.' }, 'Export HTML report'),
    h('button', { class: 'btn', 'aria-label': 'Keyboard shortcuts', title: 'Keyboard shortcuts  ?', onclick: showShortcuts }, '?')].filter(Boolean));
}
async function hubSync() {
  const b = $('#btn-sync'); if (b) { b.disabled = true; b.textContent = 'Syncing…'; }
  try {
    const r = await hubPost('/api/hub/projects/' + encodeURIComponent(PID) + '/sync', null, 'application/json');
    await loadAll({ keepView: true });
    toast(r.changed ? 'Synced from GitHub · rescanned' : 'Already up to date');
  } catch (e) { toast('Sync failed: ' + e.message); }
  renderTopbar();
}
async function hubUpload(ev) {
  const f = ev.target.files[0]; if (!f) return;
  const b = $('#btn-upload'); if (b) { b.disabled = true; b.textContent = 'Uploading…'; }
  try {
    const r = await hubPost('/api/hub/projects/' + encodeURIComponent(PID) + '/paper', f, 'application/zip');
    await loadAll({ keepView: true });
    toast('Paper version ' + r.version + ' uploaded · rescanned');
  } catch (e) { toast('Upload failed: ' + e.message); }
  renderTopbar();
}
async function hubPost(path, body, type) {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': type }, body: body == null ? '{}' : body });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((j.error && j.error.message) || ('HTTP ' + r.status));
  return j;
}
function showShortcuts() {
  const rows = [['/', 'Search'], ['F', 'Fit'], ['Esc', 'Clear'], ['G A C L', 'Switch tab'], ['[ ]', 'Toggle panels'], ['R X I', 'Triage'], ['U D B', 'Lineage direction'], ['K', 'Checkpoint at selected commit'], ['+ − 0', 'Zoom'], ['Arrows', 'Move selection'], ['?', 'This sheet']];
  modal('Keyboard shortcuts', h('div', { class: 'keys' }, rows.flatMap(r => [h('kbd', null, r[0]), h('span', null, r[1])])), [{ label: 'Close', primary: true }]);
}
async function rescan() {
  if (READONLY) return;
  const b = $('#btn-rescan'); if (b) { b.disabled = true; b.textContent = 'Scanning…'; }
  try { await apiPost('/api/scan', {}); await loadAll(); toast('Scan finished.'); }
  catch (e) { showBanner('Scan data could not be read. ' + e.message + '.', true); }
  renderTopbar();
}
function showBanner(msg, withActions) {
  const b = $('#banner'); clear(b);
  if (!msg) { b.classList.add('hidden'); return; }
  b.classList.remove('hidden');
  b.append(msg, ' ');
  if (withActions) b.append(h('button', { class: 'linkbtn', onclick: rescan }, 'Rescan'), ' ', h('button', { class: 'linkbtn', onclick: () => openPicker() }, 'Choose another folder'));
}

/* checkpoint popover */
function toggleCheckpointPanel() {
  const old = $('#cppop'); if (old) { old.remove(); return; }
  const cps = (S.checkpoints && S.checkpoints.checkpoints) || [];
  const note = h('input', { type: 'text', id: 'cpnote', maxlength: '500', placeholder: 'Note, e.g. draft v2 validated', 'aria-label': 'Checkpoint note', style: { width: '100%' } });
  const pop = h('div', { class: 'pop', id: 'cppop', role: 'dialog', 'aria-label': 'Checkpoint', style: { right: '60px' } },
    h('h4', null, 'Your Last known good'),
    h('div', { class: 'hint' }, 'A checkpoint stores the content of every node in both repositories. Alarms list what changed after it. Older checkpoints stay listed.'),
    h('div', { class: 'cplist' }, cps.length ? cps.map(c => h('div', { class: 'cp' }, h('b', { class: 'mono' }, c.id.toUpperCase()), c.active ? ' (active) ' : ' ', h('span', { class: 'muted' }, fmtTime(c.created_at)), h('div', null, c.note || h('span', { class: 'muted' }, 'no note')))) : h('div', { class: 'muted' }, 'No checkpoint yet.')),
    READONLY ? h('div', { class: 'hint' }, 'Read-only snapshot') : [note, h('div', { style: { display: 'flex', gap: '8px', marginTop: '8px', justifyContent: 'flex-end' } },
      h('button', { class: 'btn', onclick: () => pop.remove() }, 'Close'),
      h('button', { class: 'btn primary', onclick: async () => { await createCheckpoint(note.value, null); pop.remove(); } }, 'Set checkpoint'))]);
  document.body.append(pop);
  if (!READONLY) note.focus();
}
async function createCheckpoint(note, at) {
  try {
    const r = await apiPost('/api/checkpoints', { note: note || '', at: at || null });
    S.alarms = r.alarms;
    const [cps, ev, pr, tri] = await Promise.all([apiGet('/api/checkpoints'), apiGet('/api/events'), apiGet('/api/project'), apiGet('/api/triage')]);
    S.checkpoints = cps; S.events = ev; S.project = pr; S.triage = tri;
    S.alarmSel = null; S.analysis = null;
    afterDataChange(true);
    toast('Checkpoint ' + r.checkpoint.id.toUpperCase() + ' set. ' + plural(S.alarms.groups.length, 'alarm group') + ' now.');
  } catch (e) { toast('Checkpoint not saved: ' + e.message); }
}

/* triage */
async function setTriage(type, id, state, note) {
  if (READONLY) return;
  try {
    const r = await apiPost('/api/triage', { target_type: type, target_id: id, state, note: note == null ? '' : note });
    const en = r.entry; if (!en.effective_state) { en.effective_state = en.state; en.outdated = false; }
    S.triage.entries[type + ':' + id] = en;
    afterDataChange(false);
    toast('Saved');
  } catch (e) { toast('Not saved: ' + e.message); }
}
function triageControl(type, id, opts) {
  opts = opts || {};
  const { state, outdated, entry } = effState(type, id);
  const cur = entry ? entry.state : 'unreviewed';
  const note = h('textarea', { rows: '2', maxlength: '2000', placeholder: 'Why? e.g. rerun planned for Friday', 'aria-label': 'Triage note', disabled: READONLY }, entry ? entry.note : '');
  note.value = entry ? entry.note || '' : '';
  const btn = (s, label) => h('button', { class: 'btn s-' + s, 'aria-pressed': String(cur === s && !outdated), disabled: READONLY, 'data-triage': s, title: READONLY ? 'Read-only snapshot' : null,
    onclick: () => setTriage(type, id, cur === s ? 'unreviewed' : s, note.value) }, label);
  const hist = entry && entry.history && entry.history.length > 1 ? h('details', { class: 'hint' }, h('summary', null, 'History (' + entry.history.length + ')'),
    entry.history.slice().reverse().map(x => h('div', null, fmtTime(x.at) + ' · ' + (STATUS[x.state] ? STATUS[x.state].word : 'Unreviewed') + (x.note ? ' · ' + x.note : '')))) : null;
  return h('div', { class: 'tri' },
    opts.noHeading ? null : h('h4', null, 'Triage'),
    h('div', { class: 'seg', role: 'group', 'aria-label': 'Triage state' }, btn('reviewed', '✓✓ Reviewed'), btn('needs_fixing', '✕ Needs fixing'), btn('ignored', '– Ignore')),
    outdated ? h('div', { class: 'hint' }, h('span', { class: 'chip outdated' }, '↻ Changed since you reviewed it'), ' It returned to Recheck; your earlier note is kept in the history.') : null,
    h('div', { class: 'nt' }, h('label', null, 'Note (kept in ' + HUB + '/triage.json)'), note,
      h('div', null, h('button', { class: 'btn', disabled: READONLY, onclick: () => setTriage(type, id, entry ? entry.state : 'unreviewed', note.value) }, 'Save note'))),
    h('div', { class: 'hint' }, type === 'node' ? 'If this node changes again, it returns to Recheck.' : 'If this finding changes, it returns to open.'), hist);
}
function afterDataChange(rebuild) {
  rebuildIndex();
  renderTopbar();
  if (rebuild) rebuildGraph({ fit: false }); else applyGraphState();
  renderOutline(); renderDetail(); renderTimeline();
  if (S.tab === 'alarms') renderAlarms(); else renderAlarmsLazy();
  renderChecks(); renderLinks();
}
function renderAlarmsLazy() { /* alarms view is rendered on demand */ }

/* ======================================================================
   OUTLINE
   ====================================================================== */
function sectionTree() {
  const secs = ((S.graph && S.graph.nodes) || []).filter(n => n.kind === 'section');
  const key = n => [(n.attrs && n.attrs.in_appendix) ? 1 : 0, (n.loc && n.loc.path === 'main.tex') ? 0 : 1, (n.loc && n.loc.path) || '', (n.loc && n.loc.line) || 0];
  secs.sort((a, b) => { const x = key(a), y = key(b); for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1; return 0; });
  return secs;
}
function descendants(id) {
  const seen = new Set([id]), q = [id];
  while (q.length) { const c = q.shift(); for (const e of IX.out.get(c) || []) if (e.kind === 'contains' && e.status !== 'rejected' && !seen.has(e.to)) { seen.add(e.to); q.push(e.to); } }
  return seen;
}
function renderOutline() {
  const box = clear($('#left'));
  const c = counts();
  const secs = sectionTree();
  box.append(h('div', { class: 'ol-head' }, h('div', { class: 'h' }, 'Paper outline'),
    h('div', { class: 'muted mono', style: { fontSize: '12px' } }, c.recheck + ' items to recheck'),
    h('label', null, h('input', { type: 'checkbox', checked: S.onlyRecheck, onchange: ev => { S.onlyRecheck = ev.target.checked; renderOutline(); } }), 'Only sections to recheck')));
  if (!secs.length) { box.append(h('div', { class: 'empty' }, S.loading ? 'Reading outline…' : 'No sections found. Check that your main .tex file uses \\section.')); return; }
  let appHead = false;
  for (const s of secs) {
    const desc = descendants(s.id);
    let re = 0, nf = 0;
    for (const d of desc) { const st = nodeStatus(d); if (st === 'recheck') re++; if (st === 'needs_fixing') nf++; }
    if (S.onlyRecheck && !re && !nf) continue;
    if (s.attrs && s.attrs.in_appendix && !appHead) { appHead = true; box.append(h('div', { class: 'ol-grp' }, 'Appendix')); }
    const indent = ((s.attrs && s.attrs.level) || 1) - 1;
    box.append(h('div', { class: 'ol-row', role: 'button', tabindex: '0', 'aria-selected': String(S.sel === s.id), 'aria-label': s.name + (re ? ', ' + re + ' to recheck' : ''), style: { paddingLeft: (12 + indent * 12) + 'px' },
      onclick: () => { setTab('graph'); selectNode(s.id); }, ondblclick: () => { S.rightCollapsed = false; setTab('graph'); selectNode(s.id); const pv = $('#pv-toggle'); if (pv) pv.click(); },
      onkeydown: ev => { if (ev.key === 'Enter') { setTab('graph'); selectNode(s.id); } else if (ev.key === 'ArrowDown' && ev.target.nextElementSibling) ev.target.nextElementSibling.focus(); else if (ev.key === 'ArrowUp' && ev.target.previousElementSibling) ev.target.previousElementSibling.focus(); } },
      h('span', { class: 'num' }, (s.attrs && s.attrs.number) || ''), h('span', { class: 'ttl' }, (s.attrs && s.attrs.title) || s.name),
      nf ? h('span', { class: 'cnt needs_fixing', 'aria-label': nf + ' need fixing' }, '✕ ' + nf) : null,
      re ? h('span', { class: 'cnt recheck', 'aria-label': re + ' to recheck' }, '↻ ' + re) : null));
  }
}

/* ======================================================================
   DETAIL PANEL
   ====================================================================== */
let detailToken = 0;
function evidenceFor(n) {
  const out = [], seen = new Set();
  const push = (ev, why) => { const k = ev.repo + ev.path + ev.line + why; if (!seen.has(k)) { seen.add(k); out.push({ ev, why }); } };
  for (const e of IX.all.get(n.id) || []) {
    if (e.kind === 'contains' || e.status === 'rejected') continue;
    const other = IX.node.get(e.from === n.id ? e.to : e.from);
    const a = e.from === n.id ? n.name : other.name, b = e.from === n.id ? other.name : n.name;
    const tag = e.status === 'proposed' ? ' (proposed)' : '';
    for (const ev of e.evidence || []) push(ev, a + ' ' + (EDGE_PHRASE[e.kind] || e.kind) + ' ' + b + tag);
  }
  for (const f of IX.findingsByNode.get(n.id) || []) for (const ev of f.evidence) push(ev, f.title);
  return out;
}
function nodeHeader(n) {
  const st = nodeStatus(n.id);
  const col = colorOf(n.layer);
  const mono = !['thesis', 'rq', 'section'].includes(n.kind);
  return h('div', null,
    h('div', { class: 'hd' },
      h('span', { class: 'gl', style: { borderColor: 'var(--layer-' + col + ')', background: 'var(--layer-' + col + '-t)' }, 'aria-hidden': 'true' }, KIND_GLYPH[n.kind] || '?'),
      h('div', { style: { flex: 1, minWidth: 0 } }, h('div', { class: 'nm' + (mono ? ' m' : '') }, n.name),
        h('div', { class: 'meta' }, KIND_LABEL[n.kind] || n.kind, ' · ' + layerName(n) + ' · ', h('span', { class: 'chip plain mono' }, n.repo), ' ',
          STATUS[st] && st !== 'none' ? chip(st) : null))),
    n.detail ? h('div', { class: 'muted', style: { margin: '2px 0' } }, n.detail) : null,
    h('div', { class: 'meta' }, h('button', { class: 'pathlink', title: 'Copy path', onclick: () => { try { navigator.clipboard.writeText(locStr(n)); toast('Copied ' + locStr(n)); } catch (e) { toast(locStr(n)); } } }, locStr(n)),
      READONLY ? null : h('a', { class: 'btn sm', title: 'Opens in your default editor if it supports file links', href: editorHref(n) }, 'Open in editor')));
}
function editorHref(n) {
  const r = (S.project.repos || []).find(x => x.id === n.repo);
  const p = r && n.loc && n.loc.path ? r.abs_path + '/' + n.loc.path : '';
  return p ? 'vscode://file' + encodeURI(p) + (n.loc.line ? ':' + n.loc.line : '') : '#';
}
function lineageSummary(n) {
  const L = lineage(n.id);
  const sortIds = m => [...m.entries()].sort((a, b) => a[1] - b[1] || (a[0] < b[0] ? -1 : 1));
  const list = (m, cls, label) => h('details', { class: 'lin ' + cls, open: m.size <= 8 && m.size > 0 },
    h('summary', null, label + ' ' + m.size),
    h('ul', null, sortIds(m).map(([id]) => { const x = IX.node.get(id); const st = nodeStatus(id); return h('li', null,
      h('button', { class: 'it', onclick: () => selectNode(id) }, (KIND_GLYPH[x.kind] || '') + ' ' + x.name), h('span', { class: 'muted', style: { fontSize: '11px' } }, layerName(x)), STATUS[st] && st !== 'none' && st !== 'confirmed' ? chip(st) : null); })));
  return h('section', null, h('h4', null, 'Lineage'),
    h('div', { class: 'seg', style: { marginBottom: '6px' } },
      h('button', { class: 'btn sm', onclick: () => setDir('up'), title: 'Highlight only what this rests on, down to the code and runs' }, 'Trace down'),
      h('button', { class: 'btn sm', onclick: () => setDir('down'), title: 'Highlight only what this supports, up to the thesis' }, 'Trace up'),
      h('button', { class: 'btn sm', onclick: () => setDir('both') }, 'Both')),
    list(L.up, 'up', '▲ Rests on'), list(L.down, 'down', '▼ Supports'));
}
function texRendered(lines) {
  return lines.map(l => l.replace(/%.*$/, '').replace(/\\(?:cite[a-z]*|ref|eqref|cref|autoref)\{([^}]*)\}/g, '[$1]').replace(/\\label\{[^}]*\}/g, '').replace(/\\(?:emph|textbf|textit|section|subsection|caption)\*?\{([^}]*)\}/g, '$1').replace(/\\(begin|end)\{[^}]*\}/g, '').replace(/~/g, ' ').replace(/\$([^$]*)\$/g, '$1')).filter(l => l.trim()).join('\n');
}
async function fillPreview(box, n, token) {
  const set = el => { if (token === detailToken) { clear(box).append(...el); } };
  const loc = n.loc || {};
  const ev = evidenceFor(n).filter(e => e.ev.path === loc.path && e.ev.repo === n.repo).map(e => e.ev.line);
  try {
    if (n.kind === 'reference') {
      const r = await getLines(n.repo, loc.path, loc.line || 1, (loc.line || 1) + 7);
      return set([h('div', { class: 'cap' }, n.repo + ':' + loc.path + ':' + r.start + '–' + (r.start + r.lines.length - 1)), codeBlock(r.lines, r.start, [loc.line], { word: 'Here' })]);
    }
    if (n.kind === 'asset' && /\.(png|jpe?g|svg)$/i.test(loc.path || '') && !READONLY) {
      const img = h('img', { src: apiUrl('/api/raw') + '?repo=' + encodeURIComponent(n.repo) + '&path=' + encodeURIComponent(loc.path), alt: n.name, style: { maxWidth: '100%', border: '1px solid var(--border)' } });
      img.onerror = () => { if (token === detailToken) clear(box).append(h('div', { class: 'hint' }, 'No image available. ' + loc.path + ' is not a bitmap or was not found.')); };
      return set([h('div', { class: 'cap' }, n.repo + ':' + loc.path), img]);
    }
    if (n.kind === 'asset') return set([h('div', { class: 'hint' }, 'No image available. ' + (loc.path || n.name) + ' is not a bitmap or was not found.')]);
    if (!loc.path) throw new Error('no file recorded');
    const paper = n.layer != null && n.layer <= 3 && loc.line;
    let a = 1, b = 30;
    if (paper) { a = loc.line; b = loc.end_line ? Math.min(loc.end_line, a + 59) : a + (n.kind === 'rq' ? 2 : 12); }
    const r = await getLines(n.repo, loc.path, a, b);
    if (r.binary) return set([h('div', { class: 'hint' }, 'Binary file; no text preview.')]);
    const rawTxt = r.lines;
    const cap = h('div', { class: 'cap' }, n.repo + ':' + loc.path + ':' + r.start + '–' + (r.start + r.lines.length - 1) + (paper ? '' : ' (file head)'));
    const code = codeBlock(r.lines, r.start, ev, { word: 'Here' });
    const wrap = h('div', null, cap, code);
    const els = [wrap];
    if (paper) {
      let rend = false;
      const tg = h('button', { class: 'btn sm', id: 'pv-toggle', style: { margin: '6px 0' }, onclick: () => { rend = !rend; clear(wrap).append(cap, rend ? h('div', { class: 'rendered' }, texRendered(rawTxt)) : code); tg.textContent = rend ? 'Show LaTeX' : 'Show rendered text'; } }, 'Show rendered text');
      els.push(tg);
    } else if (r.total && r.total > r.lines.length && !READONLY) {
      els.push(h('button', { class: 'btn sm', style: { marginTop: '6px' }, onclick: async ev => { ev.target.disabled = true; const all = await getLines(n.repo, loc.path, 1, 400); clear(wrap).append(h('div', { class: 'cap' }, n.repo + ':' + loc.path + ':1–' + all.lines.length), codeBlock(all.lines, 1, ev && [], {})); ev.target.remove(); } }, 'Show all ' + r.total + ' lines'));
    }
    set(els);
  } catch (e) {
    if (token === detailToken) clear(box).append(h('div', { class: 'hint err' }, 'Preview unavailable: ' + e.message + '. Evidence locations are still listed.'));
  }
}
async function fillDiff(box, n, token) {
  const entries = IX.alarm.get(n.id) || [];
  const mine = entries.find(a => a.role === 'changed');
  if (!mine) return;
  const btn = h('button', { class: 'btn sm', onclick: async () => {
    btn.disabled = true;
    try {
      const a = await apiGet('/api/analyze?group=' + encodeURIComponent(mine.group.id) + '&node=' + encodeURIComponent(n.id));
      const d = (a.diffs || []).find(x => x.node_id === n.id) || a.diffs[0];
      if (token !== detailToken) return;
      clear(box).append(h('div', { class: 'cap' }, d ? d.from_label + ' → ' + d.to_label : ''), d && !d.binary ? diffBlock(d.unified) : h('div', { class: 'hint' }, 'No text diff available for this file.'));
    } catch (e) { clear(box).append(h('div', { class: 'hint err' }, 'Diff unavailable: ' + e.message)); }
  } }, 'Show diff since checkpoint');
  box.append(btn);
}
function renderDetail() {
  const box = clear($('#r-detail'));
  const token = ++detailToken;
  if (!S.sel || !IX.node.has(S.sel)) {
    box.append(h('div', { class: 'empty' }, 'Select a node in the graph to see what it rests on, what it supports, and where the evidence is.'));
    return;
  }
  const n = IX.node.get(S.sel);
  const pv = h('div', null, h('div', { class: 'skel' }), h('div', { class: 'skel', style: { width: '70%' } }), h('div', { class: 'hint' }, 'Loading preview…'));
  const df = h('div', { style: { marginTop: '6px' } });
  const evs = evidenceFor(n);
  const alarmInfo = IX.alarm.get(n.id);
  box.append(h('div', { class: 'dt' }, nodeHeader(n),
    alarmInfo ? h('div', { class: 'hint' }, alarmInfo.map(a => (a.role === 'changed' ? 'Changed in ' : 'Downstream of ') + a.group.display + ' · ' + a.group.cause.short).join(' ; ')) : null,
    lineageSummary(n),
    h('section', null, h('h4', null, 'Preview'), pv, df),
    h('section', null, h('h4', null, 'Evidence'), evs.length ? evs.map(x => h('div', { class: 'ev' },
      h('button', { class: 'pathlink', onclick: () => { try { navigator.clipboard.writeText(x.ev.path + ':' + x.ev.line); } catch (e) { } toast('Copied ' + x.ev.path + ':' + x.ev.line); } }, x.ev.repo + ':' + x.ev.path + ':' + x.ev.line),
      h('div', { class: 'why' }, x.why), h('div', { class: 'q' }, x.ev.text))) : h('div', { class: 'hint' }, 'No evidence locations recorded for this node.')),
    triageControl('node', n.id)));
  fillPreview(pv, n, token);
  fillDiff(df, n, token);
}

/* ======================================================================
   TIMELINE
   ====================================================================== */
function repoRole(id) { const r = ((S.project && S.project.repos) || []).find(x => x.id === id); return r ? r.role : 'code'; }
function eventLane(ev) { return ev.kind === 'run' ? 2 : repoRole(ev.repo) === 'paper' ? 1 : 0; }
function cpTime() {
  const cp = S.checkpoints && S.checkpoints.checkpoints.find(c => c.active);
  if (!cp) return null;
  let best = null;
  for (const ev of (S.events && S.events.events) || []) {
    const r = cp.repos && cp.repos[ev.repo];
    if (r && ev.rev && r.rev === ev.rev && (!best || ev.time > best)) best = ev.time;
  }
  return best || cp.created_at;
}
function blastFor(ev) {
  const seeds = new Set();
  if (ev.changed_nodes && ev.changed_nodes.length) ev.changed_nodes.forEach(i => seeds.add(i));
  else for (const f of ev.files || []) { const id = 'file:' + ev.repo + '/' + f.path; if (IX.node.has(id)) seeds.add(id); }
  const all = new Set(seeds), q = [...seeds];
  while (q.length) { const c = q.shift(); for (const e of IX.in.get(c) || []) if (e.propagates && e.status !== 'rejected' && !all.has(e.from)) { all.add(e.from); q.push(e.from); } }
  return { seeds: seeds.size, nodes: [...all] };
}
function selectEvent(ev) {
  S.selEvent = ev.id; S.sel = null;
  const b = blastFor(ev);
  S.blast = { ev: ev.id, nodes: b.nodes, files: (ev.files || []).length, seeds: b.seeds };
  applyGraphState(); renderDetail(); renderOutline(); renderTimeline();
}
function renderTimeline() {
  clearTips();
  const box = clear($('#timeline'));
  const strip = clear($('#tlstrip'));
  strip.classList.add('hidden');
  if (!S.events || !S.project || box.classList.contains('hidden')) return;
  const evs = S.events.events || [];
  const W = box.clientWidth || 800;
  const head = h('div', { class: 'tl-head' }, h('b', { class: 'serif' }, 'Timeline'),
    h('span', { class: 'muted' }, '● commit  ◆ paper version  ▲ run'), h('span', { style: { flex: 1 } }));
  box.append(head);
  if (!evs.length) { box.append(h('div', { class: 'empty' }, 'No history found. Without git history, the timeline shows only paper versions and runs.')); return; }
  const cpT = cpTime();
  const times = evs.map(e => Date.parse(e.time)).concat(cpT ? [Date.parse(cpT)] : []);
  let t0 = Math.min(...times), t1 = Math.max(...times);
  const lkgT = cpT ? Date.parse(cpT) : null;
  if (S.zoomRange && lkgT) t0 = lkgT - (t1 - lkgT) * 0.08;
  const span = Math.max(t1 - t0, 3600e3), pad = span * 0.04;
  t0 -= pad; t1 = t0 + span + pad * 2;
  const L0 = 100, R0 = 120, top = 22;
  const x = t => L0 + (Date.parse(t) - t0) / (t1 - t0) * (W - L0 - R0);
  const laneY = l => top + 12 + l * 24;
  const NS = 'http://www.w3.org/2000/svg';
  const el = (tag, a, txt) => { const e = document.createElementNS(NS, tag); for (const k in a || {}) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; return e; };
  const svg = el('svg', { id: 'tlsvg', width: W, height: 130, role: 'group', 'aria-label': 'Commits, paper versions and runs over time' });
  // range shading and handles
  const last = evs.filter(e => e.kind !== 'worktree').reduce((m, e) => (!m || e.time > m.time ? e : m), null) || evs[evs.length - 1];
  const xNow = x(last.time);
  if (lkgT != null) {
    const xl = x(cpT);
    const after = evs.filter(e => e.after_checkpoint && e.kind === 'commit').length;
    svg.append(el('rect', { x: xl, y: top - 4, width: Math.max(0, xNow - xl), height: 84, fill: css('--amber-bg'), opacity: 0.9 }));
    svg.append(el('text', { x: (xl + xNow) / 2, y: top + 76, 'text-anchor': 'middle' }, after + ' commits · ' + counts().recheck + ' items to recheck'));
    svg.append(el('line', { x1: xl, x2: xl, y1: 4, y2: top + 82, stroke: css('--ink'), 'stroke-width': 2 }));
    const fw = 178, fx = Math.max(4, xl - fw);
    const flag = el('g'); flag.append(el('rect', { x: fx, y: 4, width: fw, height: 16, fill: css('--ink') }));
    const ft = el('text', { x: fx + 5, y: 16 }, 'Last known good · ' + (shortOfCp() || fmtDate(cpT))); ft.style.fill = css('--paper'); flag.append(ft); svg.append(flag);
  }
  svg.append(el('line', { x1: xNow, x2: xNow, y1: 4, y2: top + 82, stroke: css('--ink'), 'stroke-width': 2, 'stroke-dasharray': '4 3' }));
  const nowW = 104, nx = xNow;
  const ng = el('g'); ng.append(el('rect', { x: nx, y: 4, width: nowW, height: 16, fill: css('--surface'), stroke: css('--ink') }));
  const nt = el('text', { x: nx + 5, y: 16 }, 'Now · ' + (last.short || '')); nt.style.fill = css('--ink'); ng.append(nt); svg.append(ng);
  // lanes
  ['Commits', 'Paper versions', 'Runs'].forEach((nm, i) => {
    svg.append(el('line', { x1: L0, x2: W - R0, y1: laneY(i), y2: laneY(i), stroke: css('--border') }));
    const tx = el('text', { x: 8, y: laneY(i) + 4, class: 'lane' }, nm); svg.append(tx);
  });
  // axis ticks
  for (let i = 0; i <= 5; i++) {
    const t = t0 + (t1 - t0) * i / 5, xx = L0 + (W - L0 - R0) * i / 5;
    svg.append(el('line', { x1: xx, x2: xx, y1: top + 82, y2: top + 86, stroke: css('--border-strong') }));
    svg.append(el('text', { x: xx, y: top + 102, 'text-anchor': i === 0 ? 'start' : i === 5 ? 'end' : 'middle' }, new Date(t).toISOString().slice(0, 10)));
  }
  // marks
  const rowsUsed = [[-99, -99, -99], [-99, -99, -99], [-99, -99, -99]];
  const OFFS = [0, 8, -8];
  for (const ev of evs.slice().sort((p, q) => (p.time < q.time ? -1 : 1))) {
    const lane = eventLane(ev), cx = x(ev.time);
    let row = rowsUsed[lane].findIndex(lx => cx - lx >= 12);
    if (row < 0) row = rowsUsed[lane].indexOf(Math.min(...rowsUsed[lane]));
    rowsUsed[lane][row] = cx;
    const cy2 = laneY(lane) + OFFS[row];
    const after = ev.after_checkpoint || ev.kind === 'worktree';
    const sel = S.selEvent === ev.id;
    const attrs = { class: 'mark', tabindex: '0', role: 'button', 'aria-label': (ev.short || ev.kind) + ' ' + ev.subject + ', ' + (after ? 'after the checkpoint' : 'before the checkpoint'),
      fill: after ? css('--ink') : css('--surface'), stroke: sel ? css('--down') : css('--ink'), 'stroke-width': sel ? 3 : 1.5, 'stroke-dasharray': ev.kind === 'worktree' ? '2 2' : '' };
    let m;
    if (ev.kind === 'run') m = el('polygon', Object.assign({ points: [cx, cy2 - 6, cx + 6, cy2 + 5, cx - 6, cy2 + 5].join(' ') }, attrs));
    else if (lane === 1) m = el('polygon', Object.assign({ points: [cx, cy2 - 6, cx + 6, cy2, cx, cy2 + 6, cx - 6, cy2].join(' ') }, attrs));
    else m = el('circle', Object.assign({ cx, cy: cy2, r: 5 }, attrs));
    m.addEventListener('click', () => selectEvent(ev));
    m.addEventListener('keydown', k => { if (k.key === 'Enter' || k.key === ' ') { k.preventDefault(); selectEvent(ev); } });
    tip(m, () => (ev.short ? ev.short + ' ' : '') + ev.subject + '\n' + ev.repo + ' · ' + fmtTime(ev.time) + '\n' + plural((ev.files || []).length, 'file') + ' changed' + (ev.flags && ev.flags.length ? '\n? Low confidence' : ''));
    svg.append(m);
  }
  const tools = head;
  tools.append(
    h('button', { class: 'btn sm', onclick: () => { S.zoomRange = true; renderTimeline(); } }, 'Zoom to range'),
    h('button', { class: 'btn sm', onclick: () => { S.zoomRange = false; renderTimeline(); } }, 'Reset'));
  const se = S.selEvent && evs.find(e => e.id === S.selEvent);
  if (se) {
    tools.append(
      h('button', { class: 'btn sm', disabled: READONLY || se.kind !== 'commit', title: READONLY ? 'Read-only snapshot' : se.kind !== 'commit' ? 'Only commits can become a checkpoint' : 'Make this commit your Last known good (K)', onclick: () => setCheckpointAtEvent(se) }, 'Set as Last known good'),
      h('button', { class: 'btn sm', disabled: true, title: 'Viewing the graph at a past commit is not in this demo' }, 'Set as Now'));
  }
  if (S.blast && se) {
    strip.append(h('div', { class: 'tl-strip' }, h('span', null, 'Commit ' + (se.short || se.kind) + ': ' + plural(S.blast.files, 'file') + ' changed → ' + plural(S.blast.nodes.length, 'node') + ' affected.'),
      h('button', { class: 'linkbtn', onclick: () => { S.openGroups.add(se.id); S.alarmSel = null; setTab('alarms'); } }, 'Show in Alarms'),
      h('button', { class: 'linkbtn', onclick: clearSelection }, 'Clear')));
    strip.classList.remove('hidden');
  }
  box.append(svg);
}
function shortOfCp() {
  const cp = S.checkpoints && S.checkpoints.checkpoints.find(c => c.active); if (!cp) return null;
  const ids = Object.keys(cp.repos || {});
  const hits = [];
  for (const r of ids) { const ev = ((S.events && S.events.events) || []).find(e => e.repo === r && e.rev === cp.repos[r].rev); if (ev) hits.push(ev); }
  hits.sort((a, b) => (a.time < b.time ? 1 : -1));
  return hits[0] ? hits[0].short : cp.id.toUpperCase();
}
function setCheckpointAtEvent(ev) {
  if (READONLY || ev.kind !== 'commit') return;
  modal('Set Last known good', h('div', null, 'Make ' + ev.short + ' of repository “' + ev.repo + '” your Last known good? Other repositories use their current files. Alarms recompute against it; older checkpoints stay listed.'),
    [{ label: 'Cancel' }, { label: 'Set checkpoint', primary: true, fn: () => createCheckpoint('At ' + ev.short + ' ' + ev.subject, { [ev.repo]: ev.rev }) }]);
}

/* ======================================================================
   ALARMS
   ====================================================================== */
function alarmNodes(g) { return g.changed.map(c => ({ id: c.node_id, role: 'changed', entry: c })).concat(g.downstream.map(d => ({ id: d.node_id, role: 'downstream', entry: d }))); }
function reasonFor(g, a) {
  if (a.role === 'changed') return (a.entry.change === 'added' ? 'New since the checkpoint' : 'Its own content changed') + ' in ' + g.cause.short + '.';
  const e = IX.edge.get(a.entry.via);
  let s = '';
  if (e) { const f = nodeLabel(e.from), t = nodeLabel(e.to); s = f + ' ' + (EDGE_PHRASE[e.kind] || e.kind) + ' ' + t + (e.status === 'approved' ? ' (link approved by you)' : '') + ', which ' + (a.entry.depth > 1 ? 'is itself downstream of' : 'changed in') + ' ' + (a.entry.depth > 1 ? 'the change in ' : '') + g.cause.short + '.'; }
  if (a.entry.output_identical === true) s += ' Producer changed; output bytes unchanged (not regenerated, or regenerated identically).';
  return s;
}
function chainFor(g, nodeId) {
  const steps = [];
  const chg = new Set(g.changed.map(c => c.node_id));
  const down = new Map(g.downstream.map(d => [d.node_id, d]));
  let cur = nodeId, guard = 0;
  while (cur && guard++ < 60) {
    if (chg.has(cur)) { steps.push({ id: cur, edge: null }); break; }
    const d = down.get(cur); if (!d) break;
    const e = IX.edge.get(d.via);
    steps.push({ id: cur, edge: e });
    cur = e ? e.to : null;
  }
  return steps.reverse();
}
function stateCounts(items) {
  const c = { unreviewed: 0, reviewed: 0, needs_fixing: 0, ignored: 0 };
  for (const id of items) { const s = effState('node', id).state; c[s] = (c[s] || 0) + 1; }
  return c;
}
function renderAlarms() {
  const v = clear($('#v-alarms'));
  if (!S.alarms) { v.append(h('div', { class: 'empty' }, 'Tracing changes…')); return; }
  const A = S.alarms;
  if (!A.checkpoint) { v.append(h('div', { class: 'pad' }, h('h2', { class: 't' }, 'Alarms'), h('div', { class: 'muted' }, 'Set a Last known good checkpoint on the timeline to list what changed after it.'))); renderAlarmPanel(); return; }
  const allIds = new Set(); A.groups.forEach(g => alarmNodes(g).forEach(a => allIds.add(a.id)));
  const sc = stateCounts(allIds);
  const f = S.alarmFilter;
  const fb = (key, label, n) => h('button', { class: 'btn sm', 'aria-pressed': String(f === key), onclick: () => { S.alarmFilter = key; renderAlarms(); } }, label + (n != null ? ' ' + n : ''));
  v.append(
    h('div', { class: 'pad', style: { paddingBottom: '0' } }, h('h2', { class: 't' }, 'To recheck since ' + (A.checkpoint.note || A.checkpoint.id.toUpperCase())),
      h('div', { class: 'muted' }, plural(allIds.size, 'item') + ' in ' + plural(A.groups.length, 'group') + '. Based on content, so a change that leaves a file identical to the checkpoint raises nothing.')),
    h('div', { class: 'toolbar', role: 'group', 'aria-label': 'Filter by triage state' }, fb('all', 'All', allIds.size), fb('unreviewed', '↻ Recheck', sc.unreviewed), fb('needs_fixing', '✕ Needs fixing', sc.needs_fixing), fb('reviewed', '✓✓ Reviewed', sc.reviewed), fb('ignored', '– Ignored', sc.ignored),
      A.groups.some(lowConf) ? fb('lowconf', '? Low confidence only') : null));
  const body = h('div', { class: 'pad', style: { flex: 1 } });
  let shown = 0;
  if (!A.groups.length) body.append(h('div', { class: 'empty' }, 'Nothing to recheck since ' + A.checkpoint.id.toUpperCase() + '. Everything downstream of your changes was reviewed or unaffected.'));
  A.groups.forEach((g, gi) => {
    if (!S.alarmsInit && gi < 3) S.openGroups.add(g.id);
    if (f === 'lowconf' && !lowConf(g)) return;
    const rows = alarmNodes(g).filter(a => f === 'all' || f === 'lowconf' || effState('node', a.id).state === f);
    if (!rows.length && f !== 'all' && f !== 'lowconf') return;
    shown++;
    const open = S.openGroups.has(g.id);
    const head = h('div', { class: 'gh', role: 'button', tabindex: '0', 'aria-expanded': String(open), onclick: ev => { if (ev.target.closest('button')) return; open ? S.openGroups.delete(g.id) : S.openGroups.add(g.id); renderAlarms(); },
      onkeydown: ev => { if (ev.key === ' ' || ev.key === 'Enter') { ev.preventDefault(); open ? S.openGroups.delete(g.id) : S.openGroups.add(g.id); renderAlarms(); } } },
      h('span', null, open ? '▾' : '▸'), h('span', { class: 'disp' }, g.display),
      h('span', { class: 'sub' }, h('b', { class: 'mono' }, g.cause.short), ' · ', g.cause.subject, h('span', { class: 'muted' }, ' · ' + g.cause.kind + ' in ' + g.cause.repo + ' · ' + fmtDate(g.cause.time) + ' · ' + (g.cause.files || []).join(', '))),
      lowConf(g) ? chip('lowconf') : null,
      h('span', { class: 'cnt recheck', 'aria-label': alarmNodes(g).length + ' to recheck' }, '↻ ' + alarmNodes(g).length),
      h('button', { class: 'btn sm', onclick: () => analyzeGroup(g) }, 'Analyze'),
      h('button', { class: 'btn sm', onclick: () => { S.sel = null; S.blast = { ev: g.id, nodes: alarmNodes(g).map(a => a.id), files: (g.cause.files || []).length, seeds: g.changed.length }; setTab('graph'); applyGraphState(); renderDetail(); } }, 'Show in graph'));
    const grp = h('div', { class: 'group' }, head);
    if (open) {
      if (lowConf(g)) for (const fl of g.flags) grp.append(h('div', { class: 'row', style: { cursor: 'default' } }, chip('lowconf'), h('div', { class: 'main' }, fl.text + ' ' + PRODUCT + ' is not sure this affects the nodes below.')));
      for (const r of rows) {
        const st = nodeStatus(r.id), n = IX.node.get(r.id) || { name: r.id, layer: null, loc: {}, kind: '' };
        const sel = S.alarmSel && S.alarmSel.gid === g.id && S.alarmSel.nid === r.id;
        grp.append(h('div', { class: 'row', role: 'button', tabindex: '0', 'aria-selected': String(!!sel), 'data-node': r.id,
          onclick: () => { S.alarmSel = { gid: g.id, nid: r.id }; S.analysis = null; renderAlarms(); },
          onkeydown: ev => { if (ev.key === 'Enter') { S.alarmSel = { gid: g.id, nid: r.id }; S.analysis = null; renderAlarms(); } } },
          chip(STATUS[st] && st !== 'confirmed' && st !== 'none' ? st : 'recheck'),
          h('div', { class: 'main' }, h('div', null, h('span', { class: 'lbl' }, n.name), h('span', { class: 'muted' }, ' · ' + layerName(n) + (r.role === 'changed' ? ' · changed' : ' · downstream (depth ' + r.entry.depth + ')')), ' ', h('span', { class: 'mono muted' }, locStr(n))), h('div', { class: 'why' }, reasonFor(g, r))),
          h('button', { class: 'btn sm', onclick: ev => { ev.stopPropagation(); showInGraph(r.id); } }, 'Show in graph')));
      }
      for (const rm of g.removed || []) grp.append(h('div', { class: 'row', style: { cursor: 'default' } }, chip('recheck'), h('div', { class: 'main' }, h('span', { class: 'lbl' }, rm.name || rm.node_id), h('div', { class: 'why' }, 'Removed since the checkpoint (' + (rm.path || '') + ').'))));
    }
    body.append(grp);
  });
  S.alarmsInit = true;
  if (A.groups.length && !shown) body.append(h('div', { class: 'empty' }, 'No items match this filter.'));
  v.append(body);
  renderAlarmPanel();
}
function analyzeGroup(g) {
  const nodes = alarmNodes(g);
  const pick = g.downstream.length ? g.downstream[g.downstream.length - 1].node_id : g.changed.length ? g.changed[0].node_id : null;
  if (!pick) return;
  S.alarmSel = { gid: g.id, nid: pick }; S.analysis = null;
  renderAlarms();
  runAnalyze();
}
async function runAnalyze() {
  if (!S.alarmSel) return;
  const key = S.alarmSel.gid + '|' + S.alarmSel.nid;
  S.analysis = { key, loading: true };
  renderAlarmPanel();
  try {
    const a = await apiGet('/api/analyze?group=' + encodeURIComponent(S.alarmSel.gid) + '&node=' + encodeURIComponent(S.alarmSel.nid));
    if (S.analysis && S.analysis.key === key) S.analysis = { key, data: a };
  } catch (e) { if (S.analysis && S.analysis.key === key) S.analysis = { key, error: e.message }; }
  renderAlarmPanel();
}
function renderAlarmPanel() {
  const box = clear($('#r-alarm'));
  const sel = S.alarmSel;
  const g = sel && S.alarms && S.alarms.groups.find(x => x.id === sel.gid);
  if (!g) { box.append(h('div', { class: 'empty' }, 'Select an item in the list to see why it needs a recheck.')); return; }
  const n = IX.node.get(sel.nid);
  const steps = chainFor(g, sel.nid);
  const dt = h('div', { class: 'dt' }, h('h2', { class: 't' }, 'Why this needs a recheck'),
    h('div', { class: 'muted', style: { marginBottom: '8px' } }, n ? n.name : sel.nid),
    h('ol', { class: 'chain', 'aria-label': 'Chain from the change to this item' },
      h('li', null, h('div', { class: 'origin' }, g.cause.kind), h('div', null, h('b', { class: 'mono' }, g.cause.short), ' ' + g.cause.subject), h('div', { class: 'muted mono' }, g.cause.repo + ' · ' + (g.cause.files || []).join(', '))),
      steps.map((s, i) => { const x = IX.node.get(s.id) || { name: s.id, loc: {} }; const ev0 = s.edge && s.edge.evidence && s.edge.evidence[0];
        return h('li', null, h('div', { class: 'origin' }, s.edge ? (s.edge.status === 'approved' ? 'Approved' : 'Direct') + ' · ' + (EDGE_PHRASE[s.edge.kind] || s.edge.kind) : 'changed'),
          h('div', null, h('button', { class: 'linkbtn', onclick: () => showInGraph(s.id) }, x.name), h('span', { class: 'muted' }, ' · ' + layerName(x))),
          h('div', { class: 'muted mono' }, ev0 ? ev0.path + ':' + ev0.line : locStr(x))); })));
  box.append(dt);
  dt.append(h('div', { style: { margin: '12px 0' } }, h('button', { class: 'btn', onclick: runAnalyze, disabled: !!(S.analysis && S.analysis.loading) }, S.analysis && S.analysis.data ? 'Analyze again' : 'Analyze')));
  const an = S.analysis && S.analysis.key === sel.gid + '|' + sel.nid ? S.analysis : null;
  if (an) {
    const sec = h('section', { 'aria-label': 'Analyzer' }, h('h3', { class: 't' }, 'Analyzer'));
    if (an.loading) sec.append(h('div', { class: 'hint' }, 'Tracing…'));
    else if (an.error) sec.append(h('div', { class: 'hint err' }, 'Analysis unavailable: ' + an.error));
    else {
      const a = an.data;
      sec.append(h('div', { class: 'hint' }, 'Chain: ' + a.chain.nodes.map(nodeLabel).join(' → ')));
      if (!a.diffs.length) sec.append(h('div', { class: 'hint' }, 'No text diff is available for the changed node.'));
      for (const d of a.diffs) sec.append(h('div', { style: { marginBottom: '8px' } }, h('div', { class: 'cap' }, d.repo + ':' + d.path + ' · ' + d.from_label + ' → ' + d.to_label + (d.truncated ? ' (cut)' : '')), d.binary ? h('div', { class: 'hint' }, 'Binary file; no text diff.') : diffBlock(d.unified)));
      sec.append(h('p', null, a.explanation));
      sec.append(h('button', { class: 'btn', 'aria-disabled': 'true', style: { color: 'var(--muted)' }, title: 'The deterministic analyzer above is all this demo uses.', onclick: async () => {
        try { await apiPost('/api/ask', { group_id: a.group_id, node_id: a.node_id }); } catch (e) { toast(READONLY ? 'Not available in this demo' : e.message); } } }, a.ai && a.ai.label ? a.ai.label : 'Ask Claude why — not available in this demo'));
    }
    dt.append(sec);
  }
  dt.append(triageControl('node', sel.nid));
}

/* ======================================================================
   CHECKS
   ====================================================================== */
const CHIP_FOR = { reference_unmatched: 'unmatched', main_appendix_mismatch: 'mismatch', untraced_number: 'nottraced', figure_without_provenance: 'nottraced' };
const ROLE_HEAD = { main: 'In the main text', appendix: 'In the appendix', bib_entry: 'In the reference record', config: 'In the code', result: 'In the result file', run_record: 'In the run record' };
function findingStatusChip(f) {
  const t = effState('finding', f.id);
  if (t.state === 'reviewed' || t.state === 'needs_fixing' || t.state === 'ignored') return chip(t.state);
  return CHIP_FOR[f.check] ? chip(CHIP_FOR[f.check]) : h('span', { class: 'chip plain' }, f.severity === 'warning' ? '! Warning' : 'i Info');
}
function filteredFindings() {
  if (!S.findings) return [];
  const F = S.fFilter, q = (F.q || '').toLowerCase();
  return S.findings.findings.filter(f => {
    if (F.kind && f.check !== F.kind) return false;
    const st = effState('finding', f.id).state;
    if (F.state === 'open' && st !== 'unreviewed') return false;
    if (F.state && F.state !== 'open' && st !== F.state) return false;
    if (q && !(f.message + ' ' + f.title + ' ' + f.id).toLowerCase().includes(q)) return false;
    return true;
  });
}
function renderChecks() {
  const v = clear($('#v-checks'));
  if (!S.findings) { v.append(h('div', { class: 'empty' }, 'Running checks…')); return; }
  const all = S.findings.findings, shown = filteredFindings();
  const F = S.fFilter;
  const na = S.findings.checks.filter(c => c.status === 'not_applicable');
  v.append(
    h('div', { class: 'pad', style: { paddingBottom: '0' } }, h('h2', { class: 't' }, 'Checks'), h('div', { class: 'muted' }, plural(all.length, 'finding') + '. Each one links to the text that caused it.')),
    h('div', { class: 'toolbar' },
      h('select', { 'aria-label': 'Kind', onchange: ev => { F.kind = ev.target.value; renderChecks(); } }, h('option', { value: '' }, 'All kinds'), S.findings.checks.map(c => h('option', { value: c.check, selected: F.kind === c.check }, c.title))),
      h('select', { 'aria-label': 'Status', onchange: ev => { F.state = ev.target.value; renderChecks(); } }, [['', 'All'], ['open', 'Open'], ['reviewed', 'Reviewed'], ['needs_fixing', 'Needs fixing'], ['ignored', 'Ignored']].map(o => h('option', { value: o[0], selected: F.state === o[0] }, o[1]))),
      h('input', { type: 'search', placeholder: 'Search findings', 'aria-label': 'Search findings', value: F.q || '', oninput: ev => { F.q = ev.target.value; renderChecks(); const i = $('#v-checks input[type=search]'); i.focus(); i.setSelectionRange(F.q.length, F.q.length); } }),
      h('span', { style: { flex: 1 } }),
      READONLY ? null : h('a', { class: 'btn', href: apiUrl('/api/export'), download: '', title: 'Saves a local HTML file you can share. It includes the evidence shown here.' }, 'Export report (HTML)')));
  const body = h('div', { class: 'pad', style: { flex: 1 } });
  const det = h('details', { style: { marginBottom: '12px' } }, h('summary', { class: 'muted' }, 'Status of all ' + S.findings.checks.length + ' checks'),
    h('table', { class: 'tbl' }, S.findings.checks.map(c => h('tr', null, h('td', null, c.title), h('td', { class: 'mono' }, c.status === 'ran' ? 'Ran · ' + plural(c.count, 'finding') : c.status === 'not_checked' ? 'Not checked' : 'Not applicable' + (c.note ? ' (' + c.note + ')' : '')), h('td', { class: 'muted' }, c.status === 'ran' || c.status === 'not_checked' ? c.note : '')))));
  body.append(det);
  for (const c of S.findings.checks.filter(c => c.status === 'not_checked')) body.append(h('div', { class: 'muted', style: { marginBottom: '8px' } }, 'References not checked online. ' + (c.note || '')));
  if (!all.length) body.append(h('div', { class: 'empty' }, na.length ? 'No findings from the checks that ran. ' + plural(na.length, 'check') + ' not applicable to this project.' : 'No findings. All checks passed on this scan. This does not guarantee the paper is correct.'));
  else if (!shown.length) body.append(h('div', { class: 'empty' }, 'No findings match this filter.'));
  for (const f of shown) {
    body.append(h('div', { class: 'card', role: 'button', tabindex: '0', 'aria-selected': String(S.findSel === f.id), 'data-finding': f.id, onclick: () => openFinding(f.id), onkeydown: ev => { if (ev.key === 'Enter') openFinding(f.id); } },
      h('div', { class: 'kind' }, f.title), h('div', null, f.message),
      h('div', { class: 'locs' }, f.evidence.map(e => e.path + ':' + e.line).join('  ·  ')),
      h('div', { class: 'acts' }, findingStatusChip(f), h('button', { class: 'btn sm', onclick: ev => { ev.stopPropagation(); openFinding(f.id); } }, 'Open evidence'))));
  }
  v.append(body);
  renderCheckPanel();
}
function openFinding(id) { S.findSel = id; layoutMain(); renderChecks(); }
async function evidenceColumn(box, evs, head) {
  box.append(h('div', { class: 'ph' }, head));
  for (const e of evs) {
    const holder = h('div', null, h('div', { class: 'cap' }, e.repo + ':' + e.path + ':' + e.line));
    box.append(holder);
    try {
      const r = await getLines(e.repo, e.path, Math.max(1, e.line - 3), e.line + 3);
      holder.append(codeBlock(r.lines, r.start, [e.line], { word: 'Here', label: e.path }));
    } catch (err) { holder.append(codeBlock([e.text], e.line, [e.line], { word: 'Here', label: e.path })); }
  }
}
function renderCheckPanel() {
  const box = clear($('#r-check'));
  const f = S.findings && S.findings.findings.find(x => x.id === S.findSel);
  if (!f) return;
  const evs = f.evidence;
  const left = h('div'), right = h('div');
  const two = evs.length === 2 && evs[0].role !== evs[1].role;
  const leftHead = (ROLE_HEAD[evs[0].role]) || 'In the paper';
  evidenceColumn(left, two ? [evs[0]] : evs, leftHead);
  if (two) evidenceColumn(right, [evs[1]], ROLE_HEAD[evs[1].role] || 'In the source');
  else {
    const d = f.details || {};
    right.append(h('div', { class: 'ph' }, f.check === 'reference_unmatched' ? 'In the offline lookup record' : 'What was found'));
    const rows = f.check === 'reference_unmatched' && d.lookup ? Object.entries(d.lookup).map(([k, v]) => [k, v == null ? 'none' : typeof v === 'object' ? JSON.stringify(v) : String(v)]) : Object.entries(d).map(([k, v]) => [k, typeof v === 'object' ? JSON.stringify(v) : String(v)]);
    right.append(rows.length ? h('table', { class: 'tbl' }, rows.map(r => h('tr', null, h('td', { class: 'mono muted' }, r[0]), h('td', { class: 'mono' }, r[1])))) : h('div', { class: 'hint' }, 'No further record for this finding.'));
  }
  box.append(h('div', { class: 'dt' },
    h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: '8px' } }, h('h2', { class: 't' }, f.title), h('button', { class: 'btn sm', onclick: () => { S.findSel = null; layoutMain(); renderChecks(); } }, 'Close  Esc')),
    h('p', null, f.message), findingStatusChip(f),
    h('div', { class: 'sbs', style: { marginTop: '12px' } }, left, right),
    h('div', { class: 'hint', style: { marginTop: '10px' } }, h('b', null, 'What was compared: '), f.message),
    f.check === 'reference_unmatched' ? h('div', { class: 'hint' }, 'A match depends on the sources searched. A reference that is real but missing from them will also appear here.') : null,
    (f.nodes || []).length ? h('div', { style: { marginTop: '8px' } }, 'Graph nodes: ', f.nodes.map(id => h('button', { class: 'btn sm', style: { marginRight: '4px' }, onclick: () => showInGraph(id) }, nodeLabel(id) + ' → graph'))) : null,
    triageControl('finding', f.id)));
}

/* ======================================================================
   LINKS
   ====================================================================== */
function linkEdges() { return ((S.graph && S.graph.edges) || []).filter(e => e.kind === 'value_match' || e.status === 'proposed'); }
function alarmNodeSet() { const s = new Set(); if (S.alarms) for (const g of S.alarms.groups) alarmNodes(g).forEach(a => s.add(g.id + '|' + a.id)); return s; }
async function decideLink(edgeId, decision, silent) {
  if (READONLY) return;
  const before = alarmNodeSet();
  try {
    const r = await apiPost('/api/links/decide', { edge_id: edgeId, decision });
    S.alarms = r.alarms;
    const i = S.graph.edges.findIndex(e => e.id === edgeId); if (i >= 0) S.graph.edges[i] = r.edge;
    S.triage = await apiGet('/api/triage');
    S.project = await apiGet('/api/project');
    afterDataChange(true);
    const after = alarmNodeSet(); let d = 0; for (const x of after) if (!before.has(x)) d++; for (const x of before) if (!after.has(x)) d++;
    if (!silent) toast('Link ' + (decision === 'approved' ? 'approved' : decision === 'rejected' ? 'rejected' : 'restored') + '. ' + plural(d, 'alarm') + ' updated.', decision === 'proposed' ? null : () => decideLink(edgeId, 'proposed'));
  } catch (e) { toast('Not saved: ' + e.message); }
}
function renderLinks() {
  const v = clear($('#v-links'));
  if (!S.graph) return;
  const f = S.linkFilter;
  const all = linkEdges();
  const rows = all.filter(e => f === 'all' ? true : e.status === f);
  const nPending = all.filter(e => e.status === 'proposed').length;
  const fb = (key, label, n) => h('button', { class: 'btn sm', 'aria-pressed': String(f === key), onclick: () => { S.linkFilter = key; S.linkChecked.clear(); renderLinks(); } }, label + ' ' + n);
  const checked = [...S.linkChecked].filter(id => rows.some(e => e.id === id));
  v.append(
    h('div', { class: 'pad', style: { paddingBottom: '0' } }, h('h2', { class: 't' }, 'Proposed links'),
      h('div', { class: 'muted' }, PRODUCT + ' suggests these connections from names, text and code references. They affect nothing until you approve them.')),
    h('div', { class: 'toolbar' }, fb('proposed', 'Proposed', nPending), fb('approved', 'Approved', all.filter(e => e.status === 'approved').length), fb('rejected', 'Rejected', all.filter(e => e.status === 'rejected').length), fb('all', 'All', all.length),
      h('span', { style: { flex: 1 } }),
      checked.length && !READONLY ? [h('button', { class: 'btn sm', onclick: async () => { for (const id of checked) await decideLink(id, 'approved', true); S.linkChecked.clear(); toast('Approved ' + checked.length + '.'); } }, 'Approve ' + checked.length),
        h('button', { class: 'btn sm', onclick: async () => { for (const id of checked) await decideLink(id, 'rejected', true); S.linkChecked.clear(); toast('Rejected ' + checked.length + '.'); } }, 'Reject ' + checked.length)] : null));
  const body = h('div', { class: 'pad', style: { flex: 1 } });
  if (!rows.length) body.append(h('div', { class: 'empty' }, f === 'proposed' ? 'No proposed links. Every link in the graph was found directly in your files.' : 'No links in this list.'));
  else body.append(h('table', { class: 'tbl' }, h('thead', null, h('tr', null, h('th', null, ''), h('th', null, 'From'), h('th', null, ''), h('th', null, 'To'), h('th', null, 'How it was found'), h('th', null, 'Why'), h('th', null, 'Evidence'), h('th', null, 'Status / actions'))),
    h('tbody', null, rows.map(e => {
      const a = IX.node.get(e.from), b = IX.node.get(e.to);
      const ev0 = (e.evidence || [])[0];
      const nodeCell = n => h('td', null, h('div', { class: 'lbl' }, n ? n.name : '?'), h('div', { class: 'muted' }, n ? layerName(n) : ''), h('div', { class: 'mono muted' }, n ? locStr(n) : ''));
      return h('tr', { class: S.linkSel === e.id ? 'sel' : '', 'data-edge': e.id, tabindex: '0', onkeydown: k => { if (k.key === 'Enter') { S.linkSel = e.id; layoutMain(); renderLinks(); } } },
        h('td', null, h('input', { type: 'checkbox', 'aria-label': 'Select link', disabled: READONLY, checked: S.linkChecked.has(e.id), onchange: ev => { ev.target.checked ? S.linkChecked.add(e.id) : S.linkChecked.delete(e.id); renderLinks(); } })),
        nodeCell(a), h('td', null, '→'), nodeCell(b),
        h('td', null, e.kind === 'value_match' ? 'Heuristic: matching name' : 'Heuristic'),
        h('td', { style: { maxWidth: '220px' } }, e.reason || ''),
        h('td', null, ev0 ? h('button', { class: 'pathlink', onclick: () => { S.linkSel = e.id; layoutMain(); renderLinks(); } }, ev0.path + ':' + ev0.line) : ''),
        h('td', null, e.status === 'proposed' ? chip('proposed') : e.status === 'approved' ? h('span', { class: 'chip reviewed' }, '\u2713 Approved') : chip('ignored'), ' ',
          e.status === 'proposed' ? [h('button', { class: 'btn sm', disabled: READONLY, onclick: () => decideLink(e.id, 'approved') }, 'Approve'), ' ', h('button', { class: 'btn sm', disabled: READONLY, onclick: () => decideLink(e.id, 'rejected') }, 'Reject')]
            : [h('span', { class: 'muted' }, e.status === 'approved' ? 'Approved' : 'Rejected'), ' ', h('button', { class: 'btn sm', disabled: READONLY, onclick: () => decideLink(e.id, 'proposed') }, e.status === 'rejected' ? 'Restore' : 'Undo')]));
    }))));
  v.append(body);
  renderLinkPanel();
}
function renderLinkPanel() {
  const box = clear($('#r-link'));
  const e = S.linkSel && IX.edge.get(S.linkSel);
  if (!e) return;
  const end = async (id, label) => {
    const n = IX.node.get(id); const col = h('div');
    col.append(h('div', { class: 'ph' }, label + ': ' + (n ? n.name : id)));
    const evs = (e.evidence || []).filter(x => n && x.repo === n.repo && x.path === (n.loc && n.loc.path));
    for (const x of evs) {
      col.append(h('div', { class: 'cap' }, x.repo + ':' + x.path + ':' + x.line));
      try { const r = await getLines(x.repo, x.path, Math.max(1, x.line - 2), x.line + 2); col.append(codeBlock(r.lines, r.start, [x.line], { word: 'Here' })); } catch (er) { col.append(codeBlock([x.text], x.line, [x.line], { word: 'Here' })); }
    }
    if (!evs.length) col.append(h('div', { class: 'hint' }, 'No evidence line recorded at this end.'));
    return col;
  };
  const a = h('div'), b = h('div');
  end(e.from, 'From').then(c => a.append(c)); end(e.to, 'To').then(c => b.append(c));
  box.append(h('div', { class: 'dt' }, h('div', { style: { display: 'flex', justifyContent: 'space-between' } }, h('h2', { class: 't' }, 'Link evidence'), h('button', { class: 'btn sm', onclick: () => { S.linkSel = null; layoutMain(); renderLinks(); } }, 'Close  Esc')),
    h('p', null, e.reason || ''), h('div', { class: 'sbs' }, a, b),
    h('div', { style: { marginTop: '12px', display: 'flex', gap: '8px' } }, h('button', { class: 'btn', onclick: () => showInGraph(e.from) }, 'Preview in graph'),
      e.status === 'proposed' ? [h('button', { class: 'btn primary', disabled: READONLY, onclick: () => decideLink(e.id, 'approved') }, 'Approve'), h('button', { class: 'btn', disabled: READONLY, onclick: () => decideLink(e.id, 'rejected') }, 'Reject')] : null)));
}

/* ======================================================================
   PICKER / SCAN
   ====================================================================== */
function recentProjects() { try { return JSON.parse(localStorage.getItem('lemmata.recent') || '[]'); } catch (e) { return []; } }
function rememberProject() {
  if (!S.project || READONLY) return;
  const rec = recentProjects().filter(r => r.root !== S.project.root);
  rec.unshift({ name: S.project.name, root: S.project.root, at: new Date().toISOString() });
  try { localStorage.setItem('lemmata.recent', JSON.stringify(rec.slice(0, 5))); } catch (e) { }
}
function openPicker(state) {
  S.showPicker = true;
  const pk = $('#picker'); pk.classList.remove('hidden');
  const st = state || {};
  const root = S.project ? S.project.root : '';
  const rec = recentProjects();
  const c = counts();
  const col = h('div', { class: 'col' },
    h('h1', null, 'Open a project'),
    h('div', { class: 'sub' }, PRODUCT + ' reads your paper, code and run logs on this computer. Nothing is uploaded.'),
    h('div', { class: 'cardp' }, h('h3', null, 'Project folder'),
      h('input', { type: 'text', id: 'pk-path', value: root, readonly: true, 'aria-label': 'Project folder', placeholder: '/path/to/your/paper-repo' }),
      h('div', { class: 'hint' }, 'This session is serving the folder above. A browser cannot browse folders, so to open another one run ', h('code', { class: 'mono' }, 'lemmata open /path/to/folder'), ' in a terminal. Paste the folder path that contains your .tex files and code.')),
    h('div', { class: 'cardp' }, h('h3', null, 'Bundled sample'), h('div', { class: 'muted' }, 'A small ML paper with planted inconsistencies, for trying ' + PRODUCT + '.'),
      h('div', { class: 'hint' }, 'Start it with ', h('code', { class: 'mono' }, 'lemmata demo'), '.')),
    h('div', { class: 'cardp' }, h('h3', null, 'Recent projects'), rec.length ? rec.map(r => h('div', null, h('b', null, r.name), ' ', h('span', { class: 'mono muted' }, r.root), h('div', { class: 'hint' }, 'last scanned ' + fmtTime(r.at)))) : h('div', { class: 'muted' }, 'No recent projects.')),
    st.running ? h('div', { class: 'cardp' }, h('div', { 'aria-live': 'polite' }, 'Scanning… all seven steps run together in one pass.'), h('div', { class: 'bar', style: { marginTop: '8px' } }, h('i')),
      h('ol', { class: 'steps' }, ['Reading LaTeX sources', 'Reading references', 'Reading code and result files', 'Reading git history', 'Reading run logs', 'Building the graph', 'Running checks'].map(s => h('li', null, h('span', { class: 'mono' }, '◐ Running'), s)))) : null,
    st.done ? h('div', { class: 'cardp' }, h('ol', { class: 'steps' }, ['Reading LaTeX sources', 'Reading references', 'Reading code and result files', 'Reading git history', 'Reading run logs', 'Building the graph', 'Running checks'].map(s => h('li', null, h('span', { class: 'mono' }, '✓ Done'), s))),
      h('div', { class: 'mono muted' }, plural(S.project.counts.nodes, 'node') + ' · ' + plural(S.project.counts.edges, 'edge') + ' · ' + plural(S.project.counts.events, 'event')),
      h('p', null, 'Scan finished in ' + st.secs + ' s. ' + plural(c.recheck, 'item') + ' to recheck, ' + plural(c.openF, 'finding') + ', ' + plural(c.prop, 'proposed link') + ' to review.')) : null,
    st.error ? h('div', { class: 'err', role: 'alert' }, '✕ Error: ' + st.error) : null,
    h('div', { style: { display: 'flex', gap: '8px' } },
      h('button', { class: 'btn primary', id: 'pk-run', disabled: READONLY || !root || st.running, title: !root ? 'Choose a folder or the sample first' : null, onclick: runScanFromPicker }, st.done ? 'Scan again' : 'Run scan'),
      h('button', { class: st.done ? 'btn primary' : 'btn', onclick: () => { pk.classList.add('hidden'); S.showPicker = false; history.replaceState(null, '', location.pathname); setTab(S.tab); } }, st.done ? 'Open graph' : 'Back to graph')));
  clear(pk).append(col);
}
async function runScanFromPicker() {
  const t0 = performance.now();
  openPicker({ running: true });
  try {
    await apiPost('/api/scan', {});
    await loadAll();
    rememberProject();
    openPicker({ done: true, secs: ((performance.now() - t0) / 1000).toFixed(1) });
  } catch (e) { openPicker({ error: e.status === 409 ? 'a scan is already running.' : e.message }); }
}

/* ======================================================================
   KEYS
   ====================================================================== */
function typing(t) { return t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable); }
function triageFocus(state) {
  if (READONLY) return;
  let type = null, id = null;
  if (S.tab === 'graph' && S.sel) { type = 'node'; id = S.sel; }
  else if (S.tab === 'alarms' && S.alarmSel) { type = 'node'; id = S.alarmSel.nid; }
  else if (S.tab === 'checks' && S.findSel) { type = 'finding'; id = S.findSel; }
  if (!id) return;
  const cur = effState(type, id);
  const note = cur.entry ? cur.entry.note : '';
  setTriage(type, id, cur.entry && cur.entry.state === state && !cur.outdated ? 'unreviewed' : state, note);
}
document.addEventListener('keydown', ev => {
  if (ev.defaultPrevented || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  const t = ev.target;
  if (ev.key === 'Escape') {
    if ($('#cppop')) { $('#cppop').remove(); return; }
    if (S.showPicker) { $('#picker').classList.add('hidden'); S.showPicker = false; return; }
    if (S.tab === 'checks' && S.findSel) { S.findSel = null; layoutMain(); renderChecks(); return; }
    if (S.tab === 'links' && S.linkSel) { S.linkSel = null; layoutMain(); renderLinks(); return; }
    if (S.tab === 'alarms' && S.alarmSel) { S.alarmSel = null; S.analysis = null; renderAlarms(); return; }
    if (typing(t)) { t.blur(); return; }
    if (S.tab === 'graph') clearSelection();
    return;
  }
  if (typing(t)) return;
  const k = ev.key;
  if (k === '/') { ev.preventDefault(); setTab('graph'); const s = $('#search'); if (s) s.focus(); }
  else if (k === '?') showShortcuts();
  else if (k === 'f' || k === 'F') { if (S.tab === 'graph') fitGraph(); }
  else if (k === 'g' || k === 'G') setTab('graph');
  else if (k === 'a' || k === 'A') setTab('alarms');
  else if (k === 'c' || k === 'C') setTab('checks');
  else if (k === 'l' || k === 'L') setTab('links');
  else if (k === '[') { S.leftCollapsed = !S.leftCollapsed; layoutMain(); }
  else if (k === ']') { S.rightCollapsed = !S.rightCollapsed; layoutMain(); }
  else if (k === 'r' || k === 'R') triageFocus('reviewed');
  else if (k === 'x' || k === 'X') triageFocus('needs_fixing');
  else if (k === 'i' || k === 'I') triageFocus('ignored');
  else if (k === 'u' || k === 'U') { if (S.tab === 'graph') setDir('up'); }
  else if (k === 'd' || k === 'D') { if (S.tab === 'graph') setDir('down'); }
  else if (k === 'b' || k === 'B') { if (S.tab === 'graph') setDir('both'); }
  else if (k === 'k' || k === 'K') { const se = S.selEvent && S.events.events.find(e => e.id === S.selEvent); if (se) setCheckpointAtEvent(se); }
  else if (S.tab === 'graph' && (k === '+' || k === '=')) zoomBy(1.3);
  else if (S.tab === 'graph' && (k === '-' || k === '_')) zoomBy(1 / 1.3);
  else if (S.tab === 'graph' && k === '0') { G.cy.zoom(1); G.cy.center(); }
  else if (S.tab === 'graph' && k.startsWith('Arrow') && !(t && t.closest && t.closest('#left'))) { ev.preventDefault(); moveSel(k === 'ArrowRight' ? 1 : k === 'ArrowLeft' ? -1 : 0, k === 'ArrowDown' ? 1 : k === 'ArrowUp' ? -1 : 0); }
  else if (S.tab === 'checks' && (k === 'ArrowDown' || k === 'ArrowUp')) {
    const list = filteredFindings(); if (!list.length) return; ev.preventDefault();
    const i = list.findIndex(f => f.id === S.findSel); const j = Math.max(0, Math.min(list.length - 1, i + (k === 'ArrowDown' ? 1 : -1)));
    openFinding(list[j].id);
  }
  else if (S.tab === 'links' && S.linkSel && (k === 'a' || k === 'd')) { /* handled above for tabs; link keys use buttons */ }
});

/* ======================================================================
   BOOT
   ====================================================================== */
async function loadAll(opts) {
  opts = opts || {};
  try {
    const [project, graph, events, findings, alarms, checkpoints, triage] = await Promise.all(
      ['project', 'graph', 'events', 'findings', 'alarms', 'checkpoints', 'triage'].map(p => apiGet('/api/' + p)));
    Object.assign(S, { project, graph, events, findings, alarms, checkpoints, triage, error: null, loading: false });
    showBanner(null);
  } catch (e) {
    S.loading = false; S.error = e.message; showBanner('Scan data could not be read. ' + e.message + '.', true);
    if (!S.graph) S.graph = { nodes: [], edges: [] };
  }
  rebuildIndex();
  document.title = (S.project ? S.project.name + ' – ' : '') + PRODUCT;
  renderTopbar();
  rebuildGraph(opts.keepView ? { fit: false } : undefined);
  renderOutline(); renderTimeline();
  renderAlarms(); renderChecks(); renderLinks();
  renderDetail();
}
/* ---------- auto-refresh: poll /api/project every 5 s, reload in place when scanned_at changes ---------- */
function scrollSnapshot() {
  const out = [];
  document.querySelectorAll('#app *').forEach(el => {
    if (el.scrollTop > 0 || el.scrollLeft > 0) {
      const key = el.id ? '#' + el.id : el.classList.length ? '.' + el.classList[0] : null;
      if (!key) return;
      out.push({ key, idx: [...document.querySelectorAll(key)].indexOf(el), top: el.scrollTop, left: el.scrollLeft });
    }
  });
  return out;
}
function scrollRestore(snap) {
  for (const s of snap) {
    const el = document.querySelectorAll(s.key)[s.idx];
    if (el) { el.scrollTop = s.top; el.scrollLeft = s.left; }
  }
}
let refreshBusy = false;
async function autoRefreshTick() {
  if (READONLY || refreshBusy || document.hidden || S.loading || !S.project) return;
  if (document.querySelector('.scrim')) return;   // a dialog is open; try again next tick
  refreshBusy = true;
  try {
    const p = await apiGet('/api/project');
    if (p.scanned_at && p.scanned_at !== S.project.scanned_at) {
      const snap = scrollSnapshot();
      await loadAll({ keepView: true });
      requestAnimationFrame(() => scrollRestore(snap));
      setTimeout(() => scrollRestore(snap), 60);
      const d = new Date();
      toast('Updated · ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'));
    }
  } catch (e) { /* server briefly busy or gone: stay quiet, retry next tick */ }
  refreshBusy = false;
}
function startAutoRefresh() {
  if (READONLY) return;
  setInterval(autoRefreshTick, 5000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) autoRefreshTick(); });
}

async function detectHub() {
  if (READONLY || !PID) return;
  try { const r = await fetch('/api/hub/status', { cache: 'no-store' }); HUB_ON = r.ok; } catch (e) { HUB_ON = false; }
}
function boot() {
  buildShell();
  S.graph = { nodes: [], edges: [] }; rebuildIndex();
  setGraphMsg({ t: 'Building graph…' });
  setTab('graph');
  detectHub().then(loadAll).then(() => {
    startAutoRefresh();
    rememberProject();
    if (location.hash === '#/open') openPicker();
    if (location.hash === '#/alarms') setTab('alarms');
  });
  let rt = null;
  window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { if (G.cy) { G.cy.resize(); syncBands(); } renderTimeline(); }, 80); });
}
boot();
