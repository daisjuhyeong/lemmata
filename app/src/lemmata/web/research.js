/* Lemmata research views (S07): Claim map, Timeline, Experiments, Tasks, Ask. Loaded after app.js and uses its helpers
   (h, clear, doc, sec, apiGet, apiPost, openTab, openNode, toast, modal, plainChip, mono, trunc, absTime, dmon, S, IX).
   Everything shown here comes from /api/claims, /api/timeline, /api/ledger, /api/tasks, /api/digest and /api/ask.
   No inline scripts, no innerHTML. */
'use strict';
const RX = { tree: null, view: 'tree', sel: null, t: 1, playing: null, claims: null, timeline: null, ledger: null, tasks: null, loaded: false, error: null, open: {}, filter: 'all', tlFilter: 'all', exFilter: 'all',
  ask: { q: '', busy: false, res: null, history: [] }, hub: null, digest: null };
const RX_TABS = { digest: ['', 'Digest'], review: ['◎', 'Review'], notation: ['𝑥', 'Notation'], claims: ['◆', 'Claims'], timeline: ['⚑', 'Timeline'], experiments: ['▦', 'Experiments'], setup: ['⊞', 'Setup'], tasks: ['☑', 'Tasks'], ask: ['?', 'Ask'], faq: ['?', 'FAQ'], numbers: ['#', 'Key numbers'], baselines: ['≡', 'Baselines'], settings: ['', 'Settings'], latex: ['', 'LaTeX'] };
const RX_VIEW_TAB = { claims: 'claims', inbox: 'changes', timeline: 'timeline', ask: 'ask' };
const RX_STATUS = { supported: ['✓', 'Supported', 'fine'], partial: ['◐', 'Partly supported', 'look'], unsupported: ['✕', 'Not supported', 'fix'] };
// One kind of item, a claim, moving through stages. The stage classes reuse the status colours.
const RX_STAGE = { hypothesis: ['○', 'Hypothesis', 'plain', 'hyp'], testing: ['◐', 'Being tested', 'look', 'partial'], finding: ['●', 'Finding', 'fine', 'supported'], refuted: ['✕', 'Not supported', 'fix', 'unsupported'], exploration: ['◌', 'Exploration', 'ign', 'explore'] };
const RX_STAGES = ['finding', 'testing', 'hypothesis', 'refuted', 'exploration'];
const RX_SCOPE = { new: ['New', 'A claim of this work'], original: ['Original', 'A claim of the paper this work extends, re-checked here'] };
function rxSt(stage) { return ' st-' + (RX_STAGE[stage] || RX_STAGE.hypothesis)[3]; }
function rxStageChip(c) { const k = RX_STAGE[c.stage] ? c.stage : 'hypothesis', s = RX_STAGE[k]; const ch = plainChip(s[0], s[1], s[2] + ' stg-' + k); ch.title = (c.stage_by === 'you' ? 'Set by you. ' : '') + (c.stage_why || '') + (c.stage_rule ? ' (rule ' + c.stage_rule + (c.stage_by === 'you' && c.stage_rule_auto ? '; the evidence alone gives rule ' + c.stage_rule_auto : '') + ')' : ''); return ch; }
function rxScopeTag(c) { const s = RX_SCOPE[c.scope]; return s ? h('span', { class: 'tag', title: s[1] }, s[0]) : null; }
function rxOpenExp(id) { RX.exView = 'map'; RX.mapSel = 'x:' + id; RX.exOpen = null; openTab('experiments'); }
/* The VS Code tab calls this to open a page with something selected (from an "Open in VS Code" link on the website). */
function rxGoto(view, sel) {
  if (view === 'experiments' && /^[qx]:/.test(sel || '')) { RX.exView = 'map'; RX.mapSel = sel; RX.exOpen = null; }
  if (view === 'setup' && /^[ixc]:/.test(sel || '')) { RX.suSel = sel.startsWith('i:') ? sel : null; RX.bdSel = sel; }
  openTab(view);
}
/* Website only: a link that opens this page in VS Code's Lemmata tab (vscode/src/core/link.ts reads it). */
function rxVsLink(sel, label, view) {
  if (EMBED || !PID) return null;
  return h('a', { class: 'btn sm', href: 'vscode://lemmata-local.lemmata/open?pid=' + encodeURIComponent(PID) + '&view=' + (view || 'experiments') + '&sel=' + encodeURIComponent(sel),
    title: 'Open in VS Code, in the Lemmata tab. Needs the Lemmata extension, connected to this hub.' }, label || 'Open in VS Code');
}
/* VS Code tab only: buttons that open an experiment's own files (scripts, settings, result) in the editor. */
function rxEditorRow(x) {
  if (!EMBED || !IX.node) return null;
  const d = x.design || {}, seen = new Set(), btns = [];
  const add = (it, kind) => { const n = it && IX.node.get(it.node_id); if (!n || !n.loc || !n.loc.path || seen.has(n.repo + ':' + n.loc.path)) return; seen.add(n.repo + ':' + n.loc.path);
    btns.push(h('button', { class: 'btn sm', title: 'Open ' + n.loc.path + ' in the editor', onclick: () => EMBED.openFile(n.repo, n.loc.path, n.loc.line || 1) }, kind + ' ' + n.loc.path.split('/').pop())); };
  (d.scripts || []).slice(0, 4).forEach(it => add(it, '▸'));
  (d.settings || []).slice(0, 3).forEach(it => add(it, '⚙'));
  if (x.result) add(x.result, '▦');
  return btns.length ? h('div', { class: 'rx-x-ed' }, h('span', { class: 'muted small' }, 'Open in editor:'), btns) : null;
}
// Why we experiment: the experiments run because of this claim, and how each came out.
function rxWhyRows(c) {
  const xs = c.experiments || [];
  if (!xs.length) return c.formal ? null : h('div', { class: 'rx-why none' }, 'No experiment tests this yet.');
  return h('div', { class: 'rx-why' }, h('div', { class: 'rx-why-h' }, 'Experiments run for this'), xs.map(x => { const g = RX_XSTATE[x.state] || RX_XSTATE.none;
    return h('button', { class: 'rx-why-r', onclick: () => rxOpenExp(x.id), title: 'Open this experiment' }, h('span', { class: 'rx-m-g x-' + x.state }, g[0]), h('b', null, x.name),
      h('span', { class: 'muted' }, !x.connected ? 'No results yet' : x.gap != null ? g[1] + (x.state === 'tie' ? ' with ' : ' ' + (x.state === 'ahead' ? 'of ' : '')) + trunc(x.vs, 22) + (x.gap ? ' by ' + rxFmt(Math.abs(x.gap)) : '') : g[1]),
      h('span', { class: 'grow' }), x.check ? plainChip('!', 'To check', 'look') : null, x.stale ? plainChip('↻', 'Old result', 'look') : null); }));
}
function rxStageSelect(c) {
  if (READONLY || c.id === 'core') return null;
  const auto = RX_STAGE[c.stage_auto] || RX_STAGE.hypothesis;
  const s = h('select', { 'aria-label': 'Stage', class: 'rx-stage-sel', title: 'Lemmata sets the stage from the evidence. Choose one yourself to overrule it.' },
    h('option', { value: 'auto', selected: c.stage_by !== 'you' }, 'Stage: from the evidence (' + auto[1] + ')'), Object.keys(RX_STAGE).map(k => h('option', { value: k, selected: c.stage_by === 'you' && c.stage === k }, 'Stage: ' + RX_STAGE[k][1] + ' (my call)')));
  s.addEventListener('change', async () => { const r = await rxPost('/api/claims', { id: c.id, stage: s.value }); if (r) { RX.claims = r; rxTrack('claim_stage_set'); await rxRefresh(); } });
  return s;
}
const RX_KIND = { contribution: 'Contribution', question: 'Research question', theorem: 'Theorem', lemma: 'Lemma', proposition: 'Proposition', corollary: 'Corollary', claim: 'Claim', core: 'Core message' };

function rxTrack(event, extra) {
  if (!HUB_ON || READONLY) return;
  fetch('/api/hub/events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.assign({ event, project: PID }, extra || {})) }).catch(() => { });
}
async function rxLoad() {
  if (READONLY && !(SNAP && SNAP.claims)) { RX.loaded = true; RX.error = 'This snapshot was made without the research views.'; return; }
  try {
    const [claims, timeline, ledger, tasks, tree, notation] = await Promise.all(['claims', 'timeline', 'ledger', 'tasks', 'tree', 'notation'].map(p => apiGet('/api/' + p)));
    let experiments = null; try { experiments = await apiGet('/api/experiments'); } catch (e) { /* the page says so */ }
    let map = null; try { map = await apiGet('/api/map'); } catch (e) { /* older data has no map */ }
    let todo = null; try { todo = await apiGet('/api/todo'); } catch (e) { /* older hubs and snapshots */ }
    let trail = null; try { trail = await apiGet('/api/trail'); } catch (e) { /* older hubs and snapshots */ }
    let setup = null; try { setup = await apiGet('/api/setup'); } catch (e) { /* older hubs and snapshots: the page says so */ }
    let hf = null; try { hf = await apiGet('/api/hypothesis'); } catch (e) { /* older hubs and snapshots have no hypothesis-first view */ }
    let study = null, numbers = null;      // S29: the kind of study, and the numbers it rests on (older hubs and snapshots have neither)
    try { study = await apiGet('/api/study'); } catch (e) { /* a method paper, as before */ }
    try { numbers = await apiGet('/api/numbers'); } catch (e) { /* the page says so */ }
    let baselines = null; try { baselines = await apiGet('/api/baselines'); } catch (e) { /* S30: older hubs and snapshots have no Baselines page */ }
    let latex = null; try { latex = await apiGet('/api/latex'); } catch (e) { /* S31: same for the LaTeX page */ }
    try { RX.review = await apiGet(READONLY ? '/api/review' : '/api/review?days=' + (RX.rvDays || 30)); } catch (e) { RX.review = null; }
    if (!READONLY) { try { RX.plans = await apiGet('/api/plans'); } catch (e) { RX.plans = null; } }
    Object.assign(RX, { claims, timeline, ledger, tasks, tree, notation, experiments, map, setup, todo, trail, hf, study, numbers, baselines, latex, loaded: true, error: null });
  } catch (e) { RX.loaded = true; RX.error = e.status === 501 ? 'Not available on sample data.' : e.message; }
}
async function rxRefresh(render) { await rxLoad(); if (render !== false) { renderLeft(); renderPage(true); renderStatus(); } }
/* S29 (ADR-009): a project is a method paper (it has an "ours") or a benchmark study (it has none). One line says which,
   and the researcher can change it there. Shown on Home, Thesis and Setup. */
const rxBench = () => !!(RX.study && RX.study.kind === 'benchmark');
const ST_BY = { you: 'set by you', map: 'from the confirmed map', rule: 'Lemmata’s reading' };
function rxStudyLine() {
  const D = RX.study; if (!D) return null;
  const bench = D.kind === 'benchmark';
  const set = async kind => { const r = await rxPost('/api/study', { kind }, kind === 'auto' ? 'Lemmata decides again.' : 'Now read as a ' + (kind === 'benchmark' ? 'benchmark study' : 'method paper') + '.'); if (r) { RX.study = r; RX.setup = null; await rxRefresh(); } };
  const sel = READONLY ? null : h('select', { class: 'st-sel', 'aria-label': 'Kind of study' }, D.kinds.map(k => h('option', { value: k.k, selected: D.kind === k.k ? '' : null }, k.word)), D.chosen ? h('option', { value: 'auto' }, 'Let Lemmata decide') : null);
  if (sel) sel.addEventListener('change', () => set(sel.value));
  return h('div', { class: 'st-line' + (D.by === 'rule' ? ' unsure' : ''), title: D.why },
    h('span', { class: 'tag' }, 'Study'), sel || h('b', null, D.word), h('span', { class: 'muted small' }, ST_BY[D.by] || D.by),
    h('span', { class: 'st-w' }, bench ? 'No method of its own. Methods are compared; each claim is decided by its own test.' : 'Ours' + (D.ours ? ': ' + D.ours : '') + ', ranked against baselines.'),
    D.by === 'rule' && !READONLY ? h('button', { class: 'linkbtn small', title: 'Keep this reading', onclick: () => set(D.kind) }, 'Confirm') : null,
    D.note ? h('span', { class: 'muted small' }, D.note) : null);
}
/* S29: while the hub cannot sync, Lemmata's copy is behind GitHub. Every page that lists what is "not there" says so. */
function rxBehindNote() {
  const s = S.project && S.project.sync; if (!s || !s.failing) return null;
  return h('div', { class: 'flag st-sync', role: 'status' }, h('b', null, 'Sync with GitHub is failing'), s.since ? ' since ' + dmon(s.since) : '', '. ', s.message || '',
    ' Lemmata still shows commit ', h('span', { class: 'mono' }, (s.head || '?').slice(0, 7)), '; a run, commit or result file it does not have may only be not pulled yet. ',
    READONLY ? null : h('button', { class: 'linkbtn', onclick: () => syncNow() }, 'Sync now'));
}
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
  modal(loc.path + (loc.line ? ':' + loc.line : ''), body, [{ label: 'Close', primary: true }]);
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
    if (path.startsWith('/api/claims')) { RX.digest = null; try { const [t, l, tr] = await Promise.all(['timeline', 'ledger', 'tree'].map(p => apiGet('/api/' + p))); RX.timeline = t; RX.ledger = l; RX.tree = tr; RX.experiments = await apiGet('/api/experiments'); RX.setup = null; RX.todo = await apiGet('/api/todo').catch(() => RX.todo); } catch (e) { /* the old tree stays */ } }
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
      s.detail ? h('span', { class: 'muted' }, ' · ', rxMath(s.detail)) : null, h('span', { class: 'grow' }), rxWhere(s.loc),
      suggested ? [h('button', { class: 'btn sm primary', disabled: READONLY, onclick: async () => { const r = await rxPost('/api/claims/link', { id: c.id, target: key, on: true }); if (r) { RX.claims = r; rxTrack('claim_linked'); renderPage(true); renderLeft(); } } }, '✓ Yes'),
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
  const open = RX.open[c.id] != null ? RX.open[c.id] : (c.stage === 'testing' || c.stage === 'refuted' || !!c.recheck || c.state === 'proposed');
  const real = c.support.filter(s => s.how !== 'suggested'), sug = c.support.filter(s => s.how === 'suggested');
  const setState = async st => { const r = await rxPost('/api/claims', { id: c.id, state: st }); if (r) { RX.claims = r; if (st !== 'proposed') rxTrack(st === 'confirmed' ? 'claim_confirmed' : 'claim_rejected'); renderPage(true); renderLeft(); } };
  return h('article', { class: 'card rx-claim' + rxSt(c.stage) + (c.state === 'rejected' ? ' rejected' : ''), id: 'cl-' + c.id.replace(/[^\w]/g, '_') },
    h('button', { class: 'rx-claim-h', 'aria-expanded': String(open), onclick: () => { RX.open[c.id] = !open; renderPage(true); } },
      h('span', { class: 'caret' }, open ? '▾' : '▸'), h('span', { class: 'rx-label' }, c.short || c.label), rxStageChip(c), rxScopeTag(c),
      c.recheck ? plainChip('↻', 'Recheck', 'look') : null, c.state === 'proposed' ? plainChip('✎', 'Draft', 'proposed') : null,
      h('span', { class: 'grow' }), h('span', { class: 'muted small', title: 'Where it comes from' }, c.label !== c.short && !/^Your claim$/.test(c.label) ? c.label : (RX_KIND[c.kind] || ''))),
    h('div', { class: 'rx-text serif' }, rxMath(c.text)),
    open ? h('div', { class: 'rx-body' },
      c.stage_why ? h('div', { class: 'rx-stage-why small' }, h('b', null, (RX_STAGE[c.stage] || RX_STAGE.hypothesis)[1] + (c.stage_by === 'you' ? ' (my call)' : '') + ': '), c.stage_by === 'you' ? 'The evidence alone says “' + (RX_STAGE[c.stage_auto] || RX_STAGE.hypothesis)[1] + '”. ' + c.stage_why : c.stage_why) : null,
      c.loc ? h('div', { class: 'muted small' }, 'In the paper: ', rxWhere(c.loc)) : null,
      rxWhyRows(c),
      c.recheck ? h('div', { class: 'rx-warn' }, '↻ Something behind this claim changed: ' + c.recheck) : null,
      c.issues.map(i => h('div', { class: 'rx-warn' }, '! ' + i)),
      real.length ? real.map(s => rxSupportRow(c, s)) : (c.experiments || []).length ? null : h('div', { class: 'rx-none' }, c.formal ? 'No proof found. If the proof is elsewhere, write “Proof of Theorem~\\ref{…}” at its start so Lemmata can connect it.' : 'Nothing backs this claim yet. Link the table, figure, section or result file that shows it.'),
      sug.map(s => rxSupportRow(c, s)),
      c.note ? h('div', { class: 'rx-note' }, h('b', null, 'Your note: '), c.note) : null,
      READONLY ? null : h('div', { class: 'btnrow' },
        c.state !== 'confirmed' ? h('button', { class: 'btn primary', onclick: () => setState('confirmed') }, 'Confirm') : h('button', { class: 'btn', onclick: () => setState('proposed') }, 'Back to draft'),
        h('button', { class: 'btn', onclick: () => rxLinkDialog(c) }, '+ Evidence'),
        h('button', { class: 'btn', onclick: () => rxEditDialog(c) }, 'Edit'), rxStageSelect(c),
        h('span', { class: 'grow' }),
        c.manual ? h('button', { class: 'linkbtn', onclick: async () => { const r = await rxPost('/api/claims/remove', { id: c.id }); if (r) { RX.claims = r; renderPage(true); renderLeft(); } } }, 'Delete')
          : c.state !== 'rejected' ? h('button', { class: 'linkbtn', onclick: () => setState('rejected') }, 'Not a claim') : h('button', { class: 'linkbtn', onclick: () => setState('proposed') }, 'Bring back'))) : null);
}
function rxAddClaimBox(root) {
  if (READONLY) return;
  const ta = h('textarea', { rows: '2', class: 'rx-ta', placeholder: 'One sentence', 'aria-label': 'New claim' });
  root.append(h('details', { class: 'details' }, h('summary', null, '+ Add a claim'), ta, h('div', { class: 'btnrow' }, h('button', { class: 'btn', onclick: async () => { if (!ta.value.trim()) return; const r = await rxPost('/api/claims/add', { text: ta.value }); if (r) { RX.claims = r; renderPage(true); renderLeft(); } } }, 'Add'))));
}
/* one line: [tag] ● sentence (S18 "rows"). state picks the dot colour; the word in the tag carries the meaning. */
function rxRow(tag, state, text, onclick, title) {
  return h('div', { class: 'row-line' + (onclick ? ' clickable' : ''), title: title || tag || null },
    h('span', { class: 'rtag' }, tag ? '[' + tag + ']' : ''), h('span', { class: 'rdot d-' + state, 'aria-hidden': 'true' }),
    onclick ? h('button', { class: 'ilink rtext', onclick, 'aria-label': tag ? tag + ': ' + text : null }, text) : h('span', { class: 'rtext' }, text));
}
const RX_DOT = { hypothesis: 'pale', exploration: 'pale', testing: 'light', finding: 'success', refuted: 'error' };
function rxAttention() {
  const d = RX.claims, rows = [];
  d.claims.filter(c => c.state !== 'rejected').forEach(c => {
    const why = c.recheck ? ['recheck', 'warning', 'Something behind it changed'] : c.state === 'proposed' ? ['confirm', 'highlight', 'Confirm or reword this claim'] : c.stage === 'refuted' ? ['not supported', 'error', 'The results do not support it'] : c.stage === 'testing' ? ['being tested', 'light', 'Results are in, but not all of them back it'] : null;
    if (why) rows.push(rxRow(why[0], why[1], (c.short || c.label) + ' — ' + why[2], () => { RX.sel = c.id; RX.open[c.id] = true; renderPage(true); }));
  });
  return rows;
}
function pageClaims() {
  const nr = rxNotReady('Claims'); if (nr) return nr;
  S.outline = [];
  const d = RX.claims, cc = d.counts;
  const seg = h('div', { class: 'rx-seg', role: 'group', 'aria-label': 'View' }, h('button', { 'aria-pressed': 'false', title: 'Thesis, claims and experiments, top down', onclick: () => { RX.exView = 'table'; openTab('experiments'); } }, 'Outline'), [['tree', 'Tree'], ['list', 'List']].map(([k, l]) => h('button', { 'aria-pressed': String(RX.view === k), onclick: () => { RX.view = k; renderPage(true); } }, l)));
  const root = doc(h('div', { class: 'row' }, h('h1', { class: 'ptitle grow' }, 'Thesis'), seg,
    h('button', { class: 'btn', title: 'Watch the tree grow', onclick: () => { RX.t = 0; openTab('timeline'); setTimeout(rxPlay, 300); } }, '▶ Growth'),
    READONLY ? null : h('a', { class: 'btn', href: apiUrl('/api/claims.md'), title: 'Download claims.md to commit to your repository' }, '↓ .md')));
  if (!d.has_paper) root.append(emptyState('◆', 'No paper connected', 'Connect a paper repository or upload the LaTeX source as a zip from the Project menu in the footer.'));
  if (RX.view === 'tree' && RX.tree) {
    root.classList.add('wide');
    root.append(rxTree({ scrub: false }));
    const c = RX.sel && d.claims.find(x => x.id === RX.sel);
    if (c) { RX.open[c.id] = true; root.append(rxClaimCard(c)); }
    else if (RX.sel === 'core' && d.core) root.append(rxCoreCard(d.core));
    else if (RX.sel && IX.node && IX.node.get(RX.sel)) root.append(rxEvidenceCard(RX.sel));
    const att = rxAttention();
    root.append(sec('Needs attention', 'attention', att.length ? att : h('div', { class: 'muted' }, 'Nothing needs you right now.')));
    rxAddClaimBox(root);
    return root;
  }
  if (d.core) root.append(rxCoreCard(d.core));
  const live = d.claims.filter(c => c.state !== 'rejected'), gone = d.claims.filter(c => c.state === 'rejected');
  const F = RX.filter;
  const pass = c => F === 'all' || (F === 'draft' ? c.state === 'proposed' : F === 'recheck' ? !!c.recheck : F === 'new' || F === 'original' ? c.scope === F : true);
  const chips = [['all', 'All', live.length], ['recheck', 'Recheck', cc.recheck], ['draft', 'Drafts', cc.proposed]].concat(live.some(c => c.scope) ? [['new', 'New', live.filter(c => c.scope === 'new').length], ['original', 'Original', live.filter(c => c.scope === 'original').length]] : []);
  if (!chips.some(x => x[0] === F)) RX.filter = 'all';
  root.append(h('div', { class: 'fchips' }, chips.map(([k, l, n]) => h('button', { class: 'fchip', 'aria-pressed': String(F === k), onclick: () => { RX.filter = k; renderPage(true); } }, l + ' ', h('span', { class: 'n' }, n)))));
  const TITLE = { finding: 'Findings', testing: 'Being tested', hypothesis: 'Hypotheses', refuted: 'Not supported', exploration: 'Explorations' };
  const groups = RX_STAGES.map(k => [TITLE[k], c => c.stage === k]);
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
  const full = h('details', { class: 'details' }, h('summary', null, 'Abstract'), h('div', { class: 'serif' }, rxMath(core.abstract || '')));
  return h('section', { class: 'rx-core' + rxSt(core.stage) },
    h('div', { class: 'rx-core-h' }, h('span', { class: 'rx-label' }, 'Core message'), rxStageChip(core), core.recheck ? plainChip('↻', 'Recheck', 'look') : null, h('span', { class: 'grow' }),
      READONLY ? null : h('button', { class: 'linkbtn small', onclick: () => rxEditDialog(core) }, 'Reword'), rxWhere(core.loc)),
    h('div', { class: 'rx-core-t serif' }, rxMath(core.text)),
    h('div', { class: 'rx-meter', role: 'img', 'aria-label': RX_STAGES.map(k => cc.stages[k] + ' ' + RX_STAGE[k][1].toLowerCase()).join(', ') },
      cc.total ? RX_STAGES.filter(k => cc.stages[k]).map(k => h('span', { class: 'seg ' + RX_STAGE[k][3], style: 'flex:' + cc.stages[k], title: cc.stages[k] + ' ' + RX_STAGE[k][1].toLowerCase() }, RX_STAGE[k][0] + ' ' + cc.stages[k])) : null),
    core.abstract ? full : null);
}

/* ---------- Research tree (S18): circles on thin lines, vertical. Core message at the top, its claims under it, the evidence behind a claim when you open it ---------- */
const SVGNS = 'http://www.w3.org/2000/svg';
function sv(tag, attrs, ...kids) {
  const el = document.createElementNS(SVGNS, tag);
  for (const k in (attrs || {})) { const v = attrs[k]; if (v == null || v === false) continue; if (k === 'onclick') el.addEventListener('click', v); else el.setAttribute(k, v); }
  const add = c => { if (c == null || c === false) return; if (Array.isArray(c)) c.forEach(add); else el.append(c.nodeType ? c : document.createTextNode(String(c))); };
  kids.forEach(add); return el;
}
const RX_GLYPH = { proof: '∎', assumption: '◇', definition: '◇', condition: '◇', hypothesis: '◇', table: '▦', figure: '◔', section: '§', equation: '∑', item: '•', result: '▤', asset: '◔', data: '⛁', code: '{}', config: '⚙', run: '▶', missing: '?' };
const RX_KINDWORD = { proof: 'Proof', assumption: 'Assumption', definition: 'Definition', table: 'Table', figure: 'Figure', section: 'Section', result: 'Result file', asset: 'Figure file', data: 'Data', code: 'Script', config: 'Settings', run: 'Run', missing: 'Nothing backs this yet' };
RX.treeOpen = RX.treeOpen || {};
function kidsCount(T, id) { return T.nodes.filter(n => n.parent === id).length; }
function rxTree(opts) {
  const T = RX.tree, N = new Map(T.nodes.map(n => [n.id, n]));
  const claims = T.nodes.filter(n => n.layer === 'claim'), core = T.nodes.find(n => n.layer === 'core');
  const kids = new Map(); claims.forEach(c => { const p = c.parent || 'core'; if (!kids.has(p)) kids.set(p, []); kids.get(p).push(c); });
  const ev = new Map(); T.edges.forEach(e => { const to = N.get(e.to); if (to && to.layer === 'root' && (e.kind === 'support' || e.kind === 'missing' || e.kind === 'trace' || N.get(e.from) && N.get(e.from).layer === 'claim')) { if (!ev.has(e.from)) ev.set(e.from, []); if (!ev.get(e.from).includes(to)) ev.get(e.from).push(to); } });
  const nRoots = new Map(); T.edges.forEach(e => { if (e.kind === 'support' && e.how !== 'suggested') nRoots.set(e.from, (nRoots.get(e.from) || 0) + 1); });
  const wrap = h('div', { class: 'rx-treewrap' });
  const root = h('ul', { class: 'rxt', role: 'tree', 'aria-label': 'Research tree: the core message, the claims under it and the evidence behind them' });
  const els = new Map(), rows = [];
  // two levels by default: the core message and its claims; a click opens what is under a node
  const isOpen = n => RX.treeOpen[n.id] != null ? RX.treeOpen[n.id] : (n.layer === 'core' || opts.scrub);
  const dotSize = n => n.layer === 'core' ? 22 : n.layer === 'claim' ? 10 + Math.min(8, (nRoots.get(n.id) || 0) + kidsCount(T, n.id)) : 8;
  const att = n => !!n.recheck || n.state === 'proposed';
  const rxWords = (t, k) => { const w = String(t || '').trim().split(/\s+/); return w.length > k ? w.slice(0, k).join(' ') + '…' : w.join(' '); };
  function node(n, depth, path) {
    path = new Set(path || []); path.add(n.id);
    const li = h('li', { class: 'rxt-li n-' + n.layer + (n.stage ? rxSt(n.stage) : '') + (n.exp ? ' x-' + n.state : '') + (att(n) ? ' att' : '') + (n.state === 'proposed' ? ' draft' : '') + (RX.sel === n.id ? ' sel' : ''), role: 'treeitem', 'aria-level': String(depth + 1) });
    const under = [...(kids.get(n.id) || []), ...(ev.get(n.id) || [])].filter(c => !path.has(c.id));
    const open = isOpen(n), nk = under.length;
    if (nk) li.setAttribute('aria-expanded', String(!!open));
    const d = dotSize(n), stageName = n.layer === 'claim' || n.layer === 'core' ? (RX_STAGE[n.stage] || RX_STAGE.hypothesis)[1] : (n.layer === 'root' && n.kind !== 'missing' ? RX_KINDWORD[n.kind] || n.kind : '');
    const label = n.layer === 'core' ? h('span', { class: 'rxt-core serif' }, rxMath(n.title || 'No core message found. Click to write it.')) : n.kind === 'missing' ? h('span', { class: 'rxt-lab' }, 'Nothing backs this yet')
      : n.layer === 'claim' ? h('span', { class: 'rxt-lab' }, h('b', { class: 'rxt-code' }, n.short), ' ', h('span', { class: 'rxt-w6' }, rxWords(n.title, 6)), h('span', { class: 'rxt-w4' }, rxWords(n.title, 4)), n.state === 'proposed' ? ' ✎' : '')
      : h('span', { class: 'rxt-lab' }, n.short);
    const caret = nk ? h('span', { class: 'rxt-caret', 'aria-hidden': 'true' }, open ? '▾' : '▸') : h('span', { class: 'rxt-caret ph', 'aria-hidden': 'true' });
    const tip = (n.short || n.title || '') + (stageName ? ' — ' + stageName : '') + (n.scope ? ', ' + RX_SCOPE[n.scope][0].toLowerCase() : '') + (n.recheck ? ', recheck' : '') + (n.state === 'proposed' ? ' (draft)' : '') + (n.layer === 'root' && n.traced === false && n.kind !== 'missing' ? ', not traced to a result file or script' : '');
    const btn = h('button', { class: 'rxt-row', 'data-id': n.id, title: tip, 'aria-label': (n.short || n.title || 'Core message') + (stageName ? ', ' + stageName : '') + (att(n) ? ', needs your attention' : ''), 'aria-current': RX.sel === n.id ? 'true' : null },
      caret, h('span', { class: 'rxt-dot' + (n.traced === false && n.layer === 'root' ? ' untraced' : '') + (n.kind === 'missing' ? ' miss' : ''), style: 'width:' + d + 'px;height:' + d + 'px', 'aria-hidden': 'true' }), label,
      n.shared > 1 ? h('span', { class: 'rxt-n' }, '×' + n.shared) : null, n.caveat ? h('span', { class: 'rxt-n', title: 'Has a caveat' }, '!') : null, n.recheck ? h('span', { class: 'rxt-n', title: 'Recheck' }, '↻') : null,
      nk && !open ? h('span', { class: 'rxt-n', title: nk + ' under it' }, '+' + nk) : null);
    const pick = () => {
      if (n.exp) return rxOpenExp(n.exp);
      if (n.layer === 'root') {
        if (n.node_id) { RX.sel = RX.sel === n.id ? null : n.id; if (!opts.scrub) renderPage(true); else { RX.view = 'tree'; openTab('claims'); } }
        else if (n.loc) rxShowLines('paper', n.loc);
        else if (n.kind === 'missing') { const cid = n.id.slice(8); RX.sel = cid; const c = RX.claims.claims.find(x => x.id === cid); if (c && !READONLY) rxLinkDialog(c); renderPage(true); }
        return;
      }
      if (nk) RX.treeOpen[n.id] = !open;
      RX.sel = RX.sel === n.id ? null : n.id;
      if (!opts.scrub) renderPage(true); else { RX.view = 'tree'; openTab('claims'); }
    };
    btn.addEventListener('click', pick);
    btn.addEventListener('keydown', ev => {
      const vis = Array.from(root.querySelectorAll('.rxt-row')), i = vis.indexOf(btn);
      if (ev.key === 'ArrowDown' && vis[i + 1]) { ev.preventDefault(); vis[i + 1].focus(); }
      else if (ev.key === 'ArrowUp' && vis[i - 1]) { ev.preventDefault(); vis[i - 1].focus(); }
      else if (ev.key === 'ArrowRight' && nk && !open) { ev.preventDefault(); RX.treeOpen[n.id] = true; renderPage(true); }
      else if (ev.key === 'ArrowLeft' && nk && open) { ev.preventDefault(); RX.treeOpen[n.id] = false; renderPage(true); }
    });
    btn.addEventListener('mouseenter', () => focus(n.id)); btn.addEventListener('mouseleave', () => focus(null)); btn.addEventListener('focus', () => focus(n.id)); btn.addEventListener('blur', () => focus(null));
    li.append(btn); els.set(n.id, li); rows.push(n);
    if (open && nk) {
      const ul = h('ul', { class: 'rxt', role: 'group' });
      under.forEach(c => ul.append(node(c, depth + 1, path)));
      li.append(ul);
    }
    return li;
  }
  if (core) root.append(node(core, 0));
  else claims.filter(c => !c.parent).forEach(c => root.append(node(c, 0)));
  wrap.append(root);
  // hover: light up everything a node rests on and everything that rests on it
  const dn = new Map(), upm = new Map(); T.edges.forEach(e => { (dn.get(e.from) || dn.set(e.from, []).get(e.from)).push(e.to); (upm.get(e.to) || upm.set(e.to, []).get(e.to)).push(e.from); });
  const reach = (id, m) => { const seen = new Set([id]), q = [id]; while (q.length) for (const x of (m.get(q.pop()) || [])) if (!seen.has(x)) { seen.add(x); q.push(x); } return seen; };
  function focus(id) {
    root.classList.toggle('focus', !!id);
    const on = id ? new Set([...reach(id, dn), ...reach(id, upm)]) : null;
    els.forEach((el, k) => el.classList.toggle('on', !!on && on.has(k)));
  }
  // time: positions never move; pieces only appear
  const t0 = T.span ? Date.parse(T.span.start) : 0, t1 = T.span ? Date.parse(T.span.end) : 0;
  const born = new Map(T.nodes.map(n => [n.id, n.born ? Date.parse(n.born) : null]));
  const firstUse = new Map(); T.edges.forEach(e => { const b = born.get(e.from); if (b != null && born.get(e.to) == null && N.get(e.to) && N.get(e.to).layer === 'root') firstUse.set(e.to, Math.min(firstUse.get(e.to) || Infinity, b)); });
  const bornOf = id => born.get(id) != null ? born.get(id) : (firstUse.get(id) != null ? firstUse.get(id) : null);
  function setTime(frac) {
    const now = t0 + (t1 - t0) * frac + 1; let shown = 0;
    els.forEach((el, id) => { const b = bornOf(id); const hide = frac < 1 && b != null && b > now; el.classList.toggle('unborn', hide); if (!hide) shown++; });
    const at = n => { const st = n.stages || []; if (frac >= 1 || !st.length) return n.stage; const past = st.filter(x => Date.parse(x.t) <= now).pop(); return past ? past.stage : st[0].by === 'history' ? 'hypothesis' : n.stage; };
    const paint = (el, stage) => { ['hyp', 'partial', 'supported', 'unsupported', 'explore'].forEach(k => el.classList.remove('st-' + k)); el.classList.add(rxSt(stage).trim()); };
    T.nodes.forEach(n => { if (n.stage && els.has(n.id)) paint(els.get(n.id), at(n)); });
    return { now, shown };
  }
  if (opts.scrub && T.span && t1 > t0) wrap.append(rxScrubber(T, t0, t1, setTime));
  else setTime(1);
  wrap.append(h('p', { class: 'rx-legend-note muted' }, 'Circle size is how much hangs on a claim. A darker fill means stronger evidence. A gold circle needs your attention. Click a circle to open what is under it.'));
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
    else if (d.table) pic = h('div', { class: 'rx-ev-tablewrap' }, h('table', { class: 'tbl rx-ev-table' }, h('tbody', null, d.table.map((r, i) => h('tr', null, r.map(c => h(i ? 'td' : 'th', null, rxMath(c))))))));
    const cav = h('textarea', { rows: '2', class: 'rx-ta', 'aria-label': 'Caveat', placeholder: 'Caveat: what a reader must keep in mind' }); cav.value = d.note.caveat || '';
    const pur = h('textarea', { rows: '2', class: 'rx-ta', 'aria-label': 'Meant to show', placeholder: 'Meant to show: the one thing this is in the paper for' }); pur.value = d.note.purpose || '';
    const linked = d.connected;
    clear(box).append(
      h('div', { class: 'rx-ev-h' }, h('span', { class: 'rx-label' }, n.name), linked ? plainChip('✓', 'Connected', 'fine') : plainChip('✕', 'Not connected', 'fix'),
        d.stale ? plainChip('↻', 'Out of date', 'look') : null, d.note.caveat ? plainChip('!', 'Caveat', 'look') : null, h('span', { class: 'grow' }),
        d.self ? gh(d.self) : null, rxWhere(n.loc, n.repo), h('button', { class: 'linkbtn small', onclick: () => openNode(nodeId) }, 'Open')),
      h('div', { class: 'rx-ev-b' }, pic, h('div', { class: 'rx-ev-r' },
        d.caption ? h('div', { class: 'serif rx-ev-cap' }, rxMath(d.caption)) : null,
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
    if (RX.tree.undated) root.append(h('div', { class: 'muted small' }, RX.tree.dated ? '' : 'No dates in git'));
  }
  const host = root; const stepsBox = h('details', { class: 'details' }, h('summary', null, 'Steps (' + tl.steps.length + ')'));
  root.append(stepsBox);
  const label = id => { const c = RX.claims && (RX.claims.claims.find(x => x.id === id) || (RX.claims.core && RX.claims.core.id === id && RX.claims.core)); return c ? (c.short || c.label) : id; };
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

/* ---------- Experiments, by research question / hypothesis ---------- */
const RX_CAT = { method: ['◆', 'Method'], settings: ['●', 'Settings'], data: ['▲', 'Data'], evaluation: ['⟂', 'Evaluation'] };
const RX_CELL = { match: ['✓', 'Matches the result file'], rounding: ['≈', 'Rounded differently'], differs: ['✕', 'Differs from the result file'], loose: ['~', 'Value is in the file, but not in the matching row and column'], untraced: ['?', 'Not found in the result file'] };
function rxFmt(v) { if (v == null) return '—'; const a = Math.abs(v); return a >= 100 ? v.toFixed(1) : a >= 1 ? v.toFixed(2) : v.toFixed(3).replace(/0$/, ''); }
function rxFieldCell(sm) {      // benchmark study: the field of what is compared, not ours against the best other
  if (!sm.best) return h('span', { class: 'muted small' }, '—');
  const meth = sm.row_kind === 'method', word = { method: 'method', dataset: 'dataset', condition: 'case', group: 'group' }[sm.row_kind] || 'row';
  return h('span', { class: 'rx-field small', title: (meth ? 'Best: ' : 'Highest: ') + sm.best.label + ' ' + rxFmt(sm.best.value) + (sm.worst ? ' · ' + (meth ? 'worst: ' : 'lowest: ') + sm.worst.label + ' ' + rxFmt(sm.worst.value) : '') + ' · ' + sm.metric + (sm.lower ? ' (lower is better)' : '') },
    meth ? [h('b', { class: 'mono' }, rxFmt(sm.best.value)), h('span', { class: 'muted' }, ' ' + trunc(sm.best.label, 12))]
      : [h('span', { class: 'mono' }, rxFmt(sm.worst ? Math.min(sm.worst.value, sm.best.value) : sm.best.value) + '–' + rxFmt(sm.worst ? Math.max(sm.worst.value, sm.best.value) : sm.best.value)), h('span', { class: 'muted' }, ' ' + (sm.of || 0) + ' ' + word + 's')]);
}
function rxGapBar(sm) {
  if (sm && sm.study === 'benchmark') return rxFieldCell(sm);
  if (!sm || sm.gap == null) return h('span', { class: 'muted small' }, sm && sm.ours != null ? rxFmt(sm.ours) : '—');
  const W = 132, mid = 56, scale = Math.max(Math.abs(sm.gap), Math.abs(sm.best.value) * 0.12, 1e-9), len = Math.max(2, Math.min(mid - 2, Math.abs(sm.gap) / scale * (mid - 2)));
  const good = sm.gap > 0, s = sv('svg', { viewBox: '0 0 ' + W + ' 18', width: W, height: 18, class: 'rx-gap', role: 'img', 'aria-label': 'Ours ' + rxFmt(sm.ours) + ', best other ' + rxFmt(sm.best.value) + ' (' + sm.best.label + ')' });
  s.append(sv('line', { x1: mid, x2: mid, y1: 1, y2: 17, class: 'zero' }), sv('rect', { x: good ? mid : mid - len, y: 5, width: len, height: 8, rx: 2, class: sm.gap === 0 ? 'tie' : good ? 'good' : 'bad' }),
    sv('text', { x: mid + (good ? len + 4 : 4), y: 13, class: 'gl' }, (sm.gap > 0 ? '+' : '') + rxFmt(sm.gap)),
    sv('title', null, sm.ours_label + ' ' + rxFmt(sm.ours) + ' · best other: ' + sm.best.label + ' ' + rxFmt(sm.best.value) + ' · ' + sm.metric + (sm.lower ? ' (lower is better)' : '')));
  return s;
}
function rxSpark(spark) {
  if (!spark.some(p => p.o != null) && spark.some(p => p.b != null)) spark = spark.map(p => Object.assign({}, p, { o: p.b, b: null }));      // no "ours": follow the best of the field
  const pts = spark.filter(p => p.o != null); if (pts.length < 2) return h('span', { class: 'muted small' }, spark.length ? spark.length + '×' : '');
  const W = 90, H = 22, vals = spark.flatMap(p => [p.o, p.b]).filter(v => v != null), lo = Math.min(...vals), hi = Math.max(...vals), sp = hi - lo || 1;
  const x = i => 3 + i * (W - 6) / (spark.length - 1), y = v => H - 3 - (v - lo) / sp * (H - 6);
  const s = sv('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, class: 'rx-spark', role: 'img', 'aria-label': spark.length + ' versions of this result' });
  const path = k => { let d = '', pen = false; spark.forEach((p, i) => { if (p[k] == null || (p.r && k === 'o')) { pen = p[k] != null && p.r ? (d += 'M' + x(i) + ',' + y(p[k]), true) : false; return; } d += (pen ? 'L' : 'M') + x(i) + ',' + y(p[k]); pen = true; }); return d; };
  s.append(sv('path', { d: path('b'), class: 'b' }), sv('path', { d: path('o'), class: 'o' }));
  spark.forEach((p, i) => { if (p.o != null) s.append(sv('circle', { cx: x(i), cy: y(p.o), r: i === spark.length - 1 ? 2.6 : 1.6, class: 'od' })); if (p.c) s.append(sv('line', { x1: x(i), x2: x(i), y1: H - 2, y2: H, class: 'tk' })); });
  return s;
}
function rxBaseOrBest(sm) {
  if (!(RX.experiments && RX.experiments.extends)) return rxGapBar(sm);
  if (sm && sm.base) return rxGapBar(Object.assign({}, sm, { gap: sm.base.gap, best: { label: sm.base.label, value: sm.base.value } }));
  return h('span', { class: 'muted small', title: 'The base method is not in these results' }, sm && sm.ours != null ? rxFmt(sm.ours) + ' · no base' : '—');
}
function rxTally(x) {
  if (!x.tally) return x.kind === 'figure' ? h('span', { class: 'rx-tl ' + (x.connected ? 'ok' : 'bad') }, x.connected ? '✓ linked' : '? not linked') : h('span', { class: 'muted small' }, x.connected ? '' : '? not linked');
  const t = x.tally, part = (k, cls) => t[k] ? h('span', { class: 'rx-tl ' + cls, title: RX_CELL[k][1] }, RX_CELL[k][0] + t[k]) : null;
  return h('span', { class: 'rx-tally' }, part('match', 'ok'), part('rounding', 'warn'), part('differs', 'bad'), part('loose', 'warn'), part('untraced', 'bad'));
}
const RX_XTYPE = { main: 'Main', ablation: 'Ablation', sensitivity: 'Sensitivity', tuning: 'Search', efficiency: 'Cost', analysis: 'Analysis', other: '' };
/* S24 step 1 (ADR-008): the claim-experiment link. One word from a rule; the sentence behind it on hover. */
const RX_LINK = { supports: ['supports', 'fine'], contradicts: ['contradicts', 'fix'], inconclusive: ['inconclusive', 'look'], not_run: ['not run', 'plain'] };
const RX_LINKS = ['supports', 'contradicts', 'inconclusive', 'not_run'];
const RX_LINK_TEST = { supports: ['test met', 'fine'], contradicts: ['test not met', 'plain'], inconclusive: ['no verdict', 'look'], not_run: ['not run', 'plain'] };      // benchmark study: a test that is not met is a result, not an error
function rxLinkChip(l) { const w = (l.rule === 'L5' ? RX_LINK_TEST : RX_LINK)[l.status] || RX_LINK.inconclusive; const ch = plainChip('', w[0], w[1] + ' lk-' + (l.rule === 'L5' && l.status === 'contradicts' ? 'not_run' : l.status)); ch.title = l.why + ' (rule ' + l.rule + (l.criterion_by === 'default' ? ', default criterion' : l.criterion_by === 'test' ? ', the claim’s own test' : '') + ')'; return ch; }
function rxLinkBar(bar, big) { const n = RX_LINKS.reduce((a, k) => a + (bar[k] || 0), 0);
  return h('span', { class: 'rx-lbar' + (big ? ' big' : ''), role: 'img', 'aria-label': RX_LINKS.filter(k => bar[k]).map(k => bar[k] + ' ' + RX_LINK[k][0]).join(', ') || 'no experiment', title: RX_LINKS.filter(k => bar[k]).map(k => bar[k] + ' ' + RX_LINK[k][0]).join(' · ') || 'No experiment yet' },
    n ? RX_LINKS.map(k => bar[k] ? h('span', { class: 'lb-' + k, style: 'flex:' + bar[k] }) : null) : null); }
/* S24 step 3: what "supports" means for this claim and this experiment. The default applies until the map or you set another. */
const RX_OVER = { main: 'the main column', all: 'every dataset', majority: 'most datasets', average: 'the average over datasets' };
function rxCriterion(x, sec, link) {
  const c = link.criterion, cid = sec.claim_id || sec.id, ours = (x.summary || {}).ours_label;
  if (!c || c.kind === 'test') return h('div', { class: 'rx-crit' }, h('span', { class: 'rx-why-h' }, 'Decided by'), h('span', { class: 'rx-crit-t' }, 'the claim’s own test, not a method’s rank'), h('span', { class: 'tag' }, 'benchmark study'),
    h('span', { class: 'rx-crit-w muted small' }, link.why + ' Rule ' + link.rule + '.'));
  const who = { default: 'default', confirmed: 'from the confirmed map', you: 'set by you' }[link.criterion_by] || link.criterion_by;
  const cmpLabel = v => v === 'best_other' ? 'the best other method' : v === 'base' ? 'the base method' : v;
  const text = 'Ours ' + (c.strict ? 'better than ' : 'at least as good as ') + cmpLabel(c.compare) + ' on ' + RX_OVER[c.over] + (c.metric && c.over === 'main' ? ' (' + c.metric + ')' : '');
  const box = h('div', { class: 'rx-crit' }, h('span', { class: 'rx-why-h' }, 'Supports when'), h('span', { class: 'rx-crit-t' }, text), h('span', { class: 'tag' }, who),
    h('span', { class: 'rx-crit-w muted small' }, link.why + ' Rule ' + link.rule + '.'));
  if (READONLY) return box;
  const save = async cr => { const r = await rxPost('/api/experiment', { id: x.id, claim: cid, criterion: cr }); if (r) { RX.experiments = r; RX.setup = null; try { RX.claims = await apiGet('/api/claims'); } catch (e) { /* keep */ } renderAll(); } };
  const methods = ((x.grid || {}).rows || []).map(r => r.label).filter(l => l && l !== ours).slice(0, 30);
  const sel = (label, val, opts, on) => { const el = h('select', { 'aria-label': label }, opts.map(o => h('option', { value: o[0], selected: o[0] === val ? '' : null }, o[1]))); el.addEventListener('change', () => on(el.value)); return el; };
  const cur = { compare: c.compare, over: c.over, strict: !!c.strict };
  const strict = h('input', { type: 'checkbox', checked: c.strict ? '' : null }); strict.addEventListener('change', () => save(Object.assign({}, cur, { strict: strict.checked })));
  box.append(h('div', { class: 'rx-crit-e' },
    h('label', null, 'Against ', sel('Compare against', c.compare, [['best_other', 'the best other method']].concat(RX.experiments.extends ? [['base', 'the base method']] : [], methods.map(m => [m, m])), v => save(Object.assign({}, cur, { compare: v })))),
    h('label', null, 'over ', sel('Over', c.over, Object.keys(RX_OVER).map(k => [k, RX_OVER[k]]), v => save(Object.assign({}, cur, { over: v })))),
    h('label', { class: 'rx-crit-s' }, strict, ' a tie does not count'),
    link.criterion_by === 'you' ? h('button', { class: 'linkbtn small', onclick: () => save(null) }, 'Reset') : null));
  return box;
}
function rxThesisHead(E) {
  const T = E.thesis; if (!T) return null;
  const stages = RX_STAGES.filter(k => T.stages[k]).map(k => h('span', { class: 'rx-th-c' }, h('b', null, T.stages[k]), ' ' + RX_STAGE[k][1].toLowerCase()));
  const links = RX_LINKS.filter(k => T.links[k]).map(k => h('span', { class: 'rx-th-c lk-' + k }, h('b', null, T.links[k]), ' ' + RX_LINK[k][0]));
  const B = T.buckets, open = RX.exBucket;
  const bucket = (k, n, label, title) => h('button', { class: 'rx-th-b' + (n ? ' has' : '') + (open === k ? ' on' : ''), 'aria-expanded': String(open === k), title, disabled: n ? null : '', onclick: () => { RX.exBucket = open === k ? null : k; renderPage(true); } }, h('b', null, n), ' ' + label);
  const head = h('section', { class: 'rx-th' },
    h('div', { class: 'rx-th-k' }, h('span', { class: 'tag' }, 'Thesis'), T.loc ? rxWhere(T.loc) : null, h('span', { class: 'grow' }), h('button', { class: 'linkbtn small', title: 'Open the claims tree', onclick: () => { RX.sel = 'core'; RX.view = 'tree'; openTab('claims'); } }, 'Tree')),
    h('p', { class: 'rx-th-t serif' }, T.text ? rxMath(T.text) : h('span', { class: 'muted' }, 'No core message yet. It is drafted from the abstract on Claims.')),
    h('div', { class: 'rx-th-row' }, h('span', { class: 'rx-th-l' }, plural(T.claims, 'claim')), stages.length ? stages : h('span', { class: 'muted' }, 'none yet')),
    E.study === 'benchmark' ? null : h('div', { class: 'rx-th-row' }, h('span', { class: 'rx-th-l' }, plural(T.links_n, 'experiment link')), T.links_n ? [rxLinkBar(T.links, true), links] : h('span', { class: 'muted' }, 'none yet')),
    h('div', { class: 'rx-th-row' }, h('span', { class: 'rx-th-l' }, 'Gaps'), bucket('untested', B.untested, B.untested === 1 ? 'claim with no experiment' : 'claims with no experiment', 'Claims nothing tests yet'),
      bucket('no_claim', B.no_claim, B.no_claim === 1 ? 'experiment with no claim' : 'experiments with no claim', 'Results that back no claim')));
  if (open === 'untested' && B.untested) head.append(h('div', { class: 'rx-th-list' }, T.untested.map(c => h('button', { class: 'rx-th-i', title: 'Open in Claims', onclick: () => { RX.sel = c.id; RX.view = 'tree'; openTab('claims'); } }, h('b', null, c.short || ''), rxStageChip(c), h('span', { class: 'serif' }, rxMath(trunc(c.text, 120)))))));
  if (open === 'no_claim' && B.no_claim) head.append(h('div', { class: 'rx-th-list' }, h('button', { class: 'linkbtn', onclick: () => { const el = document.querySelector('.rx-x-sec.loose, .rx-x-sec.k-other'); if (el) el.scrollIntoView({ block: 'start' }); } }, 'They are listed under the claims ↓')));
  return head;
}
function rxExpHead(E) {
  const X = E && E.extends;
  return h('div', { class: 'rx-x-r head' }, h('span', null, 'Experiment'), h('span', null, 'Metric'), h('span', null, E && E.study === 'benchmark' ? 'What is compared' : X ? 'Ours vs ' + trunc(X.base.name, 12) : 'Ours vs best other'), h('span', null, 'Over time'), h('span', null, 'Paper'), h('span', null, 'Last'));
}
function rxExpRow(x, sec) {
  const key = (sec ? sec.id : '-') + '|' + x.id, open = RX.exOpen === key, tu = x.tuning, link = sec && sec.kind !== 'other' && sec.links ? sec.links[x.id] : null;
  const glyph = x.attention ? ['!', 'look'] : x.connected ? ['✓', 'fine'] : ['?', 'ign'];
  const row = h('div', { class: 'rx-x-r' + (open ? ' open' : '') + (x.attention ? ' att' : '') },
    h('button', { class: 'rx-x-main', 'aria-expanded': String(open), onclick: () => { RX.exOpen = open ? null : key; renderPage(true); } },
      h('span', { class: 'sg ' + glyph[1] }, glyph[0]), h('span', { class: 'rx-x-name' }, link ? rxLinkChip(link) : null, x.map && RX_XTYPE[x.type] ? h('span', { class: 'tag rx-x-ty t-' + x.type }, RX_XTYPE[x.type]) : null, h('b', null, x.name), x.map ? h('span', { class: 'muted small' }, ' · ' + plural(x.files_n, 'file')) : null, h('span', { class: 'muted' }, x.caption ? ' ' : ''), x.caption ? h('span', { class: 'muted' }, rxMath(trunc(x.caption, 60))) : null)),
    h('span', { class: 'rx-x-metric small muted', title: x.summary ? (x.summary.measure || x.summary.metric) + (x.summary.measure && x.summary.measure !== x.summary.metric ? ' · ' + x.summary.metric : '') : null }, x.summary ? trunc(x.summary.measure || x.summary.metric, 16) + (x.summary.target != null ? '' : x.summary.lower ? ' ↓' : ' ↑') : ''),
    tu ? h('span', { class: 'small', title: tu.best ? 'Best setting: ' + tu.best.label : null }, tu.best ? [h('b', { class: 'mono' }, rxFmt(tu.best.value)), h('span', { class: 'muted' }, ' best of ' + tu.runs)] : '') : rxBaseOrBest(x.summary), rxSpark(x.spark), rxTally(x),
    h('span', { class: 'muted small' }, x.stale ? h('span', { class: 'rx-tl warn', title: 'The code or settings changed after this result was written' }, '↻ old') : x.last ? dmon(x.last) : ''));
  if (open && link && sec) row.append(rxCriterion(x, sec, link));
  if (open) row.append(rxExpDetail(x.id));
  return row;
}
function rxHistoryChart(hist, sm) {
  const W = 640, H = 190, L = 44, R = 16, T = 30, B = 26, n = hist.length;
  const vals = hist.flatMap(p => [p.ours, p.best]).filter(v => v != null); if (!vals.length) return null;
  const lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo || Math.abs(hi) * 0.1 || 1) * 0.15, y0 = lo - pad, y1 = hi + pad;
  const x = i => n === 1 ? (L + W - R) / 2 : L + i * (W - L - R) / (n - 1), y = v => T + (y1 - v) / (y1 - y0) * (H - T - B);
  const s = sv('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'rx-hist', role: 'img', 'aria-label': 'How the result moved over ' + n + ' versions' });
  [y0 + pad, (lo + hi) / 2, y1 - pad].forEach(v => s.append(sv('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), class: 'grid' }), sv('text', { x: L - 6, y: y(v) + 3, class: 'ax', 'text-anchor': 'end' }, rxFmt(v))));
  const step = k => { let d = '', prev = null; hist.forEach((p, i) => { if (p[k] == null) { prev = null; return; } if (prev == null || (p.ruler && k === 'ours')) d += 'M' + x(i) + ',' + y(p[k]); else d += 'L' + x(i) + ',' + y(prev) + 'L' + x(i) + ',' + y(p[k]); prev = p[k]; }); return d; };
  s.append(sv('path', { d: step('best'), class: 'b' }), sv('path', { d: step('ours'), class: 'o' }));
  hist.forEach((p, i) => {
    if (p.ruler) s.append(sv('line', { x1: x(i) - 14, x2: x(i) - 14, y1: T - 6, y2: H - B, class: 'ruler' }));
    if (p.changes.length) {
      s.append(sv('line', { x1: x(i), x2: x(i), y1: T - 4, y2: H - B, class: 'ev' }));
      p.cats.forEach((c, j) => s.append(sv('text', { x: x(i) + (j - (p.cats.length - 1) / 2) * 12, y: T - 9, class: 'cat c-' + c + (p.attribution === 'bundled' ? ' bundled' : ''), 'text-anchor': 'middle' }, (RX_CAT[c] || ['•'])[0],
        sv('title', null, p.changes.map(ch => ch.short + ' ' + ch.subject + (ch.keys.length ? ' (' + ch.keys.map(k => k.key + ' ' + k.from + '→' + k.to).join(', ') + ')' : '')).join('\n')))));
    }
    if (p.ours != null) s.append(sv('circle', { cx: x(i), cy: y(p.ours), r: 4.5, class: 'od' + (p.rank === 1 ? ' first' : '') }, sv('title', null, dmon(p.time) + ' · ' + sm.ours_label + ' ' + rxFmt(p.ours) + (p.best != null ? ' · best other ' + rxFmt(p.best) + ' (' + p.best_label + ')' : '') + (p.rank ? ' · rank ' + p.rank + '/' + p.of : ''))));
    if (p.best != null) s.append(sv('circle', { cx: x(i), cy: y(p.best), r: 2.5, class: 'bd' }));
    if (p.became_best) s.append(sv('text', { x: x(i), y: y(p.ours) - 9, class: 'star', 'text-anchor': 'middle' }, '★'));
    s.append(sv('text', { x: x(i), y: H - 8, class: 'ax', 'text-anchor': 'middle' }, dmon(p.time)));
  });
  return s;
}
function rxPaperGrid(x) {
  if (!x.cells) return null;
  return h('div', { class: 'rx-ev-tablewrap wide' }, h('table', { class: 'tbl rx-chk' }, h('tbody', null, x.cells.map((r, i) => h('tr', null, r.map((c, j) => {
    const st = c.status, g = st ? RX_CELL[st] : null;
    return h(i && j ? 'td' : 'th', { class: (st ? 'c-' + st : '') + (c.bold ? ' bold' : '') + (c.bold_wrong ? ' boldwrong' : ''),
      title: st ? g[1] + (c.file != null ? ' · paper ' + c.text + ' · file ' + rxFmt(c.file) + (c.file_shown !== c.file ? ' → ' + rxFmt(c.file_shown) : '') + ' (' + c.row + ', ' + c.col + ')' : '') + (c.bold_wrong ? ' · bold, but not the best in its column' : '') : null },
      rxMath(c.text), st ? h('span', { class: 'cg' }, g[0]) : null);
  }))))));
}
function rxExpDetail(id) {
  const box = h('div', { class: 'rx-x-d' }, h('div', { class: 'muted' }, '…'));
  const load = () => apiGet('/api/experiment?id=' + encodeURIComponent(id)).then(paint).catch(e => { clear(box).append(h('div', { class: 'muted' }, e.message)); });
  const post = async body => { const r = await rxPost('/api/experiment', Object.assign({ id }, body)); if (r) { try { RX.experiments = await apiGet('/api/experiments'); RX.setup = null; RX.todo = await apiGet('/api/todo').catch(() => RX.todo); } catch (e) { /* keep */ } renderPage(true); } };
  function paint(x) {
    const sm = x.summary, gh = u => u ? h('a', { class: 'ghl', href: u, target: '_blank', rel: 'noopener noreferrer' }, '↗') : null;
    const blk = (title, ...kids) => h('section', { class: 'rx-x-b' }, h('h4', null, title), kids);
    const out = [];
    // why this experiment exists: the claim it was run to test
    const why = x.why || x.questions || [], cl = id => RX.claims && RX.claims.claims.find(c => c.id === id);
    if (x.map || why.length) out.push(h('div', { class: 'rx-x-why' }, h('span', { class: 'rx-why-h' }, 'Why'), why.length ? why.map(q => { const c = cl(q.id);
      return h('button', { class: 'rx-why-r', title: 'Open this claim', onclick: () => { RX.sel = q.id; RX.view = 'tree'; openTab('claims'); } }, h('b', null, c ? c.short : q.label), c ? rxStageChip(c) : null, h('span', { class: 'serif' }, rxMath(trunc(q.text, 140)))); })
      : h('span', { class: 'rx-why none' }, 'This experiment tests no claim yet. Add the claim it is for to the project map, or it has no reason to be in the paper.')));
    if (x.caveats.length) out.push(h('div', { class: 'rx-x-cav' }, x.caveats.map(c => plainChip(c.k === 'stale' ? '↻' : '!', c.t, 'look'))));
    // result
    if (sm && x.table) {
      const rows = x.table.rows.filter(r => r.values[sm.metric] != null), vs = rows.map(r => r.values[sm.metric]), hi = Math.max(...vs.map(Math.abs)) || 1;
      const key = v => sm.target != null ? Math.abs(v - sm.target) : sm.lower ? v : -v;
      const sorted = rows.slice().sort((a, b) => key(a.values[sm.metric]) - key(b.values[sm.metric]));
      const sel = (cur, opts, fn, label) => { const s = h('select', { 'aria-label': label, disabled: READONLY }, opts.map(o => h('option', { value: o, selected: o === cur }, o))); s.addEventListener('change', () => fn(s.value)); return s; };
      out.push(blk('Result', h('div', { class: 'rx-x-ctl' }, x.map && sm.measures && sm.measures.length > 1 ? sel(sm.measure, sm.measures, v => post({ measure: v }), 'Measure') : null,
        sm.cols.length > 1 || !x.map ? sel(sm.metric, sm.cols, v => post({ metric: v }), x.map ? 'Dataset' : 'Metric') : null,
        sm.target != null ? h('span', { class: 'tag' }, '→ ' + sm.target + ' is best') : h('button', { class: 'btn sm', disabled: READONLY, title: 'Switch which direction is better', onclick: () => post({ lower: !sm.lower }) }, sm.lower ? '↓ lower is better' : '↑ higher is better'),
        x.tuning || sm.study === 'benchmark' ? null : [h('span', { class: 'muted small' }, 'ours:'), sel(sm.ours_label, sm.methods, v => post({ ours: v }), 'Our method'),
        sm.ours_by !== 'you' ? h('span', { class: 'muted small' }, ['paper', 'name', 'map'].includes(sm.ours_by) ? '' : '(guessed)') : null],
        sm.study === 'benchmark' ? h('span', { class: 'muted small' }, plural(rows.length, { method: 'method', dataset: 'dataset', condition: 'case', group: 'group' }[sm.row_kind] || 'row') + (sm.row_column ? ' (column ' + sm.row_column + ')' : '') + ', none of them “ours”') : null),
        h('div', { class: 'rx-bars' }, sorted.map((r, i) => { const v = r.values[sm.metric], me = r.label === sm.ours_label; return h('div', { class: 'rx-bar' + (me ? ' me' : '') },
          h('span', { class: 'bl' }, r.label, sm.base && r.label === sm.base.label ? h('span', { class: 'tag' }, 'base') : null), h('span', { class: 'bt' }, h('span', { class: 'bf', style: 'width:' + Math.max(1, Math.abs(v) / hi * 100) + '%' })),
          h('span', { class: 'bv mono' }, rxFmt(v) + (r.std[sm.metric] != null ? ' ±' + rxFmt(r.std[sm.metric]) : '')), h('span', { class: 'muted small' }, i === 0 && !(sm.study === 'benchmark' && sm.row_kind !== 'method') ? '★' : '')); }))));
    } else out.push(blk('Result', h('div', { class: 'rx-warn' }, x.map ? (x.connected ? 'These files could not be read as tables with the map’s metric.' : x.waiting ? 'Waiting for its result files: nothing matches its patterns yet. Lemmata looks again at every scan.' : 'No file matches this experiment’s patterns any more.') : x.connected ? 'The result file could not be read as a table (CSV or JSON with one row per method).' : 'No result file is connected. Put “% source: code:results/file.csv” above it in the LaTeX.')));
    // design
    const d = x.design || { scripts: [], settings: [], runs: [], values: [] };
    out.push(blk('Design', rxEditorRow(x) || (rxVsLink('x:' + id) ? h('div', { class: 'rx-x-ed' }, rxVsLink('x:' + id)) : null), h('dl', { class: 'rx-dl' },
      x.map && x.result ? [h('dt', null, 'Files'), h('dd', null, h('span', { class: 'rx-code mono' }, x.result.path), ' ', h('details', { class: 'rx-x-files' }, h('summary', null, plural(x.files_n, 'file')),
        (d.files || []).map(f => h('div', null, rxNodeBtn(f.node_id, f.path), Object.keys(f.fields).length ? h('span', { class: 'muted small' }, ' ' + Object.entries(f.fields).map(e => e[0] + ' ' + e[1]).join(' · ')) : null)), x.files_n > (d.files || []).length ? h('div', { class: 'muted small' }, '…') : null))] : null,
      x.map && x.paper.length ? [h('dt', null, 'In the paper'), h('dd', null, x.paper.map((p, i) => [i ? ', ' : null, rxNodeBtn(p.node_id, p.name)]))] : null,
      !x.map && x.result ? [h('dt', null, 'Result file'), h('dd', null, rxNodeBtn(x.result.node_id, x.result.path), ' ', gh(x.result.github))] : null,
      d.scripts.length || d.runs.length ? [h('dt', null, 'Made by'), h('dd', null, d.runs.map(r => [rxNodeBtn(r.node_id, r.name), r.command ? h('span', { class: 'muted mono small' }, ' ' + trunc(r.command, 60)) : null, ' ']), d.scripts.map((s, i) => [i ? ', ' : null, rxNodeBtn(s.node_id, s.name), ' ', gh(s.github)]))] : null,
      sm && sm.baselines.length ? [h('dt', null, 'Compared with'), h('dd', null, sm.baselines.map(b => h('span', { class: 'rx-code' }, b)))] : null,
      sm && sm.cols.length ? [h('dt', null, sm.datasets && sm.datasets.length ? 'Datasets' : 'Columns'), h('dd', null, (sm.datasets && sm.datasets.length ? sm.datasets : sm.cols).map(b => h('span', { class: 'rx-code' }, b)))] : null,
      d.values.length ? [h('dt', null, 'Settings'), h('dd', null, d.values.slice(0, 14).map(v => h('span', { class: 'rx-code mono', title: v.file }, v.key.split('.').pop() + ' = ' + v.value)))] : null,
      x.questions && x.questions.length ? [h('dt', null, 'Tests'), h('dd', null, x.questions.map(q => h('button', { class: 'chip-btn', title: q.text, onclick: () => { RX.sel = q.id; RX.view = 'tree'; openTab('claims'); } }, '◆ ' + ((cl(q.id) || {}).short || q.label))))] : null)));
    if (!READONLY) out.push(blk('Next experiments', rxPlanBox('x:' + id, 'experiment', false)));
    // history
    if (x.history && x.history.length) {
      const hs = x.history, chart = hs.length > 1 ? rxHistoryChart(hs, sm) : null;
      const word = { single: 'one change', bundled: 'several changes at once', none: 'no code change found', ruler: 'evaluation changed: not comparable', first: 'first version' };
      const fld = sm.study === 'benchmark';
      out.push(blk('History', chart, hs.length > 1 ? h('div', { class: 'rx-legend' }, fld ? null : h('span', null, h('span', { class: 'lg-o' }, '━'), ' ' + sm.ours_label), h('span', null, h('span', { class: 'lg-b' }, '┄'), fld ? ' best of the field' : ' best other'),
        Object.keys(RX_CAT).filter(c => hs.some(p => p.cats.includes(c))).map(c => h('span', null, h('span', { class: 'lg-g' }, RX_CAT[c][0]), ' ' + RX_CAT[c][1])), hs.some(p => p.became_best) ? h('span', null, '★ became best') : null) : null,
        h('div', { class: 'rx-steps' }, hs.slice().reverse().map(p => { const better = p.delta != null && (sm.lower ? p.delta < 0 : p.delta > 0); return h('div', { class: 'rx-st' },
          h('span', { class: 'mono small muted' }, dmon(p.time)), h('span', { class: 'mono', title: fld && p.best_label ? 'Best: ' + p.best_label : null }, rxFmt(fld ? p.best : p.ours)),
          h('span', { class: 'mono rx-dlt ' + (p.delta == null || p.delta === 0 ? '' : better ? 'good' : 'bad') }, p.delta == null ? '' : (p.delta > 0 ? '+' : '') + rxFmt(p.delta)),
          h('span', { class: 'rx-st-w' }, p.became_best ? h('b', null, '★ became best · ') : null, p.rank ? h('span', { class: 'muted' }, '#' + p.rank + '/' + p.of + ' · ') : null,
            p.changes.length ? p.changes.map((c, i) => [i ? '; ' : null, c.cats.map(k => h('span', { class: 'lg-g c-' + k, title: (RX_CAT[k] || ['', k])[1] }, (RX_CAT[k] || ['•'])[0])), ' ' + c.subject, c.keys.length ? h('span', { class: 'mono small' }, ' ' + c.keys.map(k => k.key + ' ' + k.from + '→' + k.to).join(', ')) : null]) : h('span', { class: 'muted' }, p.subject),
            p.attribution !== 'single' && p.attribution !== 'first' ? h('span', { class: 'tag' + (p.attribution === 'bundled' || p.attribution === 'ruler' ? ' warn' : '') }, word[p.attribution]) : null)); }))));
    }
    // paper check
    if (x.cells) out.push(blk('Paper check', rxPaperGrid(x),
      h('div', { class: 'rx-legend' }, Object.keys(RX_CELL).filter(k => x.tally && x.tally[k]).map(k => h('span', null, h('span', { class: 'cg c-' + k }, RX_CELL[k][0]), ' ' + RX_CELL[k][1])), h('span', { class: 'grow' }), rxWhere(x.loc)),
      x.problems.map(p => h('div', { class: 'rx-warn' }, p.kind === 'differs' ? ['✕ ' + p.row + ' · ' + p.col + ': paper ', h('b', null, p.paper), ', file ', h('b', null, rxFmt(p.file))] : ['Bold ', h('b', null, p.paper), ' in “' + p.col + '” is not the best value (' + rxFmt(p.best) + ').'])),
      x.stale ? h('div', { class: 'rx-warn' }, '↻ ' + x.stale.newer.map(n => n.name).join(', ') + ' changed after ' + x.stale.file + ' was written.') : null));
    else if (x.kind === 'figure') out.push(blk('Paper check', h('div', { class: 'row' }, x.image && !READONLY ? h('img', { class: 'rx-x-fig', src: apiUrl('/api/thumb?node=' + encodeURIComponent(x.id)), alt: x.name, onerror: ev => ev.target.remove() }) : null,
      h('div', { class: 'muted small' }, x.connected ? 'Linked to the files above. Numbers inside a picture cannot be checked.' : 'No script or result file found behind this figure.'))));
    clear(box).append(out);
  }
  load();
  return box;
}
const RX_MAP_PROMPT = name => 'Use Lemmata to understand the project "' + name + '": call project_brief (every part), read the paper and code if you have them, then propose_map. If this work extends the linked paper, set base (the original method) and goal (the new target). Fix whatever the checker drops and propose again.';
function rxMapCard() {
  const M = RX.map, E = RX.experiments; if (!M) return null;
  const act = async (path, body, msg) => { const r = await rxPost(path, body, msg); if (r) { RX.map = r; if (path.endsWith('confirm')) RX.mapOpen = false; try { RX.experiments = await apiGet('/api/experiments'); RX.setup = null; RX.todo = await apiGet('/api/todo').catch(() => RX.todo); RX.claims = await apiGet('/api/claims'); RX.tree = await apiGet('/api/tree'); } catch (e) { /* keep */ } renderLeft(); renderPage(true); } };
  const name = S.project ? S.project.name : 'this project';
  if (M.state === 'none') return h('section', { class: 'rx-map none' },
    h('div', { class: 'rx-map-h' }, h('span', { class: 'sg look' }, '◌'), h('b', null, 'Not mapped yet'), h('span', { class: 'grow' }),
      READONLY ? null : h('button', { class: 'btn sm', title: 'A rough map from file names and columns, no AI', onclick: () => act('/api/map/draft', {}, 'Draft ready to review') }, 'Draft by rules')),
    READONLY ? null : h('div', { class: 'rx-map-ask' }, h('button', { class: 'btn sm primary', title: 'Paste it into your Claude Code to map this project: ' + RX_MAP_PROMPT(name), onclick: () => copyText(RX_MAP_PROMPT(name)) }, 'Copy prompt for Claude Code')));
  const m = M.proposed || M.confirmed, prop = M.state === 'proposed', cov = M.coverage || { n_files: 0, files: [], paper: [], total: 0 };
  const dropped = (M.report || []).filter(r => r.level === 'dropped'), warns = (M.report || []).filter(r => r.level !== 'dropped');
  const qOpts = m.questions.map(q => [q.id, q.label]);
  const head = h('div', { class: 'rx-map-h' }, h('span', { class: 'sg ' + (prop ? 'look' : 'fine') }, prop ? '◐' : '✓'),
    h('b', { title: prop ? 'Not used until you confirm' : null }, prop ? 'Proposed map' : 'Project map'), h('span', { class: 'muted small' }, prop ? 'by ' + (M.proposed_by || 'agent') : M.confirmed_at ? dmon(M.confirmed_at) : ''),
    h('span', { class: 'grow' }),
    h('span', { class: 'rx-map-n' }, m.study === 'benchmark' ? h('span', { title: 'A benchmark study has no method of its own' }, h('b', null, 'Benchmark')) : h('span', { title: 'Our method' }, h('b', null, m.method ? m.method.name : '?')), m.base ? h('span', { title: 'Extends' }, '↳ ', h('b', null, m.base.name)) : null, h('span', { title: 'Questions' }, '◆ ', h('b', null, m.questions.length)), h('span', { title: 'Experiments' }, '▦ ', h('b', null, m.experiments.length)),
      cov.n_files ? h('span', { class: 'warn' }, h('b', null, cov.n_files), ' files unmapped') : null, dropped.length ? h('span', { class: 'bad' }, h('b', null, dropped.length), ' dropped') : null),
    prop && !READONLY ? [h('button', { class: 'btn sm', onclick: () => act('/api/map/discard', {}, 'Proposal discarded') }, 'Discard'), h('button', { class: 'btn sm primary', disabled: !m.experiments.length, onclick: () => act('/api/map/confirm', {}, 'Map confirmed') }, 'Confirm')] : null);
  const edit = change => act('/api/map/edit', { change });
  const body = h('details', { class: 'rx-map-d', open: prop || RX.mapOpen ? '' : null, ontoggle: ev => { if (!prop) RX.mapOpen = ev.target.open; } }, h('summary', null, prop ? 'Review' : 'Show map'),
    h('div', { class: 'rx-map-row' }, h('span', { class: 'rx-map-k' }, 'Study'),
      READONLY ? h('b', null, m.study === 'benchmark' ? 'Benchmark study' : 'Method paper') : (() => { const st = h('select', { class: 'rx-map-sc', 'aria-label': 'Kind of study' }, [['method', 'Method paper (has an “ours”)'], ['benchmark', 'Benchmark study (no method of its own)']].map(o => h('option', { value: o[0], selected: (m.study || 'method') === o[0] ? '' : null }, o[1]))); st.addEventListener('change', () => edit({ study: st.value })); return st; })(),
      m.study === 'benchmark' ? h('span', { class: 'muted small' }, Object.keys(m.roles || {}).length ? Object.entries(m.roles).map(e => e[0] + ': ' + e[1].join(', ')).join(' · ') : 'columns read by their usual names (model, dataset, variant, seed)') : null),
    m.study === 'benchmark' ? null : h('div', { class: 'rx-map-row' }, h('span', { class: 'rx-map-k' }, 'Ours'), READONLY ? h('b', null, m.method ? m.method.name : '?') : (() => { const i = h('input', { class: 'rx-map-in', value: m.method ? m.method.name : '', 'aria-label': 'Name of our method', placeholder: 'Method name' }); i.addEventListener('change', () => edit({ method: i.value })); return i; })(),
      m.method && m.method.aliases.length ? h('span', { class: 'muted small' }, 'also ' + m.method.aliases.join(', ')) : null),
    m.study === 'benchmark' ? null : h('div', { class: 'rx-map-row' }, h('span', { class: 'rx-map-k', title: 'The method of the paper this work extends' }, 'Extends'),
      READONLY ? h('b', null, m.base ? m.base.name : '—') : (() => { const i = h('input', { class: 'rx-map-in', value: m.base ? m.base.name : '', 'aria-label': 'Method being extended', placeholder: 'none' }); i.addEventListener('change', () => edit({ base: i.value })); return i; })(),
      h('span', { class: 'rx-map-k' }, 'Goal'),
      READONLY ? h('span', null, m.goal || '—') : (() => { const i = h('input', { class: 'rx-map-in wide', value: m.goal || '', 'aria-label': 'New target of the extension', placeholder: 'What the extension aims at, in one sentence' }); i.addEventListener('change', () => edit({ goal: i.value })); return i; })()),
    m.questions.map(q => h('div', { class: 'rx-map-row' }, h('span', { class: 'rx-map-k' }, q.label),
      m.base && !READONLY ? (() => { const sc = h('select', { class: 'rx-map-sc', 'aria-label': 'Original claim or extension' }, [['extension', 'Extension'], ['base', 'Original']].map(o => h('option', { value: o[0], selected: q.scope === o[0] }, o[1]))); sc.addEventListener('change', () => edit({ question: { id: q.id, scope: sc.value } })); return sc; })() : null, q.source === 'notes' ? h('span', { class: 'tag warn', title: 'Taken from your notes, not stated in the paper' }, 'notes') : null, h('span', { class: 'serif' }, rxMath(q.text)), q.evidence[0] ? rxWhere(q.evidence[0], q.evidence[0].repo) : null,
      READONLY ? null : h('button', { class: 'linkbtn small', title: 'Remove this question', onclick: () => edit({ remove: 'question:' + q.id }) }, '✕'))),
    h('div', { class: 'rx-map-tw' }, h('table', { class: 'tbl rx-map-t' }, h('thead', null, h('tr', null, ['Experiment', 'Kind', 'Tests', 'Files', 'Metric', 'Paper', ''].map(t => h('th', null, t)))),
      h('tbody', null, m.experiments.map(x => { const ty = h('select', { disabled: READONLY, 'aria-label': 'Kind' }, Object.keys(RX_XTYPE).map(t => h('option', { value: t, selected: t === x.type }, RX_XTYPE[t] || 'Other')));
        ty.addEventListener('change', () => edit({ experiment: { id: x.id, type: ty.value } }));
        const ts = h('select', { disabled: READONLY, 'aria-label': 'Which question it tests' }, h('option', { value: '' }, '—'), qOpts.map(o => h('option', { value: o[0], selected: x.tests[0] === o[0] }, o[1] + (x.tests.length > 1 && x.tests[0] === o[0] ? ' +' + (x.tests.length - 1) : ''))));
        ts.addEventListener('change', () => edit({ experiment: { id: x.id, tests: ts.value ? [ts.value] : [] } }));
        return h('tr', null, h('td', null, h('b', null, x.name), x.note ? h('div', { class: 'muted small' }, trunc(x.note, 90)) : null), h('td', null, ty), h('td', null, ts),
          h('td', { class: 'mono small', title: x.files.join('\n') }, x.waiting ? h('span', { class: 'tag warn', title: 'No file matches yet. Lemmata looks again at every scan.' }, 'waiting') : h('b', null, x.matched), ' ' + trunc(x.files[0] || '', 30)), h('td', { class: 'mono small' }, x.metric || h('span', { class: 'muted' }, 'guess')),
          h('td', { class: 'small' }, x.paper.map((p, i) => [i ? ', ' : null, rxNodeBtn(p, ((IX.node && IX.node.get(p)) || {}).name || p)])), h('td', null, READONLY ? null : h('button', { class: 'linkbtn small', title: 'Remove this experiment', onclick: () => edit({ remove: 'experiment:' + x.id }) }, '✕'))); })))),
    m.ignore.length ? h('div', { class: 'rx-map-row' }, h('span', { class: 'rx-map-k' }, 'Ignored'), m.ignore.map(p => h('span', { class: 'rx-code mono' }, p))) : null,
    dropped.length ? h('div', { class: 'rx-map-rep' }, h('b', null, 'Dropped by the checker'), dropped.map(r => h('div', { class: 'rx-warn' }, '✕ ' + r.where + ': ' + r.why))) : null,
    warns.length ? h('div', { class: 'rx-map-rep' }, warns.map(r => h('div', { class: 'muted small' }, (r.level === 'waiting' ? '… ' : '! ') + r.where + ': ' + r.why))) : null,
    !READONLY ? h('div', { class: 'rx-map-ask' }, h('button', { class: 'btn sm', title: 'Paste it into your Claude Code to redo the map: ' + RX_MAP_PROMPT(name), onclick: () => copyText(RX_MAP_PROMPT(name)) }, 'Copy prompt for Claude Code'),
      !prop ? h('button', { class: 'btn sm', onclick: () => act('/api/map/draft', {}, 'Draft ready to review') }, 'Draft by rules') : null) : null);
  return h('section', { class: 'rx-map ' + M.state }, head, body);
}
function rxUnmapped(U) {
  if (!U || (!U.n_files && !U.paper.length)) return null;
  const post = async p => { const r = await rxPost('/api/map/edit', { change: { ignore: p } }, 'Ignored. Confirm the map to apply.'); if (r) { RX.map = r; renderPage(true); } };
  return h('section', { class: 'rx-x-sec loose' }, h('div', { class: 'rx-x-h' }, h('span', { class: 'sg ign' }, '○'), h('span', { class: 'rx-x-q static' }, 'Not in the map'),
    h('span', { class: 'rx-x-qt muted' }, [U.n_files ? plural(U.n_files, 'result file') : null, U.paper.length ? plural(U.paper.length, 'table or figure', 'tables or figures') : null].filter(Boolean).join(' · ')), h('span', { class: 'grow' })),
    h('div', { class: 'rx-um' }, U.files.map(c => h('div', { class: 'rx-um-r' }, h('span', { class: 'rx-code mono' }, c.pattern), h('span', { class: 'muted small' }, plural(c.n, 'file') + (c.columns.length ? ' · ' + trunc(c.columns.join(', '), 50) : '')), h('span', { class: 'grow' }),
      READONLY ? null : h('button', { class: 'linkbtn small', title: 'Never show files like these', onclick: () => post(c.pattern) }, 'Ignore'))),
      U.paper.map(p => h('div', { class: 'rx-um-r' }, rxNodeBtn(p.node_id, p.name), h('span', { class: 'muted small' }, trunc(p.caption, 80)), h('span', { class: 'grow' }), h('span', { class: 'rx-tl bad' }, '? no experiment')))));
}
/* The map: ours on the left, the questions it must answer, and the experiments behind each. Click a question for its
   progress, an experiment for its detail. Positions are computed, never dragged. */
function rxExpState(x, X) { return rxExpState0(x, X); }
function rxExpState0(x, X) {
  const sm = x.summary; if (x.tuning || !sm) return { k: 'none', g: null };
  const g = X ? (sm.base ? sm.base.gap : null) : sm.gap;
  return { k: g == null ? 'none' : g > 0 ? 'ahead' : g < 0 ? 'behind' : 'tie', g };
}
const RX_XSTATE = { ahead: ['▲', 'Ahead'], behind: ['▼', 'Behind'], tie: ['=', 'Level'], none: ['·', 'No comparison'] };
function rxExpMap(E, renderSec) {
  const X = E.extends, secs = E.sections, vs = X ? X.base.name : 'the best other method';
  const exps = [], seen = new Map(), own = new Set();
  secs.forEach(s => s.experiments.forEach(x => { if (!seen.has(x.id)) { seen.set(x.id, x); exps.push(x); } if (s.scope !== 'base') own.add(x.id); }));
  // an experiment that only re-checks the original paper's claim compares that paper's method with the others, as the paper did
  const rxExpState = (x, X_) => rxExpState0(x, X_ && own.has(x.id) ? X_ : null);
  const RH = 44, QH = 108, GAP = 14, CX = [0, 225, 555], CW = [195, 290, 245], W = CX[2] + CW[2];
  const ey = new Map(exps.map((x, i) => [x.id, i * RH]));
  const qy = new Map(); let bottom = 0, sc0;
  secs.forEach(s => { if (X && s.kind !== 'other' && s.scope !== sc0) { sc0 = s.scope; bottom += 26; } const ys = s.experiments.map(x => ey.get(x.id) + RH / 2); const want = ys.length ? ys.reduce((a, c) => a + c, 0) / ys.length - QH / 2 : bottom; const y = Math.max(bottom, want); qy.set(s.id, y); bottom = y + QH + GAP; });
  const H = Math.max(bottom - GAP, exps.length * RH, 200), rootY = H / 2 - 70;
  const sel = RX.mapSel || '', selQ = sel.startsWith('q:') ? sel.slice(2) : null, selX = sel.startsWith('x:') ? sel.slice(2) : null;
  const litX = new Set(), litQ = new Set();
  if (selQ) { litQ.add(selQ); (secs.find(s => s.id === selQ) || { experiments: [] }).experiments.forEach(x => litX.add(x.id)); }
  if (selX) { litX.add(selX); secs.forEach(s => { if (s.experiments.some(x => x.id === selX)) litQ.add(s.id); }); }
  const dim = (set, id) => sel && !set.has(id) ? ' dim' : '';
  const pick = k => { RX.mapSel = RX.mapSel === k ? null : k; RX.exOpen = null; renderPage(true); };
  const svg = sv('svg', { class: 'rx-m-edges', viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, 'aria-hidden': 'true' });
  const curve = (x1, y1, x2, y2) => 'M' + x1 + ',' + y1 + ' C' + (x1 + x2) / 2 + ',' + y1 + ' ' + (x1 + x2) / 2 + ',' + y2 + ' ' + x2 + ',' + y2;
  const box = h('div', { class: 'rx-m', style: 'width:' + W + 'px;height:' + H + 'px' }, svg);
  // tally
  const tally = list => { const t = { ahead: 0, behind: 0, tie: 0, none: 0, check: 0 }; list.forEach(x => { t[rxExpState(x, X).k]++; if (x.attention) t.check++; }); return t; };
  const meter = (list, big) => { const t = tally(list), n = list.length || 1; return h('span', { class: 'rx-m-meter' + (big ? ' big' : ''), title: t.ahead + ' ahead, ' + t.behind + ' behind, ' + t.tie + ' level, ' + t.none + ' without a comparison' },
    ['ahead', 'tie', 'behind', 'none'].map(k => t[k] ? h('span', { class: 'm-' + k, style: 'flex:' + t[k] }) : null)); };
  const all = tally(exps), cmp = all.ahead + all.behind + all.tie;
  box.append(h('button', { class: 'rx-m-root' + (sel ? ' dim' : ''), style: 'left:0;top:' + rootY + 'px;width:' + CW[0] + 'px', onclick: () => { RX.mapSel = null; renderPage(true); }, title: 'Show everything' },
    E.thesis && E.thesis.text ? h('span', { class: 'rx-m-goal rx-m-thesis serif' }, rxMath(trunc(E.thesis.text, 110))) : null,
    h('span', { class: 'rx-m-ours' + (E.thesis && E.thesis.text ? ' sub' : '') }, E.study === 'benchmark' ? 'Benchmark study' : (E.map && E.map.method ? E.map.method.name : null) || 'Ours'), X ? h('span', { class: 'rx-m-sub' }, 'extends ' + X.base.name) : null,
    X && X.goal ? h('span', { class: 'rx-m-goal serif' }, trunc(X.goal, 90)) : null, meter(exps, true),
    h('span', { class: 'rx-m-sub' }, E.study === 'benchmark' ? plural(exps.length, 'experiment') + ', each claim decided by its test' : cmp ? 'Ahead of ' + trunc(vs, 18) + ' in ' + all.ahead + ' of ' + cmp : 'Nothing to compare yet'), all.check ? h('span', { class: 'rx-m-chk' }, '! ' + all.check + ' to check') : null));
  let lastScope;
  secs.forEach(s => {
    const y = qy.get(s.id), t = tally(s.experiments), c = t.ahead + t.behind + t.tie, st = s.stage ? RX_STAGE[s.stage] : RX_STATUS[s.status];
    svg.append(sv('path', { d: curve(CW[0], rootY + 70, CX[1], y + QH / 2), class: 'me' + dim(litQ, s.id) }));
    if (X && s.scope !== lastScope && s.kind !== 'other') { box.append(h('span', { class: 'rx-m-scope', style: 'left:' + CX[1] + 'px;top:' + (y - 24) + 'px' }, s.scope === 'extension' ? 'New claims' : s.scope === 'base' ? 'Original paper, re-checked' : '')); lastScope = s.scope; }
    box.append(h('button', { class: 'rx-m-q' + (s.stage ? rxSt(s.stage) : ' st-' + s.status) + (selQ === s.id ? ' sel' : '') + dim(litQ, s.id), style: 'left:' + CX[1] + 'px;top:' + y + 'px;width:' + CW[1] + 'px;height:' + QH + 'px', 'aria-pressed': String(selQ === s.id), onclick: () => pick('q:' + s.id) },
      h('span', { class: 'rx-m-qh' }, h('b', null, s.short || s.label), s.stage ? h('span', { class: 'rx-m-stage ' + st[2], title: s.stage_why || '' }, st[0] + ' ' + st[1]) : null, h('span', { class: 'grow' }), s.stage ? null : h('span', { class: 'sg ' + st[2] }, st[0])),
      h('span', { class: 'rx-m-qt serif' }, rxMath(trunc(s.text, 96))),
      s.experiments.length ? h('span', { class: 'rx-m-qf' }, meter(s.experiments), h('span', { class: 'rx-m-sub' }, c ? t.ahead + ' of ' + c + ' ahead' : plural(s.experiments.length, 'experiment'))) : h('span', { class: 'rx-m-qf' }, h('span', { class: 'rx-m-chk bad' }, 'Not tested yet'))));
    s.experiments.forEach(x => { const es = rxExpState(x, X); svg.append(sv('path', { d: curve(CX[1] + CW[1], y + QH / 2, CX[2], ey.get(x.id) + RH / 2), class: 'me x-' + es.k + (sel && !(litQ.has(s.id) && litX.has(x.id)) ? ' dim' : '') })); });
  });
  exps.forEach(x => { const es = rxExpState(x, X), g = RX_XSTATE[es.k];
    box.append(h('button', { class: 'rx-m-x x-' + es.k + (selX === x.id ? ' sel' : '') + dim(litX, x.id), style: 'left:' + CX[2] + 'px;top:' + (ey.get(x.id) + 4) + 'px;width:' + CW[2] + 'px;height:' + (RH - 8) + 'px', 'aria-pressed': String(selX === x.id), onclick: () => pick('x:' + x.id),
      title: x.name + ' · ' + (x.tuning ? 'Search: best of ' + x.tuning.runs : g[1] + (es.g != null ? ' of ' + vs + ' by ' + rxFmt(Math.abs(es.g)) : '')) + (x.attention ? ' · something to check' : '') },
      h('span', { class: 'rx-m-g' }, g[0]), h('span', { class: 'rx-m-xn' }, x.name), x.attention ? h('span', { class: 'rx-m-chk' }, '!') : null,
      h('span', { class: 'rx-m-xv mono' }, x.tuning ? 'best of ' + x.tuning.runs : es.g != null ? (es.g > 0 ? '+' : es.g < 0 ? '−' : '') + rxFmt(Math.abs(es.g)) : ''))); });
  const out = [h('div', { class: 'rx-m-wrap' }, box),
    h('div', { class: 'rx-legend' }, Object.keys(RX_XSTATE).map(k => h('span', null, h('span', { class: 'rx-m-g x-' + k }, RX_XSTATE[k][0]), ' ' + RX_XSTATE[k][1] + (k === 'ahead' || k === 'behind' ? ' ' + (k === 'ahead' ? 'of ' : '') + trunc(vs, 22) : ''))), h('span', null, '! to check'))];
  if (selQ) { const s = secs.find(q => q.id === selQ); if (s) out.push(renderSec(s)); }
  else if (selX && seen.has(selX)) { const x = seen.get(selX); out.push(h('section', { class: 'rx-x-sec' }, h('div', { class: 'rx-x-h' }, h('b', null, x.name), x.caption ? h('span', { class: 'muted' }, trunc(x.caption, 110)) : null), h('div', { class: 'rx-m-detail' }, rxExpDetail(x.id)))); }
  else out.push(h('p', { class: 'muted rx-m-hint' }, 'Click a claim to see the experiments run for it, or an experiment to see why it was run.'));
  return out;
}
function pageExperiments() {
  const nr = rxNotReady('Experiments'); if (nr) return nr;
  S.outline = [];
  let E = RX.experiments;
  const seg = h('div', { class: 'rx-seg', role: 'group', 'aria-label': 'View' }, [['table', 'Outline'], ['map', 'Map']].map(([k, l]) => h('button', { 'aria-pressed': String((RX.exView || 'table') === k), onclick: () => { RX.exView = k; renderPage(true); } }, l)), h('button', { 'aria-pressed': 'false', title: 'The claims as a tree', onclick: () => { RX.view = 'tree'; openTab('claims'); } }, 'Tree'));
  const root = doc(h('div', { class: 'row' }, h('h1', { class: 'ptitle grow' }, 'Thesis'), E ? seg : null));
  if (!E) return root.append(h('p', { class: 'muted' }, 'Not available.')), root;
  root.append(rxStudyLine(), rxBehindNote());
  const c = E.counts, mapped = !!E.unmapped;
  const HF = RX.hf && RX.hf.mode === 'hypothesis_first';
  if (HF) {
    // hypotheses are shown above with their own test; below, only what no hypothesis covers (no duplicate rows in the website or the VS Code tab)
    const own = new Set(RX.hf.hypotheses.map(x => x.claim_id).filter(Boolean));
    E = Object.assign({}, E, { sections: E.sections.filter(s => !own.has(mapped ? s.claim_id : s.id)) });
    root.append(rxHypoFirst());
    if (!E.sections.length && !(E.unassigned || []).length && !mapped) return root;
    root.append(h('h2', { class: 'hf-h2' }, 'Result files no hypothesis covers yet'));
  }
  if (!HF) root.append(rxThesisHead(E));
  const X = E.extends;
  if (X) root.append(h('div', { class: 'rx-ext' }, h('span', { class: 'rx-ext-b' }, h('b', null, (E.map.method || {}).name || 'Ours'), ' extends ', h('b', null, X.base.name)),
    X.goal ? h('span', { class: 'rx-ext-g serif' }, '→ ' + X.goal) : h('span', { class: 'muted small' }, 'No goal')));
  if (c.attention || E.sections.length) root.append(h('div', { class: 'rx-x-sum' }, h('span', null, h('b', null, c.experiments), ' experiments'), c.attention ? h('span', { class: 'warn' }, h('b', null, c.attention), ' to check') : null));
  const head = () => rxExpHead(E);
  const WORD = { supported: 'Tested, nothing to check', partial: 'Something to check', unsupported: 'Not tested' };
  const renderSec = s => {
    const st = RX_STATUS[s.status], cid = mapped ? s.claim_id : s.id;
    const sec = h('section', { class: 'rx-x-sec' + (s.kind === 'other' ? ' k-other' : '') + (s.stage ? rxSt(s.stage) : ' st-' + s.status) },
      h('div', { class: 'rx-x-h' }, s.stage ? null : h('span', { class: 'sg ' + st[2], title: mapped ? WORD[s.status] : st[1] }, st[0]),
        cid ? h('button', { class: 'rx-x-q', title: 'Open in Claims', onclick: () => { RX.sel = cid; RX.view = 'tree'; openTab('claims'); } }, s.short || s.label) : h('span', { class: 'rx-x-q static' }, s.label),
        s.stage ? rxStageChip(s) : null,
        h('span', { class: 'rx-x-qt serif' + (s.kind === 'other' ? ' muted' : '') }, rxMath(trunc(s.text, 150))), h('span', { class: 'grow' }), s.loc ? rxWhere(s.loc) : null, s.bar && s.kind !== 'other' && s.experiments.length && E.study !== 'benchmark' ? rxLinkBar(s.bar) : null, h('span', { class: 'muted small' }, s.experiments.length ? plural(s.experiments.length, 'experiment') : '')));
    if (s.experiments.length) sec.append(h('div', { class: 'rx-x-t' }, head(), s.experiments.map(x => rxExpRow(x, s))));
    else sec.append(h('div', { class: 'rx-x-none miss' }, h('span', null, 'Not tested yet'),
      READONLY ? null : s.suggested.map(g => h('button', { class: 'chip-btn', title: 'Link this as the experiment for it', onclick: async () => { const r = await rxPost('/api/claims/link', { id: s.id, target: g.node_id, on: true }); if (r) { RX.claims = r; await rxRefresh(); } } }, g.name + '?'))));
    return sec;
  };
  if (RX.exView === 'map') { root.classList.add('wide'); root.append(rxExpMap(E, renderSec)); }
  else {
    let lastScope;
    for (const s of E.sections) {
      if (X && s.scope !== lastScope && s.kind !== 'other') { root.append(h('h2', { class: 'rx-ext-h' }, s.scope === 'extension' ? 'New claims' : s.scope === 'base' ? 'The original paper’s claims, re-checked' : 'Other questions')); lastScope = s.scope; }
      root.append(renderSec(s));
    }
  }
  root.append(rxMapCard());
  if (mapped) root.append(rxUnmapped(E.unmapped));
  else if (E.unassigned.length) {
    const opts = E.sections.map(s => [s.id, s.label]), few = RX.exAll ? E.unassigned : E.unassigned.slice(0, 8);
    root.append(h('section', { class: 'rx-x-sec loose' }, h('div', { class: 'rx-x-h' }, h('span', { class: 'sg ign' }, '○'), h('span', { class: 'rx-x-q static' }, 'No question'), h('span', { class: 'rx-x-qt muted' }, plural(E.unassigned.length, 'result') + ' no question points to'), h('span', { class: 'grow' }),
        E.unassigned.length > 8 ? h('button', { class: 'linkbtn small', onclick: () => { RX.exAll = !RX.exAll; renderPage(true); } }, RX.exAll ? 'Show fewer' : 'Show all') : null),
      h('div', { class: 'rx-x-t' }, head(), few.map(x => { const row = rxExpRow(x, null);
        if (!READONLY && opts.length) { const sel = h('select', { class: 'rx-x-assign', 'aria-label': 'Which question does this test?' }, h('option', { value: '' }, 'Tests…'), opts.map(o => h('option', { value: o[0] }, o[1])));
          sel.addEventListener('change', async () => { if (!sel.value) return; const r = await rxPost('/api/claims/link', { id: sel.value, target: x.id, on: true }); if (r) { RX.claims = r; await rxRefresh(); } }); row.querySelector('.rx-x-main').after(sel); row.classList.add('assign'); }
        return row; }))));
  }
  if (RX.ledger && RX.ledger.rows.length) root.append(h('details', { class: 'details' }, h('summary', null, 'All result files (' + RX.ledger.rows.length + ')'), rxLedgerList()));
  return root;
}
function rxLedgerList() {
  const L = RX.ledger, rows = L.rows, out = [];
  const stChip = r => r.status === 'stale' ? plainChip('↻', 'Out of date', 'look') : r.status === 'current' ? plainChip('✓', 'Current', 'fine') : plainChip('?', 'No known source', 'ign');
  for (const r of rows) {
    out.push(h('article', { class: 'card rx-ex st-' + r.status },
      h('div', { class: 'rx-ex-h' }, h('button', { class: 'linkbtn', 'aria-expanded': String(RX.exSel === r.node_id), onclick: () => { RX.exSel = RX.exSel === r.node_id ? null : r.node_id; renderPage(true); } }, h('b', null, r.name)), stChip(r), h('span', { class: 'grow' }), r.made ? h('span', { class: 'muted small' }, 'written ' + absTime(r.made.time) + ' · ', mono(r.made.short)) : null),
      h('dl', { class: 'rx-dl' },
        r.code.length || r.runs.length ? [h('dt', null, 'Made by'), h('dd', null, r.runs.map(x => [rxNodeBtn(x.node_id, x.name), x.command ? h('span', { class: 'muted mono small' }, ' ' + trunc(x.command, 70)) : null, ' ']), r.code.map((x, i) => [i || r.runs.length ? ', ' : null, rxNodeBtn(x.node_id, x.name)]))] : [h('dt', null, 'Made by'), h('dd', { class: 'muted' }, 'Unknown. No script writes a file with this name.')],
        r.settings.length ? [h('dt', null, 'Settings'), h('dd', null, r.settings.map((x, i) => [i ? ', ' : null, rxNodeBtn(x.node_id, x.name)]))] : null,
        h('dt', null, 'Used in'), h('dd', null, r.used_by.length ? r.used_by.map((x, i) => [i ? ', ' : null, rxNodeBtn(x.node_id, x.name)]) : h('span', { class: 'muted' }, 'Nothing in the paper.')),
        r.claims.length ? [h('dt', null, 'Backs'), h('dd', null, r.claims.map((x, i) => [i ? ', ' : null, h('button', { class: 'linkbtn', onclick: () => { RX.open[x.id] = true; RX.filter = 'all'; openTab('claims'); } }, x.label)]))] : null),
      RX.exSel === r.node_id ? rxEvidenceCard(r.node_id) : null,
      r.newer.length ? h('div', { class: 'rx-warn' }, '↻ Changed after this file was written: ', r.newer.slice(0, 3).map((x, i) => [i ? '; ' : null, h('b', null, x.name), ' on ' + dmon(x.time) + ' (“' + trunc(x.subject || '', 60) + '”)']), '. Rerun it, or check that the change does not affect the output.') : null));
  }
  return out;
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
/* One baseline, opened: every shared experiment with ours and the baseline side by side (no hover needed to see the numbers). */
function rxBaselineTable(b, ours) {
  const G = { ahead: ['▲', 'fine', 'Ahead'], behind: ['▼', 'fix', 'Behind'], tie: ['=', 'ign', 'Level'] };
  const oursName = (b.experiments.find(x => x.ours_label) || {}).ours_label || ours;
  const dir = x => x.target != null ? '→ ' + x.target : x.lower ? '↓' : '↑';
  return h('div', { class: 'rx-rv-bd' }, h('table', { class: 'tbl rx-bt' },
    h('thead', null, h('tr', null, h('th', null, 'Experiment'), h('th', null, 'Metric'), h('th', { class: 'num me' }, oursName), h('th', { class: 'num' }, b.name), h('th', { class: 'num' }, 'Gap'))),
    h('tbody', null, b.experiments.map(x => { const g = G[x.state] || G.tie;
      return h('tr', { class: 'x-' + x.state },
        h('td', null, h('button', { class: 'linkbtn', title: (x.question ? x.question + ' · ' : '') + 'Open this experiment', onclick: () => rxOpenExp(x.id) }, x.name)),
        h('td', { class: 'muted small' }, (x.metric || '') + (x.col ? ' · ' + x.col : ''), h('span', { title: x.target != null ? 'Closest to ' + x.target + ' is best' : x.lower ? 'Lower is better' : 'Higher is better' }, ' ' + dir(x))),
        h('td', { class: 'num mono me' }, x.ours == null ? '—' : rxFmt(x.ours)),
        h('td', { class: 'num mono' }, x.value == null ? '—' : rxFmt(x.value)),
        h('td', { class: 'num mono' }, h('span', { class: 'rx-bt-g ' + g[1], title: g[2] + ' (positive means ' + oursName + ' is better)' }, g[0] + ' ' + (x.gap > 0 ? '+' : x.gap < 0 ? '−' : '') + rxFmt(Math.abs(x.gap)))));
    }))),
    h('div', { class: 'muted small rx-bt-n' }, 'Gap: how much better ' + oursName + ' is on that experiment\'s metric. Positive means ahead, whichever direction the metric goes.'));
}
/* Review: should I continue? Three checks on top, the questions under them, the checklist one click down. */
const RX_VERDICT = { yes: ['✓', 'Yes', 'fine'], partly: ['◐', 'Partly', 'look'], no: ['✕', 'No', 'fix'], none: ['○', 'Not yet', 'ign'] };
const RX_CONF_PROMPT = name => 'Use Lemmata to check confounds for the project "' + name + '": call confound_brief, open the scripts and settings it names, then report_confounds for every question.';
/* S20 next experiments: Claude Code (the researcher's own) plans them from experiment_brief; the researcher reviews and copies the prompt. */
const RX_PLAN_PROMPT = (name, target, what) => 'Use Lemmata to plan the next experiment for the ' + what + ' "' + target + '" in the project "' + name + '": call experiment_brief with that target, open the scripts and settings it names, then call propose_experiments with up to three options, each as a structured spec in the format experiment_brief gives. Plan only: do not change code or run anything.';
const RX_PLAN_KIND = { rerun: 'Rerun', seeds: 'More seeds', baseline: 'Baseline', ablation: 'Ablation', sensitivity: 'Sensitivity', new: 'New', fix: 'Fix' };
/* One plan as a form: every section of the run prompt is a field; Lemmata renders the prompt from the fields (engine/plans.py). */
const RX_PLAN_FIELDS = [
  ['goal', 'Goal', 'area', 'One sentence: what the run finds out'],
  ['supports', 'Supports the claim if', 'area', 'Metric, datasets, seeds and margin'],
  ['against', 'Counts against it if', 'area', ''],
  ['inconclusive', 'Inconclusive if', 'line', 'Default: neither of the above'],
  ['context', 'Files to read first', 'lines', 'One per line: path — what it is'],
  ['protected', 'Leave unchanged', 'lines', 'One path per line: evaluation code, data splits, baselines, existing results'],
  ['steps', 'Changes to make', 'lines', 'One step per line, each as small as possible'],
  ['baseline_check', 'Reproduce first', 'line', 'A known value and tolerance, e.g. ADWIN fp 43.5 within 2'],
  ['smoke', 'Smoke test', 'mono', 'A tiny run that checks the pipeline end to end'],
  ['run', 'Full run', 'monolines', 'One command per line, seeds included'],
  ['results_to', 'Results go to', 'line', 'Path and layout of the new result files'],
  ['budget', 'Budget', 'line', 'e.g. at most 18 runs and 3 hours'],
  ['stop', 'Also stop if', 'lines', 'One condition per line (optional)']];
function rxPlanCard(p0) {
  let p = p0;
  RX.plOpen = RX.plOpen || {};
  const pre = h('pre', { class: 'rx-pl-pre mono' }, p.prompt);
  const lintBox = h('div', { class: 'rx-pl-lint' });
  const titleEl = h('b', null, p.title);
  const paintLint = () => { clear(lintBox); (p.lint || []).forEach(w => lintBox.append(h('div', { class: 'rx-warn small' }, '! ' + w))); };
  const save = async body => {
    try { const r = await apiPost('/api/plans', Object.assign({ id: p.id }, body)); RX.plans = r; const n = r.plans.find(x => x.id === p.id); if (n) { p = n; pre.textContent = p.prompt; titleEl.textContent = p.title; paintLint(); } }
    catch (e) { toast(e.message || 'Could not save that change.'); }
  };
  const asText = (k, kind) => { const v = p.spec[k]; return k === 'context' ? v.map(c => c.path + (c.role ? ' — ' + c.role : '')).join('\n') : Array.isArray(v) ? v.join('\n') : (v || ''); };
  const form = h('div', { class: 'rx-pl-form' }, h('label', { class: 'rx-pl-f' }, h('span', null, 'Title'), (() => { const i = h('input', { type: 'text', value: p.title, maxlength: '90', 'aria-label': 'Title' }); i.addEventListener('change', () => { if (i.value.trim()) save({ title: i.value }); }); return i; })()),
    RX_PLAN_FIELDS.map(([k, label, kind, ph]) => {
      const multi = kind === 'area' || kind === 'lines' || kind === 'monolines';
      const el = multi ? h('textarea', { rows: String(Math.max(2, Math.min(8, asText(k).split('\n').reduce((n, l) => n + Math.max(1, Math.ceil(l.length / (kind.startsWith('mono') ? 56 : 78))), 0)))), placeholder: ph, spellcheck: kind.startsWith('mono') ? 'false' : null, class: kind.startsWith('mono') ? 'mono' : null, 'aria-label': label }, asText(k))
        : h('input', { type: 'text', value: asText(k), placeholder: ph, spellcheck: kind === 'mono' ? 'false' : null, class: kind === 'mono' ? 'mono' : null, 'aria-label': label });
      el.addEventListener('change', () => { const v = el.value; save({ spec: { [k]: (kind === 'lines' || kind === 'monolines') ? v.split('\n').map(x => x.trim()).filter(Boolean) : v } }); });
      return h('label', { class: 'rx-pl-f' }, h('span', null, label), el);
    }));
  const det = (key, summary, body) => { const d = h('details', { class: 'rx-pl-d', open: RX.plOpen[p.id + key] ? '' : null }, h('summary', null, summary), body); d.addEventListener('toggle', () => { RX.plOpen[p.id + key] = d.open; }); return d; };
  paintLint();
  const rules = () => JSON.stringify({ permissions: { deny: p.deny } }, null, 2);
  return h('div', { class: 'rx-pl' + (p.state === 'copied' ? ' used' : '') },
    h('div', { class: 'rx-pl-h' }, h('span', { class: 'tag' }, RX_PLAN_KIND[p.kind] || p.kind), titleEl, p.edited ? h('span', { class: 'muted small' }, 'edited') : null,
      p.state === 'copied' ? h('span', { class: 'muted small' }, 'copied ' + dmon(p.copied_at)) : null),
    h('div', { class: 'rx-pl-l' }, h('span', { class: 'muted' }, 'Why '), p.why),
    h('div', { class: 'rx-pl-l' }, h('span', { class: 'muted' }, 'Decides '), h('span', null, 'supports if ' + (p.spec.supports || '?') + '; against if ' + (p.spec.against || '?'))),
    p.files.length ? h('div', { class: 'rx-pl-l' }, h('span', { class: 'muted' }, 'Builds on '), p.files.map((f, i) => [i ? ', ' : null, rxWhere(f, f.repo)])) : null,
    lintBox,
    det('f', 'Edit the experiment', form),
    det('p', 'Prompt for Claude Code', pre),
    h('div', { class: 'row rx-rv-act' },
      h('button', { class: 'btn sm' + (p.state === 'copied' ? '' : ' primary'), title: 'Copy the prompt, then paste it into a new Claude Code session in this project', onclick: () => { copyText(p.prompt); if (p.state !== 'copied') save({ state: 'copied' }); } }, 'Copy prompt for Claude Code'),
      p.deny && p.deny.length ? h('button', { class: 'btn sm', title: 'Claude Code permission rules that block its edit tools on the paths to leave unchanged. Add them to .claude/settings.local.json in the repository. They do not cover shell commands unless the sandbox is on.', onclick: () => copyText(rules()) }, 'Copy protection rules') : null,
      h('button', { class: 'linkbtn small', onclick: async () => { await save({ state: 'dropped' }); renderPage(true); } }, 'Drop')));
}
function rxPlanBox(target, what, label) {
  if (READONLY) return null;
  const name = S.project ? S.project.name : 'this project';
  const mine = ((RX.plans && RX.plans.plans) || []).filter(p => p.target === target);
  const ask = RX_PLAN_PROMPT(name, target, what);
  const refresh = async () => { try { RX.plans = await apiGet('/api/plans'); } catch (e) { toast(e.message || 'Could not load the plans.'); } renderPage(true); };
  return h('div', { class: 'rx-pl-box' }, label ? h('div', { class: 'rx-label' }, 'Next experiments') : null,
    mine.length ? mine.map(rxPlanCard) : h('div', { class: 'muted small' }, 'Claude Code reads this ' + what + ', its gaps and its scripts, and proposes up to three experiments. Each comes as a form you can change: goal, decision rule, files to read and to leave alone, steps, commands. Lemmata turns it into the prompt.'),
    h('div', { class: 'row rx-rv-act' },
      h('button', { class: 'btn sm' + (mine.length ? '' : ' primary'), title: 'Paste it into your Claude Code: ' + ask, onclick: () => copyText(ask) }, mine.length ? 'Plan again with Claude Code' : 'Plan with Claude Code'),
      h('button', { class: 'linkbtn small', onclick: refresh }, 'Check for new plans')));
}
function pageReview() {
  const nr = rxNotReady('Review'); if (nr) return nr;
  S.outline = [];
  const R = RX.review, days = RX.rvDays || 30, name = S.project ? S.project.name : 'this project';
  const setDays = async d => { RX.rvDays = d; try { RX.review = await apiGet('/api/review?days=' + d); } catch (e) { /* keep */ } renderPage(true); };
  const seg = h('div', { class: 'rx-seg', role: 'group', 'aria-label': 'Period' }, [[30, '30 days'], [7, '1 week'], [1, '1 day']].map(([d, l]) => h('button', { 'aria-pressed': String(days === d), disabled: READONLY && days !== d, onclick: () => setDays(d) }, l)));
  const root = doc(h('div', { class: 'row' }, h('h1', { class: 'ptitle grow' }, 'Review'), R ? seg : null));
  root.classList.add('wide');
  if (!R) return root.append(h('p', { class: 'muted' }, 'Not available.')), root;
  root.append(rxBehindNote());
  const post = async body => { const r = await rxPost('/api/review', Object.assign({ days }, body)); if (r) { RX.review = r; renderPage(true); } };
  const F = RX.rvFilter, fc = F && R.checks.find(c => c.k === F);
  root.append(h('div', { class: 'rx-rv-checks' }, R.checks.map((c, i) => { const v = RX_VERDICT[c.verdict];
    return h('button', { class: 'rx-rv-check v-' + c.verdict + (F === c.k ? ' sel' : ''), 'aria-pressed': String(F === c.k), title: (c.help || '') + ' Click to see the questions behind this.', onclick: () => { RX.rvFilter = F === c.k ? null : c.k; renderPage(true); } },
      h('span', { class: 'rx-rv-q' }, c.q), h('span', { class: 'rx-rv-v ' + v[2] }, v[0] + ' ' + (c.k === 'paper' && c.verdict === 'partly' ? 'For a smaller paper' : v[1])), h('span', { class: 'rx-rv-l' }, c.line)); })));
  // hoped vs supported
  const hopedIn = h('textarea', { class: 'rx-rv-hoped serif', rows: 2, disabled: READONLY, placeholder: 'The best-case conclusion, in one or two sentences. Write it before the results are in.', 'aria-label': 'Hoped conclusion' }, R.hoped || '');
  hopedIn.addEventListener('change', () => post({ hoped: hopedIn.value }));
  root.append(h('div', { class: 'rx-rv-two' },
    h('div', { class: 'rx-rv-pane' }, h('div', { class: 'rx-label' }, 'Hoped conclusion'), hopedIn),
    h('div', { class: 'rx-rv-pane' }, h('div', { class: 'rx-label' }, 'Supported today'),
      R.supported.length ? R.supported.map(c => h('div', { class: 'serif rx-rv-s' }, h('b', null, c.label + ' '), rxMath(trunc(c.text, 140)))) : h('div', { class: 'muted' }, 'No claim is fully backed yet.'),
      R.not_yet.length ? h('details', { class: 'rx-rv-ny' }, h('summary', null, plural(R.not_yet.length, 'claim') + ' not yet'), R.not_yet.map(c => h('div', { class: 'serif rx-rv-s no', title: 'Missing: ' + c.missing.join(', ') }, h('b', null, c.label + ' '), h('s', null, rxMath(trunc(c.text, 140)))))) : null)));
  // ours against each baseline
  if (R.baselines && R.baselines.length) { const BV = { ahead: ['▲', 'Ahead', 'fine'], behind: ['▼', 'Behind', 'fix'], mixed: ['=', 'Mixed', 'look'] };
    const sec = h('section', { class: 'rx-x-sec' }, h('div', { class: 'rx-rv-b head' }, h('span', null, R.ours + ' against'), h('span', null, 'Experiments'), h('span', null, ''), h('span', null, 'Overall')));
    for (const b of (RX.rvAllB ? R.baselines : R.baselines.slice(0, 6))) { const open = RX.rvB === b.name, v = BV[b.verdict];
      sec.append(h('button', { class: 'rx-rv-b' + (open ? ' open' : ''), 'aria-expanded': String(open), onclick: () => { RX.rvB = open ? null : b.name; renderPage(true); } },
        h('span', null, h('b', null, b.name), b.base ? h('span', { class: 'tag', title: 'The method this work extends' }, 'base') : null),
        h('span', { class: 'rx-m-meter', title: b.ahead + ' ahead, ' + b.tie + ' level, ' + b.behind + ' behind' }, ['ahead', 'tie', 'behind'].map(k => b[k] ? h('span', { class: 'm-' + k, style: 'flex:' + b[k] }) : null)),
        h('span', { class: 'muted small' }, b.ahead + ' of ' + b.of + ' ahead'), h('span', { class: 'rx-rv-tr ' + v[2] }, v[0] + ' ' + v[1])));
      if (open) sec.append(rxBaselineTable(b, R.ours));
    }
    if (R.baselines.length > 6) sec.append(h('div', { class: 'rx-x-none' }, h('button', { class: 'linkbtn small', onclick: () => { RX.rvAllB = !RX.rvAllB; renderPage(true); } }, RX.rvAllB ? 'Show fewer' : 'Show all ' + R.baselines.length + ' baselines')));
    root.append(sec); }
  if (R.study === 'benchmark' && RX.numbers) root.append(nbSummary(RX.numbers));
  // behind list for the "ahead" check
  // questions
  const TREND = { moved: ['↗', 'Moved', 'fine'], stalled: ['–', 'Stalled', 'ign'], none: ['○', 'Not started', 'ign'] };
  const rows = R.questions.filter(q => !fc || fc.rows.includes(q.id));
  const tbl = h('section', { class: 'rx-x-sec' }, h('div', { class: 'rx-rv-r head' }, h('span', null, 'Claim'), h('span', null, 'Question'), h('span', null, 'Complete'), h('span', null, days === 30 ? '30 days' : days === 7 ? '1 week' : '1 day')));
  for (const q of rows) {
    const open = RX.rvOpen === q.id, t = TREND[q.trend];
    const segs = q.started ? h('span', { class: 'rx-rv-segs' }, q.checklist.map(c => h('i', { class: 's-' + c.state, title: c.label + ': ' + c.why })), h('span', { class: 'muted small' }, ' ' + q.done + '/' + q.of)) : h('span', { class: 'muted small' }, 'Not started');
    tbl.append(h('button', { class: 'rx-rv-r' + (open ? ' open' : ''), 'aria-expanded': String(open), onclick: () => { RX.rvOpen = open ? null : q.id; renderPage(true); } },
      h('b', { title: q.ref && q.ref !== q.label ? q.ref + ' in the project map' : null }, q.label), h('span', { class: 'rx-rv-q' }, q.stage ? rxStageChip(q) : null, q.scope ? rxScopeTag({ scope: q.scope === 'extension' ? 'new' : q.scope === 'base' ? 'original' : null }) : null, h('span', { class: 'serif rx-rv-t' }, rxMath(trunc(q.text, 120)))), segs,
      h('span', { class: 'rx-rv-tr ' + t[2] }, t[0] + ' ' + (q.behind && q.trend !== 'none' ? 'Behind in ' + q.behind : t[1]))));
    if (open) { const conf = q.checklist.find(c => c.k === 'confounds'), rep = conf && conf.report;
      const G = { done: ['✓', 'fine', 'Done'], todo: ['○', 'look', 'To do'], stale: ['↻', 'look', 'Check again'], na: ['–', 'ign', 'Not applicable'] };
      tbl.append(h('div', { class: 'rx-rv-d' },
        q.checklist.map(c => h('div', { class: 'rx-rv-item' }, h('span', { class: 'sg ' + G[c.state][1], title: G[c.state][2] }, G[c.state][0]), h('b', null, c.label), h('span', { class: 'muted' }, c.why))),
        rep && rep.confounds.length ? h('div', { class: 'rx-rv-conf' }, rep.confounds.map((c, i) => h('div', { class: 'rx-rv-cf' + (c.resolved ? ' ok' : '') },
          h('input', { type: 'checkbox', checked: c.resolved ? '' : null, disabled: READONLY, 'aria-label': 'Resolved', title: 'Resolved', onchange: () => post({ question: q.id, resolve: i }) }),
          h('span', null, c.text), rxWhere(c.evidence, c.evidence.repo)))) : null,
        rxPlanBox('q:' + q.id, 'claim', true),
        h('div', { class: 'row rx-rv-act' },
          READONLY ? null : h('button', { class: 'btn sm primary', title: 'Paste it into your Claude Code: ' + RX_CONF_PROMPT(name), onclick: () => copyText(RX_CONF_PROMPT(name)) }, 'Copy confound check for Claude Code'),
          READONLY ? null : h('button', { class: 'btn sm', title: 'Mark confounds as checked by you, without an agent', onclick: () => post({ question: q.id, mine: !(rep && rep.by === 'you') }) }, rep && rep.by === 'you' ? 'Undo my check' : 'I checked it myself'),
          q.started ? h('button', { class: 'btn sm', onclick: () => { RX.exView = 'map'; RX.mapSel = 'q:' + q.id; openTab('experiments'); } }, 'Open experiments') : null,
          q.started ? rxVsLink('q:' + q.id) : null,
          rep ? h('span', { class: 'muted small' }, 'Confounds: ' + rep.by + ', ' + dmon(rep.at)) : null)));
    }
  }
  if (!rows.length) tbl.append(h('div', { class: 'rx-x-none' }, R.questions.length ? 'Nothing behind this check.' : R.study === 'benchmark' ? 'No claim yet. Confirm the hypotheses on Thesis.' : 'No questions yet. Confirm a project map on the Experiments page.'));
  root.append(tbl);
  return root;
}
function pageTasks() {
  const nr = rxNotReady('Tasks'); if (nr) return nr;
  S.outline = [];
  const T2 = RX.tasks;
  const root = doc(h('h1', { class: 'ptitle' }, 'Tasks'),
    null);
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
  return root;
}
/* The digest as plain prose: one line each, every line a link to the page it is about (Copy still copies the text as sent). */
function rxDigestProse(text) {
  const out = h('div', { class: 'rx-digest-p' });
  String(text || '').split('\n').forEach(raw => {
    const line = raw.trim(); if (!line) return;
    const head = /^\*(.+)\*$/.exec(line);
    if (head) { out.append(h('p', { class: 'rx-dg-h' }, head[1])); return; }
    const sub = /^[–-]\s/.test(line), txt = line.replace(/^[•–-]\s*/, '');
    const to = /result file|results\/|\.(csv|json|ya?ml)\b/i.test(txt) ? 'experiments' : /claim|^C\d+\b/i.test(txt) ? 'claims' : /task|feedback/i.test(txt) ? 'tasks' : /recheck|to look at/i.test(txt) ? 'changes' : 'history';
    out.append(h('div', { class: 'rx-dg-l' + (sub ? ' sub' : '') }, h('button', { class: 'ilink', onclick: () => openTab(to) }, txt)));
  });
  return out;
}
function rxDigestBox() {
  const box = h('div', { class: 'card' });
  const paint = () => {
    clear(box);
    if (!RX.digest) { box.append(h('p', { class: 'muted' }, 'Loading…')); return; }
    box.append(rxDigestProse(RX.digest.text),
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


/* ---------- Digest (S18): this week in prose, open tasks, then the history by week ---------- */
function pageDigest() {      // Home (S24 step 8): one research as a whole. The tab key stays 'digest' so old links keep working.
  const nr = rxNotReady('Home'); if (nr) return nr;
  S.outline = [];
  const root = doc(h('h1', { class: 'ptitle' }, S.project ? S.project.name : 'Home'));
  const E = RX.experiments, T = RX.trail;
  root.append(rxStudyLine(), rxBehindNote());
  if (E && E.thesis) { const th = rxThesisHead(E); th.classList.add('home'); th.querySelector('.rx-th-k .linkbtn').replaceWith(h('button', { class: 'linkbtn small', onclick: () => openTab('experiments') }, 'Open the thesis')); root.append(th); }
  if (T) { const ym = RX.trMonth || (RX.trDay || T.today).slice(0, 7); root.append(h('section', { class: 'hm-cal' }, trMonth(T, ym, 'all', true), RX.trDay ? trDayPanel(T, RX.trDay) : h('div', { class: 'muted small su-hint' }, 'Click a day to see its work sessions: what was done, why, by whom, where, how and with what result.'))); }
  const cards = h('div', { class: 'hm-cards' });
  const todoN = RX.todo ? RX.todo.counts.total : 0, lim = RX.hmAll ? 0 : 6;
  cards.append(h('section', { class: 'hm-card hm-todo' }, h('div', { class: 'hm-h' }, h('h3', null, 'Next to do'), h('span', { class: 'hm-n' }, todoN), h('span', { class: 'grow' }),
      RX.todo && todoN > 6 ? h('button', { class: 'linkbtn small', onclick: () => { RX.hmAll = !RX.hmAll; renderPage(true); } }, RX.hmAll ? 'Show fewer' : 'Show all') : null, h('button', { class: 'linkbtn small', onclick: () => openTab('tasks') }, 'Add feedback')),
    rxTodoList(lim)));
  const side = h('div', { class: 'hm-col' });
  side.append(h('section', { class: 'hm-card' }, h('div', { class: 'hm-h' }, h('h3', null, 'Deadlines'), h('span', { class: 'grow' }), h('button', { class: 'linkbtn small', onclick: () => openTab('history') }, 'Add')),
    T && T.ahead.length ? T.ahead.slice(0, 5).map(d => { const days = Math.round((Date.parse(d.date) - Date.parse(T.today)) / 864e5); return h('div', { class: 'hm-dl' }, h('span', { class: 'hm-dd' + (days <= 7 ? ' soon' : '') }, 'D-' + days), h('span', { class: 'grow' }, d.title), h('span', { class: 'muted small' }, dmon(d.date))); }) : h('div', { class: 'muted small' }, 'No deadlines yet.')));
  if (T) { const since = new Date(Date.parse(T.today) - 7 * 864e5).toISOString().slice(0, 10), recent = T.sessions ? T.sessions.filter(x => x.day >= since).slice(0, 8).map(x => ({ day: x.day, kind: x.kinds.includes('runs') ? 'runs' : x.kinds[0], title: x.title, _s: x })) : T.entries.filter(e => e.day >= since).slice(0, 8);
    side.append(h('section', { class: 'hm-card' }, h('div', { class: 'hm-h' }, h('h3', null, 'Last 7 days'), h('span', { class: 'grow' }), h('button', { class: 'linkbtn small', onclick: () => openTab('history') }, 'Trail')),
      recent.length ? recent.map(e => h('div', { class: 'tr-e k-' + e.kind }, h('span', { class: 'tr-c mono' }, dmon(e.day)), e._s ? null : h('span', { class: 'tag tr-k' }, TR_KIND[e.kind]),
        e._s ? h('button', { class: 'ilink', title: 'Open this day', onclick: () => { RX.trDay = e.day; RX.trMonth = e.day.slice(0, 7); renderPage(true); } }, trunc(e.title, 64)) : h('span', null, trunc(e.title, 70)), e._s && e._s.why.claims.length ? h('span', { class: 'tag' }, e._s.why.claims.join(', ')) : null)) : h('div', { class: 'muted small' }, 'Nothing in the last 7 days.'))); }
  cards.append(side);
  root.append(cards);
  if (!READONLY) root.append(sec('This week', 'digest', rxDigestBox()));
  root.classList.add('wide');
  return root;
}

/* ---------- Ask ---------- */
const RX_EXAMPLES = ['Which claims are not supported?', 'Which results are out of date?', 'What decisions were made recently?', 'What are my open tasks?'];
function rxAnswerCard(a) {
  const go = a.type === 'claim' ? () => { RX.open[a.id] = true; RX.filter = 'all'; openTab('claims'); } : a.type === 'step' ? () => openTab('timeline') : a.type === 'task' ? () => openTab('tasks')
    : a.type === 'check' ? () => { S.focusFinding = a.id; openTab('checks'); } : () => openNode(a.id);
  return h('article', { class: 'card rx-ans' },
    h('div', { class: 'rx-ans-h' }, h('button', { class: 'linkbtn', onclick: go }, h('b', null, a.title)), a.status ? rxChip(a.status) : null, a.recheck ? plainChip('↻', 'Recheck', 'look') : null,
      h('span', { class: 'grow' }), h('span', { class: 'muted small' }, { claim: 'Claim', item: 'In the paper', result: 'Result file', step: 'Timeline', task: 'Task', impact: 'Impact', check: 'Check' }[a.type] || '')),
    a.text ? h('div', null, rxMath(a.text)) : null,
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


/* ---------- Math: TeX between $...$ or \[...\] is typeset with the bundled KaTeX (no network). Falls back to the source. ---------- */
const RX_MATH_RE = /(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$[^$]+?\$)/;
function rxTex(tex, display) {
  const el = h('span', { class: display ? 'rx-math disp' : 'rx-math' });
  if (typeof katex === 'undefined') { el.textContent = tex; return el; }
  try { katex.render(tex, el, { throwOnError: false, displayMode: !!display, macros: Object.assign({}, (RX.claims && RX.claims.macros) || {}), strict: 'ignore', trust: false, maxExpand: 300, errorColor: css('--text-secondary') }); }
  catch (e) { el.textContent = tex; }
  return el;
}
function rxMath(text) {
  if (!text || (text.indexOf('$') < 0 && text.indexOf('\\[') < 0 && text.indexOf('\\(') < 0)) return text || '';
  return String(text).split(RX_MATH_RE).map((p, i) => {
    if (!(i % 2)) return p;
    if (p.startsWith('$$')) return rxTex(p.slice(2, -2), true);
    if (p.startsWith('\\[')) return rxTex(p.slice(2, -2), true);
    if (p.startsWith('\\(')) return rxTex(p.slice(2, -2), false);
    return rxTex(p.slice(1, -1), false);
  });
}

/* ---------- Notation: glossary of symbols, what each means, where meanings disagree, and the name in the code ---------- */
function rxCodeChip(sym, c) {
  const sug = c.how === 'suggested';
  const post = async body => { const r = await rxPost('/api/notation', Object.assign({ symbol: sym.key }, body)); if (r) { RX.notation = r; renderPage(true); renderLeft(); } };
  return h('span', { class: 'rx-code' + (sug ? ' sug' : ''), title: c.kind + ' in ' + c.path + (c.line ? ':' + c.line : '') },
    h('span', { class: 'mono' }, c.name + (c.value != null ? ' = ' + c.value : '')),
    c.github ? h('a', { class: 'ghl', href: c.github, target: '_blank', rel: 'noopener noreferrer', 'aria-label': 'Open on GitHub' }, '↗') : null,
    READONLY ? null : sug ? [h('button', { class: 'xbtn ok', title: 'Yes, same thing', 'aria-label': 'Accept ' + c.name, onclick: () => post({ link: c.id }) }, '✓'), h('button', { class: 'xbtn', title: 'No', 'aria-label': 'Reject ' + c.name, onclick: () => post({ unlink: c.id }) }, '×')]
      : h('button', { class: 'xbtn', title: 'Unlink', 'aria-label': 'Unlink ' + c.name, onclick: () => post({ unlink: c.id }) }, '×'));
}
function rxIssueLine(sym, x) {
  const where = l => rxWhere(l);
  if (x.kind === 'conflict') return h('div', { class: 'rx-nt-issue' }, plainChip('≠', 'Two meanings', 'fix'), x.meanings.map((m, i) => [i ? h('span', { class: 'muted' }, ' ≠ ') : ' ', h('b', null, m.text), ' ', where(m.loc)]));
  if (x.kind === 'synonym') return h('div', { class: 'rx-nt-issue' }, plainChip('=', 'Two symbols', 'look'), ' ', x.others.map((k, i) => [i ? ', ' : null, rxTex(k)]), h('span', { class: 'muted' }, ' also ' + (x.others.length > 1 ? 'mean' : 'means') + ' “' + x.meaning + '”'));
  if (x.kind === 'value') return h('div', { class: 'rx-nt-issue' }, plainChip('≠', x.confirmed ? 'Paper ≠ code' : 'Paper ≠ code?', x.confirmed ? 'fix' : 'look'), ' paper ', h('b', { class: 'mono' }, x.paper.value), ' ', where(x.paper.loc),
    h('span', { class: 'muted' }, ' · code '), h('b', { class: 'mono' }, x.code.name + ' = ' + x.code.value), x.code.github ? [' ', h('a', { class: 'ghl', href: x.code.github, target: '_blank', rel: 'noopener noreferrer' }, '↗')] : null);
  if (x.kind === 'variant') return h('div', { class: 'rx-nt-issue' }, plainChip('~', 'Also written', 'look'), ' ', x.others.map(k => rxTex(k)));
  return null;
}
function pageNotation() {
  const nr = rxNotReady('Notation'); if (nr) return nr;
  S.outline = [];
  const N = RX.notation;
  const root = doc(h('h1', { class: 'ptitle' }, 'Notation'));
  if (!N || !N.has_paper) return root.append(emptyState('𝑥', 'No paper connected', 'The glossary is read from the math in the LaTeX source.')), root;
  const F = RX.ntFilter || 'all', c = N.counts;
  const live = N.symbols.filter(s => !s.ignored);
  const pass = s => F === 'all' ? !s.ignored : F === 'issues' ? s.issues.length && !s.ignored : F === 'code' ? s.code.length && !s.ignored : F === 'undefined' ? !s.meaning && !s.ignored : s.ignored;
  root.append(h('div', { class: 'fchips' }, [['all', 'All', live.length], ['issues', 'Inconsistent', live.filter(s => s.issues.length).length], ['code', 'In code', live.filter(s => s.code.length).length], ['undefined', 'No meaning found', live.filter(s => !s.meaning).length], ['ignored', 'Hidden', N.symbols.length - live.length]]
    .filter(x => x[0] !== 'ignored' || x[2]).map(([k, l, n]) => h('button', { class: 'fchip', 'aria-pressed': String(F === k), onclick: () => { RX.ntFilter = k; renderPage(true); } }, l + ' ', h('span', { class: 'n' }, n)))));
  const rows = N.symbols.filter(pass);
  if (!rows.length) return root.append(h('div', { class: 'muted' }, N.symbols.length ? 'None.' : 'No symbols found in the math.')), root;
  const tb = h('div', { class: 'rx-nt' }, h('div', { class: 'rx-nt-r head' }, h('span', null, 'Symbol'), h('span', null, 'Means'), h('span', null, 'In the code'), h('span', null, 'Used')));
  for (const s of rows) {
    const open = RX.ntOpen === s.key;
    const post = async body => { const r = await rxPost('/api/notation', Object.assign({ symbol: s.key }, body)); if (r) { RX.notation = r; renderPage(true); renderLeft(); } };
    tb.append(h('div', { class: 'rx-nt-r' + (s.issues.length ? ' bad' : '') + (open ? ' open' : '') },
      h('button', { class: 'rx-nt-sym', 'aria-expanded': String(open), onclick: () => { RX.ntOpen = open ? null : s.key; renderPage(true); } }, rxTex(s.tex)),
      h('span', { class: s.meaning ? '' : 'muted' }, s.meaning || '—', s.meaning_by === 'you' ? h('span', { class: 'muted small' }, ' ✎') : null),
      h('span', { class: 'rx-nt-code' }, s.code.length ? s.code.map(cd => rxCodeChip(s, cd)) : h('span', { class: 'muted' }, '—')),
      h('span', { class: 'muted small mono' }, s.uses + '×'),
      s.issues.length ? h('div', { class: 'rx-nt-x' }, s.issues.map(x => rxIssueLine(s, x))) : null,
      open ? rxNotationDetail(s, post) : null));
  }
  root.append(tb);
  return root;
}
function rxNotationDetail(s, post) {
  const inp = h('input', { type: 'text', value: s.meaning || '', 'aria-label': 'Meaning', placeholder: 'What it means, in a few words' });
  return h('div', { class: 'rx-nt-x detail' },
    s.meanings.length ? h('div', null, s.meanings.map(m => h('div', { class: 'rx-ev-row' }, h('span', null, '“' + m.text + '”'), rxWhere(m.loc), m.in_appendix ? h('span', { class: 'tag' }, 'Appendix') : null,
      READONLY || m.text === s.meaning ? null : h('button', { class: 'linkbtn small', onclick: () => post({ meaning: m.text }) }, 'Use this')))) : h('div', { class: 'muted small' }, 'No sentence found that says what it is.'),
    s.values.length ? h('div', { class: 'small' }, h('span', { class: 'muted' }, 'Stated values: '), s.values.map((v, i) => [i ? ', ' : null, h('b', { class: 'mono' }, v.value), ' ', rxWhere(v.loc)])) : null,
    s.first ? h('div', { class: 'small muted' }, 'First used ', rxWhere(s.first), ' · on ' + plural(s.lines, 'line') + (s.appendix_only ? ' · appendix only' : '')) : null,
    READONLY ? null : h('div', { class: 'btnrow' }, inp, h('button', { class: 'btn', onclick: () => post({ meaning: inp.value }) }, 'Save meaning'),
      h('button', { class: 'linkbtn', onclick: () => post({ ignore: !s.ignored }) }, s.ignored ? 'Show again' : 'Hide (not a symbol)')));
}

/* ---------- wiring into the shell ---------- */
/* ---------- Setup (S23): the metrics, datasets and methods the experiments use ----------
   Left: every metric, dataset and method found in the experiments' result files. Middle: the experiments. Right: the
   claims they test. Click any box: what it connects to stays lit, and the panel under the map says how each experiment
   uses it, where the paper and the code name it, and what to check. Everything comes from /api/setup (rules only). */
const SU_KIND = { metric: ['Metrics', 'Metric'], dataset: ['Datasets', 'Dataset'], method: ['Methods', 'Method'] };
const SU_ROLE = { ours: 'Ours', base: 'Extends', baseline: 'Baseline', variant: 'Variant', compared: 'Compared', row: 'Row' };
const SU_XTYPE = { main: 'Main', ablation: 'Ablation', sensitivity: 'Sensitivity', tuning: 'Search', efficiency: 'Cost', analysis: 'Analysis', other: 'Other', table: 'Table', figure: 'Figure', result: 'Result', group: '' };
function suDir(u) { return u.target != null ? 'closest to ' + rxFmt(u.target) : u.lower ? '↓ lower is better' : '↑ higher is better'; }
function suDirShort(d) { return !d ? 'recorded only' : d === 'mixed' ? '! direction differs' : d.startsWith('target') ? '→ ' + d.slice(7) + ' is best' : d === 'lower' ? '↓ lower is better' : '↑ higher is better'; }
function suSub(it, D) {
  const nx = it.experiments.length, ex = plural(nx, 'experiment');
  if (it.kind === 'metric') return suDirShort(it.direction) + ' · ' + (it.main_in ? 'main in ' + it.main_in + ' of ' + nx : ex);
  if (it.kind === 'dataset') return ex + (it.compared ? ' · ours best in ' + it.ours_best + ' of ' + it.compared : '');
  if (it.role === 'compared') return 'Compared · ' + (it.ranked ? 'best in ' + it.best_in + ' of ' + it.ranked : ex);
  if (it.role === 'ours') return 'Ours · ' + ex;
  return (SU_ROLE[it.role] || 'Method') + ' · ' + (it.compared ? 'beats ours in ' + it.wins + ' of ' + it.compared : ex);
}
async function suLoad() {
  if (RX.setupBusy) return; RX.setupBusy = true;
  try { RX.setup = await apiGet('/api/setup'); RX.setupErr = null; } catch (e) { RX.setupErr = e.status === 404 || e.status === 501 ? 'This hub has no Setup page yet. It appears after the hub updates.' : e.message; }
  RX.setupBusy = false; const t = S.tabs[S.active]; if (t && t.k === 'setup') renderPage(true);
}
function suGotoClaim(cid) { RX.sel = cid; RX.view = 'tree'; openTab('claims'); }
function suLink(sel, label, cls, title) { return h('button', { class: 'chip-btn su-chip' + (cls ? ' ' + cls : ''), title: title || null, onclick: () => { RX.suSel = sel; renderPage(true); const el = document.querySelector('.su-detail'); if (el) el.scrollIntoView({ block: 'nearest' }); } }, label); }
function suWhereLine(hit) {
  const loc = { path: hit.path, line: hit.line };
  const open = EMBED && hit.repo ? h('button', { class: 'linkbtn mono small', title: 'Open in the editor', onclick: () => EMBED.openFile(hit.repo, hit.path, hit.line || 1) }, hit.path + ':' + hit.line) : rxWhere(loc, hit.repo);
  return h('div', { class: 'su-hit' }, open, hit.appendix ? h('span', { class: 'tag' }, 'appendix') : null, h('span', { class: 'su-hit-t' + (hit.kind ? ' mono' : ' serif') }, rxMath(hit.text || '')));
}
function suUsesTable(it, D) {
  const byX = new Map(D.experiments.map(x => [x.id, x])), byC = new Map(D.claims.map(c => [c.id, c]));
  const xcell = u => { const x = byX.get(u.x) || { name: u.x, claims: [] };
    return h('td', null, h('button', { class: 'ilink', title: 'Open this experiment', onclick: () => rxOpenExp(u.x) }, x.name),
      h('div', { class: 'su-cl' }, x.claims.map(c => byC.get(c) ? h('button', { class: 'linkbtn small', title: byC.get(c).text, onclick: () => suGotoClaim(c) }, byC.get(c).label) : null))); };
  const num = (v, cls) => h('td', { class: 'mono' + (cls ? ' ' + cls : '') }, v == null ? '—' : rxFmt(v));
  const best = b => b ? [h('span', null, rxFmt(b.value)), h('span', { class: 'muted small' }, ' ' + trunc(b.label, 18))] : '—';
  let head, rows;
  const bench = D.study === 'benchmark';
  if (bench && it.kind === 'metric') {
    head = ['Experiment', 'Role', 'Better', 'Best', 'Worst', 'Datasets'];
    rows = it.uses.map(u => h('tr', null, xcell(u), h('td', null, u.role === 'main' ? h('b', null, 'Main number') : u.role === 'compared' ? 'In the table' : h('span', { class: 'muted' }, 'Recorded, not compared')),
      h('td', { class: 'small' }, u.role === 'main' ? suDir(u) : '—'), h('td', { class: 'mono' }, best(u.field && u.field.best)), h('td', { class: 'mono' }, best(u.field && u.field.worst)), h('td', { class: 'small' }, (u.datasets || []).length ? trunc(u.datasets.join(', '), 60) : '—')));
  } else if (bench && it.kind === 'dataset') {
    head = ['Experiment', 'Metric', 'Best', 'Worst', 'Methods', 'Not run'];
    rows = it.uses.map(u => h('tr', null, xcell(u), h('td', { class: 'small' }, h('span', { class: 'mono' }, u.metric), h('div', { class: 'muted small' }, suDir(u))),
      h('td', { class: 'mono' }, u.as_row ? h('span', { class: 'muted small' }, 'a row of the table') : best(u.best_other)), h('td', { class: 'mono' }, best(u.worst)),
      h('td', { class: 'small' }, u.methods || '—'), h('td', { class: 'small' + ((u.missing || []).length ? ' warn' : ' muted') }, (u.missing || []).length ? trunc(u.missing.join(', '), 50) : 'none')));
  } else if (bench) {
    head = ['Experiment', 'Metric', 'This method', 'Rank', 'Best in', 'Per dataset'];
    rows = it.uses.map(u => h('tr', null, xcell(u), h('td', { class: 'small' }, h('span', { class: 'mono' }, u.metric), h('div', { class: 'muted small' }, suDir(u) + (u.column && u.column !== u.metric ? ' · ' + u.column : ''))),
      num(u.value, u.rank === 1 ? 'good' : ''), h('td', { class: 'small' }, u.rank ? u.rank + ' of ' + u.methods : '—'), h('td', { class: 'small' }, u.of_cols ? u.best_in + ' of ' + u.of_cols : '—'),
      h('td', null, h('div', { class: 'su-cells' }, (u.cells || []).filter(c => c.dataset).slice(0, 80).map(c => h('span', { class: 'su-cell' + (c.value == null ? ' miss' : ''), title: c.dataset + ': ' + (c.value == null ? 'no result' : rxFmt(c.value)) + (c.n ? ' · ' + plural(c.n, 'run') : '') },
        h('span', { class: 'su-cd' }, trunc(c.dataset, 12)), h('span', { class: 'mono' }, c.value == null ? '×' : rxFmt(c.value))))))));
  } else if (it.kind === 'metric') {
    head = ['Experiment', 'Role', 'Better', 'Ours', 'Best other', 'Datasets'];
    rows = it.uses.map(u => h('tr', null, xcell(u), h('td', null, u.role === 'main' ? h('b', null, 'Main number') : u.role === 'compared' ? 'In the table' : h('span', { class: 'muted' }, 'Recorded, not compared')),
      h('td', { class: 'small' }, u.role === 'main' ? suDir(u) : '—'), u.tuning ? h('td', { class: 'small' }, u.best_setting ? ['best ', h('span', { class: 'mono' }, rxFmt(u.best_setting.value)), h('div', { class: 'muted small' }, trunc(u.best_setting.label, 28))] : '—') : num(u.ours),
      h('td', { class: 'mono' }, u.tuning ? h('span', { class: 'muted' }, plural(u.runs || 0, 'setting')) : best(u.best_other)), h('td', { class: 'small' }, (u.datasets || []).length ? trunc(u.datasets.join(', '), 60) : '—')));
  } else if (it.kind === 'dataset') {
    head = ['Experiment', 'Metric', 'Ours', 'Best other', 'Rank of ours', 'Not run'];
    rows = it.uses.map(u => h('tr', null, xcell(u), h('td', { class: 'small' }, h('span', { class: 'mono' }, u.metric), h('div', { class: 'muted small' }, suDir(u))),
      u.tuning ? h('td', { class: 'small' }, u.best_setting ? ['best ', h('span', { class: 'mono' }, rxFmt(u.best_setting.value)), h('div', { class: 'muted small' }, trunc(u.best_setting.label, 28))] : '—') : num(u.ours, u.rank === 1 ? 'good' : u.rank ? 'bad' : ''),
      h('td', { class: 'mono' }, u.tuning ? h('span', { class: 'muted' }, plural(u.runs || 0, 'setting')) : best(u.best_other)),
      h('td', { class: 'small' }, u.rank ? u.rank + ' of ' + u.methods : '—'), h('td', { class: 'small' + ((u.missing || []).length ? ' warn' : ' muted') }, (u.missing || []).length ? trunc(u.missing.join(', '), 50) : 'none')));
  } else if (it.role === 'ours') {
    head = ['Experiment', 'Metric', 'Ours', 'Rank', 'Runs per cell'];
    rows = it.uses.map(u => h('tr', null, xcell(u), h('td', { class: 'small' }, h('span', { class: 'mono' }, u.metric), h('div', { class: 'muted small' }, suDir(u) + (u.column && u.column !== u.metric ? ' · ' + u.column : ''))), num(u.value, u.rank === 1 ? 'good' : ''),
      h('td', { class: 'small' }, u.ours_here ? (u.rank ? u.rank + ' of ' + u.methods : '—') : h('span', { class: 'muted' }, 'not ours here (ours: ' + (u.ours_label || '?') + ')')), h('td', { class: 'small' }, u.runs || '—')));
  } else {
    head = ['Experiment', 'Metric', 'This method', 'Ours', 'Ours ahead by', 'Per dataset'];
    rows = it.uses.map(u => h('tr', null, xcell(u), h('td', { class: 'small' }, h('span', { class: 'mono' }, u.metric), h('div', { class: 'muted small' }, suDir(u) + (u.column && u.column !== u.metric ? ' · ' + u.column : ''))),
      num(u.value), u.ours_here ? h('td', { class: 'small muted' }, 'ours here') : num(u.ours), u.gap == null ? h('td', { class: 'muted' }, '—') : h('td', { class: 'mono ' + (u.gap > 0 ? 'good' : u.gap < 0 ? 'bad' : '') }, (u.gap > 0 ? '+' : u.gap < 0 ? '−' : '') + rxFmt(Math.abs(u.gap))),
      h('td', null, h('div', { class: 'su-cells' }, (u.cells || []).filter(c => c.dataset).map(c => h('span', { class: 'su-cell' + (c.value == null ? ' miss' : c.better === true ? ' bad' : c.better === false ? ' good' : ''),
        title: c.dataset + ': ' + (c.value == null ? 'no result' : rxFmt(c.value) + (c.ours != null ? ' vs ours ' + rxFmt(c.ours) + (c.better ? ' (beats ours)' : c.better === false ? ' (ours better)' : '') : '')) + (c.n ? ' · ' + plural(c.n, 'run') : '') },
        h('span', { class: 'su-cd' }, trunc(c.dataset, 12)), h('span', { class: 'mono' }, c.value == null ? '×' : rxFmt(c.value))))))));
  }
  return h('div', { class: 'su-tw' }, h('table', { class: 'tbl su-t' }, h('thead', null, h('tr', null, head.map(t => h('th', null, t)))), h('tbody', null, rows)));
}
function suItemDetail(it, D) {
  const P = it.paper || {}, C = it.code || {};
  const facts = [];
  if (it.kind === 'metric') facts.push(suDirShort(it.direction), it.main_in ? 'main number in ' + plural(it.main_in, 'experiment') : 'never the main number');
  if (it.kind === 'dataset') { facts.push(plural(it.experiments.length, 'experiment')); if (it.compared) facts.push('ours best in ' + it.ours_best + ' of ' + it.compared); if ((it.metrics || []).length) facts.push('scored with ' + it.metrics.join(', ')); }
  if (it.kind === 'method') { facts.push(SU_ROLE[it.role] || 'Method', plural(it.experiments.length, 'experiment')); if (it.compared) facts.push('beats ours in ' + it.wins + ' of ' + plural(it.compared, 'comparison')); if (it.ranked) facts.push('best in ' + it.best_in + ' of ' + plural(it.ranked, 'column')); }
  return h('section', { class: 'rx-x-sec su-detail' },
    h('div', { class: 'rx-x-h' }, h('span', { class: 'tag' }, SU_KIND[it.kind][1]), h('b', { class: 'su-dn' }, it.name), it.aliases.length ? h('span', { class: 'muted small' }, 'also ' + it.aliases.join(', ')) : null, h('span', { class: 'grow' }),
      rxVsLink('i:' + it.id, null, 'setup'), h('button', { class: 'linkbtn small', onclick: () => { RX.suSel = null; renderPage(true); } }, 'Close')),
    h('div', { class: 'su-body' },
      h('div', { class: 'su-facts' }, facts.map(f => h('span', null, f))),
      it.checks.length ? h('div', { class: 'su-checks' }, it.checks.map(c => h('div', { class: 'rx-warn' }, '! ' + c.t))) : null,
      h('h4', { class: 'su-h' }, 'How the experiments use it'), suUsesTable(it, D),
      h('div', { class: 'su-two' },
        h('div', null, h('h4', { class: 'su-h' }, 'In the paper', h('span', { class: 'muted small' }, P.n ? ' · ' + plural(P.n, 'line') + (P.appendix_only ? ', appendix only' : '') : '')),
          P.n ? [P.lines.map(suWhereLine), P.cites.length ? h('div', { class: 'su-cites' }, h('span', { class: 'muted small' }, 'Cited with it: '), P.cites.map(c => h('span', { class: 'su-cite', title: c.key }, c.title ? trunc(c.title, 70) + (c.year ? ' (' + c.year + ')' : '') : h('span', { class: 'mono' }, c.key)))) : null]
            : h('p', { class: 'muted small' }, D.has_paper === false ? 'No paper linked.' : 'The paper never names it.')),
        h('div', null, h('h4', { class: 'su-h' }, 'In the code', h('span', { class: 'muted small' }, C.n ? ' · ' + plural(C.files || 0, 'file') : '')),
          C.n ? C.hits.map(suWhereLine) : h('p', { class: 'muted small' }, 'Not found in the code or settings by name.')))));
}
function suGroupChips(ids, D, main) {
  const byI = new Map(D.items.map(it => [it.id, it]));
  return ['metric', 'dataset', 'method'].map(k => { const its = ids.map(i => byI.get(i)).filter(it => it && it.kind === k); if (!its.length) return null;
    return h('div', { class: 'su-grp' }, h('span', { class: 'su-gk' }, SU_KIND[k][0]), its.map(it => suLink('i:' + it.id, it.name + (it.id === main ? ' · main number' : '') + (it.role && it.role !== 'baseline' ? ' · ' + SU_ROLE[it.role] : ''), 'k-' + it.kind + (it.checks.length ? ' chk' : '')))); });
}
function suOtherDetail(sel, D) {
  const id = sel.slice(2);
  if (sel.startsWith('x:')) { const x = D.experiments.find(e => e.id === id); if (!x) return null;
    const byC = new Map(D.claims.map(c => [c.id, c]));
    return h('section', { class: 'rx-x-sec su-detail' }, h('div', { class: 'rx-x-h' }, h('span', { class: 'tag' }, 'Experiment'), h('b', { class: 'su-dn' }, x.name), SU_XTYPE[x.type] ? h('span', { class: 'muted small' }, SU_XTYPE[x.type]) : null, h('span', { class: 'grow' }),
      h('button', { class: 'btn sm', onclick: () => rxOpenExp(x.id) }, 'Open experiment'), rxVsLink('x:' + x.id), h('button', { class: 'linkbtn small', onclick: () => { RX.suSel = null; renderPage(true); } }, 'Close')),
      h('div', { class: 'su-body' }, x.claims.length ? h('div', { class: 'su-grp' }, h('span', { class: 'su-gk' }, 'Tests'), x.claims.map(c => byC.get(c) ? suLink('c:' + c, byC.get(c).label, null, byC.get(c).text) : null)) : h('p', { class: 'muted small' }, 'Tests no claim yet.'),
        x.items.length ? suGroupChips(x.items, D, x.main_metric) : h('p', { class: 'muted small' }, 'Its result files could not be read as tables, so its setup is unknown.'))); }
  const c = D.claims.find(q => q.id === id); if (!c) return null;
  const byX = new Map(D.experiments.map(x => [x.id, x]));
  return h('section', { class: 'rx-x-sec su-detail' + (c.stage ? rxSt(c.stage) : '') }, h('div', { class: 'rx-x-h' }, h('span', { class: 'tag' }, 'Claim'), h('b', { class: 'su-dn' }, c.label), c.stage ? rxStageChip(c) : null, h('span', { class: 'grow' }),
    h('button', { class: 'btn sm', onclick: () => suGotoClaim(c.id) }, 'Open in Claims'), h('button', { class: 'linkbtn small', onclick: () => { RX.suSel = null; renderPage(true); } }, 'Close')),
    h('div', { class: 'su-body' }, h('p', { class: 'serif su-ct' }, rxMath(c.text)),
      h('div', { class: 'su-grp' }, h('span', { class: 'su-gk' }, 'Tested by'), c.experiments.map(x => byX.get(x) ? suLink('x:' + x, byX.get(x).name) : null)), suGroupChips(c.items, D)));
}
/* S25: Setup as a protocol sheet, read top-down: claim -> experiment -> protocol -> coverage grid -> trace of one cell.
   (Founder, chat 2026-11-16 12:31-12:32 KST: the curve map is replaced; a researcher must be able to double-check the traces.) */
const SU_ANS = { yes: ['✓', 'fine', 'Yes'], no: ['✕', 'fix', 'No'], you: ['?', 'look', 'You check'] };
RX.suTrace = RX.suTrace || {};
function suCellKey(xid, m, c) { return xid + '|' + m + '|' + c; }
function suLoadTrace(xid) {
  if (RX.suTrace[xid]) return;
  RX.suTrace[xid] = { loading: true };
  apiGet('/api/experiment?id=' + encodeURIComponent(xid)).then(d => { RX.suTrace[xid] = { d }; }).catch(e => { RX.suTrace[xid] = { err: e.message }; }).then(() => { const t = S.tabs[S.active]; if (t && t.k === 'setup') renderPage(true); });
}
function suTracePanel(x, method, col) {
  const T = RX.suTrace[x.id];
  const box = h('div', { class: 'su-tr' });
  const head = h('div', { class: 'su-tr-h' }, h('b', null, method), ' on ', h('b', null, col), h('span', { class: 'grow' }), h('button', { class: 'linkbtn small', onclick: () => { RX.suCell = null; renderPage(true); } }, 'Close'));
  box.append(head);
  if (!T || T.loading) return box.append(h('div', { class: 'muted small' }, 'Reading the trace…')), box;
  if (T.err) return box.append(h('div', { class: 'muted small' }, 'Could not read it: ' + T.err)), box;
  const d = T.d, ds = (x.grid.datasets || [])[x.grid.cols.indexOf(col)] || col, nm = s => String(s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  const step = (n, title, ok, kids) => h('div', { class: 'su-st' + (ok ? '' : ' miss') }, h('span', { class: 'su-st-n' }, n), h('div', { class: 'su-st-b' }, h('div', { class: 'su-st-t' }, title, ok ? null : h('span', { class: 'tag warn' }, 'not found')), kids));
  // 1 paper
  let pc = null; (d.cells || []).forEach(r => r.forEach(c => { if (c.row && nm(c.row) === nm(method) && nm(c.col) === nm(ds)) pc = c; }));
  const file = (x.grid.rows.find(r => r.label === method) || { values: {} }).values[col];
  box.append(step(1, 'What the paper says', !!pc, pc ? [h('span', { class: 'mono' }, pc.text), h('span', { class: 'muted small' }, ' in ' + (Array.isArray(d.paper) && d.paper[0] ? d.paper[0].name : d.name) + ' · '), d.loc ? rxWhere(d.loc, d.map ? 'paper' : (d.repo || 'paper')) : null,
      h('span', { class: 'tag' + (pc.status === 'match' || pc.status === 'rounding' ? '' : ' warn') }, pc.status === 'match' ? 'matches the file' : pc.status === 'rounding' ? 'matches after rounding' : pc.status === 'differs' ? 'differs: the file gives ' + rxFmt(pc.file) : pc.status || '')]
    : h('span', { class: 'muted small' }, Array.isArray(d.paper) && d.paper.length ? 'This cell is not in ' + d.paper[0].name + '.' : 'No paper table is linked to this experiment.')));
  // 2 result files
  const fs = ((d.design || {}).files || []).concat(!((d.design || {}).files || []).length && d.result ? [{ node_id: d.result.node_id, path: d.result.path }] : []), mine = fs.filter(f => f.fields && nm(f.fields.method) === nm(method) && nm(f.fields.dataset) === nm(ds)), shown = mine.length ? mine : fs.filter(f => !f.fields || (!f.fields.method && !f.fields.dataset)).slice(0, 6);
  box.append(step(2, 'Where it comes from: result files' + (file != null ? ' → ' + rxFmt(file) : ''), shown.length > 0, shown.length ? shown.slice(0, 8).map(f => h('div', { class: 'su-f' }, h('button', { class: 'linkbtn mono small', title: 'Open this file', onclick: () => (EMBED && d.repo ? EMBED.openFile(d.repo, f.path, 1) : openTab('node', f.node_id)) }, f.path),
      f.fields && f.fields.seed ? h('span', { class: 'muted small' }, ' seed ' + f.fields.seed) : null)).concat(mine.length ? [h('div', { class: 'muted small' }, plural(mine.length, 'file') + ' averaged into this number.')] : [h('div', { class: 'muted small' }, 'The method and dataset are columns inside these files.')])
    : h('span', { class: 'muted small' }, 'No result file for this cell.')));
  // 3 scripts and settings
  const sc = ((d.design || {}).scripts || []).concat((d.design || {}).settings || [], ((d.design || {}).runs || []).filter(r => r.command).map(r => ({ node_id: r.node_id, name: r.command }))), vals = ((d.design || {}).values || []);
  box.append(step(3, 'How: script and settings', sc.length > 0, sc.length ? [h('div', null, sc.slice(0, 6).map(n => h('button', { class: 'linkbtn mono small su-fl', onclick: () => openTab('node', n.node_id) }, n.name))),
      vals.length ? h('div', { class: 'su-vals' }, vals.slice(0, 10).map(v => h('span', { class: 'mono small' }, v.key + ' = ' + v.value))) : null] : h('span', { class: 'muted small' }, 'Lemmata found no script or settings file that writes these results.')));
  // 4 who ran it: the logged runs of this experiment, the ones for this method and dataset first
  const rs = ((x.context || {}).runs || []), hit = r => { const f = r.fields || {}; return (f.method || []).some(v => nm(v) === nm(method)) && (!(f.dataset || []).length || f.dataset.some(v => nm(v) === nm(ds))); };
  const mineR = rs.filter(hit), showR = (mineR.length ? mineR : rs).slice(0, 3);
  box.append(step(4, 'Who ran it' + (mineR.length ? '' : showR.length ? ' (runs of this experiment; none names this cell)' : ''), showR.length > 0, showR.length ? showR.map(r => h('div', { class: 'su-f' }, h('span', null, (r.who === 'you' ? 'You' : r.who === 'agent' ? 'Coding agent' : 'File watcher') + (r.host ? ' on ' + r.host : '') + ', ' + dmon(r.t) + ' ' + String(r.t).slice(11, 16)),
      r.sha ? h('span', { class: 'mono muted small' }, ' ' + r.sha + (r.dirty ? ' + uncommitted changes' : '')) : null, r.exit ? h('span', { class: 'tag warn' }, 'exit ' + r.exit) : null, r.command ? h('div', { class: 'mono small muted', title: r.command }, '$ ' + trunc(r.command.replace(/\s*\n\s*/g, ' ⏎ '), 150)) : null))
    : h('span', { class: 'muted small' }, 'No logged run wrote these files. Runs are logged from the VS Code terminal, the results watcher or your coding agent.')));
  // 5 when
  const hs = d.history || [], last = hs[hs.length - 1];
  box.append(step(5, 'When: last written', !!last, last ? [h('span', null, dmon(last.time)), h('span', { class: 'mono muted small' }, ' ' + (last.short || '')), h('span', { class: 'muted small' }, ' “' + trunc(last.subject || '', 60) + '”'),
      (last.changes || []).length ? h('div', { class: 'muted small' }, 'Changed with it: ' + last.changes.flatMap(c => c.files || []).slice(0, 4).join(', ')) : null,
      d.stale ? h('div', { class: 'rx-warn' }, '! The code or settings changed after this.') : null] : h('span', { class: 'muted small' }, 'No commit history for these files.')));
  box.append(h('div', { class: 'su-tr-f' }, h('button', { class: 'btn sm', onclick: () => rxOpenExp(x.id) }, 'Open the experiment'), rxVsLink('x:' + x.id)));
  return box;
}
function suContext(x, claim) {   // S26: why, what, where, how, when, who on one strip above the protocol
  const C = x.context, P = x.protocol; if (!C) return null;
  const cell = (k, v, miss) => h('div', { class: 'su-cx-c' + (miss ? ' miss' : '') }, h('span', { class: 'su-cx-k' }, k), h('div', { class: 'su-cx-v' }, v));
  const base = P && !P.search ? P.methods.filter(m => m.role !== 'ours').length : 0;
  const dir = P ? (P.target != null ? '' : P.lower ? ' (lower is better)' : ' (higher is better)') : '';
  const what = !P ? 'Result files that could not be read as a table.' : P.search ? 'A search over ' + plural(P.settings_n, 'setting') + ', judged by ' + P.metric + '.'
    : P.study === 'benchmark' ? (P.rows ? plural(P.rows.n, { dataset: 'dataset', condition: 'case', group: 'group' }[P.rows.kind] || 'row') + (P.rows.column ? ' (column ' + P.rows.column + ')' : '') + ', measured by ' + P.metric + '. No method is compared here.'
      : plural(P.methods.length, 'method') + ' compared' + (P.datasets.length ? ' on ' + plural(P.datasets.length, 'dataset') : '') + ', judged by ' + P.metric + dir + '. None of them is “ours”.')
    : (P.ours || 'Ours') + ' against ' + plural(base, 'other method') + (P.datasets.length ? ' on ' + plural(P.datasets.length, 'dataset') : '') + ', judged by ' + P.metric + (P.target != null ? '' : P.lower ? ' (lower is better)' : ' (higher is better)') + '.';
  const W = C.where, H = C.how, T = C.when, O = C.who;
  const howBits = H.scripts.concat(H.code.filter(c => !H.scripts.some(sc => sc.endsWith(c)))), noHow = !howBits.length && !H.settings.length;
  const who = O.by.map(w => (w.who === 'you' ? 'you' : w.who === 'agent' ? 'coding agent' : 'file watcher') + ' ×' + w.n);
  return h('div', { class: 'su-cx' },
    cell('Why', claim ? [h('button', { class: 'ilink', onclick: () => suGotoClaim(claim.id) }, claim.label), h('span', { class: 'muted' }, ' ' + trunc(claim.text, 90))] : h('span', null, 'It tests no claim yet.'), !claim),
    cell('What', what),
    cell('Where', [W.hosts.length ? h('span', null, W.hosts.join(', ') + ' · ') : null, h('span', { class: 'mono small' }, (W.repo ? W.repo + ': ' : '') + (W.folder ? W.folder + '/' : '(top folder)')), h('span', { class: 'muted small' }, ' ' + plural(W.files_n || 0, 'file')),
      W.hosts.length ? null : h('div', { class: 'muted small' }, 'No logged run, so the server is unknown.')]),
    cell('How', noHow ? h('span', null, 'No script or settings file is linked to these results.') : [howBits.map(n => h('span', { class: 'mono small ss-kv' }, n)), H.settings.map(n => h('span', { class: 'mono small ss-kv' }, n)),
      H.command ? h('div', { class: 'mono small muted su-cx-cmd', title: H.command }, '$ ' + trunc(H.command.replace(/\s*\n\s*/g, ' ⏎ '), 110)) : null], noHow),
    cell('When', T.last ? [h('span', null, T.first && T.first.slice(0, 10) !== T.last.slice(0, 10) ? dmon(T.first) + ' → ' + dmon(T.last) : dmon(T.last)), h('span', { class: 'muted small' }, ' · results changed ' + (T.updates === 1 ? 'once' : (T.updates || 0) + ' times')),
      T.stale ? h('div', { class: 'rx-warn' }, '! Code or settings changed after the last result.') : null] : h('span', null, 'No dated result yet.'), !T.last),
    cell('Who', O.runs ? who.join(', ') + ' (' + plural(O.runs, 'logged run') + ')' : [h('span', null, 'No logged run.'), O.commit ? h('span', { class: 'muted small' }, ' Results came in with commit ' + O.commit + '.') : null], !O.runs));
}
function suSheet(x, claim, D, hl) {
  const P = x.protocol, link = claim && claim.links[x.id];
  const card = h('section', { class: 'su-sh' + (x.attention ? ' att' : '') });
  card.append(h('div', { class: 'su-sh-h' }, link ? rxLinkChip(Object.assign({ criterion_by: '' }, link)) : null, SU_XTYPE[x.type] ? h('span', { class: 'tag' }, SU_XTYPE[x.type]) : null, h('b', null, x.name), h('span', { class: 'grow' }),
    P && P.last ? h('span', { class: 'muted small' }, 'last result ' + dmon(P.last)) : null, h('button', { class: 'linkbtn small', onclick: () => rxOpenExp(x.id) }, 'Open')));
  card.append(suContext(x, claim));
  if (!P) return card.append(h('p', { class: 'muted small' }, 'Its result files could not be read as a table, so there is no protocol to show.')), card;
  const itemBtn = (kind, name, extra) => { const id = kind + ':' + name.toLowerCase().replace(/[^a-z0-9]/g, ''); const it = D.items.find(i => i.id === id);
    return h('button', { class: 'su-pi k-' + kind + (hl === id ? ' on' : '') + (it && it.checks.length ? ' chk' : ''), title: it ? 'Where the paper and the code name it' : null, onclick: () => { RX.suSel = RX.suSel === 'i:' + id ? null : 'i:' + id; renderPage(true); } }, name, extra && extra !== String(name).toLowerCase() ? h('span', { class: 'muted' }, ' ' + extra) : null); };
  const row = (k, ...v) => h('div', { class: 'su-pr' }, h('span', { class: 'su-pk' }, k), h('div', { class: 'su-pv' }, v));
  card.append(h('div', { class: 'su-p' },
    row('Metric', itemBtn('metric', P.metric, P.target != null ? '→ ' + rxFmt(P.target) : P.lower ? '↓ lower is better' : '↑ higher is better'), P.measures.filter(m => m !== P.metric).length ? h('span', { class: 'muted small' }, 'also recorded: ' + P.measures.filter(m => m !== P.metric).join(', ')) : null),
    row('Datasets', P.datasets.length ? P.datasets.map(d => itemBtn('dataset', d)) : h('span', { class: 'muted small' }, 'not split by dataset')),
    P.search ? row('Search', h('span', null, plural(P.settings_n, 'setting') + ' tried'), P.best ? h('span', { class: 'muted small' }, 'best: ' + P.best.label + ' (' + rxFmt(P.best.value) + ')') : null)
      : P.rows ? row({ dataset: 'Datasets (rows)', condition: 'Cases', group: 'Groups' }[P.rows.kind] || 'Rows', h('span', null, P.rows.names.join(', ') + (P.rows.n > P.rows.names.length ? ' and ' + (P.rows.n - P.rows.names.length) + ' more' : '')), h('span', { class: 'muted small' }, 'not methods'))
      : row(P.study === 'benchmark' ? 'Compared' : 'Methods', P.methods.map(m => itemBtn('method', m.name, m.role !== 'baseline' && m.role !== 'compared' ? SU_ROLE[m.role].toLowerCase() : null))),
    P.search ? null : row('Runs', h('span', null, P.seeds ? (P.seeds[0] === P.seeds[1] ? P.seeds[0] : P.seeds[0] + ' to ' + P.seeds[1]) + ' per result' : '—')),
    P.paper.length ? row('In the paper', h('span', null, P.paper.join(', '))) : null));
  if (x.grid) {
    const G = x.grid, sel = RX.suCell && RX.suCell.x === x.id ? RX.suCell : null;
    const hlM = hl && hl.startsWith('method:') ? hl.slice(7) : null, hlD = hl && hl.startsWith('dataset:') ? hl.slice(8) : null, nm = s => String(s).toLowerCase().replace(/[^a-z0-9]/g, '');
    card.append(h('div', { class: 'su-gw' }, h('table', { class: 'su-g' }, h('thead', null, h('tr', null, h('th', null, P.metric + (P.lower ? ' ↓' : P.target != null ? '' : ' ↑')), G.cols.map((c, i) => h('th', { class: hlD === nm(G.datasets[i]) ? 'hl' : null }, G.datasets[i])))),
      h('tbody', null, (G.rows.length > 14 && !hl && !sel && !(RX.suRows || {})[x.id] ? G.rows.slice(0, 12) : G.rows).map(r => h('tr', { class: (r.role === 'ours' ? 'ours' : '') + (hlM === nm(r.label) ? ' hl' : '') }, h('th', null, r.label, !['baseline', 'compared', 'row'].includes(r.role) && SU_ROLE[r.role] && SU_ROLE[r.role].toLowerCase() !== String(r.label).toLowerCase() ? h('span', { class: 'tag' }, SU_ROLE[r.role].toLowerCase()) : null),
        G.cols.map((c, i) => { const v = r.values[c], on = sel && sel.m === r.label && sel.c === c;
          return h('td', { class: (v == null ? 'miss' : '') + (r.best.includes(c) ? ' best' : '') + (on ? ' on' : '') + (hlD === nm(G.datasets[i]) ? ' hl' : '') },
            h('button', { class: 'su-cb', title: v == null ? 'No result: ' + r.label + ' on ' + G.datasets[i] : 'Trace this number', 'aria-pressed': String(!!on), onclick: () => { RX.suCell = on ? null : { x: x.id, m: r.label, c }; if (!on) suLoadTrace(x.id); renderPage(true); } },
              v == null ? '—' : h('span', { class: 'mono' }, rxFmt(v)), v != null && r.n[c] ? h('span', { class: 'su-cn' }, '×' + r.n[c]) : null)); })))))));
    if (G.rows.length > 14 && !hl && !sel) card.append(h('button', { class: 'linkbtn small su-more', onclick: () => { RX.suRows = Object.assign({}, RX.suRows, { [x.id]: !(RX.suRows || {})[x.id] }); renderPage(true); } }, (RX.suRows || {})[x.id] ? 'Show the first 12 rows' : 'Show all ' + G.rows.length + ' rows'));
    if (sel) card.append(suTracePanel(x, sel.m, sel.c));
    else card.append(h('div', { class: 'muted small su-hint' }, 'Click a number to trace it: what the paper says → where it comes from → how → who ran it → when. ×n is the number of runs; bold is the best in its column.'));
  }
  card.append(h('div', { class: 'su-ck' }, (x.checklist || []).map(c => { const a = SU_ANS[c.a]; return h('div', { class: 'su-ck-r', title: c.why }, h('span', { class: 'sg ' + a[1] }, a[0]), h('span', { class: 'su-ck-q' }, c.q), h('span', { class: 'muted small' }, c.a === 'you' ? 'You check. ' + c.why : c.why)); })));
  return card;
}
/* ---------- Setup board (S28): thesis <- claims <- experiments <- what was used ----------
   Four columns of cards at the top of Setup (founder, chat 2026-11-18 17:06 KST: a flowchart at the top of the page to see how
   the setup connects to the thesis, "think of a kanban system"). Click a card: its path to the thesis stays lit, the rest dims,
   and one sentence says the path in words. Lines join the lit path only, so the board does not turn into the curve map S25 removed. */
const BD_KIND = { metric: ['Metrics', 'metric'], dataset: ['Datasets', 'dataset'], method: ['Methods', 'method'], condition: ['Conditions', 'condition'] };
const BD_CAP = 6, BD_XCAP = 8;
RX.bdMore = RX.bdMore || {};
function bdSelNow(B) {
  if (B.mode === 'paper') { const i = RX.suSel && RX.suSel.startsWith('i:') ? RX.suSel : null; if (i) RX.bdSel = i; else if ((RX.bdSel || '').startsWith('i:')) RX.bdSel = null; }
  const s = RX.bdSel; if (!s) return null;
  if (s === 't') return s;
  const id = s.slice(2), list = s[0] === 'c' ? B.claims : s[0] === 'x' ? B.experiments : s[0] === 'i' ? B.items : [];
  return list.some(o => o.id === id) ? s : (RX.bdSel = null);
}
function bdPick(B, key, keep) {
  RX.bdSel = RX.bdSel === key && !keep ? null : key;
  if (B.mode === 'paper') RX.suSel = RX.bdSel && RX.bdSel.startsWith('i:') ? RX.bdSel : null;
  RX.suAll = false; renderPage(true);
}
function bdLit(B, sel) {      // what stays lit for a selection: the cards on its path to the thesis
  if (!sel) return null;
  const L = { t: false, c: new Set(), x: new Set(), i: new Set() }, id = sel.slice(2), known = new Set(B.claims.map(c => c.id));
  const whole = x => { L.x.add(x.id); x.items.forEach(i => L.i.add(i)); };
  if (sel === 't') { known.forEach(c => L.c.add(c)); B.experiments.forEach(x => { if (x.claims.some(c => known.has(c))) whole(x); }); }
  else if (sel[0] === 'c') { L.c.add(id); B.experiments.forEach(x => { if (x.claims.includes(id)) whole(x); }); }
  else if (sel[0] === 'x') { const x = B.experiments.find(e => e.id === id); whole(x); x.claims.forEach(c => { if (known.has(c)) L.c.add(c); }); }
  else { L.i.add(id); B.experiments.forEach(x => { if (x.items.includes(id)) { L.x.add(x.id); x.claims.forEach(c => { if (known.has(c)) L.c.add(c); }); } }); }
  L.t = sel === 't' || L.c.size > 0;
  return L;
}
function bdAnd(a, n) { a = [...a]; n = n || 4; if (a.length > n) return a.slice(0, n).join(', ') + ' and ' + (a.length - n) + ' more'; return a.length < 2 ? a.join('') : a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1]; }
function bdXName(B, x) { return B.mode === 'paper' ? x.name : x.id; }
function bdKinds(B, ids) {
  const its = B.items.filter(it => ids.has ? ids.has(it.id) : ids.includes(it.id));
  return Object.keys(BD_KIND).map(k => { const a = its.filter(it => it.kind === k); if (!a.length) return null;
    if (a.every(it => it.summary)) return a.map(it => it.name).join(', ');
    return a.some(it => it.group) ? plural(a.length, 'dataset group') : plural(a.length, BD_KIND[k][1]); }).filter(Boolean);
}
function bdTrace(B, sel, L) {
  const word = B.thesis.kind === 'problem' ? 'problem' : 'thesis', id = sel.slice(2);
  const xs = B.experiments.filter(x => L.x.has(x.id)), cs = B.claims.filter(c => L.c.has(c.id)).map(c => c.label || 'a claim');
  const used = bdKinds(B, L.i), on = used.length ? ' It is built on ' + bdAnd(used, 5) + '.' : '';
  if (sel === 't') { const N = B.experiments.length, C = B.counts;
    return (N ? xs.length + ' of ' + plural(N, B.mode === 'paper' ? 'experiment' : 'step') + ' reach the ' + word + ' through ' + plural(B.claims.length, B.mode === 'paper' ? 'claim' : 'hypothesis', 'hypotheses') + '.' : 'No experiment yet.')
      + (C.experiments_no_claim ? ' ' + C.experiments_no_claim + ' test no claim, so what they use does not count for it.' : '') + (C.claims_untested ? ' ' + plural(C.claims_untested, 'claim') + ' ' + (C.claims_untested === 1 ? 'has' : 'have') + ' no experiment.' : ''); }
  if (sel[0] === 'c') { const c = B.claims.find(q => q.id === id);
    return xs.length ? (c.label || 'This claim') + ' is tested by ' + bdAnd(xs.map(x => bdXName(B, x))) + '.' + on.replace('It is', xs.length === 1 ? 'It is' : 'They are') : 'Nothing tests ' + (c.label || 'this claim') + ' yet, so nothing that was used backs it.'; }
  if (sel[0] === 'x') { const x = xs[0];
    return bdXName(B, x) + (cs.length ? ' tests ' + bdAnd(cs) + '.' : ' tests no claim, so what it uses does not reach the ' + word + ' yet.') + on; }
  const it = B.items.find(q => q.id === id), v = xs.length === 1;
  return it.name + ' is used in ' + bdAnd(xs.map(x => bdXName(B, x))) + (cs.length ? ', which ' + (v ? 'tests ' : 'test ') + bdAnd(cs) + '.' : ', which ' + (v ? 'tests' : 'test') + ' no claim. It does not reach the ' + word + ' yet.');
}
function bdItemSub(it) {
  if (it.group) { const n = (it.uses || []).map(u => u.datasets).filter(Boolean), a = Math.min(...n), b = Math.max(...n); return n.length ? (a === b ? '' : 'up to ') + plural(b, 'dataset') : null; }
  if (it.summary) return null;
  if (it.role && it.role !== 'baseline') return SU_ROLE[it.role] ? SU_ROLE[it.role].toLowerCase() : it.role;
  if ((it.named_by || []).length) return 'named in ' + it.named_by.join(', ');
  return null;
}
function bdGo(B, key, label, title) { return h('button', { class: 'chip-btn', title: title || null, onclick: () => bdPick(B, key, true) }, label); }
function bdDetail(B, sel) {      // what the selected card is, in rows (an item of a paper project opens its own page section instead)
  const id = sel.slice(2), hf = B.mode === 'hypothesis_first';
  const row = (k, ...v) => h('div', { class: 'su-pr' }, h('span', { class: 'su-pk' }, k), h('div', { class: 'su-pv' }, v));
  const close = h('button', { class: 'linkbtn small', onclick: () => bdPick(B, sel) }, 'Close');
  const head = (tag, name, ...more) => h('div', { class: 'rx-x-h' }, h('span', { class: 'tag' }, tag), h('b', { class: 'su-dn' }, name), more, h('span', { class: 'grow' }), close);
  const xBtn = x => bdGo(B, 'x:' + x.id, bdXName(B, x), x.name), cBtn = c => bdGo(B, 'c:' + c.id, c.label || trunc(c.text, 30), c.text);
  const byKind = ids => Object.keys(BD_KIND).map(k => { const a = B.items.filter(it => ids.includes(it.id) && it.kind === k); return a.length ? row(BD_KIND[k][0], a.map(it => bdGo(B, 'i:' + it.id, it.name + (it.checks ? ' !' : '')))) : null; });
  if (sel === 't') { const T = B.thesis;
    return h('section', { class: 'rx-x-sec su-detail' }, head(T.kind === 'problem' ? 'Problem' : 'Thesis', ''), h('div', { class: 'su-body' },
      T.text ? h('p', { class: 'serif su-ct' }, rxMath(T.text)) : h('p', { class: 'muted' }, T.missing), T.approach ? row('Approach', h('span', null, T.approach)) : null,
      h('div', { class: 'su-p' }, row(hf ? 'Hypotheses' : 'Claims', B.claims.length ? B.claims.map(cBtn) : h('span', { class: 'muted small' }, 'none yet')), row('', h('button', { class: 'btn sm', onclick: () => openTab('experiments') }, 'Open Thesis'))))); }
  if (sel[0] === 'c') { const c = B.claims.find(q => q.id === id), xs = B.experiments.filter(x => x.claims.includes(id));
    return h('section', { class: 'rx-x-sec su-detail' + (c.stage ? rxSt(c.stage) : '') }, head(hf ? 'Hypothesis' : 'Claim', c.label || '', c.stage ? rxStageChip(c) : null, c.tier && c.tier !== 'confirmatory' ? h('span', { class: 'tag' }, c.tier) : null),
      h('div', { class: 'su-body' }, h('p', { class: 'serif su-ct' }, rxMath(c.text)), h('div', { class: 'su-p' },
        c.stage_why ? row('Stands at', h('span', null, c.stage_why)) : null,
        row('Tested by', xs.length ? xs.map(xBtn) : h('span', { class: 'rx-warn' }, '! Nothing tests it yet.')),
        byKind([...new Set(xs.flatMap(x => x.items))]),
        row('', h('button', { class: 'btn sm', onclick: () => { if (hf) { RX.hfOpen = c.id; openTab('experiments'); } else suGotoClaim(c.id); } }, hf ? 'Open in Thesis' : 'Open in Claims'))))); }
  if (sel[0] === 'x') { const x = B.experiments.find(q => q.id === id), U = x.used, cs = B.claims.filter(c => x.claims.includes(c.id));
    const dims = U ? [U.methods ? plural(U.methods, 'method') : null, U.datasets ? plural(U.datasets, 'dataset') : null, U.conditions.length > 1 ? plural(U.conditions.length, 'condition') : null, U.seeds ? plural(U.seeds, 'seed') : null].filter(Boolean) : [];
    return h('section', { class: 'rx-x-sec su-detail' }, head(hf ? 'Step' : 'Experiment', bdXName(B, x), hf ? h('span', { class: 'tag' }, x.status) : SU_XTYPE[x.type] ? h('span', { class: 'tag' }, SU_XTYPE[x.type]) : null),
      h('div', { class: 'su-body' }, hf ? h('p', { class: 'su-ct' }, x.name) : null, h('div', { class: 'su-p' },
        row('Tests', cs.length ? cs.map(cBtn) : h('span', { class: 'rx-warn' }, '! No claim. What it uses does not reach the thesis yet.')),
        U && U.rows && U.methods ? row('Runs', h('span', null, plural(U.rows, 'run') + ': ' + dims.join(' × ')), U.failed ? h('span', { class: 'rx-warn' }, '! ' + U.failed + ' marked failed in the result files') : null)
          : U && U.datasets ? row('Covers', h('span', null, plural(U.datasets, 'dataset'))) : null,
        byKind(x.items),
        hf ? row('Writes', x.deliverables.length ? x.deliverables.map(d => /\.[a-z0-9]+$/i.test(d) && !/\.gz$/i.test(d) ? rxWhere({ path: d }, 'code') : h('span', { class: 'mono small' }, d)) : h('span', { class: 'muted small' }, 'nothing named yet')) : null,
        hf && x.depends_on.length ? row('Needs', x.depends_on.map(d => { const o = B.experiments.find(q => q.id === d); return o ? xBtn(o) : h('span', { class: 'mono small' }, d); })) : null,
        hf && !x.items.length ? row('Used', h('span', { class: 'muted small' }, U && U.files ? 'Its tables name no method, dataset or metric column.' : 'No readable table among its result files (csv or tsv, plain or .gz), so what it used is unknown.')) : null,
        hf && U && U.skipped ? row('', h('span', { class: 'muted small' }, plural(U.skipped, 'file') + ' too large to read.')) : null,
        hf && U && U.partial ? row('', h('span', { class: 'muted small' }, plural(U.partial, 'compressed file') + ' read in part only (very large).')) : null,
        x.sheets.length ? row('Sheets', h('span', { class: 'muted small' }, plural(x.sheets.length, 'result-file sheet') + ' below ↓')) : null,
        hf ? null : row('', h('button', { class: 'btn sm', onclick: () => rxOpenExp(x.id) }, 'Open the experiment'))))); }
  const it = B.items.find(q => q.id === id), kind = BD_KIND[it.kind] || ['Items', 'item'], byX = new Map(B.experiments.map(x => [x.id, x]));
  const cols = it.kind === 'method' ? [['datasets', 'Datasets'], ['seeds', 'Seeds'], ['rows', 'Runs'], ['failed', 'Failed']] : it.group ? [['datasets', 'Datasets'], ['methods', 'Methods']] : it.kind === 'dataset' ? [['methods', 'Methods'], ['rows', 'Runs']] : it.kind === 'condition' ? [['rows', 'Runs']] : [['files', 'Result files']];
  return h('section', { class: 'rx-x-sec su-detail' }, head(kind[1][0].toUpperCase() + kind[1].slice(1) + (it.group ? ' group' : ''), it.name),
    h('div', { class: 'su-body' },
      (it.named_by || []).length ? h('p', { class: 'su-ct' }, 'Named in ' + bdAnd(it.named_by) + '.') : null,
      h('div', { class: 'su-tw' }, h('table', { class: 'tbl su-t bd-ut' }, h('thead', null, h('tr', null, h('th', null, 'Step'), cols.map(c => h('th', { class: 'num' }, c[1])), h('th', null, 'Tests'))),
        h('tbody', null, (it.uses || []).map(u => { const x = byX.get(u.x); return h('tr', null, h('td', null, x ? xBtn(x) : u.x), cols.map(c => h('td', { class: 'num mono' + (c[0] === 'failed' && u.failed ? ' bad' : '') }, u[c[0]] == null ? '—' : u[c[0]])),
          h('td', null, x && x.claims.length ? x.claims.join(', ') : h('span', { class: 'muted' }, 'no claim'))); })))),
      it.group ? (it.uses || []).map(u => u.names && u.names.length ? h('p', { class: 'small bd-names' }, h('b', null, u.x + ' '), h('span', { class: 'muted' }, u.names.join(', ') + (u.datasets > u.names.length ? ' and ' + (u.datasets - u.names.length) + ' more' : ''))) : null) : null,
      it.summary ? h('p', { class: 'su-ct' }, 'Its tables hold these columns of numbers; none has the name of a known metric.') : null,
      it.summary && it.names ? h('p', { class: 'small mono muted bd-names' }, it.names.join(', ') + (it.n > it.names.length ? ' and ' + (it.n - it.names.length) + ' more' : '')) : null));
}
function bdWire(el, B, L) {      // lines between the cards of one path, measured after layout
  const svg = el.querySelector('.bd-w'), body = el.querySelector('.bd-b'); if (!svg || !body || !el.isConnected) return;
  clear(svg);
  const cols = [...body.querySelectorAll('.bd-col')], r0 = body.getBoundingClientRect();
  if (cols.length < 4 || cols[1].getBoundingClientRect().left - cols[0].getBoundingClientRect().left < 40) return;      // stacked columns: no lines
  svg.setAttribute('width', r0.width); svg.setAttribute('height', r0.height); svg.setAttribute('viewBox', '0 0 ' + r0.width + ' ' + r0.height);
  const cards = new Map([...body.querySelectorAll('.bd-c')].map(c => [c.dataset.k, c.getBoundingClientRect()])), E = [];
  const edge = (a, b) => { const A = cards.get(a), Z = cards.get(b); if (A && Z) E.push([A.right - r0.left, A.top + A.height / 2 - r0.top, Z.left - r0.left, Z.top + Z.height / 2 - r0.top]); };
  const known = new Set(B.claims.map(c => c.id)), tc = [], cx = [], xi = [];
  B.claims.forEach(c => { if (!L || (L.t && L.c.has(c.id))) tc.push(['t', 'c:' + c.id]); });
  B.experiments.forEach(x => { if (L && !L.x.has(x.id)) return;
    x.claims.forEach(c => { if (known.has(c) && (!L || L.c.has(c))) cx.push(['c:' + c, 'x:' + x.id]); });
    x.items.forEach(i => { if ((!L || L.i.has(i)) && cards.has('i:' + i) && cards.has('x:' + x.id)) xi.push(['x:' + x.id, 'i:' + i]); }); });
  tc.concat(cx, L || xi.length <= 24 ? xi : []).forEach(e => edge(e[0], e[1]));
  E.forEach(([x1, y1, x2, y2]) => { const m = (x1 + x2) / 2; svg.append(sv('path', { class: 'bd-e' + (L ? ' lit' : ''), d: 'M' + x1 + ',' + y1 + ' C' + m + ',' + y1 + ' ' + m + ',' + y2 + ' ' + x2 + ',' + y2 })); });
}
function bdBoard(B) {
  const sel = bdSelNow(B), L = bdLit(B, sel), C = B.counts, hf = B.mode === 'hypothesis_first', T = B.thesis;
  const cw = hf ? ['Hypotheses', 'hypothesis', 'hypotheses'] : ['Claims', 'claim', 'claims'], xw = hf ? ['Steps', 'step'] : ['Experiments', 'experiment'];
  const lit = key => !L || (key === 't' ? L.t : L[key[0]].has(key.slice(2)));
  const card = (key, cls, kids, title) => h('button', { class: 'bd-c ' + cls + (sel === key ? ' on' : '') + (L ? (lit(key) ? ' lit' : ' dim') : ''), 'data-k': key, 'aria-pressed': String(sel === key), title: title || null, onclick: () => bdPick(B, key) }, kids);
  const col = (name, n, sub, kids) => h('div', { class: 'bd-col' }, h('div', { class: 'bd-ch' }, h('span', { class: 'bd-cn' }, name), n != null ? h('span', { class: 'bd-cc' }, n) : null, h('span', { class: 'bd-cs' }, sub)), kids);
  const more = (k, hidden, word) => hidden > 0 || RX.bdMore[k] ? h('button', { class: 'linkbtn small bd-more', onclick: () => { RX.bdMore[k] = !RX.bdMore[k]; renderPage(true); } }, RX.bdMore[k] ? 'Show fewer' : '+ ' + hidden + ' more ' + word) : null;
  const first = (list, key, cap) => L && list.length > cap ? list.filter(o => lit(key(o))).concat(list.filter(o => !lit(key(o)))) : list;      // over the cap, the lit cards first, so the cap never hides the path
  const reach = new Set(B.claims.map(c => c.id));
  // 1. thesis
  const tcol = col(T.kind === 'problem' ? 'Problem' : 'Thesis', null, hf ? 'what the research solves' : 'what the paper says',
    card('t', 'th' + (T.text ? '' : ' gap'), [T.text ? h('span', { class: 'bd-tx serif' }, rxMath(trunc(T.text, 230))) : h('span', { class: 'bd-tx muted' }, T.missing),
      T.approach ? h('span', { class: 'bd-s' }, trunc(T.approach, 150)) : null, T.state === 'unreviewed' ? h('span', { class: 'bd-s' }, '[confirm] not confirmed by you yet') : null]));
  // 2. claims
  const ccol = col(cw[0], B.claims.length, hf ? 'answer it' : 'back it', B.claims.length ? B.claims.map(c => card('c:' + c.id, 'cl' + (c.experiments.length ? '' : ' gap'), [
    h('span', { class: 'bd-r' }, h('b', null, c.label || 'Claim'), c.stage ? rxStageChip(c) : null, c.tier && c.tier !== 'confirmatory' ? h('span', { class: 'bd-s' }, c.tier) : null),
    h('span', { class: 'bd-tx serif' }, rxMath(trunc(c.text, 96))), c.experiments.length ? null : h('span', { class: 'bd-s warn' }, '! nothing tests it yet'), c.confirmed === false ? h('span', { class: 'bd-s' }, '[confirm]') : null], c.text))
    : h('p', { class: 'muted small bd-none' }, hf ? 'No hypothesis yet.' : 'No claim yet.'));
  // 3. experiments
  const xsAll = first(B.experiments.filter(x => x.claims.some(c => reach.has(c))).concat(B.experiments.filter(x => !x.claims.some(c => reach.has(c)))), x => 'x:' + x.id, BD_XCAP);
  const xs = RX.bdMore.x ? xsAll : xsAll.slice(0, BD_XCAP);
  const xcol = col(xw[0], B.experiments.length, 'test them', B.experiments.length ? [xs.map(x => { const U = x.used, on = x.claims.filter(c => reach.has(c));
    const dims = U ? [U.methods ? plural(U.methods, 'method') : null, U.datasets ? plural(U.datasets, 'dataset') : null, U.seeds ? plural(U.seeds, 'seed') : null].filter(Boolean) : [];
    return card('x:' + x.id, 'ex' + (on.length ? '' : ' gap'), [
      h('span', { class: 'bd-r' }, h('b', null, bdXName(B, x)), hf ? h('span', { class: 'bd-s' }, '[' + x.status + ']') : SU_XTYPE[x.type] ? h('span', { class: 'bd-s' }, SU_XTYPE[x.type].toLowerCase()) : null),
      hf ? h('span', { class: 'bd-tx' }, trunc(x.name, 80)) : null, dims.length ? h('span', { class: 'bd-s' }, dims.join(' × ')) : null,
      U && U.failed ? h('span', { class: 'bd-s warn' }, '! ' + U.failed + ' of ' + U.rows + ' runs failed') : null, on.length ? null : h('span', { class: 'bd-s warn' }, '! tests no claim')], x.name); }),
    more('x', xsAll.length - BD_XCAP, xw[1] + 's')] : h('p', { class: 'muted small bd-none' }, 'No ' + xw[1] + ' yet.'));
  // 4. what was used, by kind
  const icol = col('What was used', B.items.length, 'in them', B.items.length ? Object.keys(BD_KIND).map(k => { const all = first(B.items.filter(it => it.kind === k), it => 'i:' + it.id, BD_CAP); if (!all.length) return null;
    const show = RX.bdMore[k] ? all : all.slice(0, BD_CAP);
    return h('div', { class: 'bd-k' }, h('div', { class: 'bd-kh' }, BD_KIND[k][0], h('span', { class: 'bd-cc' }, ' ' + all.length)),
      h('div', { class: 'bd-its' }, show.map(it => { const sub = bdItemSub(it); return card('i:' + it.id, 'it k-' + k, [h('span', { class: 'bd-in' }, it.name), sub ? h('span', { class: 'bd-s' }, sub) : null, it.failed ? h('span', { class: 'bd-s warn', title: it.failed + ' of its runs are marked failed in the result files' }, '! ' + it.failed + ' failed') : it.checks ? h('span', { class: 'bd-s warn', title: plural(it.checks, 'thing') + ' to check' }, '!') : null], it.name + (sub ? ' · ' + sub : '')); })),
      more(k, all.length - BD_CAP, BD_KIND[k][0].toLowerCase())); })
    : h('p', { class: 'muted small bd-none' }, hf ? 'The steps’ result tables name no method, dataset or metric yet.' : 'Nothing read from the result files yet.'));
  const gaps = [C.experiments_no_claim ? plural(C.experiments_no_claim, xw[1]) + ' with no claim' : null, C.claims_untested ? plural(C.claims_untested, cw[1], cw[2]) + ' with no ' + xw[1] : null].filter(Boolean);
  const el = h('section', { class: 'bd' + (L ? ' has-sel' : ''), 'aria-label': 'How the setup connects to the thesis' },
    h('div', { class: 'bd-h' }, h('h2', { class: 'bd-t' }, 'How the setup connects to the ' + (T.kind === 'problem' ? 'problem' : 'thesis')),
      gaps.length ? h('span', { class: 'rx-warn bd-gap' }, '! ' + gaps.join(' · ')) : null, h('span', { class: 'grow' }),
      sel ? h('button', { class: 'linkbtn small', onclick: () => bdPick(B, sel) }, 'Clear') : null),
    B.waiting ? h('p', { class: 'muted small' }, 'The hypotheses are not drafted yet, so this board is made from the result files. ', h('button', { class: 'linkbtn', onclick: () => openTab('experiments') }, 'Open Thesis'), '.') : null,
    h('div', { class: 'bd-b' }, sv('svg', { class: 'bd-w', 'aria-hidden': 'true' }), tcol, ccol, xcol, icol),
    h('p', { class: 'bd-tr' + (sel ? '' : ' muted') }, sel ? bdTrace(B, sel, L) : 'Click a card to light its path to the ' + (T.kind === 'problem' ? 'problem' : 'thesis') + '. A dashed card is not connected yet.'),
    sel && !(B.mode === 'paper' && sel[0] === 'i') ? bdDetail(B, sel) : null);
  const draw = () => bdWire(el, B, L);
  requestAnimationFrame(() => { draw(); if (!el.isConnected || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => { if (!el.isConnected) return ro.disconnect(); draw(); }); ro.observe(el.querySelector('.bd-b')); });
  return el;
}
function bdSheets(B) {      // the result-file sheets a board selection narrows the page to (null: all of them)
  const sel = B && bdSelNow(B); if (!sel || sel === 't' || sel[0] === 'i') return null;
  const id = sel.slice(2), xs = sel[0] === 'x' ? B.experiments.filter(x => x.id === id) : B.experiments.filter(x => x.claims.includes(id));
  return new Set(xs.flatMap(x => x.sheets));
}
function pageSetup() {
  const nr = rxNotReady('Setup'); if (nr) return nr;
  S.outline = [];
  const D = RX.setup;
  const root = doc();
  if (!D) {
    if (RX.setupErr) return root.append(h('h1', { class: 'ptitle' }, 'Setup'), emptyState('!', 'Not available', RX.setupErr, [h('button', { class: 'btn', onclick: () => { RX.setupErr = null; suLoad(); } }, 'Try again')])), root;
    suLoad(); return root.append(h('h1', { class: 'ptitle' }, 'Setup'), h('p', { class: 'muted' }, 'Reading the experiments…')), root;
  }
  const c = D.counts, hfB = D.board && D.board.mode === 'hypothesis_first' && (D.board.experiments.length || D.board.claims.length);
  root.classList.add('wide');
  root.append(h('h1', { class: 'ptitle' }, 'Setup'), rxStudyLine(), rxBehindNote(), hfB ? null :
    h('div', { class: 'rx-x-sum' }, h('span', null, h('b', null, c.experiments), ' experiments'), h('span', null, h('b', null, c.dataset), ' datasets'), h('span', null, h('b', null, c.method), D.study === 'benchmark' ? ' compared methods' : ' methods', c.baselines ? ' (' + c.baselines + ' baselines)' : ''), h('span', null, h('b', null, c.metric), ' metrics'),
      c.checks ? h('span', { class: 'warn' }, h('b', null, c.checks), ' to check') : null,
      h('button', { class: 'linkbtn', id: 'su-baselines', title: 'Each baseline\'s paper, PDF, code, idea and published numbers', onclick: () => openTab('baselines') }, 'Baselines →')));
  const B = D.board && (D.board.experiments.length || D.board.claims.length) ? D.board : null, hf = B && B.mode === 'hypothesis_first';
  if (!D.mapped && !hf) root.append(h('div', { class: 'flag' }, 'No confirmed project map yet: each result file is read on its own, so this is rough. ', h('button', { class: 'linkbtn', onclick: () => openTab('experiments') }, 'Confirm the map on Thesis'), '.'));
  if (B) root.append(bdBoard(B));
  if (!D.experiments.some(x => x.protocol)) return root.append(B ? h('p', { class: 'muted' }, 'No result file could be read as a table of methods and numbers, so there are no sheets below.') : emptyState('○', 'Nothing to show yet', 'No result file could be read as a table of methods and numbers.', [])), root;
  let sel = RX.suSel || null;
  const hl = sel && sel.startsWith('i:') && D.items.some(it => it.id === sel.slice(2)) ? sel.slice(2) : null;
  if (hl) root.append(suItemDetail(D.items.find(it => it.id === hl), D));
  const byX = new Map(D.experiments.map(x => [x.id, x])), seen = new Set(), only = bdSheets(B);
  const uses = x => (!hl || x.items.includes(hl)) && (!only || only.has(x.id));
  const sheetsN = D.experiments.filter(x => x.protocol).length;
  if (hf && !hl && !only && !RX.suAll && sheetsN > 12)      // top-down: the steps first, a step's result files on request
    return root.append(h('div', { class: 'su-cl-h' }, h('span', { class: 'rx-x-q static' }, 'Result files'), h('span', { class: 'rx-x-qt muted' }, sheetsN + ' result files have a sheet. Click a step above to see its files, or '),
      h('button', { class: 'linkbtn', onclick: () => { RX.suAll = true; renderPage(true); } }, 'show all ' + sheetsN))), root;
  if (only) root.append(h('p', { class: 'muted small bd-flt' }, only.size ? 'Showing the ' + plural(only.size, 'sheet') + ' of the selected card. ' : 'The selected card has no sheet. ', h('button', { class: 'linkbtn', onclick: () => bdPick(B, RX.bdSel) }, 'Show all')));
  D.claims.forEach(cl => {
    const xs = cl.experiments.map(id => byX.get(id)).filter(x => x && uses(x)); if (!xs.length) return;
    root.append(h('div', { class: 'su-cl-h' + (cl.stage ? rxSt(cl.stage) : '') }, h('button', { class: 'rx-x-q', title: 'Open in Thesis', onclick: () => suGotoClaim(cl.id) }, cl.label), cl.stage ? rxStageChip(cl) : null, h('span', { class: 'rx-x-qt serif' }, rxMath(trunc(cl.text, 160)))));
    xs.forEach(x => {
      if (D.study === 'benchmark' && seen.has(x.id) && !hl) {      // one sheet per experiment: under a later claim, only the line that says how it bears on that claim
        const link = cl.links[x.id], first = D.claims.find(c => c.experiments.includes(x.id));
        return root.append(h('div', { class: 'su-sh su-ref' }, h('div', { class: 'su-sh-h' }, link ? rxLinkChip(Object.assign({ criterion_by: '' }, link)) : null, h('b', null, x.name), h('span', { class: 'muted small' }, 'its sheet is above, under ' + (first ? first.label : 'another claim')), h('span', { class: 'grow' }), h('button', { class: 'linkbtn small', onclick: () => rxOpenExp(x.id) }, 'Open'))));
      }
      seen.add(x.id); root.append(suSheet(x, cl, D, hl)); });
  });
  const loose = D.experiments.filter(x => !seen.has(x.id) && !x.claims.length && x.protocol && uses(x));
  if (loose.length) { root.append(h('div', { class: 'su-cl-h' }, h('span', { class: 'rx-x-q static' }, 'No claim'), h('span', { class: 'rx-x-qt muted' }, 'Experiments that test no claim'))); loose.forEach(x => root.append(suSheet(x, null, D, hl))); }
  if (hl && !root.querySelector('.su-sh')) root.append(h('p', { class: 'muted' }, 'No experiment uses it.'));
  return root;
}
/* ---------- To-do and Trail (S24 steps 4-5, ADR-008 section 5) ----------
   To-do: made by rules; every item opens the thing it is about. Trail: what was done, day by day, deadlines ahead,
   and a whole-month view at the bottom (founder, chat 2026-11-16 11:21 KST). */
const TD_TAG = { person: 'waiting', confirm: 'confirm', paper: 'paper', stale: 'old', gap: 'gap' };
function rxOpenTarget(t) {
  if (!t) return;
  if (t.view === 'claims') { if (t.sel) RX.sel = t.sel; RX.view = 'tree'; if (t.at) RX.t = t.at; return openTab('claims'); }
  if (t.view === 'experiments' && t.sel && t.sel.startsWith('x:')) return rxOpenExp(t.sel.slice(2));
  if (t.view === 'setup') return rxGoto('setup', t.sel);
  if (t.view === 'node' && t.id) return openTab('node', t.id);
  if (t.view === 'commit') { if (t.url) { if (EMBED) { const a = h('a', { href: t.url }); document.body.append(a); a.click(); a.remove(); } else window.open(t.url, '_blank', 'noopener'); } return; }
  if (t.view === 'runs') return openTab('experiments');
  if (t.view === 'numbers') { RX.nbSel = t.sel || null; return openTab('numbers'); }
  return openTab(t.view || 'digest');
}
function rxTodoList(limit) {
  const D = RX.todo;
  if (!D) return h('div', { class: 'muted' }, 'Not available on this hub yet.');
  if (!D.items.length) return h('div', { class: 'muted' }, 'Nothing to do right now.' + (D.counts.snoozed ? ' ' + D.counts.snoozed + ' snoozed.' : ''));
  const out = []; let shown = 0;
  for (const g of D.groups) {
    const its = D.items.filter(it => it.group === g.id); if (!its.length) continue;
    if (limit && shown >= limit) break;
    out.push(h('div', { class: 'td-g' }, g.label + ' · ' + g.n));
    for (const it of its) {
      if (limit && shown >= limit) break; shown++;
      out.push(h('div', { class: 'row-line td-r' }, h('span', { class: 'rtag' }, '[' + TD_TAG[it.group] + ']'),
        h('button', { class: 'ilink td-t', title: it.why + ' (' + it.rule + ')', onclick: () => rxOpenTarget(it.target) }, trunc(it.text, 150)),
        it.due ? h('span', { class: 'tag warn' }, 'due ' + dmon(it.due)) : null,
        h('span', { class: 'td-w muted small' }, trunc(it.why, 110)),
        READONLY || it.group === 'person' ? null : h('button', { class: 'linkbtn small td-s', title: 'Hide for a week. It comes back if it is still true.', onclick: async () => {
          const d = new Date(); d.setDate(d.getDate() + 7); const r = await rxPost('/api/todo', { key: it.key, snooze_until: d.toISOString().slice(0, 10) }); if (r) { RX.todo = r; renderPage(true); } } }, 'Snooze')));
    }
  }
  if (limit && D.items.length > shown) out.push(h('div', { class: 'row-line' }, h('span', { class: 'rtag' }), h('span', { class: 'muted small' }, (D.items.length - shown) + ' more below the first ' + shown)));
  return out;
}
const TR_KIND = { paper: 'Paper', code: 'Code', runs: 'Runs', claims: 'Claims', feedback: 'Feedback', decisions: 'Decisions' };
function trEntry(e) {
  const can = e.target && (e.target.view !== 'commit' || e.target.url);
  return h('div', { class: 'tr-e k-' + e.kind }, h('span', { class: 'tr-c mono' }, e.t.slice(11, 16)), h('span', { class: 'tag tr-k' }, TR_KIND[e.kind]),
    can ? h('button', { class: 'ilink', onclick: () => rxOpenTarget(Object.assign({}, e.target, { at: e.at })) }, trunc(e.title, 130)) : h('span', null, trunc(e.title, 130)),
    e.ref ? h('span', { class: 'mono muted small' }, e.ref) : null, e.decision ? h('span', { class: 'tag warn' }, 'decision') : null, e.why ? h('span', { class: 'muted small' }, e.why) : null);
}
function trMonth(D, ym, filter, onDay) {
  const [y, m] = ym.split('-').map(Number), first = new Date(y, m - 1, 1), n = new Date(y, m, 0).getDate(), lead = (first.getDay() + 6) % 7;
  const p = v => String(v).padStart(2, '0'), key = d => y + '-' + p(m) + '-' + p(d);
  const dl = {}; D.deadlines.forEach(d => { (dl[d.date] = dl[d.date] || []).push(d); });
  const step = k => { const d = new Date(y, m - 1 + k, 1); RX.trMonth = d.getFullYear() + '-' + p(d.getMonth() + 1); renderPage(true); };
  const cells = [];
  for (let i = 0; i < lead; i++) cells.push(h('div', { class: 'tm-c off' }));
  for (let d = 1; d <= n; d++) {
    const k = key(d), c = D.days[k] || null, tot = c ? D.kinds.reduce((a, kk) => a + (filter === 'all' || filter === kk ? c[kk] : 0), 0) : 0;
    cells.push(h('button', { class: 'tm-c' + (k === D.today ? ' today' : '') + (tot ? ' has' : '') + (dl[k] ? ' due' : '') + (RX.trDay === k ? ' sel' : ''), disabled: tot || dl[k] ? null : '',
      title: (tot ? D.kinds.filter(kk => c[kk]).map(kk => c[kk] + ' ' + TR_KIND[kk].toLowerCase()).join(', ') : 'Nothing recorded') + (dl[k] ? ' · due: ' + dl[k].map(x => x.title).join(', ') : ''),
      onclick: () => { RX.trDay = RX.trDay === k && onDay ? null : k; renderPage(true); if (!onDay) { const el = document.getElementById('tr-' + k); if (el) el.scrollIntoView({ block: 'start', behavior: 'smooth' }); } } },
      h('span', { class: 'tm-d' }, d), tot ? h('span', { class: 'tm-dots' }, D.kinds.filter(kk => c[kk] && (filter === 'all' || filter === kk)).map(kk => h('span', { class: 'tm-dot k-' + kk, title: c[kk] + ' ' + TR_KIND[kk].toLowerCase() }))) : null,
      tot ? h('span', { class: 'tm-n' }, tot) : null, dl[k] ? h('span', { class: 'tm-due' }, trunc(dl[k][0].title, 14)) : null));
  }
  return h('section', { class: 'tm' }, h('div', { class: 'tm-h' }, h('h3', null, MON[m - 1] + ' ' + y), h('span', { class: 'grow' }),
      h('button', { class: 'btn sm', 'aria-label': 'Previous month', onclick: () => step(-1) }, '←'), h('button', { class: 'btn sm', onclick: () => { RX.trMonth = null; renderPage(true); } }, 'This month'), h('button', { class: 'btn sm', 'aria-label': 'Next month', onclick: () => step(1) }, '→')),
    h('div', { class: 'tm-g head' }, ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(w => h('div', { class: 'tm-w' }, w))), h('div', { class: 'tm-g' }, cells));
}
/* S25: deadlines from a venue, your own dates, the calendar link, and the day panel */
const DL_KIND = { abstract: 'abstract', paper: 'paper', decision: 'decision', journal: 'journal', milestone: 'milestone' };
function tdReload() { apiGet('/api/todo').then(r => { RX.todo = r; renderAll(); }).catch(() => { /* keep the old list */ }); }
function trDeadlineRow(d, D) {
  const days = Math.round((Date.parse(d.date) - Date.parse(D.today)) / 864e5);
  return h('div', { class: 'tr-e ahead' }, h('span', { class: 'tr-c mono' }, days >= 0 ? 'D-' + days : 'past'), h('span', { class: 'tag tr-k' }, dmon(d.date) + (d.date.slice(0, 4) !== D.today.slice(0, 4) ? ' ' + d.date.slice(0, 4) : '')),
    h('span', null, d.title), d.tz ? h('span', { class: 'muted small' }, d.time + ' ' + d.tz) : null, d.kind && d.kind !== 'milestone' ? h('span', { class: 'tag' }, DL_KIND[d.kind]) : null,
    d.link ? h('a', { class: 'small', href: d.link, target: '_blank', rel: 'noopener noreferrer' }, 'venue page') : null, d.source ? h('a', { class: 'small muted', href: d.source, target: '_blank', rel: 'noopener noreferrer', title: 'Community-kept data: check the venue page' }, 'source') : null,
    READONLY ? null : h('button', { class: 'linkbtn small', onclick: async () => { const r = await rxPost('/api/deadlines', { remove: d.id }); if (r) { RX.trail = r; tdReload(); renderPage(true); } } }, 'Remove'));
}
function trAhead(D) {
  const box = h('section', { class: 'tr-ahead' }, h('div', { class: 'dayhead' }, 'Ahead'), D.ahead.length ? D.ahead.map(d => trDeadlineRow(d, D)) : h('div', { class: 'muted small' }, 'No deadlines yet.'));
  if (READONLY) return box;
  const mode = RX.dlMode || 'conf', seg = h('div', { class: 'rx-seg', role: 'group', 'aria-label': 'Add' }, [['conf', 'Conference'], ['own', 'Journal or own date']].map(([k, l]) => h('button', { 'aria-pressed': String(mode === k), onclick: () => { RX.dlMode = k; RX.dlFound = null; renderPage(true); } }, l)));
  const set = r => { if (r) { RX.trail = r; tdReload(); RX.dlFound = null; renderPage(true); } };
  let form;
  if (mode === 'conf') {
    const ni = h('input', { type: 'text', placeholder: 'Venue, e.g. ICML', 'aria-label': 'Venue', maxlength: '60', value: (RX.dlFound || {}).q || '' }), yi = h('input', { type: 'number', 'aria-label': 'Year', min: '2020', max: '2100', value: String((RX.dlFound || {}).y || (+D.today.slice(0, 4) + 1)) });
    form = h('form', { class: 'tr-f', onsubmit: async ev => { ev.preventDefault(); if (!ni.value.trim()) return; RX.dlFound = { q: ni.value.trim(), y: +yi.value, busy: true }; renderPage(true);
        try { RX.dlFound.r = await apiPost('/api/venue', { name: ni.value.trim(), year: +yi.value }); } catch (e) { RX.dlFound.err = e.message; } RX.dlFound.busy = false; renderPage(true); } }, ni, yi, h('button', { class: 'btn sm', type: 'submit' }, 'Find deadlines'));
    const F = RX.dlFound;
    if (F && F.busy) form.append(h('div', { class: 'muted small tr-fn' }, 'Looking it up…'));
    if (F && F.err) form.append(h('div', { class: 'rx-warn tr-fn' }, F.err));
    if (F && F.r) { const r = F.r, dated = r.deadlines.filter(d => d.date);
      form.append(h('div', { class: 'tr-found' }, h('div', null, h('b', null, r.venue + ' ' + r.year), r.full_name ? h('span', { class: 'muted small' }, ' ' + r.full_name) : null, r.when ? h('span', { class: 'muted small' }, ' · ' + r.when + (r.place ? ', ' + r.place : '')) : null),
        r.deadlines.map(d => h('div', { class: 'tr-e' }, h('span', { class: 'tag tr-k' }, d.label), d.date ? h('span', { class: 'mono' }, d.date + ' ' + d.time) : h('span', { class: 'muted' }, 'not announced (' + d.raw + ')'), d.tz ? h('span', { class: 'muted small' }, d.tz) : null)),
        h('div', { class: 'muted small' }, 'From ', h('a', { href: r.source, target: '_blank', rel: 'noopener noreferrer' }, r.source_name), '. It can be wrong or late: check ', r.link ? h('a', { href: r.link, target: '_blank', rel: 'noopener noreferrer' }, 'the venue page') : 'the venue page', ' before you rely on it.'),
        dated.length ? h('button', { class: 'btn sm primary', type: 'button', onclick: async () => set(await rxPost('/api/venue', { name: F.q, year: F.y, add: true })) }, 'Add these ' + dated.length + ' dates') : null)); }
  } else {
    const di = h('input', { type: 'date', 'aria-label': 'Date' }), ti = h('input', { type: 'text', placeholder: 'What is due, e.g. Submit to TKDE, Draft to advisor', 'aria-label': 'Title', maxlength: '160' }), vi = h('input', { type: 'text', placeholder: 'Journal (optional)', 'aria-label': 'Journal', maxlength: '120' });
    form = h('form', { class: 'tr-f', onsubmit: async ev => { ev.preventDefault(); if (!di.value || !ti.value.trim()) return; set(await rxPost('/api/deadlines', { date: di.value, title: ti.value.trim(), kind: vi.value.trim() ? 'journal' : 'milestone', venue: vi.value.trim() || undefined })); } }, di, ti, vi, h('button', { class: 'btn sm', type: 'submit' }, 'Add date'),
      h('div', { class: 'muted small tr-fn' }, 'A journal has no shared deadline, so you set your own target dates.'));
  }
  box.append(h('div', { class: 'tr-add' }, seg, form), trCalLink());
  return box;
}
function trCalLink() {
  if (EMBED) return EMBED.site ? h('div', { class: 'muted small tr-cal' }, 'The calendar link for Google Calendar is on the website: ', h('a', { href: EMBED.site }, 'open the Trail there'), '.') : null;
  const C = RX.cal;
  if (C === undefined) { RX.cal = null; apiGet('/api/calendar').then(r => { RX.cal = r; renderPage(true); }).catch(() => { RX.cal = { err: true }; }); }
  if (!C || C.err) return null;
  const base = (typeof HUB_ON !== 'undefined' && HUB_ON && PID) ? location.origin + '/cal/' + PID + '/' : null, url = C.token && base ? base + C.token + '.ics' : null;
  const act = async a => { const r = await rxPost('/api/calendar', { action: a }); if (r) { RX.cal = r; renderPage(true); } };
  const isPrivate = /^(localhost|127\.|100\.|10\.|192\.168\.)/.test(location.hostname);
  return h('details', { class: 'details tr-cal' }, h('summary', null, 'Google Calendar and other calendar apps'),
    h('p', { class: 'small' }, 'Only deadlines and your own dates are shared (' + C.events + ' now), not your daily activity.'),
    h('div', { class: 'tr-f' }, h('a', { class: 'btn sm', href: apiUrl('/api/calendar.ics') }, 'Download .ics (one time)'),
      url ? [h('input', { type: 'text', readonly: '', value: url, 'aria-label': 'Subscription link', onclick: ev => ev.target.select() }), h('button', { class: 'btn sm', onclick: () => copyText(url) }, 'Copy'), h('button', { class: 'linkbtn small', onclick: () => act('revoke') }, 'Turn the link off')]
        : base ? h('button', { class: 'btn sm', onclick: () => act('create') }, 'Make a subscription link') : h('span', { class: 'muted small' }, 'A subscription link needs the hub.')),
    url ? h('p', { class: 'muted small' }, 'In Google Calendar: Other calendars → + → From URL, and paste the link. It then updates by itself (Google re-reads it every few hours). Anyone with the link can read these dates.' + (isPrivate ? ' This address is private to your devices, so Google cannot reach it: open Lemmata at its public address and copy the link from there.' : '')) : null);
}
/* S26: a day is shown as work sessions. One card answers what, why, who, where, how, when and with what result;
   the raw commands sit behind a switch, inspection commands hidden (founder, chat 2026-11-16 14:10 KST). */
const SS_WHO = { you: 'You, in the terminal', agent: 'Coding agent', watcher: 'File watcher' };
const SS_TYPE = { run: 'run', script: 'script', analysis: 'analysis', inspection: 'look', setup: 'set-up', git: 'git', writing: 'paper', other: 'other' };
RX.ssOpen = RX.ssOpen || {}; RX.ssInsp = RX.ssInsp || {}; RX.ssCard = RX.ssCard || {};
function ssTime(s) { const a = s.start.slice(11, 16), b = s.end.slice(11, 16); return a === b ? a : a + '–' + b; }
function ssDur(m) { return m < 1 ? null : m < 60 ? m + ' min' : Math.floor(m / 60) + ' h' + (m % 60 ? ' ' + (m % 60) + ' min' : ''); }
function ssWho(s) { return s.who.map(w => SS_WHO[w.who] + ' (' + plural(w.n, 'command') + ')').concat(s.authors.map(a => 'commit by ' + a)); }
async function ssNote(body) { const r = await rxPost('/api/session', body); if (r) { RX.trail = r; RX.ssEdit = null; renderPage(true); } }
function ssNoteBox(s) {
  if (READONLY) return s.note && s.note.state === 'proposed' ? h('div', { class: 'ss-note' }, h('span', { class: 'tag warn' }, 'draft summary, not confirmed')) : null;
  if (RX.ssEdit === s.id) {
    const inp = h('input', { type: 'text', maxlength: 300, value: s.note ? s.note.text : '', placeholder: 'One sentence: what was this session for?', 'aria-label': 'Session summary' });
    const save = () => { if (inp.value.trim()) ssNote({ id: s.id, text: inp.value.trim() }); };
    inp.addEventListener('keydown', ev => { if (ev.key === 'Enter') save(); if (ev.key === 'Escape') { RX.ssEdit = null; renderPage(true); } });
    setTimeout(() => inp.focus(), 0);
    return h('div', { class: 'ss-note edit' }, inp, h('button', { class: 'btn sm', onclick: save }, 'Save'), h('button', { class: 'linkbtn small', onclick: () => { RX.ssEdit = null; renderPage(true); } }, 'Cancel'));
  }
  const edit = label => h('button', { class: 'linkbtn small', onclick: () => { RX.ssEdit = s.id; renderPage(true); } }, label);
  if (!s.note) return h('div', { class: 'ss-note' }, h('span', { class: 'muted small' }, 'Title made by rules. '), edit('Write a summary'), h('span', { class: 'muted small' }, ' or ask your coding agent to draft one (Lemmata tool: session_summary).'));
  if (s.note.state === 'proposed') return h('div', { class: 'ss-note' }, h('span', { class: 'tag warn' }, 'draft by your agent'), h('button', { class: 'btn sm', onclick: () => ssNote({ id: s.id, action: 'confirm' }) }, 'Confirm'), edit('Edit'),
    h('button', { class: 'linkbtn small', onclick: () => ssNote({ id: s.id, action: 'remove' }) }, 'Discard'), h('span', { class: 'muted small' }, 'By rules: ' + s.rule_title));
  return h('div', { class: 'ss-note' }, h('span', { class: 'muted small' }, 'Summary ' + (s.note.by === 'agent' ? 'drafted by your agent, confirmed by you. ' : 'written by you. ')), edit('Edit'), h('button', { class: 'linkbtn small', onclick: () => ssNote({ id: s.id, action: 'remove' }) }, 'Remove'));
}
function ssMoved(r) {
  const moved = r.before != null && r.before !== r.after, better = moved && (r.lower ? r.after < r.before : r.after > r.before), ahead = r.best_other != null && (r.lower ? r.after <= r.best_other : r.after >= r.best_other);
  return h('div', { class: 'tr-res' }, h('button', { class: 'ilink', onclick: () => rxOpenExp(r.x) }, r.name), r.claims.length ? h('span', { class: 'tag' }, 'tests ' + r.claims.join(', ')) : h('span', { class: 'tag warn' }, 'no claim'),
    h('span', { class: 'mono' }, (r.before != null ? rxFmt(r.before) + ' → ' : 'first result ') + rxFmt(r.after)), moved ? h('span', { class: better ? 'good' : 'bad' }, better ? 'better' : 'worse') : r.before != null ? h('span', { class: 'muted' }, 'unchanged') : null,
    r.field ? h('span', { class: 'muted small' }, 'best of the field') : r.best_other != null ? h('span', { class: 'muted small' }, 'best other ' + rxFmt(r.best_other) + (ahead ? ' · ours ahead' : ' · ours behind')) : null, r.metric ? h('span', { class: 'muted small' }, 'on ' + r.metric + (r.lower ? ' ↓' : ' ↑')) : null);
}
function ssCard(s) {
  const row = (k, v) => v == null || (Array.isArray(v) && !v.flat(3).filter(Boolean).length) ? null : h('div', { class: 'ss-r' }, h('span', { class: 'ss-k' }, k), h('div', { class: 'ss-v' }, v));
  const W = s.where, H = s.how, R = s.result, dur = ssDur(s.minutes);
  const card = h('article', { class: 'ss' + (s.note && s.note.state === 'proposed' ? ' draft' : '') + (R.failed ? ' bad' : ''), id: 'ss-' + s.id });
  card.append(h('div', { class: 'ss-h' }, h('span', { class: 'ss-t mono' }, ssTime(s)), dur ? h('span', { class: 'muted small' }, dur) : null, h('b', { class: 'ss-title' }, s.title)), ssNoteBox(s));
  const why = [s.why.known ? null : h('span', { class: 'tag warn' }, 'unknown'), h('span', { class: s.why.known ? null : 'muted' }, s.why.text),
    s.experiments.map(x => h('button', { class: 'ilink ss-x', title: x.how === 'wrote' ? 'It wrote result files of this experiment' : x.how === 'names' ? 'Its command names this experiment’s result folder' : x.how === 'reads' ? 'It read this experiment’s results' : 'A commit changed this experiment’s results', onclick: () => rxOpenExp(x.id) }, x.name))];
  const where = [W.hosts.length ? h('span', null, W.hosts.join(', ')) : null, W.places.map(p => h('span', { class: 'mono small' }, p.name)), W.shas.length ? h('span', { class: 'muted small' }, 'at commit ' + W.shas.join(', ') + (W.dirty ? ' with uncommitted changes' : '')) : null,
    W.scratch ? h('span', { class: 'muted small' }, plural(W.scratch, 'command') + ' from the agent’s scratch folder') : null];
  const how = [H.scripts.map(x => h('span', { class: 'mono small' }, x.name + (x.n > 1 ? ' ×' + x.n : ''))), H.configs.length ? h('span', { class: 'muted small' }, 'settings file: ' + H.configs.join(', ')) : null,
    H.env.map(v => h('span', { class: 'mono small ss-kv' }, v.key + '=' + trunc(v.value, 40))), H.args.map(a => h('span', { class: 'mono small ss-kv' }, a.key + ': ' + a.values.join(', ')))];
  const res = [R.moved.map(ssMoved), R.metrics.length ? h('div', null, R.metrics.map(m => h('span', { class: 'mono small ss-kv' }, m.key + ' = ' + rxFmt(m.value)))) : null,
    R.files.map(f => h('div', { class: 'tr-files' }, h('span', { class: 'tag' + (f.tracked ? '' : ' muted') }, f.n + (f.tracked ? ' result' : '') + (f.n === 1 ? ' file' : ' files')), h('span', { class: 'mono small muted' }, f.dir + '/  ' + f.names.join('  ') + (f.n > f.names.length ? '  …' : '')))),
    R.notes.map(n => h('div', { class: /failed|uncommitted/.test(n) ? 'rx-warn' : 'muted small' }, n))];
  card.append(h('div', { class: 'ss-b' },
    row('What', h('ul', { class: 'ss-ul' }, s.what.map(w => h('li', null, w)))),
    row('Why', why), row('Who', ssWho(s).length ? ssWho(s).join(' · ') : null), row('Where', where), row('How', how),
    row('Result', res.flat().filter(Boolean).length ? res : h('span', { class: 'muted small' }, 'Nothing was written or changed.'))));
  const open = RX.ssOpen[s.id], insp = RX.ssInsp[s.id], nrec = s.commands_n + s.entries.length;
  if (nrec) {
    const label = [s.commands_n ? plural(s.commands_n, 'command') : null, s.commits ? plural(s.commits, 'commit') : null, s.entries.length - s.commits > 0 ? plural(s.entries.length - s.commits, 'other record') : null].filter(Boolean).join(', ');
    card.append(h('button', { class: 'linkbtn small ss-more', 'aria-expanded': String(!!open), onclick: () => { RX.ssOpen[s.id] = !open; renderPage(true); } }, (open ? 'Hide the records' : 'Show the records') + ' (' + label + ') ' + (open ? '▾' : '▸')));
    if (open) {
      const box = h('div', { class: 'ss-rec' });
      s.entries.forEach(e => { box.append(trEntry(e)); const d = e.detail; if (d) Object.keys(d.files || {}).forEach(k => box.append(h('div', { class: 'tr-files tr-dd' }, h('span', { class: 'tag' }, k + ' · ' + d.files_n[k]), h('span', { class: 'mono small muted' }, d.files[k].join('  ') + (d.files_n[k] > d.files[k].length ? '  …' : ''))))); });
      s.commands.filter(c => insp || !c.hidden).forEach(c => box.append(h('div', { class: 'ss-c' + (c.exit ? ' bad' : '') + (c.hidden ? ' insp' : '') }, h('span', { class: 'tr-c mono' }, c.t.slice(11, 16)), h('span', { class: 'tag' }, SS_TYPE[c.type]), h('span', { class: 'tag' + (c.who === 'agent' ? ' warn' : '') }, c.who),
        h('code', { class: 'ss-cmd', title: c.command }, trunc(c.command.replace(/\s*\n\s*/g, ' ⏎ '), 260)), c.exit ? h('span', { class: 'tag warn' }, 'exit ' + c.exit) : null)));
      if (s.commands_n > s.commands.length) box.append(h('div', { class: 'muted small' }, 'Only the last ' + s.commands.length + ' commands are listed.'));
      if (s.hidden_n) box.append(h('button', { class: 'linkbtn small', onclick: () => { RX.ssInsp[s.id] = !insp; renderPage(true); } }, insp ? 'Hide the inspection commands' : 'Also show ' + plural(s.hidden_n, 'inspection command') + ' (ls, cat, pgrep and the like)'));
      card.append(box);
    }
  }
  return card;
}
function ssRow(s) {   // one line per session on the Trail list; click for the card
  const open = RX.ssCard[s.id];
  const line = h('button', { class: 'ss-row' + (open ? ' on' : ''), 'aria-expanded': String(!!open), onclick: () => { RX.ssCard[s.id] = !open; renderPage(true); } }, h('span', { class: 'tr-c mono' }, ssTime(s)), h('span', { class: 'ss-row-t' }, trunc(s.title, 110)),
    s.note && s.note.state === 'proposed' ? h('span', { class: 'tag warn' }, 'draft') : null, s.why.claims.length ? h('span', { class: 'tag' }, s.why.claims.join(', ')) : null,
    s.who.map(w => h('span', { class: 'tag' + (w.who === 'agent' ? ' warn' : '') }, w.who === 'you' ? 'you' : w.who)), s.result.failed ? h('span', { class: 'tag warn' }, s.result.failed + ' failed') : null,
    h('span', { class: 'muted small' }, [s.commands_n ? plural(s.commands_n, 'command') : null, s.commits ? plural(s.commits, 'commit') : null].filter(Boolean).join(', ')));
  return open ? [line, ssCard(s)] : line;
}
function trDayPanel(D, day) {
  const dls = D.deadlines.filter(d => d.date === day), ss = (D.sessions || []).filter(s => s.day === day).slice().reverse();
  const box = h('section', { class: 'tr-day' }, h('div', { class: 'tr-day-h' }, h('b', null, dmon(day) + ' ' + day.slice(0, 4) + ' · ' + ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][new Date(day + 'T00:00:00').getDay()]),
    ss.length ? h('span', { class: 'muted small' }, plural(ss.length, 'work session') + ' · ' + (ssDur(ss.reduce((a, s) => a + s.minutes, 0)) || 'under a minute') + ' of recorded activity') : null, h('span', { class: 'grow' }),
    h('button', { class: 'linkbtn small', onclick: () => { RX.trDay = null; renderPage(true); } }, 'Close')));
  dls.forEach(d => { const open = RX.todo ? RX.todo.items.filter(i => i.group !== 'gap').length : 0;
    box.append(trDeadlineRow(d, D), h('div', { class: 'tr-dd muted small' }, d.venue ? d.venue + ' · ' : '', open ? open + ' to-do items are still open (not counting gaps).' : 'No to-do items open.')); });
  if (!D.sessions) { D.entries.filter(e => e.day === day).forEach(e => box.append(trEntry(e))); return box; }   // a hub from before S26
  if (!ss.length && !dls.length) box.append(h('div', { class: 'muted small' }, 'Nothing recorded on this day.'));
  ss.forEach(s => box.append(ssCard(s)));
  if (ss.length) box.append(h('div', { class: 'muted small su-hint' }, 'A session is activity with no gap longer than ' + (D.gap_minutes || 60) + ' minutes. Everything except a confirmed summary is worked out by rules from the logged commands, commits and result files.'));
  return box;
}
async function trLoad() {
  if (RX.trailBusy) return; RX.trailBusy = true;
  try { RX.trail = await apiGet('/api/trail'); RX.trailErr = null; } catch (e) { RX.trailErr = e.status === 404 || e.status === 501 ? 'This hub has no Trail yet. It appears after the hub updates.' : e.message; }
  RX.trailBusy = false; const t = S.tabs[S.active]; if (t && (t.k === 'history' || t.k === 'trail')) renderPage(true);
}
function pageTrail() {
  const nr = rxNotReady('Trail'); if (nr) return nr;
  S.outline = [];
  const root = doc(h('h1', { class: 'ptitle' }, 'Trail'));
  const D = RX.trail;
  if (!D) { if (RX.trailErr) return root.append(h('p', { class: 'muted' }, RX.trailErr)), root; trLoad(); return root.append(h('p', { class: 'muted' }, 'Reading the history…')), root; }
  const F = RX.trFilter || 'all';
  root.append(trAhead(D));
  root.append(h('div', { class: 'fchips' }, [['all', 'All']].concat(D.kinds.map(k => [k, TR_KIND[k] + ' ' + D.counts[k]])).map(([k, l]) => h('button', { class: 'fchip', 'aria-pressed': String(F === k), onclick: () => { RX.trFilter = k; renderPage(true); } }, l))));
  const bySession = !!D.sessions;
  const es = bySession ? D.sessions.filter(x => F === 'all' || x.kinds.includes(F)).map(x => Object.assign({ t: x.start, _s: true }, x)) : D.entries.filter(e => F === 'all' || e.kind === F), cap = RX.trAll ? es.length : (bySession ? 60 : 120);
  if (!es.length) root.append(h('div', { class: 'muted' }, 'Nothing recorded yet.'));
  let week = null, day = null;
  es.slice(0, cap).forEach(e => {
    const w = weekStart(e.t);
    if (w !== week) { root.append(h('div', { class: 'tr-w' }, 'Week of ' + dmon(w) + (w.slice(0, 4) !== D.today.slice(0, 4) ? ' ' + w.slice(0, 4) : ''))); week = w; }
    if (e.day !== day) { root.append(h('div', { class: 'dayhead tr-d' + (RX.trDay === e.day ? ' sel' : ''), id: 'tr-' + e.day }, e.day === D.today ? 'Today' : dmon(e.day) + ' · ' + ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][new Date(e.day + 'T00:00:00').getDay()])); day = e.day; }
    root.append(e._s ? ssRow(e) : trEntry(e));
  });
  if (es.length > cap) root.append(h('button', { class: 'linkbtn', onclick: () => { RX.trAll = true; renderPage(true); } }, 'Show all ' + es.length));
  // the whole month, at the bottom
  root.append(trMonth(D, RX.trMonth || (RX.trDay || D.last || D.today).slice(0, 7), F));
  return root;
}

/* S27: FAQ. Questions a researcher asks, each answered in two or three sentences with a button to the page that holds the
   answer (founder, chat 2026-11-16 14:34 KST: "where can I check the experiments done so far? Add these type of FAQs"). */
const FAQ = [
  ['Finding things', [
    ['Where can I check the experiments done so far?', 'Thesis lists every experiment under the claim it tests, with one word for what it shows: supports, contradicts, inconclusive or not run. Setup shows how each one was run: metric, datasets, methods and the numbers. Trail shows when each was run, day by day.', [['Thesis', 'experiments'], ['Setup', 'setup'], ['Trail', 'history']]],
    ['Which experiment backs which claim?', 'On Thesis, each claim has its experiments under it. The bar at the top counts how many support, contradict or are inconclusive. Experiments that test no claim, and claims with no experiment, are listed as gaps.', [['Thesis', 'experiments']]],
    ['Where does a number in my paper come from?', 'On Setup, click the number in the experiment’s table. The trace shows what the paper says, the result files behind it, the script and settings, who ran it and when it was last written.', [['Setup', 'setup']]],
    ['How does what I used connect to the thesis?', 'The board at the top of Setup: thesis (or problem), claims, experiments, and what was used, as four columns of cards. Click a card and its path to the thesis stays lit, with one sentence saying the path. A dashed card is not connected yet, such as an experiment that tests no claim.', [['Setup', 'setup']]],
    ['Which datasets, metrics and baselines do I use, and where?', 'Each Setup sheet names them. Click a name to see every experiment that uses it and where the paper and the code mention it. A “!” marks something to check, such as a baseline missing on one dataset.', [['Setup', 'setup']]],
    ['What did I, or my coding agent, do on a given day?', 'Click the day in the calendar on Home. The day is shown as work sessions: what was done, for which claim, by whom, on which server and folder, with which script, and what came out. The raw commands are behind “Show the records”.', [['Home', 'digest'], ['Trail', 'history']]],
    ['What should I do next?', '“Next to do” on Home is made by rules: feedback someone is waiting on, things waiting for you to confirm, places where the paper disagrees with the results, results that are out of date, and gaps. Each item opens the thing it is about.', [['Home', 'digest']]],
    ['Does the paper still agree with the results?', 'Items tagged [paper] in “Next to do” are cells where the paper and the result files differ. Checks lists every mismatch with the file and line. Each Setup sheet also says how many cells match.', [['Checks', 'checks'], ['Home', 'digest']]],
    ['Which results are out of date?', 'A result is out of date when the code or settings behind it changed after it was written. These show as [old] items in “Next to do” and as a warning on the experiment’s Setup sheet.', [['Home', 'digest'], ['Setup', 'setup']]],
    ['My work has no method of its own. Why does Lemmata look for “ours”?', 'It should not. Set the study to “Benchmark study” on Home, Thesis or Setup. Nothing is then called “ours”: the methods in your result files are listed as compared methods, datasets and test rows are no longer mistaken for methods, and each claim is decided by its own test instead of a method’s rank. A method paper keeps “ours” and the baseline comparison.', [['Home', 'digest'], ['Setup', 'setup']]],
    ['Where does a number in my report come from, and is it still right?', 'Key numbers lists the numbers the study rests on under the claim each belongs to: what the report says, what the committed file holds today, the commit that last wrote the file and the runs behind it. A number no file stores, a file no logged run wrote and a mismatch are listed as open gaps.', [['Key numbers', 'numbers']]],
    ['Lemmata says a run or a file is not in GitHub, but it is.', 'Look for the “Sync with GitHub is failing” note. While syncing fails, Lemmata’s copy of your repository is behind, and the note says why: usually the saved GitHub sign-in has expired or covers public repositories only. Sign in to GitHub again on the Projects page, then use “Sync now”.', [['Home', 'digest']]],
    ['What changed since I last looked?', 'Changes lists what moved since your last checkpoint and what to re-check because of it. “Mark everything as looked at” starts a new checkpoint.', [['Changes', 'changes']]],
  ]],
  ['Keeping it right', [
    ['Lemmata has an experiment or a claim wrong. How do I fix it?', 'Lemmata drafts and you confirm. On Thesis you can edit and confirm the project map (which files form which experiment, which claim each tests), set a claim’s stage yourself, and change when an experiment counts as support under “Supports when”.', [['Thesis', 'experiments']]],
    ['Why does an experiment say “supports” when the result is a tie?', 'By default a tie with the best other method counts as support. Set a stricter rule for that experiment under “Supports when” on Thesis. Every status shows the rule that produced it.', [['Thesis', 'experiments']]],
    ['How do runs get recorded?', 'From three places: commands run in the VS Code terminal with the Lemmata extension, the results watcher that sees result files change, and your coding agent through the Lemmata tools. Runs made elsewhere appear only once their result files are committed. A logged command that wrote no file and no number (a check, a look at a file) is kept as a command, not counted as an experiment.', [['Trail', 'history']]],
    ['A day shows “Lemmata cannot tell” under Why. What now?', 'Nothing in that session wrote a result file of a mapped experiment. Write a one-sentence summary on the card, or ask your coding agent to draft one and then confirm it. If the files belong to an experiment, add them to the project map on Thesis.', [['Home', 'digest'], ['Thesis', 'experiments']]],
    ['How do I get session summaries written for me?', 'In your coding agent with the Lemmata tools connected, ask it to draft summaries for the sessions that have none. Each draft is marked “draft by your agent” until you confirm, edit or discard it. It runs on your own plan.', [['Trail', 'history']]],
    ['Does Lemmata send my work to an AI model?', 'No. Tracking is done by rules on your own machine or hub. A model is used only when your own coding agent drafts the project map or a session summary, and nothing it drafts counts until you confirm it.', []],
  ]],
  ['Planning and sharing', [
    ['How do I add a deadline?', 'On Trail, under Ahead. For a conference, type the venue and year and Lemmata looks up the abstract and paper deadlines. For a journal or your own milestone, set the date yourself. Deadlines show in the calendar on Home.', [['Trail', 'history']]],
    ['Can I see the deadlines in Google Calendar?', 'Yes. On the website, open “Google Calendar and other calendar apps” on Trail and make a subscription link. Google can only read it when the hub has a public address.', [['Trail', 'history']]],
    ['My advisor gave feedback. Where does it go?', 'Use “Add feedback” on Home and paste the notes. Lemmata splits them into tasks, links each to the part of the paper or the files it is about, and shows what else to re-check when it is done.', [['Home', 'digest'], ['Tasks', 'tasks']]],
    ['What do I bring to a meeting?', '“This week” at the bottom of Home is a short digest of the last seven days: claims that changed stage, runs, open tasks. Copy it into your notes.', [['Home', 'digest']]],
    ['What should I check before I submit?', 'Review answers three questions for a period: are there new results, how does your method compare with the baselines, and is the evidence enough to write the paper. Checks lists the problems found in the paper and code, each with its file and line. Then clear the [paper] and [old] items in “Next to do”, and read the checklist at the bottom of each Setup sheet.', [['Review', 'review'], ['Checks', 'checks'], ['Setup', 'setup']]],
  ]],
  ['A routine that works', [
    ['How do I get the most out of Lemmata each week?', 'Start the week on Home: clear “Next to do” and look at the deadlines. After a batch of runs, open the day and confirm the session summaries while you still remember why you ran them. Before a meeting, copy “This week”. Before a deadline, go through Review, Checks and the Setup checklists.', [['Home', 'digest']]],
    ['Website or VS Code?', 'They show the same pages. Use VS Code while you work: it jumps to the file and line, and it records the runs. Use the website for the wide views: the calendar, the sidebar and the calendar link.', []],
  ]],
];
function pageFaq() {
  S.outline = [];
  const root = doc(h('h1', { class: 'ptitle' }, 'FAQ'), h('p', { class: 'muted' }, 'Where to look for what. Each answer has a button to the page it is about.'));
  return faqBlock(root);
}
function faqBlock(root) {
  const q = (RX.faqQ || '').toLowerCase().trim();
  const inp = h('input', { type: 'search', value: RX.faqQ || '', placeholder: 'Filter the questions', 'aria-label': 'Filter the questions' });
  inp.addEventListener('input', () => { RX.faqQ = inp.value; renderPage(true); const el = document.querySelector('.fq-f input'); if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); } });
  root.append(h('div', { class: 'fq-f' }, inp));
  let shown = 0;
  FAQ.forEach(([head, items]) => {
    const its = items.filter(([qq, a]) => !q || (qq + ' ' + a).toLowerCase().includes(q)); if (!its.length) return;
    root.append(h('h2', { class: 'fq-h' }, head));
    its.forEach(([qq, a, links]) => { shown++;
      const d = h('details', { class: 'fq' }, h('summary', null, qq), h('p', null, a), links.length ? h('div', { class: 'fq-l' }, links.map(([label, k]) => h('button', { class: 'btn sm', onclick: () => openTab(k) }, 'Open ' + label))) : null);
      if (q || RX.faqOpen === qq) d.open = true;
      d.addEventListener('toggle', () => { if (d.open) RX.faqOpen = qq; else if (RX.faqOpen === qq) RX.faqOpen = null; });
      root.append(d); });
  });
  if (!shown) root.append(h('p', { class: 'muted' }, 'No question matches. Try Ask for a question about this project’s content.'), h('button', { class: 'btn sm', onclick: () => openTab('ask') }, 'Open Ask'));
  return root;
}
/* ---------- S27 hypothesis-first: problem -> hypotheses -> test -> experiments, on the Thesis page ----------
   Everything comes from /api/hypothesis. Lemmata never calls a model: what needs one is a job for the researcher's own LLM
   (Claude Code over MCP, or any LLM given the job's markdown). The researcher decides: Confirm, Fix, Delete, Combine, Tell. */
const HF_TIER = { confirmatory: ['Confirmatory', 'Pre-registered: its test was fixed before the data.'], secondary: ['Secondary', 'Pre-registered without a confirmatory claim: numbers, no verdict.'], exploratory: ['Exploratory', 'Decided after seeing the data, or no frozen test.'] };
const HF_JOB = { understand_problem: 'State the problem', draft_hypotheses: 'Draft the hypotheses', revise: 'Propose what else must change', combine: 'Combine hypotheses', comprehend_input: 'Read what you told Lemmata', premise_check: 'Check the cited source' };
const HF_PF = [['gap', 'Gap'], ['why_it_matters', 'Why it matters'], ['approach', 'Approach'], ['if_solved', 'If it works']];
const HF_RULE = { R0: 'set by you', R1: 'test met', R2: 'test not met', R3: 'tested, no verdict', R4: 'not run or no rule', R5: 'exploratory' };
async function hfPost(path, body, okMsg) {
  try { const r = await apiPost(path, body); RX.hf = r; toast(r.message || okMsg || 'Saved.'); try { RX.claims = await apiGet('/api/claims'); RX.experiments = await apiGet('/api/experiments'); } catch (e) { /* the page still shows the new view */ } renderPage(true); return r; }
  catch (e) { toast(e.message); return null; }
}
const hfAct = (action, extra) => hfPost('/api/hypothesis', Object.assign({ action }, extra || {}));
function hfAsk(title, label, value, fn, opts) {
  const ta = h('textarea', { class: 'hf-ta', rows: (opts && opts.rows) || 4, 'aria-label': label, placeholder: (opts && opts.placeholder) || '' }); ta.value = value || '';
  modal(title, h('div', null, h('p', { class: 'muted small' }, label), ta), [{ label: 'Cancel' }, { label: (opts && opts.ok) || 'Save', primary: true, fn: () => fn(ta.value) }], { width: 560 });
}
function hfFix(hy) {
  const st = h('textarea', { class: 'hf-ta', rows: 3, 'aria-label': 'Statement' }); st.value = hy.statement;
  const an = h('textarea', { class: 'hf-ta', rows: 2, 'aria-label': 'What it answers' }); an.value = hy.answers || '';
  const why = h('textarea', { class: 'hf-ta', rows: 2, 'aria-label': 'What is wrong', placeholder: 'Or say in plain words what is wrong: "this is not my point; the point is…"' });
  modal('Fix ' + hy.id, h('div', null,
    h('label', { class: 'hf-l' }, 'Statement'), st, h('label', { class: 'hf-l' }, 'What it answers'), an, h('label', { class: 'hf-l' }, 'What is wrong (optional)'), why,
    hy.criterion && hy.criterion.frozen ? h('p', { class: 'muted small' }, 'Its test was frozen in ', mono(hy.criterion.frozen.file), '. Changing the hypothesis is recorded as a deviation; the frozen test stays as it is.') : null,
    h('p', { class: 'muted small' }, 'Your edit applies now. Your LLM is then asked what else must change; you review that before it applies.')),
  [{ label: 'Cancel' }, { label: 'Save', primary: true, fn: () => hfAct('fix', { target: hy.id, text: st.value, note: why.value || null, fields: { answers: an.value } }) }], { width: 600 });
}
function hfFixProblem(p) {
  const tas = HF_PF.map(([k, l]) => { const t = h('textarea', { class: 'hf-ta', rows: 2, 'aria-label': l }); t.value = ((p || {})[k] || {}).text || ''; return [k, l, t]; });
  const why = h('textarea', { class: 'hf-ta', rows: 2, 'aria-label': 'What is wrong', placeholder: 'Or say in plain words what is wrong.' });
  modal('Fix the problem', h('div', null, tas.map(([k, l, t]) => [h('label', { class: 'hf-l' }, l), t]), h('label', { class: 'hf-l' }, 'What is wrong (optional)'), why,
    h('p', { class: 'muted small' }, 'Every hypothesis under it is marked stale, and your LLM proposes what else must change.')),
  [{ label: 'Cancel' }, { label: 'Save', primary: true, fn: () => { const f = {}; tas.forEach(([k, l, t]) => { if (t.value !== (((p || {})[k] || {}).text || '')) f[k] = t.value; }); hfAct('fix', { target: 'problem', fields: f, note: why.value || null }); } }], { width: 620 });
}
async function hfJobText(id) { const j = await apiGet('/api/hypothesis/job?id=' + encodeURIComponent(id)); return j.markdown; }
function hfPaste(j) {
  hfAsk('Paste your LLM’s answer', 'The JSON your LLM returned for ' + j.id + ' (' + (HF_JOB[j.type] || j.type) + '). Lemmata checks every quote and rule against the files and drops what fails.', '', async v => {
    let res; try { res = JSON.parse(v); } catch (e) { toast('That is not valid JSON.'); return; }
    const r = await hfPost('/api/hypothesis/submit', { job: j.id, result: res }, 'Checked and stored for your review.');
    if (r && r.submit_report && r.submit_report.length) modal('What Lemmata dropped or flagged', h('ul', { class: 'hf-rep' }, r.submit_report.map(x => h('li', null, h('b', null, x.level), ' · ' + x.where + ': ' + x.why))), [{ label: 'Close', primary: true }]);
  }, { rows: 10, ok: 'Check and store' });
}
function hfJobs(D) {
  if (!D.jobs.length || READONLY) return null;
  return h('section', { class: 'hf-sec hf-jobs' }, h('div', { class: 'hf-sh' }, h('span', { class: 'tag' }, 'Waiting for your LLM'), h('span', { class: 'muted small' }, 'Lemmata never calls a model. In Claude Code, say: “do Lemmata’s jobs for this project” (tools hypothesis_job and submit_hypothesis_job). Or copy a job into any LLM and paste its answer back.')),
    D.jobs.map(j => h('div', { class: 'hf-row' }, h('span', { class: 'hf-tag' }, '[' + j.id + ']'), h('span', { class: 'grow' }, h('b', null, HF_JOB[j.type] || j.type), h('span', { class: 'muted small' }, ' · ' + j.trigger + (j.target ? ' · ' + j.target : ''))),
      h('button', { class: 'linkbtn small', onclick: async () => { try { copyText(await hfJobText(j.id)); } catch (e) { toast(e.message); } } }, 'Copy job'),
      h('a', { class: 'linkbtn small', href: apiUrl('/api/hypothesis/job.md?id=' + encodeURIComponent(j.id)), download: '' }, '.md'),
      h('button', { class: 'linkbtn small', onclick: () => hfPaste(j) }, 'Paste answer'))));
}
function hfChangeSets(D) {
  if (!D.change_sets.length) return null;
  return D.change_sets.map(cs => {
    const picks = cs.operations.map(() => h('input', { type: 'checkbox', checked: '' }));
    const val = v => v == null ? '–' : Array.isArray(v) ? v.join(', ') || '–' : typeof v === 'object' ? (v.id ? v.id + ': ' : '') + (v.statement || '') : String(v);
    return h('section', { class: 'hf-sec hf-cs' }, h('div', { class: 'hf-sh' }, h('span', { class: 'tag' }, 'Proposed change'), h('span', { class: 'muted small' }, (HF_JOB[cs.trigger.kind] || cs.trigger.kind) + ' · by ' + cs.by)),
      cs.understood ? h('p', { class: 'hf-und serif' }, 'Understood: ', cs.understood) : null,
      h('div', { class: 'hf-ops' }, cs.operations.map((o, i) => h('label', { class: 'hf-op' }, READONLY ? null : picks[i],
        h('span', { class: 'hf-op-w' }, h('span', null, h('b', null, o.op + ' ' + (o.target || (o.targets || []).join(' + ') || (o.after && o.after.id) || '')), o.field ? h('span', { class: 'muted' }, ' · ' + o.field) : null,
          (cs.not_in_protocol || []).includes(i) ? h('span', { class: 'tag hf-nip', title: 'The protocol does not say this; accepting it gives you a proposal file for your notes' }, 'not in protocol') : null),
          o.op === 'revise' || o.op === 'relink' ? h('span', { class: 'hf-ba' }, h('span', { class: 'hf-before' }, val(o.before)), ' → ', h('span', { class: 'hf-after' }, val(o.after))) : o.after ? h('span', { class: 'hf-ba' }, h('span', { class: 'hf-after' }, val(o.after))) : null,
          o.reason ? h('span', { class: 'muted small' }, o.reason) : null, o.from ? h('span', { class: 'muted small' }, 'from your words: “' + o.from.quote + '”') : null)))),
      (cs.report || []).length ? h('p', { class: 'muted small' }, plural(cs.report.length, 'item') + ' dropped or flagged by the checker.') : null,
      READONLY ? null : h('div', { class: 'row' }, h('button', { class: 'btn primary', onclick: () => { const w = picks.map((p, i) => p.checked ? i : -1).filter(i => i >= 0); if (!w.length) { toast('Tick at least one change.'); return; } hfPost('/api/hypothesis/change', { id: cs.id, decision: 'accept', which: w }).then(r => { if (r && /proposal/.test(r.message || '')) toast(r.message, { label: 'Download the proposal', fn: () => { const a = h('a', { href: apiUrl('/api/hypothesis/proposal.md?id=' + encodeURIComponent(cs.id)), download: '' }); document.body.append(a); a.click(); a.remove(); } }); }); } }, 'Accept'),
        h('button', { class: 'btn', onclick: () => hfPost('/api/hypothesis/change', { id: cs.id, decision: 'reject' }) }, 'Reject')));
  });
}
function hfProblem(D) {
  const P = D.problem, p = P.confirmed || P.proposed;
  const sec = h('section', { class: 'hf-sec hf-prob' + (P.confirmed ? ' ok' : '') },
    h('div', { class: 'hf-sh' }, h('span', { class: 'tag' }, 'Problem'), h('span', { class: 'hf-tag' }, P.confirmed ? '[confirmed]' : P.validity === 'not_valid' ? '[not valid]' : p ? '[confirm]' : '[waiting for your LLM]'), h('span', { class: 'grow' }),
      p && !READONLY ? [!P.confirmed ? h('button', { class: 'btn primary small', onclick: () => hfAct('confirm', { target: 'problem' }) }, 'Confirm') : null,
        h('button', { class: 'linkbtn small', onclick: () => hfFixProblem(p) }, 'Fix'),
        !P.confirmed ? h('button', { class: 'linkbtn small', onclick: () => hfAsk('Not the problem you are solving?', 'Say what is wrong. Your LLM tries again from the sources and your words.', '', v => hfAct('not_valid', { target: 'problem', note: v }), { ok: 'Send' }) }, 'Not valid') : null,
        h('button', { class: 'linkbtn small', onclick: () => hfAsk('Delete the problem statement', 'A project needs a root. Say in your words what the problem is; your LLM states it again from that.', '', v => hfAct('delete', { target: 'problem', text: v }), { ok: 'Delete and replace' }) }, 'Delete')] : null));
  if (!p) return sec.append(h('p', { class: 'muted' }, 'Your LLM states what problem the research is trying to solve, from the protocol, the report and the notes. You then say whether that is right.')), sec;
  if (!P.confirmed) sec.append(h('p', { class: 'hf-q' }, 'Is this the problem you are solving?'));
  sec.append(h('dl', { class: 'hf-dl' }, HF_PF.map(([k, l]) => { const f = p[k] || {}; return [h('dt', null, l), h('dd', null, f.text ? h('span', { class: 'serif' }, f.text) : h('span', { class: 'muted' }, f.note || 'not stated'),
    (f.evidence || []).map(ev => [' ', rxWhere(ev, 'code')]), f.edited ? h('span', { class: 'muted small' }, ' (edited)') : null)]; })));
  return sec;
}
function hfResult(hy) {
  const r = hy.result; if (!r || !r.values) return null;
  const v = Object.entries(r.values).map(([k, x]) => h('span', { class: 'hf-v' }, h('span', { class: 'muted' }, k + ' '), mono(typeof x === 'number' ? (Math.abs(x) < 1e-3 && x !== 0 ? x.toExponential(1) : String(+x.toFixed(4))) : String(x))));
  return h('span', { class: 'hf-vals' }, v);
}
function hfHyp(hy, D) {
  const open = RX.hfOpen === hy.id, sel = (RX.hfSel || []).includes(hy.id);
  const row = h('div', { class: 'hf-h' + (open ? ' open' : '') + ' t-' + hy.tier + rxSt(hy.stage) },
    h('div', { class: 'hf-hr' },
      READONLY ? null : h('input', { type: 'checkbox', checked: sel ? '' : null, title: 'Select to combine', 'aria-label': 'Select ' + hy.id + ' to combine', onchange: ev => { const s = new Set(RX.hfSel || []); ev.target.checked ? s.add(hy.id) : s.delete(hy.id); RX.hfSel = [...s]; renderPage(true); } }),
      h('button', { class: 'hf-id', 'aria-expanded': String(open), onclick: () => { RX.hfOpen = open ? null : hy.id; renderPage(true); } }, hy.id),
      rxStageChip(Object.assign({}, hy, { stage_by: hy.stage_rule === 'R0' ? 'you' : 'rule' })),
      h('span', { class: 'hf-st serif grow' }, hy.statement, hy.stance === 'tested' ? h('span', { class: 'muted small' }, ' — ' + ((hy.source || {}).cite || 'someone else’s claim')) : null),
      hfResult(hy),
      hy.tested_by.length ? h('span', { class: 'muted small' }, 'by ' + hy.tested_by.join(', ')) : null,
      hy.deviations.after ? h('span', { class: 'hf-dev', title: plural(hy.deviations.after, 'deviation') + ' after its data: ' + hy.deviations.ids.join(', ') }, plural(hy.deviations.after, 'deviation')) : null,
      hy.validity === 'unreviewed' ? h('span', { class: 'hf-tag', title: 'Not confirmed by you yet' }, '[confirm]') : null,
      hy.stale ? h('span', { class: 'hf-tag', title: hy.stale }, '[stale]') : null),
    open ? hfDetail(hy, D) : null);
  return row;
}
function hfDetail(hy, D) {
  const c = hy.criterion || {}, devs = D.deviations.filter(x => hy.deviations.ids.includes(x.id));
  return h('div', { class: 'hf-d' },
    h('dl', { class: 'hf-dl' },
      hy.answers ? [h('dt', null, 'Answers'), h('dd', null, hy.answers)] : null,
      h('dt', null, 'Tier'), h('dd', null, HF_TIER[hy.tier][0], h('span', { class: 'muted small' }, ' · ' + HF_TIER[hy.tier][1]), hy.tier_was ? h('span', { class: 'muted small' }, ' (was ' + hy.tier_was + ')') : null),
      h('dt', null, 'Test'), h('dd', null, c.text || h('span', { class: 'muted' }, 'none stated'), c.frozen ? h('span', { class: 'muted small' }, ' · frozen in ', mono(c.frozen.file), hy.frozen_at ? ' (' + hy.frozen_at.day + ', ' + hy.frozen_at.sha + ')' : '') : null),
      h('dt', null, 'Rule'), h('dd', null, c.rule ? [mono(c.rule.file), ' row ', mono(JSON.stringify(c.rule.select)), ': ', c.rule.conditions.map(k => k.column + ' ' + k.op + ' ' + k.value).join(' and ')] : h('span', { class: 'muted' }, 'no rule yet: the stage stays where it is'),
        (hy.sub_rules || []).length ? h('span', { class: 'muted small' }, ' + ' + plural(hy.sub_rules.length, 'sub-condition') + ' from the merged hypotheses') : null),
      h('dt', null, 'Stage'), h('dd', null, RX_STAGE[hy.stage][1], h('span', { class: 'muted small' }, ' · rule ' + hy.stage_rule + ' (' + HF_RULE[hy.stage_rule] + '): ' + hy.stage_why)),
      hy.evidence.length ? [h('dt', null, 'Source'), h('dd', null, hy.evidence.map(ev => [rxWhere(ev, 'code'), ' ']))] : null,
      hy.aliases.length ? [h('dt', null, 'Merged from'), h('dd', null, hy.aliases.join(', '))] : null,
      (hy.prediction || []).length ? [h('dt', null, 'Your prediction'), h('dd', null, hy.prediction.map(p => p.outcome.replace('_', ' ') + ' (' + p.at.slice(0, 10) + ')').join(' → '))] : null,
      devs.length ? [h('dt', null, 'Deviations'), h('dd', null, devs.map(x => h('div', { class: 'small' }, h('b', null, x.id), ' ' + (x.date || ''), ' · ' + x.title + ' · ', x.timing[hy.id] === 'after_data' ? h('b', null, 'after data') : x.timing[hy.id] === 'before_data' ? 'before data' : 'date unknown', x.path ? [' ', rxWhere({ path: x.path, line: x.line }, 'code')] : null)))] : null),
    hfEvidence(hy),
    READONLY ? null : h('div', { class: 'row hf-acts' },
      hy.validity !== 'valid' ? h('button', { class: 'btn primary small', onclick: () => hfAct('confirm', { target: hy.id }) }, 'Confirm') : null,
      h('button', { class: 'btn small', onclick: () => hfFix(hy) }, 'Fix'),
      h('button', { class: 'btn small', onclick: () => hfAsk('Delete ' + hy.id, 'It is archived, not erased. Restore it from the list of archived hypotheses. Why (optional)?', '', v => hfAct('delete', { target: hy.id, note: v || null }), { ok: 'Delete', rows: 2 }) }, 'Delete'),
      !hy.result || hy.result.met == null ? h('select', { class: 'hf-pred', 'aria-label': 'Your prediction', onchange: ev => { if (ev.target.value) hfAct('predict', { target: hy.id, prediction: ev.target.value }); } }, h('option', { value: '' }, 'Predict…'), h('option', { value: 'supported' }, 'Supported'), h('option', { value: 'not_supported' }, 'Not supported'), h('option', { value: 'mixed' }, 'Mixed')) : null,
      hy.stance === 'tested' ? h('button', { class: 'linkbtn small', onclick: () => hfAct('premise', { target: hy.id }) }, 'Check the source') : null,
      h('span', { class: 'grow' }),
      h('select', { class: 'hf-pred', 'aria-label': 'Set the stage yourself', onchange: ev => { if (ev.target.value) hfAct('stage', { target: hy.id, stage: ev.target.value }); } }, h('option', { value: '' }, 'Stage…'), h('option', { value: 'auto' }, 'By the rule'), RX_STAGES.map(k => h('option', { value: k }, RX_STAGE[k][1])))));
}
/* S29: under a hypothesis, the experiments the map files under it and the numbers the report quotes for it.
   Top-down: problem, hypothesis, its test, the experiments behind it, the numbers it rests on, the runs that wrote them. */
function hfEvidence(hy) {
  const E = RX.experiments, N = RX.numbers, out = [];
  const sec = E && hy.claim_id ? E.sections.find(s => (s.claim_id || s.id) === hy.claim_id) : null;
  if (sec && sec.experiments.length) out.push(h('div', { class: 'hf-ev' }, h('div', { class: 'hf-evh' }, 'Experiments', h('span', { class: 'muted small' }, ' · from the project map')),
    h('div', { class: 'rx-x-t' }, rxExpHead(E), sec.experiments.map(x => rxExpRow(x, sec)))));
  const g = N && N.groups.find(g => g.key === 'h:' + hy.id);
  if (g) out.push(h('div', { class: 'hf-ev' }, h('div', { class: 'hf-evh' }, 'Key numbers', h('span', { class: 'muted small' }, ' · ' + nbCounts(g.counts)), h('span', { class: 'grow' }),
    h('button', { class: 'linkbtn small', onclick: () => openTab('numbers') }, 'All key numbers')), nbTable(g, true)));
  return out.length ? out : null;
}
function hfBranch() {
  if (typeof PID === 'undefined' || !PID || READONLY) return null;
  if (RX.hfBranch === undefined) { RX.hfBranch = null; fetch('/api/hub/projects/' + encodeURIComponent(PID) + '/branch', { cache: 'no-store' }).then(r => r.ok ? r.json() : null).then(b => { RX.hfBranch = b; if (b && b.newer && b.newer.length) renderPage(true); }).catch(() => {}); }
  const B = RX.hfBranch; if (!B) return null;
  const sw = name => async () => { toast('Switching to ' + name + '…'); try { const r = await fetch('/api/hub/projects/' + encodeURIComponent(PID) + '/branch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ branch: name }) }); const j = await r.json(); if (!r.ok) throw new Error((j.error || {}).message || 'failed'); RX.hfBranch = undefined; await loadAll(); await rxRefresh(); toast('Now tracking ' + name + '.'); } catch (e) { toast(e.message); } };
  const pick = h('select', { class: 'hf-pred', 'aria-label': 'Track another branch', onchange: ev => { if (ev.target.value) sw(ev.target.value)(); } }, h('option', { value: '' }, 'Track another branch…'), B.branches.filter(b => b.name !== B.tracked).map(b => h('option', { value: b.name }, b.name + (b.date ? ' · ' + b.date.slice(0, 10) : ''))));
  return h('div', { class: 'hf-branch' + (B.newer.length ? ' warn' : '') }, h('span', null, 'Tracking ', mono(B.tracked)), B.newer.length ? h('span', null, ' · ', mono(B.newer[0].name), ' has newer commits (' + B.newer[0].date.slice(0, 10) + ')', ' ', h('button', { class: 'linkbtn small', onclick: sw(B.newer[0].name) }, 'Track it')) : null, h('span', { class: 'grow' }), pick);
}
function rxHypoFirst() {
  const D = RX.hf, out = h('div', { class: 'hf' });
  out.append(hfBranch() || h('span'));
  if (!READONLY) {
    const ta = h('textarea', { class: 'hf-ta hf-tell', rows: 2, 'aria-label': 'Tell Lemmata', placeholder: 'Tell Lemmata: a hypothesis, a correction, what your advisor said… Your LLM works out what it changes; you accept it.' });
    out.append(h('div', { class: 'hf-tellbox' }, ta, h('button', { class: 'btn', onclick: () => { if (ta.value.trim()) hfAct('tell', { text: ta.value }); } }, 'Tell')));
  }
  out.append(hfJobs(D) || h('span'));
  (hfChangeSets(D) || []).forEach(x => out.append(x));
  out.append(hfProblem(D));
  const live = D.hypotheses.filter(x => !x.archived), gone = D.hypotheses.filter(x => x.archived);
  const C = D.counts.stages;
  const head = h('div', { class: 'hf-sh' }, h('span', { class: 'tag' }, 'Hypotheses'), h('span', { class: 'muted small' }, RX_STAGES.filter(k => C[k]).map(k => C[k] + ' ' + RX_STAGE[k][1].toLowerCase()).join(' · ') || 'none yet'), h('span', { class: 'grow' }),
    (RX.hfSel || []).length >= 2 && !READONLY ? h('button', { class: 'btn small', onclick: () => hfAsk('Combine ' + RX.hfSel.join(' + '), 'How do they relate (optional)? Your LLM drafts one hypothesis that keeps each original test as a sub-condition.', '', v => { const t = RX.hfSel; RX.hfSel = []; hfAct('combine', { targets: t, note: v || null }); }, { ok: 'Ask my LLM', rows: 2 }) }, 'Combine ' + RX.hfSel.length) : null,
    live.some(x => x.validity === 'unreviewed') && !READONLY ? h('button', { class: 'linkbtn small', onclick: async () => { for (const x of live.filter(x => x.validity === 'unreviewed')) { try { await apiPost('/api/hypothesis', { action: 'confirm', target: x.id }); } catch (e) { toast(e.message); } } await rxRefresh(); } }, 'Confirm all') : null);
  const hs = h('section', { class: 'hf-sec' }, head);
  if (!live.length) hs.append(h('p', { class: 'muted' }, D.problem.confirmed ? 'Your LLM drafts the hypotheses under the confirmed problem.' : 'Hypotheses are drafted once you confirm the problem.'));
  for (const t of ['confirmatory', 'secondary', 'exploratory']) {
    const g = live.filter(x => x.tier === t); if (!g.length) continue;
    hs.append(h('div', { class: 'hf-tier t-' + t }, h('div', { class: 'hf-th' }, HF_TIER[t][0], h('span', { class: 'muted small' }, ' · ' + HF_TIER[t][1])), g.map(x => hfHyp(x, D))));
  }
  if (gone.length) hs.append(h('details', { class: 'details' }, h('summary', null, 'Archived (' + gone.length + ')'), gone.map(x => h('div', { class: 'hf-row' }, h('b', null, x.id), h('span', { class: 'grow muted' }, ' ' + trunc(x.statement, 90) + ' · ' + (x.archived.reason === 'merged' ? 'merged into ' + x.archived.merged_into : 'deleted')),
    READONLY ? null : h('button', { class: 'linkbtn small', onclick: () => hfAct('restore', { target: x.id }) }, 'Restore')))));
  out.append(hs);
  if (D.experiments.length) out.append(h('section', { class: 'hf-sec' }, h('div', { class: 'hf-sh' }, h('span', { class: 'tag' }, 'Experiments')),
    D.experiments.map(x => h('div', { class: 'hf-row' }, h('span', { class: 'hf-tag' }, '[' + x.status + ']'), h('b', null, x.id), h('span', { class: 'grow' }, ' ' + x.title), h('span', { class: 'muted small' }, x.tests_claims.length ? 'tests ' + x.tests_claims.join(', ') : 'no hypothesis'), x.deliverables[0] ? rxWhere({ path: x.deliverables[0] }, 'code') : null))));
  const devA = D.deviations.filter(x => x.after_data);
  if (D.deviations.length) out.append(h('details', { class: 'details hf-sec' }, h('summary', null, 'Deviations from the frozen design (' + D.deviations.length + ', ' + devA.length + ' after data)'),
    D.deviations.map(x => h('div', { class: 'hf-row small' }, h('b', null, x.id), h('span', { class: 'muted' }, ' ' + (x.date || '–')), h('span', { class: 'grow' }, ' ' + x.title), x.affects.length ? h('span', { class: 'muted' }, x.affects.join(', ')) : null, x.after_data ? h('span', { class: 'hf-dev' }, 'after data') : null))));
  if (D.questions.length) out.append(h('details', { class: 'details hf-sec' }, h('summary', null, 'Open questions (' + D.questions.length + ')'), D.questions.map(q => h('div', { class: 'hf-row small' }, q.text))));
  return out;
}

/* ---------- Key numbers (S29) ----------
   The numbers a study rests on, by claim: what the report says, what the committed file holds (read again at every scan),
   the commit that last wrote the file and the runs behind it. What cannot be traced is listed as an open gap. Rules only. */
const NB_ST = { ok: ['✓', 'fine', 'Agrees with the report'], mismatch: ['✕', 'fix', 'The report and the file disagree'], missing: ['?', 'look', 'Cannot be read from the file'],
  gap: ['◌', 'look', 'A known gap: no committed file holds it yet'], unquoted: ['·', 'ign', 'Read from the file; nothing to compare it with'] };
const NB_GAP = { mismatch: 'differs', missing: 'missing', gap: 'no file', uncommitted: 'not committed', stale: 'older than code', no_run: 'no run logged', run_code: 'code not in GitHub', start_commit: 'start commit unknown' };
const NB_PROMPT = name => 'Use Lemmata to list the key numbers of the project "' + name + '": call key_numbers with brief=true, read the report and the result files, then propose_numbers. For a number the report quotes that no committed file stores, say so with "gap". Fix whatever the checker drops and propose again.';
function nbCounts(c) { return ['ok', 'mismatch', 'missing', 'gap', 'unquoted'].filter(k => c[k]).map(k => c[k] + ' ' + (k === 'ok' ? 'agree' : k === 'unquoted' ? 'not compared' : k === 'gap' ? (c[k] === 1 ? 'gap' : 'gaps') : k)).join(' · ') || 'none'; }
function nbRead(n) {
  const r = n.read; if (!r) return 'no file stores it';
  const cond = c => c.or ? '(' + c.or.map(cond).join(' or ') + ')' : c.column + ' ' + (c.op === '==' ? '=' : c.op) + (c.value == null ? '' : ' ' + (Array.isArray(c.value) ? c.value.join(' | ') : c.value));
  const wh = (r.where || []).map(cond).join(' and '), am = (r.among || []).map(cond).join(' and ');
  if (r.key || r.keys) return (r.agg === 'value' ? '' : r.agg + ' of ') + (r.key || r.keys.join(', '));
  return (r.agg === 'value' ? r.column : r.agg + (r.column ? ' of ' + r.column : '')) + (wh ? ' where ' + wh : '') + (am ? ' among ' + am : '');
}
function nbTable(g, compact) {
  const act = async body => { const r = await rxPost('/api/numbers', body); if (r) { RX.numbers = r; RX.review = await apiGet('/api/review?days=' + (RX.rvDays || 30)).catch(() => RX.review); RX.todo = await apiGet('/api/todo').catch(() => RX.todo); renderAll(); } };
  return h('div', { class: 'su-tw' }, h('table', { class: 'tbl nb-t' }, h('thead', null, h('tr', null, ['', 'Number', 'Report', 'File', 'Stored in', compact ? null : 'Written by', ''].filter(t => t !== null).map(t => h('th', null, t)))),
    h('tbody', null, g.numbers.map(n => { const st = NB_ST[n.status], q = n.quoted;
      return h('tr', { class: 'nb-r s-' + n.status + (n.state === 'proposed' ? ' prop' : '') + (RX.nbSel === n.id ? ' hl' : ''), id: 'nb-' + n.id.replace(/[^\w]/g, '_') },
        h('td', null, h('span', { class: 'sg ' + st[1], title: st[2] }, st[0])),
        h('td', null, h('span', { class: 'nb-l' }, n.label), n.state === 'proposed' ? h('span', { class: 'hf-tag', title: 'Proposed, not confirmed by you yet' }, ' [confirm]') : n.state === 'test' ? h('span', { class: 'tag', title: 'Read from the row of the test table that decides this hypothesis' }, ' test') : null,
          n.why || n.gap ? h('div', { class: 'muted small nb-w' }, n.status === 'gap' && n.gap ? n.gap : n.why || '') : null),
        h('td', { class: 'mono' }, q ? [q.text, q.path ? [' ', rxWhere({ path: q.path, line: q.line }, 'code')] : null] : h('span', { class: 'muted' }, '—')),
        h('td', { class: 'mono' + (n.status === 'mismatch' ? ' bad' : '') }, n.found == null ? h('span', { class: 'muted' }, '—') : n.found),
        h('td', { class: 'small' }, n.file ? [h('span', { class: 'mono' }, n.file), h('div', { class: 'muted small', title: nbRead(n) }, trunc(nbRead(n), 70)),
          n.commit ? h('div', { class: 'muted small', title: n.commit.subject }, 'commit ' + n.commit.short + ' · ' + dmon(n.commit.time)) : n.found != null ? h('div', { class: 'rx-tl warn' }, 'in no commit') : null] : h('span', { class: 'muted' }, 'no file')),
        compact ? null : h('td', { class: 'small' }, n.runs.length ? n.runs.map(r => h('div', { class: 'mono small', title: r.state }, r.run_id + (r.sha ? ' @' + r.sha : ''))) : n.scripts.length ? h('span', { class: 'muted' }, n.scripts.join(', ') + ' (by name, no logged run)') : n.found != null ? h('span', { class: 'muted' }, 'no logged run') : ''),
        h('td', null, READONLY || n.state === 'test' ? null : h('button', { class: 'linkbtn small', title: 'Remove this number from the list', onclick: () => act({ action: 'remove', number: n.id }) }, '✕'))); }))));
}
function nbSummary(N) {      // one strip, on Review: where the study's numbers stand
  const c = N.counts;
  return h('section', { class: 'rx-x-sec nb-sum' }, h('div', { class: 'rx-x-h' }, h('span', { class: 'rx-x-q static' }, 'Key numbers'),
    h('span', { class: 'rx-x-qt' }, c.total ? nbCounts(c) : 'None listed yet.'), c.gaps ? h('span', { class: 'muted small' }, plural(c.gaps, 'open provenance gap')) : null, h('span', { class: 'grow' }),
    c.proposed ? h('span', { class: 'hf-tag' }, '[' + c.proposed + ' to confirm]') : null, h('button', { class: 'linkbtn', onclick: () => openTab('numbers') }, 'Open')));
}
function pageNumbers() {
  const nr = rxNotReady('Key numbers'); if (nr) return nr;
  S.outline = [];
  const N = RX.numbers, name = S.project ? S.project.name : 'this project';
  const root = doc(h('h1', { class: 'ptitle' }, 'Key numbers'));
  root.classList.add('wide');
  if (!N) return root.append(h('p', { class: 'muted' }, 'This hub has no Key numbers page yet. It appears after the hub updates.')), root;
  const act = async (body, msg) => { const r = await rxPost('/api/numbers', body, msg); if (r) { RX.numbers = r; RX.review = await apiGet('/api/review?days=' + (RX.rvDays || 30)).catch(() => RX.review); RX.todo = await apiGet('/api/todo').catch(() => RX.todo); renderAll(); } };
  const c = N.counts;
  root.append(h('p', { class: 'lede muted' }, 'The numbers the study rests on, each read again from its committed file and compared with what the report says.'), rxBehindNote());
  root.append(h('div', { class: 'rx-x-sum' }, h('span', null, h('b', null, c.total), ' numbers'), h('span', null, h('b', null, c.ok), ' agree'), c.mismatch ? h('span', { class: 'bad' }, h('b', null, c.mismatch), ' differ') : null,
    c.missing ? h('span', { class: 'warn' }, h('b', null, c.missing), ' missing') : null, c.gap ? h('span', { class: 'warn' }, h('b', null, c.gap), c.gap === 1 ? ' known gap' : ' known gaps') : null,
    c.unquoted ? h('span', null, h('b', null, c.unquoted), ' not compared') : null, h('span', null, h('b', null, c.runs), ' logged runs behind them')));
  if (c.proposed) root.append(h('div', { class: 'flag nb-prop' }, h('b', null, plural(c.proposed, 'number') + ' proposed'), ' by ' + (N.proposed_by || 'agent') + (N.replaces.length ? ' (' + N.replaces.length + ' replace a confirmed one)' : '') + '. Nothing counts until you confirm. ',
    READONLY ? null : [h('button', { class: 'btn sm primary', onclick: () => act({ action: 'confirm' }, 'Confirmed.') }, 'Confirm'), ' ', h('button', { class: 'btn sm', onclick: () => act({ action: 'discard' }, 'Proposal discarded.') }, 'Discard')]));
  const dropped = (N.report || []).filter(r => r.level === 'dropped'), notes = (N.report || []).filter(r => r.level !== 'dropped');
  if (dropped.length || notes.length) root.append(h('details', { class: 'details', open: dropped.length && c.proposed ? '' : null }, h('summary', null, 'What the checker said (' + dropped.length + ' dropped, ' + notes.length + ' notes)'),
    dropped.map(r => h('div', { class: 'rx-warn' }, '✕ ' + r.where + ': ' + r.why)), notes.map(r => h('div', { class: 'muted small' }, '! ' + r.where + ': ' + r.why))));
  if (!c.total) root.append(emptyState('#', 'No key number yet', 'A hypothesis with a test lists the numbers of its test here by itself. For the others, your own agent reads the report and proposes the list; Lemmata checks every entry against the files and you confirm.',
    READONLY ? [] : [h('button', { class: 'btn primary', title: NB_PROMPT(name), onclick: () => copyText(NB_PROMPT(name)) }, 'Copy prompt for Claude Code')]));
  for (const g of N.groups) {
    const open = RX.nbOpen ? RX.nbOpen === (g.key || '-') : true;
    const sec = h('section', { class: 'rx-x-sec nb-g' + (g.stage ? rxSt(g.stage) : '') }, h('div', { class: 'rx-x-h' },
      g.claim_id ? h('button', { class: 'rx-x-q', title: 'Open in Thesis', onclick: () => { if (g.key.startsWith('h:')) { RX.hfOpen = g.label; openTab('experiments'); } else suGotoClaim(g.claim_id); } }, g.label) : h('span', { class: 'rx-x-q static' }, g.label),
      g.stage ? rxStageChip({ stage: g.stage, stage_by: 'rule', stage_why: g.stage_why || '' }) : null, h('span', { class: 'rx-x-qt serif' + (g.key ? '' : ' muted') }, rxMath(trunc(g.text, 150))), h('span', { class: 'grow' }),
      h('span', { class: 'muted small' }, nbCounts(g.counts))));
    if (g.numbers.length) sec.append(nbTable(g));
    if (g.runs.length) sec.append(h('details', { class: 'details nb-runs' }, h('summary', null, plural(g.runs.length, 'logged run') + ' behind these files'),
      g.runs.map(r => h('div', { class: 'hf-row small' }, h('span', { class: 'hf-tag' }, '[' + r.state + ']'), h('b', { class: 'mono' }, r.run_id), h('span', { class: 'mono muted' }, r.sha ? '@' + r.sha : 'no commit'),
        r.sha_basis === 'results_commit' ? h('span', { class: 'tag warn', title: 'The commit the run started from was not recorded; this is the commit that first held its results.' }, 'first results commit') : null,
        h('span', { class: 'grow mono small', title: r.command }, trunc(r.command || '', 80)), r.note ? h('span', { class: 'muted small' }, trunc(r.note, 60)) : null, h('span', { class: 'muted small' }, r.time ? dmon(r.time) : '')))));
    root.append(sec);
  }
  if (N.gaps.length) root.append(h('section', { class: 'rx-x-sec nb-gaps' }, h('div', { class: 'rx-x-h' }, h('span', { class: 'rx-x-q static' }, 'Open provenance gaps'), h('span', { class: 'rx-x-qt muted' }, 'What cannot be traced yet. Each goes away when a committed file or a logged run closes it.'), h('span', { class: 'grow' }), h('span', { class: 'muted small' }, N.gaps.length)),
    N.gaps.map(x => h('div', { class: 'hf-row small' }, h('span', { class: 'hf-tag' }, '[' + (NB_GAP[x.k] || x.k) + ']'), h('span', { class: 'grow' }, x.t)))));
  if (c.total && !READONLY) root.append(h('div', { class: 'rx-map-ask' }, h('button', { class: 'btn sm', title: NB_PROMPT(name), onclick: () => copyText(NB_PROMPT(name)) }, 'Copy prompt for Claude Code'), h('span', { class: 'muted small' }, ' to add or redo the list')));
  if (RX.nbSel) setTimeout(() => { const el = document.getElementById('nb-' + RX.nbSel.replace(/[^\w]/g, '_')); if (el) el.scrollIntoView({ block: 'center' }); RX.nbSel = null; }, 0);
  return root;
}
/* ---------- Baselines (S30): one row per compared method, with where to check it ----------
   Founder (chat 2026-11-19 17:59 KST): a separate page to organise the baselines in a table, with the paper's PDF, the GitHub code,
   the intuition and the published performance, to track them against our own method. */
const BL_PROMPT = (name, one) => 'Use Lemmata for the project "' + name + '": call baselines with brief=true, then fill in ' + (one ? 'the card of ' + one : 'every baseline that is missing something') +
  '. Read the paper that introduced each baseline and its repository yourself. Give the paper\'s title, authors, year, venue, link and PDF link; the code link; the idea in one or two sentences of your own; where it falls short; and the numbers the paper reports on this project\'s datasets, with the table they are printed in. Leave out what you cannot find. Then call propose_baselines.';
const BL_PART = { paper: 'paper', pdf: 'PDF', code: 'code', intuition: 'idea', published: 'published numbers' };
const BL_FIELD = { 'paper.title': 'Title', 'paper.authors': 'Authors', 'paper.year': 'Year', 'paper.venue': 'Venue', 'paper.url': 'Paper link', 'paper.pdf': 'PDF link', code: 'Code', intuition: 'Idea', limit: 'Falls short', differs: 'Ours differs', notes: 'Notes', published: 'Published numbers' };
const BL_ROLE = { base: 'the method being extended', baseline: 'baseline', compared: 'compared method' };
function blExt(href, label) { return h('a', { class: 'ghl bl-ext', href, target: '_blank', rel: 'noopener noreferrer', title: href, onclick: ev => ev.stopPropagation() }, label + ' ↗'); }
function blPaperLine(p) { return [p.authors ? trunc(p.authors, 60) : null, p.venue, p.year].filter(Boolean).join(' · '); }
function blNumbers(r, B) {      // published numbers beside what the project measured; then what was measured with nothing published beside it
  const bench = B.study === 'benchmark';
  const seen = new Set(r.compare.filter(x => x.mine != null).map(x => x.x + '|' + x.dataset.toLowerCase() + '|' + x.metric.toLowerCase()));
  const rest = r.mine.filter(m => !seen.has(m.x + '|' + (m.dataset || '').toLowerCase() + '|' + m.metric.toLowerCase()));
  if (!r.compare.length && !rest.length) return h('p', { class: 'muted small' }, 'No published number yet, and none measured in this project.');
  const dir = x => x.lower == null ? '' : x.lower ? ' ↓' : ' ↑';
  return h('div', { class: 'su-tw' }, h('table', { class: 'nb-t bl-n' }, h('thead', null, h('tr', null, h('th', null, 'Dataset'), h('th', null, 'Measure'), h('th', { class: 'num' }, 'Published'), h('th', null, 'Printed in'),
    h('th', { class: 'num' }, 'Measured here'), bench ? null : h('th', { class: 'num' }, B.ours || 'Ours'), h('th', { class: 'num', title: 'Measured here minus published. Lemmata gives no verdict on it.' }, 'Difference'))),
    h('tbody', null, r.compare.map(x => h('tr', null, h('td', null, x.dataset), h('td', null, x.metric + dir(x)),
      h('td', { class: 'num mono' }, x.text || rxFmt(x.published), x.scaled ? h('div', { class: 'muted small', title: 'The paper and your result file use different scales.' }, 'read as ' + rxFmt(x.published_scaled)) : null),
      h('td', { class: 'small' }, x.url ? blExt(x.url, x.where || 'source') : (x.where || h('span', { class: 'muted' }, '—')), x.note ? h('div', { class: 'muted small' }, x.note) : null),
      h('td', { class: 'num mono' }, x.mine == null ? h('span', { class: 'muted', title: 'This project has no result for this method on this dataset and measure.' }, 'not run') : h('button', { class: 'linkbtn mono', title: 'Open the experiment', onclick: () => rxOpenExp(x.x) }, rxFmt(x.mine))),
      bench ? null : h('td', { class: 'num mono' }, x.ours == null ? '—' : rxFmt(x.ours)),
      h('td', { class: 'num mono' }, x.diff == null ? '—' : (x.diff > 0 ? '+' : '') + rxFmt(x.diff)))),
    rest.map(m => h('tr', { class: 'bl-rest' }, h('td', null, m.dataset || m.column), h('td', null, m.metric + dir(m)), h('td', { class: 'num muted' }, '—'), h('td', { class: 'small muted' }, 'no published number'),
      h('td', { class: 'num mono' }, h('button', { class: 'linkbtn mono', title: 'Open the experiment', onclick: () => rxOpenExp(m.x) }, rxFmt(m.value))),
      bench ? null : h('td', { class: 'num mono' }, m.ours == null ? '—' : rxFmt(m.ours)), h('td', { class: 'num muted' }, '—'))))));
}
function blForm(r, B, act) {
  const e = r.entry, p = e.paper || {}, f = {}, bench = B.study === 'benchmark';
  const inp = (key, val, ph) => { const i = h('input', { type: 'text', value: val == null ? '' : String(val), placeholder: ph || '', 'aria-label': BL_FIELD[key] || key, class: 'bl-in' }); f[key] = i; return [h('label', null, BL_FIELD[key]), i]; };
  const ta = (key, val, ph) => { const t = h('textarea', { rows: '2', class: 'rx-ta', placeholder: ph, 'aria-label': BL_FIELD[key] }); t.value = val || ''; f[key] = t; return [h('label', null, BL_FIELD[key]), t]; };
  const body = h('tbody');
  const cell = (val, ph, list) => h('input', { type: 'text', value: val == null ? '' : String(val), placeholder: ph, 'aria-label': ph, list: list || null });
  const pubRow = q => { const c = [cell(q.dataset, 'Dataset', 'bl-ds'), cell(q.metric, 'Measure', 'bl-mt'), cell(q.text != null ? q.text : q.value, 'Number'), cell(q.where, 'Table 2'), cell(q.url, 'https://… (if not this paper)'), cell(q.note, 'Protocol note')];
    const tr = h('tr', null, c.map(i => h('td', null, i)), h('td', null, h('button', { class: 'linkbtn small', title: 'Remove this number', onclick: () => tr.remove() }, '✕')));
    tr._get = () => ({ dataset: c[0].value.trim(), metric: c[1].value.trim(), value: c[2].value.trim(), where: c[3].value.trim() || null, url: c[4].value.trim() || null, note: c[5].value.trim() || null });
    body.append(tr); };
  (e.published || []).forEach(pubRow);
  const save = async () => {
    const pubs = [...body.children].map(tr => tr._get()).filter(q => q.dataset || q.metric || q.value);
    const fields = { paper: { title: f['paper.title'].value, authors: f['paper.authors'].value, year: f['paper.year'].value, venue: f['paper.venue'].value, url: f['paper.url'].value, pdf: f['paper.pdf'].value },
      code: f.code.value, intuition: f.intuition.value, limit: f.limit.value, notes: f.notes.value, published: pubs };
    if (f.differs) fields.differs = f.differs.value;
    const d = await act({ action: 'save', name: r.name, fields }, 'Saved.');
    if (d) { RX.blEdit = null; (d.notes || []).forEach(n => toast(n.why)); renderPage(true); }
  };
  return h('div', { class: 'bl-edit' }, h('div', { class: 'bl-form' },
    inp('paper.title', p.title, 'The paper that introduced it'), inp('paper.authors', p.authors, 'Family names'), inp('paper.year', p.year, '2021'), inp('paper.venue', p.venue, 'ICLR'),
    inp('paper.url', p.url, 'https://… the paper\'s page'), inp('paper.pdf', p.pdf_derived ? '' : p.pdf, p.pdf_derived ? p.pdf + ' (from the arXiv page)' : 'https://… .pdf'), inp('code', e.code, 'https://github.com/…'),
    ta('intuition', e.intuition, 'The idea in one or two sentences, in your words'), ta('limit', e.limit, 'Where it falls short'),
    bench ? null : ta('differs', e.differs, 'How ' + (B.ours || 'your method') + ' differs from it'), ta('notes', e.notes, 'Anything to remember when you run or cite it')),
    h('div', { class: 'bl-ph' }, 'Published numbers'),
    h('datalist', { id: 'bl-ds' }, B.datasets.map(d => h('option', { value: d }))), h('datalist', { id: 'bl-mt' }, B.metrics.map(d => h('option', { value: d }))),
    h('div', { class: 'su-tw' }, h('table', { class: 'nb-t bl-pub' }, h('thead', null, h('tr', null, ['Dataset', 'Measure', 'Number', 'Printed in', 'Link', 'Note', ''].map(t => h('th', null, t)))), body)),
    h('div', { class: 'bl-acts' }, h('button', { class: 'linkbtn small', onclick: () => pubRow({}) }, '+ Add a number'), h('span', { class: 'grow' }),
      h('button', { class: 'btn sm', onclick: () => { RX.blEdit = null; renderPage(true); } }, 'Cancel'), h('button', { class: 'btn sm primary', onclick: save }, 'Save')));
}
function blDetail(r, B, act, name) {
  const e = r.entry, p = e.paper || {}, bench = B.study === 'benchmark';
  const none = t => h('span', { class: 'muted' }, t || 'not filled in');
  const kids = [];
  if (r.proposal) kids.push(h('div', { class: 'flag bl-prop' }, h('b', null, 'Proposed by ' + (r.proposal.by || 'your agent') + '. '), 'Open each link before you confirm.',
    h('div', { class: 'bl-chg' }, r.changes.map(ch => h('div', { class: 'hf-row small' }, h('span', { class: 'hf-tag' }, '[' + (BL_FIELD[ch.field] || ch.field) + ']'),
      ch.field === 'published' ? h('span', { class: 'grow' }, ch.numbers.map(q => h('div', null, q.metric + ' on ' + q.dataset + ': ', h('b', { class: 'mono' }, q.text || q.value), q.where ? ' (' + q.where + ')' : '', q.note ? h('span', { class: 'muted' }, ' · ' + q.note) : null)))
        : h('span', { class: 'grow' }, ch.before ? [h('s', { class: 'muted' }, trunc(String(ch.before), 120)), ' → '] : null, /^https:/.test(String(ch.after)) ? blExt(ch.after, trunc(String(ch.after), 70)) : String(ch.after))))),
    READONLY ? null : h('div', { class: 'bl-acts' }, h('button', { class: 'btn sm primary', onclick: () => act({ action: 'confirm', name: r.name }, 'Confirmed.') }, 'Confirm'), h('button', { class: 'btn sm', onclick: () => act({ action: 'discard', name: r.name }, 'Discarded.') }, 'Discard'))));
  if (RX.blEdit === r.key && !READONLY) { kids.push(blForm(r, B, act)); return h('div', { class: 'bl-det' }, kids); }
  kids.push(h('dl', { class: 'bl-card' },
    h('dt', null, 'Paper'), h('dd', null, p.title ? h('b', null, p.title) : none(), blPaperLine(p) ? h('div', { class: 'muted small' }, blPaperLine(p)) : null,
      h('div', null, p.url ? blExt(p.url, 'Paper') : null, p.pdf ? blExt(p.pdf, 'PDF') : none('no PDF link'))),
    h('dt', null, 'Code'), h('dd', null, e.code ? blExt(e.code, trunc(e.code.replace(/^https:\/\//, ''), 70)) : none()),
    h('dt', null, 'Idea'), h('dd', null, e.intuition || none()),
    h('dt', null, 'Falls short'), h('dd', null, e.limit || none()),
    bench ? null : [h('dt', null, (B.ours || 'Ours') + ' differs'), h('dd', null, e.differs || none())],
    e.notes ? [h('dt', null, 'Notes'), h('dd', null, e.notes)] : null,
    h('dt', null, 'In your paper'), h('dd', { class: 'small' }, r.cited.length ? ['cited as ', r.cited.map((ci, i) => [i ? ', ' : '', h('span', { class: 'mono' }, ci.key), ci.title ? ' (' + trunc(ci.title, 60) + (ci.year ? ', ' + ci.year : '') + ')' : ''])]
      : r.named ? 'named on ' + plural(r.named, 'line') + ', not cited there' : r.in_results ? none('not named') : none('not in your result files yet'))));
  kids.push(h('div', { class: 'bl-ph' }, 'Published and measured'), blNumbers(r, B));
  kids.push(h('div', { class: 'bl-acts' },
    READONLY ? null : h('button', { class: 'btn sm primary', onclick: () => { RX.blEdit = r.key; renderPage(true); } }, r.has_entry ? 'Edit' : 'Fill in'),
    READONLY ? null : h('button', { class: 'btn sm', title: BL_PROMPT(name, r.name), onclick: () => copyText(BL_PROMPT(name, r.name)) }, 'Copy prompt for Claude Code'),
    r.item ? h('button', { class: 'linkbtn small', title: 'Where the paper and the code name it', onclick: () => { RX.suSel = 'i:' + r.item; RX.bdSel = 'i:' + r.item; openTab('setup'); } }, 'Open in Setup') : null,
    r.experiments.map(x => h('button', { class: 'linkbtn small', onclick: () => rxOpenExp(x.id) }, x.name)), h('span', { class: 'grow' }),
    e.at ? h('span', { class: 'muted small' }, 'card by ' + (e.by || 'you') + ', ' + dmon(e.at)) : null,
    r.has_entry && !READONLY ? h('button', { class: 'linkbtn small', title: r.in_results ? 'Empty this card. The baseline stays, because it is in your result files.' : 'Stop tracking this baseline', onclick: () => act({ action: 'remove', name: r.name }, r.in_results ? 'Card emptied.' : 'Removed.') }, r.in_results ? 'Empty the card' : 'Remove') : null));
  return h('div', { class: 'bl-det' }, kids);
}
function pageBaselines() {
  const nr = rxNotReady('Baselines'); if (nr) return nr;
  S.outline = [];
  const B = RX.baselines, name = S.project ? S.project.name : 'this project';
  const root = doc(h('h1', { class: 'ptitle' }, 'Baselines'));
  root.classList.add('wide');
  if (!B) return root.append(h('p', { class: 'muted' }, 'This hub has no Baselines page yet. It appears after the hub updates.')), root;
  const bench = B.study === 'benchmark', c = B.counts;
  const act = async (body, msg) => { const r = await rxPost('/api/baselines', body, msg); if (r) { RX.baselines = r; renderAll(); } return r; };
  root.append(h('p', { class: 'lede muted' }, 'Each method ' + (bench ? 'the study compares' : 'you compare with') + ': where to read it, where its code is, what its idea is, and what its paper reported beside what you measured.'), rxBehindNote());
  if (c.total) root.append(h('div', { class: 'rx-x-sum' }, h('span', null, h('b', null, c.total), c.total === 1 ? ' baseline' : ' baselines'), h('span', null, h('b', null, c.pdf), ' with a PDF'), h('span', null, h('b', null, c.code), ' with code'),
    h('span', null, h('b', null, c.intuition), ' with the idea'), h('span', null, h('b', null, c.numbers), ' published numbers'), h('span', null, h('b', null, c.reproduced), ' beside one of yours')));
  if (c.proposed) root.append(h('div', { class: 'flag nb-prop' }, h('b', null, plural(c.proposed, 'card') + ' proposed'), ' by ' + (B.proposed_by || 'agent') + '. Nothing counts until you confirm. Open a row to see what would change. ',
    READONLY ? null : [h('button', { class: 'btn sm primary', onclick: () => act({ action: 'confirm' }, 'Confirmed.') }, 'Confirm all'), ' ', h('button', { class: 'btn sm', onclick: () => act({ action: 'discard' }, 'Proposal discarded.') }, 'Discard all')]));
  const dropped = (B.report || []).filter(r => r.level === 'dropped'), notes = (B.report || []).filter(r => r.level !== 'dropped');
  if (dropped.length || notes.length) root.append(h('details', { class: 'details', open: dropped.length && c.proposed ? '' : null }, h('summary', null, 'What the checker said (' + dropped.length + ' dropped, ' + notes.length + ' notes)'),
    dropped.map(r => h('div', { class: 'rx-warn' }, '✕ ' + r.where + ': ' + r.why)), notes.map(r => h('div', { class: 'muted small' }, '! ' + r.where + ': ' + r.why))));
  if (!c.total) root.append(emptyState('≡', 'No baseline yet', B.mapped ? 'The result files name no method other than your own. Add one below to start tracking it before you run it.' : 'Lemmata lists a baseline as soon as the result files name one. Until the project map is confirmed the list can be rough. You can also add one below.', []));
  else {
    const tb = h('tbody');
    for (const r of B.rows) {
      const e = r.entry, p = e.paper || {}, on = RX.blOpen === r.key;
      const toggle = () => { RX.blOpen = on ? null : r.key; if (on) RX.blEdit = null; renderPage(true); };
      const miss = r.missing.map(m => BL_PART[m]);
      tb.append(h('tr', { class: 'bl-r' + (on ? ' on' : '') + (r.proposal ? ' prop' : ''), id: 'bl-' + r.key, onclick: toggle },
        h('td', null, h('button', { class: 'bl-name', 'aria-expanded': String(on), onclick: ev => { ev.stopPropagation(); toggle(); } }, r.name),
          h('span', { class: 'bl-sub' }, r.in_results ? (BL_ROLE[r.role] || 'baseline') : 'not in your results yet'),
          r.proposal ? h('span', { class: 'hf-tag' }, '[confirm]') : miss.length ? h('span', { class: 'hf-tag', title: 'Still missing: ' + miss.join(', ') }, miss.length === 5 ? '[empty]' : '[no ' + miss.slice(0, 2).join(', ') + (miss.length > 2 ? ', +' + (miss.length - 2) : '') + ']') : null),
        h('td', null, p.title ? h('span', { title: p.title }, trunc(p.title, 64)) : h('span', { class: 'muted' }, '—'), blPaperLine(p) ? h('span', { class: 'bl-sub' }, blPaperLine(p)) : null,
          h('div', null, p.url ? blExt(p.url, 'Paper') : null, p.pdf ? blExt(p.pdf, 'PDF') : null)),
        h('td', null, e.code ? blExt(e.code, r.code_host === 'github.com' ? 'GitHub' : r.code_host) : h('span', { class: 'muted' }, '—')),
        h('td', { class: 'bl-idea' }, e.intuition ? trunc(e.intuition, 130) : h('span', { class: 'muted' }, '—')),
        h('td', { class: 'small' }, r.compare.length ? [h('b', null, r.compare.length), ' published', h('span', { class: 'bl-sub' }, r.reproduced + ' beside one of yours')] : r.mine.length ? h('span', { class: 'muted' }, 'measured here, nothing published beside it') : h('span', { class: 'muted' }, '—'))));
      if (on) tb.append(h('tr', { class: 'bl-d' }, h('td', { colspan: '5' }, blDetail(r, B, act, name))));
    }
    root.append(h('div', { class: 'su-tw' }, h('table', { class: 'bl-t' }, h('thead', null, h('tr', null, ['Method', 'Paper', 'Code', 'Idea', 'Numbers'].map(t => h('th', null, t)))), tb)));
  }
  if (!READONLY) {
    const add = h('input', { type: 'text', placeholder: 'A method you plan to compare with', 'aria-label': 'New baseline', maxlength: '80' });
    const go = async () => { const v = add.value.trim(); if (!v) return; const d = await act({ action: 'save', name: v, fields: {} }, 'Added.'); if (d) { const r = d.rows.find(x => x.name.toLowerCase() === v.toLowerCase()); if (r) { RX.blOpen = r.key; RX.blEdit = r.key; renderPage(true); } } };
    add.addEventListener('keydown', ev => { if (ev.key === 'Enter') go(); });
    root.append(h('div', { class: 'bl-add' }, add, h('button', { class: 'btn sm', onclick: go }, 'Add')),
      c.total ? h('div', { class: 'rx-map-ask' }, h('button', { class: 'btn sm', title: BL_PROMPT(name), onclick: () => copyText(BL_PROMPT(name)) }, 'Copy prompt for Claude Code'), h('span', { class: 'muted small' }, ' to have your agent fill in what is missing; you confirm')) : null);
  }
  if (RX.blSel) setTimeout(() => { const el = document.getElementById('bl-' + RX.blSel); if (el) el.scrollIntoView({ block: 'center' }); RX.blSel = null; }, 0);
  return root;
}
/* ---------- Settings (S31) ----------
   Founder (chat 2026-11-19 23:53 KST): a Settings button at the bottom left holding the FAQ, how Lemmata works and light / dark
   mode, like the settings of the Claude app. One page of sections; nothing here is a modal. */
function pageSettings() {
  S.outline = [];
  const root = doc(h('h1', { class: 'ptitle' }, 'Settings'));
  const SECS = [['appearance', 'Appearance'], ['project', 'Project'], ['agents', 'Agents'], ['how', 'How Lemmata works'], ['faq', 'FAQ'], ['about', 'About']];
  const sec = (id, kids) => h('section', { class: 'st-sec', id: 'st-' + id }, h('h2', { class: 'st-h' }, SECS.find(x => x[0] === id)[1]), kids);
  const row = (label, hint, control) => h('div', { class: 'st-row' }, h('div', { class: 'st-l' }, h('div', null, label), hint ? h('div', { class: 'muted small' }, hint) : null), control ? h('div', { class: 'st-c' }, control) : null);
  root.append(h('nav', { class: 'st-nav', 'aria-label': 'Sections' }, SECS.map(([id, l]) => h('button', { class: 'linkbtn', onclick: () => { const el = document.getElementById('st-' + id); if (el) el.scrollIntoView({ block: 'start' }); } }, l))));
  // appearance
  const cur = themeGet();
  root.append(sec('appearance', row('Theme', EMBED ? 'In VS Code, Lemmata follows the editor\'s own theme.' : 'System follows your computer\'s light or dark setting. Kept in this browser.',
    EMBED ? null : h('div', { class: 'seg', role: 'group', 'aria-label': 'Theme' }, [['system', 'System'], ['light', 'Light'], ['dark', 'Dark']].map(([v, l]) =>
      h('button', { class: 'btn sm', id: 'th-' + v, 'aria-pressed': String(cur === v), onclick: () => { themeSet(v); renderAll(); } }, l))))));
  // project
  const hc = hubControls(), pk = [];
  if (S.project) pk.push(row(S.project.name, S.project.scanned_at ? 'Files read ' + agoText(S.project.scanned_at) : null, READONLY ? null : h('button', { class: 'btn sm', disabled: !!BUSY, onclick: () => syncNow() }, 'Sync now')));
  if (!READONLY) pk.push(row('Export report', 'A single HTML file you can share. It is a copy; it does not update.', h('a', { class: 'btn sm', href: apiUrl('/api/export'), download: '' }, 'Download')));
  hc.menu.forEach(m => pk.push(row(m.label, m.hint || null, m.fn ? h('button', { class: 'btn sm', onclick: m.fn }, /^←/.test(m.label) ? 'Open' : 'Change') : null)));
  if (pk.length) root.append(sec('project', pk));
  // agents for the researcher's own Claude Code
  if (!READONLY) root.append(h('section', { class: 'st-sec', id: 'st-agents' }, h('h2', { class: 'st-h' }, 'Agents for Claude Code'),
    row('LaTeX agent and paper agents', 'They run in your own Claude Code, on your own plan and model. Paste the prompt in Claude Code inside your research repository: it fetches the agent files from Lemmata and writes them to .claude/.', h('button', { class: 'btn sm', id: 'st-kit', title: KIT_PROMPT, onclick: () => copyText(KIT_PROMPT) }, 'Copy install prompt')),
    row('Write LaTeX', 'Ask for a table, a paragraph or a caption; your agent writes it from everything Lemmata holds.', h('button', { class: 'btn sm', onclick: () => openTab('latex') }, 'Open LaTeX'))));
  // how Lemmata works
  root.append(sec('how', [T.intro.map(([head, text], i) => h('div', { class: 'hf-row st-how' }, h('span', { class: 'hf-tag' }, '[' + (i + 1) + ']'), h('span', { class: 'grow' }, h('b', null, head), ' ', text))),
    h('div', { class: 'st-acts' }, h('button', { class: 'btn sm', onclick: () => intro(true) }, 'Show the walkthrough'))]));
  // FAQ
  const fq = h('div', { class: 'st-faq' }, h('p', { class: 'muted small' }, 'Where to look for what. Each answer has a button to the page it is about.'));
  faqBlock(fq);
  root.append(sec('faq', fq));
  // about: which build this hub runs
  const ab = [row('Lemmata', 'Reads your paper, code and results; shows what backs each claim and what changed. It runs no language model: what needs one is done by your own agent.', null)];
  if (HUB_ON && !READONLY) {
    if (RX.build === undefined) { RX.build = null; fetch('/api/hub/status', { cache: 'no-store' }).then(r => r.json()).then(d => { RX.build = d.build || {}; RX.buildV = d.version; const t = S.tabs[S.active]; if (t && t.k === 'settings') renderPage(true); }).catch(() => { RX.build = {}; }); }
    const b = RX.build;
    ab.push(row('This hub runs', !b ? 'Reading…' : b.branch ? 'New pages appear here after the hub has updated to the branch that holds them.' : 'Self-update is not set up on the hub, so it runs whatever was last installed by hand.',
      b && (b.branch || b.commit) ? h('span', { class: 'mono small', id: 'st-build' }, [b.branch, b.commit, b.updated ? dmon(b.updated) : null].filter(Boolean).join(' · ') + (b.result && b.result !== 'updated' ? ' · last update ' + b.result.replace('_', ' ') : '')) : null));
  }
  root.append(sec('about', ab));
  if (RX.stSel) setTimeout(() => { const el = document.getElementById('st-' + RX.stSel); if (el) el.scrollIntoView({ block: 'start' }); RX.stSel = null; }, 0);
  return root;
}
/* ---------- LaTeX to paste (S31) ----------
   Founder (chat 2026-11-19 23:53 KST): the paper is in Overleaf, which Lemmata cannot read, so Lemmata is where the LaTeX is made:
   tables, paragraphs and captions written by the researcher's own agent from everything Lemmata holds, ready to copy and paste. */
const LX_PROMPT = (name, id) => 'For the Lemmata project "' + name + '": ' + (id ? 'call Lemmata\'s latex tool with request=' + id + ', write it from that brief only, and hand it in with submit_latex.' : 'call Lemmata\'s latex tool for the open requests, write each one from its brief only, and hand each in with submit_latex.') + ' Use the lemmata-latex agent if it is installed. Copy every number exactly, and show me the LaTeX as well.';
const KIT_PROMPT = 'Call Lemmata\'s agent_kit tool and write each file it returns into this repository at the path it gives (under .claude/). Do not change a file that already exists and differs; list those instead. Then tell me which agents and skills are now available.';
const LX_STATE = { ok: ['[checked]', 'd-ok', 'Every decimal number in it is one your files hold, and its form is sound.'], check: ['[check]', 'd-warn', 'Something in it could not be confirmed. Open "What the check found".'], stale: ['[stale]', 'd-err', 'A number that was in your files when this was written is no longer there. If you pasted it, the paper is out of date.'] };
function lxCode(latex, id) {
  const pre = h('pre', { class: 'lx-code', id: id || null, tabindex: '0' }, latex);
  return h('div', { class: 'lx-box' }, h('button', { class: 'btn sm lx-copy', onclick: () => copyText(latex) }, 'Copy'), pre);
}
function pageLatex() {
  const nr = rxNotReady('LaTeX'); if (nr) return nr;
  S.outline = [];
  const L = RX.latex, name = S.project ? S.project.name : 'this project';
  const root = doc(h('h1', { class: 'ptitle' }, 'LaTeX'));
  root.classList.add('wide');
  if (!L) return root.append(h('p', { class: 'muted' }, 'This hub has no LaTeX page yet. It appears after the hub updates.')), root;
  const c = L.counts;
  const act = async (body, msg) => { const r = await rxPost('/api/latex', body, msg); if (r) { RX.latex = r; renderAll(); } return r; };
  root.append(h('p', { class: 'lede muted' }, 'Tables, paragraphs and captions to paste into your paper. Tables by rule are exact copies of your result files. Anything else is written by your own agent from everything Lemmata holds about the project, and its numbers are checked against your files.'), rxBehindNote());
  // ask
  if (!READONLY) {
    const kind = h('select', { 'aria-label': 'What to write' }, Object.entries(L.kinds).map(([k, l]) => h('option', { value: k, selected: (RX.lxKind || 'table') === k ? '' : null }, l)));
    const tgt = h('select', { 'aria-label': 'About' }, L.targets.map((t, i) => h('option', { value: String(i), selected: RX.lxTarget === (t.id || '') ? '' : null }, trunc((t.type === 'experiment' ? 'Experiment: ' : t.type === 'claim' ? 'Claim ' : '') + t.name, 90))));
    const ask = h('textarea', { rows: '2', class: 'rx-ta', 'aria-label': 'What you want', placeholder: 'What you want, in your words. For example: one table with the main results, ours last, best in bold; then a two-sentence caption.' });
    ask.value = RX.lxAsk || ''; ask.addEventListener('input', () => { RX.lxAsk = ask.value; });
    const go = async () => { const t = L.targets[Number(tgt.value)] || L.targets[0]; RX.lxKind = kind.value; RX.lxTarget = t.id || '';
      const d = await act({ action: 'request', kind: kind.value, target: t.type === 'project' ? null : { type: t.type, id: t.id }, ask: ask.value }, 'Asked. It waits for your agent.'); if (d) { RX.lxAsk = ''; renderPage(true); } };
    root.append(h('h2', { class: 'st-h' }, 'Ask your agent'), h('div', { class: 'lx-ask' }, h('div', { class: 'lx-pick' }, kind, h('span', { class: 'muted' }, 'about'), tgt), ask,
      h('div', { class: 'bl-acts' }, h('button', { class: 'btn sm primary', id: 'lx-go', onclick: go }, 'Ask'), h('span', { class: 'muted small' }, 'Lemmata writes nothing itself. Your agent gets the full brief and hands the LaTeX back here.'))));
  }
  const open = L.requests.filter(r => r.status === 'open');
  if (open.length) root.append(h('div', { class: 'flag nb-prop' }, h('b', null, plural(open.length, 'request') + ' waiting for your agent. '),
    READONLY ? null : [h('button', { class: 'btn sm primary', title: LX_PROMPT(name), onclick: () => copyText(LX_PROMPT(name)) }, 'Copy prompt for Claude Code'), h('span', { class: 'muted small' }, ' or type /lemmata-latex there')]),
    open.map(r => h('div', { class: 'hf-row lx-req', id: 'lx-' + r.id }, h('span', { class: 'hf-tag' }, '[' + (L.kinds[r.kind] || r.kind).toLowerCase() + ']'), h('span', { class: 'grow' }, h('b', null, r.target.name), r.ask ? ['. ', r.ask] : null, h('span', { class: 'muted small' }, ' · asked ' + dmon(r.created))),
      READONLY ? null : h('button', { class: 'linkbtn small', onclick: () => act({ action: 'remove_request', id: r.id }, 'Removed.') }, 'Remove'))));
  // written
  if (L.snippets.length) {
    root.append(h('h2', { class: 'st-h' }, 'Written for you'), h('div', { class: 'rx-x-sum' }, h('span', null, h('b', null, c.snippets), c.snippets === 1 ? ' snippet' : ' snippets'), h('span', null, h('b', null, c.ok), ' checked'),
      c.check ? h('span', { class: 'warn' }, h('b', null, c.check), ' to check') : null, c.stale ? h('span', { class: 'warn' }, h('b', null, c.stale), ' stale') : null));
    for (const sn of L.snippets) {
      const k = sn.check, st = LX_STATE[k.status] || LX_STATE.check, on = RX.lxOpen === sn.id || L.snippets.length === 1 || k.status !== 'ok' && RX.lxOpen == null;
      const found = [];
      if (k.stale.length) found.push(h('div', { class: 'rx-warn' }, 'No longer in your files: ', h('span', { class: 'mono' }, k.stale.join(', ')), '. The results changed after this was written.'));
      const rest = k.unknown.filter(x => !k.stale.includes(x));
      if (rest.length) found.push(h('div', null, 'Not found in your files: ', h('span', { class: 'mono' }, rest.join(', ')), '. A value your agent computed (an average, a difference) shows up here; check that its notes say so.'));
      k.form.forEach(f => found.push(h('div', { class: 'rx-warn' }, 'Form: ' + f + '.')));
      if (k.cites_todo.length) found.push(h('div', null, 'Citations still to fill in: ', h('span', { class: 'mono' }, k.cites_todo.join(', ')), '.'));
      if (k.cites_unknown && k.cites_unknown.length) found.push(h('div', null, 'Citation keys not in your bibliography: ', h('span', { class: 'mono' }, k.cites_unknown.join(', ')), '.'));
      if (k.cites_unknown == null && k.cites.length) found.push(h('div', { class: 'muted' }, 'Citation keys were not checked: Lemmata has no bibliography for this project.'));
      if (!found.length) found.push(h('div', { class: 'muted' }, plural(k.numbers, 'decimal number') + ' read, all found in your files. Form is sound.'));
      root.append(h('section', { class: 'lx-sn' + (on ? ' on' : ''), id: 'lx-' + sn.id },
        h('div', { class: 'hf-row lx-head', onclick: () => { RX.lxOpen = on ? '' : sn.id; renderPage(true); } }, h('span', { class: 'rdot ' + st[1], 'aria-hidden': 'true' }), h('span', { class: 'hf-tag', title: st[2] }, st[0]),
          h('button', { class: 'bl-name grow', 'aria-expanded': String(on), onclick: ev => { ev.stopPropagation(); RX.lxOpen = on ? '' : sn.id; renderPage(true); } }, sn.title), h('span', { class: 'muted small' }, (L.kinds[sn.kind] || sn.kind) + ' · ' + sn.by + ' · ' + dmon(sn.at)),
          h('button', { class: 'btn sm', onclick: ev => { ev.stopPropagation(); copyText(sn.latex); } }, 'Copy')),
        on ? [lxCode(sn.latex), sn.notes ? h('p', { class: 'small' }, h('b', null, 'Your agent says: '), sn.notes) : null,
          h('div', { class: 'lx-found small' }, h('b', null, 'What the check found'), found),
          sn.sources.length ? h('div', { class: 'small muted' }, 'From: ' + sn.sources.join(' · ')) : null,
          READONLY ? null : h('div', { class: 'bl-acts' }, h('button', { class: 'linkbtn small', onclick: () => act({ action: 'remove_snippet', id: sn.id }, 'Removed.') }, 'Remove'))] : null));
    }
  }
  // tables by rule
  root.append(h('h2', { class: 'st-h' }, 'Tables by rule'));
  if (!L.tables.length) root.append(h('p', { class: 'muted' }, 'No result file could be read as a table of methods and numbers yet.'));
  else {
    root.append(h('p', { class: 'muted small' }, 'Built from your result files with no model: the numbers are exactly the ones in the files. Needs the booktabs package.'));
    for (const t of L.tables) {
      const on = RX.lxTab === t.x;
      root.append(h('section', { class: 'lx-sn' + (on ? ' on' : '') },
        h('div', { class: 'hf-row lx-head', onclick: () => { RX.lxTab = on ? null : t.x; renderPage(true); } }, h('span', { class: 'hf-tag' }, '[table]'),
          h('button', { class: 'bl-name grow', 'aria-expanded': String(on), onclick: ev => { ev.stopPropagation(); RX.lxTab = on ? null : t.x; renderPage(true); } }, t.name),
          h('span', { class: 'muted small' }, [t.metric ? t.metric + (t.lower ? ' ↓' : ' ↑') : null, t.rows + ' × ' + t.cols].filter(Boolean).join(' · ')),
          h('button', { class: 'btn sm', onclick: ev => { ev.stopPropagation(); copyText(t.latex); } }, 'Copy')),
        on ? [t.note ? h('p', { class: 'small muted' }, t.note) : null, lxCode(t.latex),
          h('div', { class: 'bl-acts' }, h('button', { class: 'linkbtn small', onclick: () => rxOpenExp(t.x) }, 'Open the experiment'))] : null));
    }
  }
  return root;
}
const RX_PAGES = { latex: pageLatex, settings: pageSettings, baselines: pageBaselines, numbers: pageNumbers, digest: pageDigest, review: pageReview, notation: pageNotation, claims: pageClaims, timeline: pageTimeline, experiments: pageExperiments, setup: pageSetup, history: pageTrail, trail: pageTrail, tasks: pageTasks, ask: pageAsk, faq: pageFaq };
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
