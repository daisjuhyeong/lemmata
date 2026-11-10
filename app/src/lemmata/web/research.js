/* Lemmata research views (S07): Claim map, Timeline, Experiments, Tasks, Ask. Loaded after app.js and uses its helpers
   (h, clear, doc, sec, apiGet, apiPost, openTab, openNode, toast, modal, plainChip, mono, trunc, absTime, dmon, S, IX).
   Everything shown here comes from /api/claims, /api/timeline, /api/ledger, /api/tasks, /api/digest and /api/ask.
   No inline scripts, no innerHTML. */
'use strict';
const RX = { claims: null, timeline: null, ledger: null, tasks: null, loaded: false, error: null, open: {}, filter: 'all', tlFilter: 'all', exFilter: 'all',
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
    const [claims, timeline, ledger, tasks] = await Promise.all(['claims', 'timeline', 'ledger', 'tasks'].map(p => apiGet('/api/' + p)));
    Object.assign(RX, { claims, timeline, ledger, tasks, loaded: true, error: null });
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
    if (path.startsWith('/api/claims')) Promise.all(['timeline', 'ledger'].map(p => apiGet('/api/' + p))).then(([t, l]) => { RX.timeline = t; RX.ledger = l; RX.digest = null; }).catch(() => { });
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
    suggested ? h('div', { class: 'muted small' }, 'Lemmata guessed this from the wording. It does not count until you say yes.') : null,
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
function pageClaims() {
  const nr = rxNotReady('Claims'); if (nr) return nr;
  S.outline = [];
  const d = RX.claims, cc = d.counts;
  const root = doc(h('div', { class: 'row' }, h('h1', { class: 'ptitle grow' }, 'Claims'),
    READONLY ? null : h('a', { class: 'btn', href: apiUrl('/api/claims.md'), title: 'A claims.md file you can commit to your repository' }, 'Download claims.md')),
    h('p', { class: 'muted' }, 'What the paper says, and what backs each statement. Lemmata drafted this from the LaTeX and the repository; a claim counts once you confirm it, and a suggested link counts once you accept it.'));
  if (!d.has_paper) {
    root.append(emptyState('◆', 'No paper connected yet', 'Claims are drafted from the LaTeX source: the abstract, the contribution list, research questions and theorems. Connect a paper repository or upload the Overleaf source as a zip from the project menu (⋯). You can also write claims yourself below.'));
  }
  const core = d.core;
  if (core) {
    root.append(h('section', { class: 'rx-core st-' + core.status },
      h('div', { class: 'rx-core-h' }, h('span', { class: 'rx-label' }, 'Core message'), rxChip(core.status), core.recheck ? plainChip('↻', 'Recheck', 'look') : null, h('span', { class: 'grow' }), rxWhere(core.loc)),
      h('div', { class: 'rx-core-t serif' }, core.text),
      h('div', { class: 'rx-meter', role: 'img', 'aria-label': cc.supported + ' supported, ' + cc.partial + ' partly, ' + cc.unsupported + ' not supported' },
        cc.total ? [['supported', cc.supported], ['partial', cc.partial], ['unsupported', cc.unsupported]].filter(x => x[1]).map(([k, n]) => h('span', { class: 'seg ' + k, style: 'flex:' + n }, String(n))) : null),
      h('div', { class: 'muted small' }, cc.total ? cc.supported + ' of ' + cc.total + ' claims under it are supported' + (cc.partial ? ', ' + cc.partial + ' partly' : '') + (cc.unsupported ? ', ' + cc.unsupported + ' not' : '') + '. The core message is only as strong as the claims that carry it.' : 'No claims found under it yet.')));
  }
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
  if (!READONLY) {
    const ta = h('textarea', { rows: '2', class: 'rx-ta', placeholder: 'A claim the paper makes that Lemmata did not find, in one sentence', 'aria-label': 'New claim' });
    root.append(sec('Add a claim yourself', 'add', ta, h('div', { class: 'btnrow' }, h('button', { class: 'btn', onclick: async () => { if (!ta.value.trim()) return; const r = await rxPost('/api/claims/add', { text: ta.value }); if (r) { RX.claims = r; renderPage(true); renderLeft(); } } }, 'Add claim'))));
  }
  if (gone.length) root.append(h('details', { class: 'details' }, h('summary', null, 'Not claims (' + gone.length + ')'), gone.map(rxClaimCard)));
  return root;
}

/* ---------- Timeline ---------- */
function pageTimeline() {
  const nr = rxNotReady('Timeline'); if (nr) return nr;
  S.outline = [];
  const tl = RX.timeline, F = RX.tlFilter;
  const root = doc(h('h1', { class: 'ptitle' }, 'Timeline'),
    h('p', { class: 'muted' }, 'How the work got here. Commits are grouped into steps by day and by what they touched; steps that look like decisions (a changed setting, metric, baseline or data set, or a reversal) are marked.'));
  const label = id => { const c = RX.claims && (RX.claims.claims.find(x => x.id === id) || (RX.claims.core && RX.claims.core.id === id && RX.claims.core)); return c ? c.label : id; };
  const steps = tl.steps.filter(s => F === 'all' || (F === 'decisions' ? s.decision : F === 'claims' ? s.affects.length : s.role === F)).slice().reverse();
  root.append(h('div', { class: 'fchips' }, [['all', 'All', tl.steps.length], ['decisions', 'Decisions', tl.decisions], ['claims', 'Touching a claim', tl.steps.filter(s => s.affects.length).length], ['code', 'Code', null], ['paper', 'Paper', null]]
    .map(([k, l, n]) => h('button', { class: 'fchip', 'aria-pressed': String(F === k), onclick: () => { RX.tlFilter = k; renderPage(true); } }, l, n != null ? [' ', h('span', { class: 'n' }, n)] : null))));
  if (!steps.length) return root.append(h('div', { class: 'muted' }, tl.steps.length ? 'Nothing with this filter.' : 'No commits yet.')), root;
  let month = null;
  for (const s of steps) {
    const mk = s.day.slice(0, 7);
    if (mk !== month) { month = mk; root.append(h('div', { class: 'dayhead' }, MON[+mk.slice(5, 7) - 1] + ' ' + mk.slice(0, 4))); }
    const open = !!RX.open['tl:' + s.id];
    root.append(h('article', { class: 'rx-step' + (s.decision ? ' decision' : '') },
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
    h('p', { class: 'muted' }, 'One row per result file: what made it, when, and who relies on it. “Out of date” means the script or settings behind a file were committed after the file itself, so the file may not reflect the current code.'));
  root.append(h('div', { class: 'fchips' }, [['all', 'All', L.rows.length], ['stale', 'Out of date', c.stale], ['unknown', 'No known source', c.unknown], ['current', 'Current', c.current]].map(([k, l, n]) =>
    h('button', { class: 'fchip', 'aria-pressed': String(F === k), onclick: () => { RX.exFilter = k; renderPage(true); } }, l + ' ', h('span', { class: 'n' }, n)))));
  const rows = L.rows.filter(r => F === 'all' || r.status === F);
  if (!L.rows.length) return root.append(emptyState('▦', 'No result files found', 'Lemmata looks for files in folders named results, outputs, figures, tables, plots or logs, and for run records in runs/*.json.')), root;
  const stChip = r => r.status === 'stale' ? plainChip('↻', 'Out of date', 'look') : r.status === 'current' ? plainChip('✓', 'Current', 'fine') : plainChip('?', 'No known source', 'ign');
  for (const r of rows) {
    root.append(h('article', { class: 'card rx-ex st-' + r.status },
      h('div', { class: 'rx-ex-h' }, rxNodeBtn(r.node_id, r.name), stChip(r), h('span', { class: 'grow' }), r.made ? h('span', { class: 'muted small' }, 'written ' + absTime(r.made.time) + ' · ', mono(r.made.short)) : null),
      h('dl', { class: 'rx-dl' },
        r.code.length || r.runs.length ? [h('dt', null, 'Made by'), h('dd', null, r.runs.map(x => [rxNodeBtn(x.node_id, x.name), x.command ? h('span', { class: 'muted mono small' }, ' ' + trunc(x.command, 70)) : null, ' ']), r.code.map((x, i) => [i || r.runs.length ? ', ' : null, rxNodeBtn(x.node_id, x.name)]))] : [h('dt', null, 'Made by'), h('dd', { class: 'muted' }, 'Unknown. No script writes a file with this name.')],
        r.settings.length ? [h('dt', null, 'Settings'), h('dd', null, r.settings.map((x, i) => [i ? ', ' : null, rxNodeBtn(x.node_id, x.name)]))] : null,
        h('dt', null, 'Used in'), h('dd', null, r.used_by.length ? r.used_by.map((x, i) => [i ? ', ' : null, rxNodeBtn(x.node_id, x.name)]) : h('span', { class: 'muted' }, 'Nothing in the paper.')),
        r.claims.length ? [h('dt', null, 'Backs'), h('dd', null, r.claims.map((x, i) => [i ? ', ' : null, h('button', { class: 'linkbtn', onclick: () => { RX.open[x.id] = true; RX.filter = 'all'; openTab('claims'); } }, x.label)]))] : null),
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
    h('p', { class: 'muted' }, 'Paste what your advisor, a co-author or a reviewer said. Lemmata splits it into tasks and links each one to the part of the paper or code it is about, and to what else you will need to recheck.'));
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
    h('p', { class: 'muted' }, 'Ask about the claims, the evidence, the history or what a change would affect. Lemmata answers by looking things up in what it has read from your paper and repository. It is a search with rules, not an AI model, so it only tells you what is there.'),
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
