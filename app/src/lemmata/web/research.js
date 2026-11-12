/* Lemmata research views (S07): Claim map, Timeline, Experiments, Tasks, Ask. Loaded after app.js and uses its helpers
   (h, clear, doc, sec, apiGet, apiPost, openTab, openNode, toast, modal, plainChip, mono, trunc, absTime, dmon, S, IX).
   Everything shown here comes from /api/claims, /api/timeline, /api/ledger, /api/tasks, /api/digest and /api/ask.
   No inline scripts, no innerHTML. */
'use strict';
const RX = { tree: null, view: 'tree', sel: null, t: 1, playing: null, claims: null, timeline: null, ledger: null, tasks: null, loaded: false, error: null, open: {}, filter: 'all', tlFilter: 'all', exFilter: 'all',
  ask: { q: '', busy: false, res: null, history: [] }, hub: null, digest: null };
const RX_TABS = { digest: ['', 'Digest'], review: ['◎', 'Review'], notation: ['𝑥', 'Notation'], claims: ['◆', 'Claims'], timeline: ['⚑', 'Timeline'], experiments: ['▦', 'Experiments'], tasks: ['☑', 'Tasks'], ask: ['?', 'Ask'] };
const RX_VIEW_TAB = { claims: 'claims', inbox: 'changes', timeline: 'timeline', ask: 'ask' };
const RX_STATUS = { supported: ['✓', 'Supported', 'fine'], partial: ['◐', 'Partly supported', 'look'], unsupported: ['✕', 'Not supported', 'fix'] };
// One kind of item, a claim, moving through stages. The stage classes reuse the status colours.
const RX_STAGE = { hypothesis: ['○', 'Hypothesis', 'plain', 'hyp'], testing: ['◐', 'Being tested', 'look', 'partial'], finding: ['●', 'Finding', 'fine', 'supported'], refuted: ['✕', 'Not supported', 'fix', 'unsupported'], exploration: ['◌', 'Exploration', 'ign', 'explore'] };
const RX_STAGES = ['finding', 'testing', 'hypothesis', 'refuted', 'exploration'];
const RX_SCOPE = { new: ['New', 'A claim of this work'], original: ['Original', 'A claim of the paper this work extends, re-checked here'] };
function rxSt(stage) { return ' st-' + (RX_STAGE[stage] || RX_STAGE.hypothesis)[3]; }
function rxStageChip(c) { const k = RX_STAGE[c.stage] ? c.stage : 'hypothesis', s = RX_STAGE[k]; const ch = plainChip(s[0], s[1], s[2] + ' stg-' + k); ch.title = (c.stage_by === 'you' ? 'Set by you. ' : '') + (c.stage_why || ''); return ch; }
function rxScopeTag(c) { const s = RX_SCOPE[c.scope]; return s ? h('span', { class: 'tag', title: s[1] }, s[0]) : null; }
function rxOpenExp(id) { RX.exView = 'map'; RX.mapSel = 'x:' + id; RX.exOpen = null; openTab('experiments'); }
/* The VS Code tab calls this to open a page with something selected (from an "Open in VS Code" link on the website). */
function rxGoto(view, sel) {
  if (view === 'experiments' && /^[qx]:/.test(sel || '')) { RX.exView = 'map'; RX.mapSel = sel; RX.exOpen = null; }
  openTab(view);
}
/* Website only: a link that opens this page in VS Code's Lemmata tab (vscode/src/core/link.ts reads it). */
function rxVsLink(sel, label) {
  if (EMBED || !PID) return null;
  return h('a', { class: 'btn sm', href: 'vscode://lemmata-local.lemmata/open?pid=' + encodeURIComponent(PID) + '&view=experiments&sel=' + encodeURIComponent(sel),
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
    try { RX.review = await apiGet(READONLY ? '/api/review' : '/api/review?days=' + (RX.rvDays || 30)); } catch (e) { RX.review = null; }
    Object.assign(RX, { claims, timeline, ledger, tasks, tree, notation, experiments, map, loaded: true, error: null });
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
    if (path.startsWith('/api/claims')) { RX.digest = null; try { const [t, l, tr] = await Promise.all(['timeline', 'ledger', 'tree'].map(p => apiGet('/api/' + p))); RX.timeline = t; RX.ledger = l; RX.tree = tr; RX.experiments = await apiGet('/api/experiments'); } catch (e) { /* the old tree stays */ } }
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
  const seg = h('div', { class: 'rx-seg', role: 'group', 'aria-label': 'View' }, [['tree', 'Tree'], ['list', 'List']].map(([k, l]) => h('button', { 'aria-pressed': String(RX.view === k), onclick: () => { RX.view = k; renderPage(true); } }, l)));
  const root = doc(h('div', { class: 'row' }, h('h1', { class: 'ptitle grow' }, 'Claims'), seg,
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
function rxGapBar(sm) {
  if (!sm || sm.gap == null) return h('span', { class: 'muted small' }, sm && sm.ours != null ? rxFmt(sm.ours) : '—');
  const W = 132, mid = 56, scale = Math.max(Math.abs(sm.gap), Math.abs(sm.best.value) * 0.12, 1e-9), len = Math.max(2, Math.min(mid - 2, Math.abs(sm.gap) / scale * (mid - 2)));
  const good = sm.gap > 0, s = sv('svg', { viewBox: '0 0 ' + W + ' 18', width: W, height: 18, class: 'rx-gap', role: 'img', 'aria-label': 'Ours ' + rxFmt(sm.ours) + ', best other ' + rxFmt(sm.best.value) + ' (' + sm.best.label + ')' });
  s.append(sv('line', { x1: mid, x2: mid, y1: 1, y2: 17, class: 'zero' }), sv('rect', { x: good ? mid : mid - len, y: 5, width: len, height: 8, rx: 2, class: sm.gap === 0 ? 'tie' : good ? 'good' : 'bad' }),
    sv('text', { x: mid + (good ? len + 4 : 4), y: 13, class: 'gl' }, (sm.gap > 0 ? '+' : '') + rxFmt(sm.gap)),
    sv('title', null, sm.ours_label + ' ' + rxFmt(sm.ours) + ' · best other: ' + sm.best.label + ' ' + rxFmt(sm.best.value) + ' · ' + sm.metric + (sm.lower ? ' (lower is better)' : '')));
  return s;
}
function rxSpark(spark) {
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
function rxExpRow(x, sec) {
  const key = (sec ? sec.id : '-') + '|' + x.id, open = RX.exOpen === key, tu = x.tuning;
  const glyph = x.attention ? ['!', 'look'] : x.connected ? ['✓', 'fine'] : ['?', 'ign'];
  const row = h('div', { class: 'rx-x-r' + (open ? ' open' : '') + (x.attention ? ' att' : '') },
    h('button', { class: 'rx-x-main', 'aria-expanded': String(open), onclick: () => { RX.exOpen = open ? null : key; renderPage(true); } },
      h('span', { class: 'sg ' + glyph[1] }, glyph[0]), h('span', { class: 'rx-x-name' }, x.map && RX_XTYPE[x.type] ? h('span', { class: 'tag rx-x-ty t-' + x.type }, RX_XTYPE[x.type]) : null, h('b', null, x.name), x.map ? h('span', { class: 'muted small' }, ' · ' + plural(x.files_n, 'file')) : null, h('span', { class: 'muted' }, x.caption ? ' ' : ''), x.caption ? h('span', { class: 'muted' }, rxMath(trunc(x.caption, 60))) : null)),
    h('span', { class: 'rx-x-metric small muted', title: x.summary ? (x.summary.measure || x.summary.metric) + (x.summary.measure && x.summary.measure !== x.summary.metric ? ' · ' + x.summary.metric : '') : null }, x.summary ? trunc(x.summary.measure || x.summary.metric, 16) + (x.summary.target != null ? '' : x.summary.lower ? ' ↓' : ' ↑') : ''),
    tu ? h('span', { class: 'small', title: tu.best ? 'Best setting: ' + tu.best.label : null }, tu.best ? [h('b', { class: 'mono' }, rxFmt(tu.best.value)), h('span', { class: 'muted' }, ' best of ' + tu.runs)] : '') : rxBaseOrBest(x.summary), rxSpark(x.spark), rxTally(x),
    h('span', { class: 'muted small' }, x.stale ? h('span', { class: 'rx-tl warn', title: 'The code or settings changed after this result was written' }, '↻ old') : x.last ? dmon(x.last) : ''));
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
  const post = async body => { const r = await rxPost('/api/experiment', Object.assign({ id }, body)); if (r) { try { RX.experiments = await apiGet('/api/experiments'); } catch (e) { /* keep */ } renderPage(true); } };
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
        x.tuning ? null : [h('span', { class: 'muted small' }, 'ours:'), sel(sm.ours_label, sm.methods, v => post({ ours: v }), 'Our method'),
        sm.ours_by !== 'you' ? h('span', { class: 'muted small' }, ['paper', 'name', 'map'].includes(sm.ours_by) ? '' : '(guessed)') : null]),
        h('div', { class: 'rx-bars' }, sorted.map((r, i) => { const v = r.values[sm.metric], me = r.label === sm.ours_label; return h('div', { class: 'rx-bar' + (me ? ' me' : '') },
          h('span', { class: 'bl' }, r.label, sm.base && r.label === sm.base.label ? h('span', { class: 'tag' }, 'base') : null), h('span', { class: 'bt' }, h('span', { class: 'bf', style: 'width:' + Math.max(1, Math.abs(v) / hi * 100) + '%' })),
          h('span', { class: 'bv mono' }, rxFmt(v) + (r.std[sm.metric] != null ? ' ±' + rxFmt(r.std[sm.metric]) : '')), h('span', { class: 'muted small' }, i === 0 ? '★' : '')); }))));
    } else out.push(blk('Result', h('div', { class: 'rx-warn' }, x.map ? (x.connected ? 'These files could not be read as tables with the map’s metric.' : 'No file matches this experiment’s patterns any more.') : x.connected ? 'The result file could not be read as a table (CSV or JSON with one row per method).' : 'No result file is connected. Put “% source: code:results/file.csv” above it in the LaTeX.')));
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
    // history
    if (x.history && x.history.length) {
      const hs = x.history, chart = hs.length > 1 ? rxHistoryChart(hs, sm) : null;
      const word = { single: 'one change', bundled: 'several changes at once', none: 'no code change found', ruler: 'evaluation changed: not comparable', first: 'first version' };
      out.push(blk('History', chart, hs.length > 1 ? h('div', { class: 'rx-legend' }, h('span', null, h('span', { class: 'lg-o' }, '━'), ' ' + sm.ours_label), h('span', null, h('span', { class: 'lg-b' }, '┄'), ' best other'),
        Object.keys(RX_CAT).filter(c => hs.some(p => p.cats.includes(c))).map(c => h('span', null, h('span', { class: 'lg-g' }, RX_CAT[c][0]), ' ' + RX_CAT[c][1])), hs.some(p => p.became_best) ? h('span', null, '★ became best') : null) : null,
        h('div', { class: 'rx-steps' }, hs.slice().reverse().map(p => { const better = p.delta != null && (sm.lower ? p.delta < 0 : p.delta > 0); return h('div', { class: 'rx-st' },
          h('span', { class: 'mono small muted' }, dmon(p.time)), h('span', { class: 'mono' }, rxFmt(p.ours)),
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
  const act = async (path, body, msg) => { const r = await rxPost(path, body, msg); if (r) { RX.map = r; if (path.endsWith('confirm')) RX.mapOpen = false; try { RX.experiments = await apiGet('/api/experiments'); RX.claims = await apiGet('/api/claims'); RX.tree = await apiGet('/api/tree'); } catch (e) { /* keep */ } renderLeft(); renderPage(true); } };
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
    h('span', { class: 'rx-map-n' }, h('span', { title: 'Our method' }, h('b', null, m.method ? m.method.name : '?')), m.base ? h('span', { title: 'Extends' }, '↳ ', h('b', null, m.base.name)) : null, h('span', { title: 'Questions' }, '◆ ', h('b', null, m.questions.length)), h('span', { title: 'Experiments' }, '▦ ', h('b', null, m.experiments.length)),
      cov.n_files ? h('span', { class: 'warn' }, h('b', null, cov.n_files), ' files unmapped') : null, dropped.length ? h('span', { class: 'bad' }, h('b', null, dropped.length), ' dropped') : null),
    prop && !READONLY ? [h('button', { class: 'btn sm', onclick: () => act('/api/map/discard', {}, 'Proposal discarded') }, 'Discard'), h('button', { class: 'btn sm primary', disabled: !m.experiments.length, onclick: () => act('/api/map/confirm', {}, 'Map confirmed') }, 'Confirm')] : null);
  const edit = change => act('/api/map/edit', { change });
  const body = h('details', { class: 'rx-map-d', open: prop || RX.mapOpen ? '' : null, ontoggle: ev => { if (!prop) RX.mapOpen = ev.target.open; } }, h('summary', null, prop ? 'Review' : 'Show map'),
    h('div', { class: 'rx-map-row' }, h('span', { class: 'rx-map-k' }, 'Ours'), READONLY ? h('b', null, m.method ? m.method.name : '?') : (() => { const i = h('input', { class: 'rx-map-in', value: m.method ? m.method.name : '', 'aria-label': 'Name of our method', placeholder: 'Method name' }); i.addEventListener('change', () => edit({ method: i.value })); return i; })(),
      m.method && m.method.aliases.length ? h('span', { class: 'muted small' }, 'also ' + m.method.aliases.join(', ')) : null),
    h('div', { class: 'rx-map-row' }, h('span', { class: 'rx-map-k', title: 'The method of the paper this work extends' }, 'Extends'),
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
          h('td', { class: 'mono small', title: x.files.join('\n') }, h('b', null, x.matched), ' ' + trunc(x.files[0] || '', 30)), h('td', { class: 'mono small' }, x.metric || h('span', { class: 'muted' }, 'guess')),
          h('td', { class: 'small' }, x.paper.map((p, i) => [i ? ', ' : null, rxNodeBtn(p, ((IX.node && IX.node.get(p)) || {}).name || p)])), h('td', null, READONLY ? null : h('button', { class: 'linkbtn small', title: 'Remove this experiment', onclick: () => edit({ remove: 'experiment:' + x.id }) }, '✕'))); })))),
    m.ignore.length ? h('div', { class: 'rx-map-row' }, h('span', { class: 'rx-map-k' }, 'Ignored'), m.ignore.map(p => h('span', { class: 'rx-code mono' }, p))) : null,
    dropped.length ? h('div', { class: 'rx-map-rep' }, h('b', null, 'Dropped by the checker'), dropped.map(r => h('div', { class: 'rx-warn' }, '✕ ' + r.where + ': ' + r.why))) : null,
    warns.length ? h('div', { class: 'rx-map-rep' }, warns.map(r => h('div', { class: 'muted small' }, '! ' + r.where + ': ' + r.why))) : null,
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
    h('span', { class: 'rx-m-ours' }, (E.map && E.map.method ? E.map.method.name : null) || 'Ours'), X ? h('span', { class: 'rx-m-sub' }, 'extends ' + X.base.name) : null,
    X && X.goal ? h('span', { class: 'rx-m-goal serif' }, trunc(X.goal, 90)) : null, meter(exps, true),
    h('span', { class: 'rx-m-sub' }, cmp ? 'Ahead of ' + trunc(vs, 18) + ' in ' + all.ahead + ' of ' + cmp : 'Nothing to compare yet'), all.check ? h('span', { class: 'rx-m-chk' }, '! ' + all.check + ' to check') : null));
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
  const E = RX.experiments;
  const seg = h('div', { class: 'rx-seg', role: 'group', 'aria-label': 'View' }, [['map', 'Map'], ['table', 'Table']].map(([k, l]) => h('button', { 'aria-pressed': String((RX.exView || 'table') === k), onclick: () => { RX.exView = k; renderPage(true); } }, l)));
  const root = doc(h('div', { class: 'row' }, h('h1', { class: 'ptitle grow' }, 'Experiments'), E ? seg : null));
  if (!E) return root.append(h('p', { class: 'muted' }, 'Not available.')), root;
  const c = E.counts, mapped = !!E.unmapped;
  root.append(rxMapCard());
  const X = E.extends;
  if (X) root.append(h('div', { class: 'rx-ext' }, h('span', { class: 'rx-ext-b' }, h('b', null, (E.map.method || {}).name || 'Ours'), ' extends ', h('b', null, X.base.name)),
    X.goal ? h('span', { class: 'rx-ext-g serif' }, '→ ' + X.goal) : h('span', { class: 'muted small' }, 'No goal')));
  root.append(h('div', { class: 'rx-x-sum' }, h('span', null, h('b', null, c.questions), ' claims'), h('span', null, h('b', null, c.experiments), ' experiments'), c.no_claim ? h('span', { class: 'warn', title: 'Experiments that test no claim' }, h('b', null, c.no_claim), ' without a claim') : null, 
    c.untested ? h('span', { class: 'bad' }, h('b', null, c.untested), ' not tested') : null, c.attention ? h('span', { class: 'warn' }, h('b', null, c.attention), ' to check') : null));
  const head = () => h('div', { class: 'rx-x-r head' }, h('span', null, 'Experiment'), h('span', null, 'Metric'), h('span', null, X ? 'Ours vs ' + trunc(X.base.name, 12) : 'Ours vs best other'), h('span', null, 'Over time'), h('span', null, 'Paper'), h('span', null, 'Last'));
  const WORD = { supported: 'Tested, nothing to check', partial: 'Something to check', unsupported: 'Not tested' };
  const renderSec = s => {
    const st = RX_STATUS[s.status], cid = mapped ? s.claim_id : s.id;
    const sec = h('section', { class: 'rx-x-sec' + (s.stage ? rxSt(s.stage) : ' st-' + s.status) },
      h('div', { class: 'rx-x-h' }, s.stage ? null : h('span', { class: 'sg ' + st[2], title: mapped ? WORD[s.status] : st[1] }, st[0]),
        cid ? h('button', { class: 'rx-x-q', title: 'Open in Claims', onclick: () => { RX.sel = cid; RX.view = 'tree'; openTab('claims'); } }, s.short || s.label) : h('span', { class: 'rx-x-q static' }, s.label),
        s.stage ? rxStageChip(s) : null,
        h('span', { class: 'rx-x-qt serif' + (s.kind === 'other' ? ' muted' : '') }, rxMath(trunc(s.text, 150))), h('span', { class: 'grow' }), h('span', { class: 'muted small' }, s.experiments.length ? plural(s.experiments.length, 'experiment') : '')));
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
function pageReview() {
  const nr = rxNotReady('Review'); if (nr) return nr;
  S.outline = [];
  const R = RX.review, days = RX.rvDays || 30, name = S.project ? S.project.name : 'this project';
  const setDays = async d => { RX.rvDays = d; try { RX.review = await apiGet('/api/review?days=' + d); } catch (e) { /* keep */ } renderPage(true); };
  const seg = h('div', { class: 'rx-seg', role: 'group', 'aria-label': 'Period' }, [[30, '30 days'], [7, '1 week'], [1, '1 day']].map(([d, l]) => h('button', { 'aria-pressed': String(days === d), disabled: READONLY && days !== d, onclick: () => setDays(d) }, l)));
  const root = doc(h('div', { class: 'row' }, h('h1', { class: 'ptitle grow' }, 'Review'), R ? seg : null));
  root.classList.add('wide');
  if (!R) return root.append(h('p', { class: 'muted' }, 'Not available.')), root;
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
        h('div', { class: 'row rx-rv-act' },
          READONLY ? null : h('button', { class: 'btn sm primary', title: 'Paste it into your Claude Code: ' + RX_CONF_PROMPT(name), onclick: () => copyText(RX_CONF_PROMPT(name)) }, 'Copy confound check for Claude Code'),
          READONLY ? null : h('button', { class: 'btn sm', title: 'Mark confounds as checked by you, without an agent', onclick: () => post({ question: q.id, mine: !(rep && rep.by === 'you') }) }, rep && rep.by === 'you' ? 'Undo my check' : 'I checked it myself'),
          q.started ? h('button', { class: 'btn sm', onclick: () => { RX.exView = 'map'; RX.mapSel = 'q:' + q.id; openTab('experiments'); } }, 'Open experiments') : null,
          q.started ? rxVsLink('q:' + q.id) : null,
          rep ? h('span', { class: 'muted small' }, 'Confounds: ' + rep.by + ', ' + dmon(rep.at)) : null)));
    }
  }
  if (!rows.length) tbl.append(h('div', { class: 'rx-x-none' }, R.questions.length ? 'Nothing behind this check.' : 'No questions yet. Confirm a project map on the Experiments page.'));
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
function pageDigest() {
  const nr = rxNotReady('Digest'); if (nr) return nr;
  S.outline = [];
  const root = doc(h('h1', { class: 'ptitle' }, 'Digest'));
  if (!READONLY) root.append(sec('This week', 'digest', rxDigestBox()));
  const open = RX.tasks ? RX.tasks.tasks.filter(t => t.state === 'open') : [];
  root.append(sec('Open tasks (' + open.length + ')', 'tasks', open.length ? open.slice(0, 8).map(t => h('div', { class: 'row-line' }, h('span', { class: 'rtag' }, '[task]'), h('button', { class: 'ilink', onclick: () => openTab('tasks') }, trunc(t.text || t.title || '', 140)))) : h('div', { class: 'muted' }, 'Nothing open.'),
    h('div', { class: 'row-line' }, h('span', { class: 'rtag' }), h('button', { class: 'linkbtn', onclick: () => openTab('tasks') }, 'All tasks and feedback'))));
  const hist = pageHistory({ weekly: true });
  root.append(sec('History', 'history', Array.from(hist.childNodes).filter(n => !(n.tagName === 'H1'))));
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
const RX_PAGES = { digest: pageDigest, review: pageReview, notation: pageNotation, claims: pageClaims, timeline: pageTimeline, experiments: pageExperiments, tasks: pageTasks, ask: pageAsk };
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
