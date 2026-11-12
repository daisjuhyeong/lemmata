/* Lemmata hub pages: landing and tutorial (public site), pair (private hub), sign in with GitHub, projects, new project,
   account. Plain JS, no build, no CDN. Contracts: wiki/sprints/S04/S04-brief.md, wiki/sprints/S07/S07-brief.md. */
'use strict';
(function () {
  const root = document.getElementById('root'), who = document.getElementById('who');
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const k in attrs || {}) {
      const v = attrs[k];
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k === 'style') el.style.cssText = v;   // CSSOM, allowed under a no-inline-style CSP (setAttribute would not be)
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const c of kids.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : document.createTextNode(String(c)));
    return el;
  }
  const clear = el => { while (el.firstChild) el.removeChild(el.firstChild); return el; };
  const plural = (n, a, b) => n + ' ' + (n === 1 ? a : (b || a + 's'));

  async function api(method, path, body) {
    const opt = { method, cache: 'no-store', headers: {} };
    if (body !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
    let r;
    try { r = await fetch(path, opt); } catch (e) { const x = new Error('Cannot reach the Lemmata server.'); x.network = true; throw x; }
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      // errors are {error:{code,message}}; a switched-off feature answers {error:"feature_disabled"}
      const str = typeof j.error === 'string' ? j.error : null;
      const e = new Error((j.error && j.error.message) || (str === 'feature_disabled' ? 'That option is switched off.' : 'HTTP ' + r.status));
      e.status = r.status; e.code = str || (j.error && j.error.code); throw e;
    }
    return j;
  }

  /* ---------- state ---------- */
  const S = { status: null, view: 'home', gh: null, flow: null, pollTimer: null, error: null, flowKind: 'github', privateRepos: true };
  const lsGet = (k, d) => { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } };
  const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } };
  const isPublic = () => S.status && S.status.mode === 'public';
  function track(event, extra) {   // usage events for the start-view comparison; never blocks the page
    if (!S.status || !S.status.authenticated) return;
    api('POST', '/api/hub/events', Object.assign({ event }, extra || {})).catch(() => { });
  }
  /* The four ways Lemmata can help. One is assigned as the start view when an account is created (round-robin, so the
     groups stay the same size); the person can change it at any time, and that choice is the more interesting signal. */
  const VIEWS = [
    { k: 'claims', glyph: '◆', name: 'Claim map', one: 'Is every statement backed up?',
      what: 'Your core message at the top, each claim under it, and what backs it: a proof, an assumption, a table traced to a result file and the script that made it. Green, amber or red per claim.' },
    { k: 'inbox', glyph: '↻', name: 'Recheck inbox', one: 'What do I need to look at again?',
      what: 'After each change in the code or the paper, a short list of the tables, figures and sections that may no longer match, with the reason.' },
    { k: 'timeline', glyph: '⚑', name: 'Research timeline', one: 'How did this work get here?',
      what: 'The commit history grouped into readable steps and decisions, so you (or a new lab member) can get on and off the project.' },
    { k: 'ask', glyph: '?', name: 'Ask Lemmata', one: 'Let me just ask.',
      what: 'A question box over the project: what supports this claim, what breaks if I change this file, which results are out of date. Answers link to the evidence.' },
  ];
  const viewOf = k => VIEWS.find(v => v.k === k) || VIEWS[0];

  function pairedOf(st) { return st.authenticated !== undefined ? !!st.authenticated : (st.paired !== undefined ? !!st.paired : !!st.session); }
  function ghUser(st) {
    const g = st.github;
    if (g && g.user) return g.user;
    if (st.user) return st.user;
    if (g && g.login) return g;
    return null;
  }

  async function boot() {
    try { S.status = await api('GET', '/api/hub/status'); }
    catch (e) { return showFatal(e); }
    route();
  }
  function route() {
    stopPoll();
    document.body.classList.remove('wide');
    const bsub = document.getElementById('bsub'); if (bsub) bsub.textContent = '';
    renderWho();
    if (!pairedOf(S.status)) return isPublic() ? viewLanding() : viewPair();
    const u = ghUser(S.status);
    if (u && S.view === 'home' && !lsGet('lemmata.welcomed.' + u.login, false)) S.view = 'welcome';
    if (S.view === 'welcome') return viewWelcome();
    if (S.view === 'account') return viewAccount();
    if (S.view === 'new') return viewNew();
    return viewHome();
  }
  function renderWho() {
    clear(who);
    const u = pairedOf(S.status) && ghUser(S.status);
    if (!u) return;
    who.append(...[h('button', { class: 'linkbtn', onclick: () => { S.view = 'welcome'; route(); } }, 'How it works'),
      u.avatar_url ? h('img', { src: u.avatar_url, alt: '', onerror: ev => ev.target.remove() }) : null,
      h('button', { class: 'linkbtn', id: 'account', onclick: () => { S.view = 'account'; route(); } }, h('b', null, u.login)),
      h('button', { class: 'btn sm', onclick: signOut }, 'Sign out')].filter(Boolean));
  }
  function showFatal(e) {
    clear(root).append(h('h1', null, 'Lemmata'), h('div', { class: 'alert', role: 'alert' }, h('b', null, '✕ Cannot reach the server. '), e.message),
      h('div', { class: 'acts' }, h('button', { class: 'btn', onclick: boot }, 'Retry')));
  }
  function errBox(msg) { return msg ? h('div', { class: 'alert', role: 'alert' }, h('b', null, '✕ '), msg) : null; }
  function focusRoot() { root.focus(); }

  /* ---------- pairing ---------- */
  const CODE_OK = /[^ABCDEFGHJKMNPQRSTUVWXYZ23456789]/g;
  function viewPair(err) {
    clear(root);
    const input = h('input', { type: 'text', class: 'paircode', id: 'code', maxlength: '8', autocomplete: 'off', autocapitalize: 'characters', spellcheck: 'false', 'aria-label': 'Pairing code' });
    const btn = h('button', { class: 'btn primary', id: 'pair-go', disabled: true }, 'Pair this device');
    const msg = h('div', { id: 'pair-err' }, errBox(err));
    input.addEventListener('input', () => {
      input.value = input.value.toUpperCase().replace(CODE_OK, '').slice(0, 8);
      btn.disabled = input.value.length !== 8;
    });
    const go = async () => {
      if (input.value.length !== 8) return;
      btn.disabled = true; btn.textContent = 'Pairing…';
      try {
        await api('POST', '/api/hub/pair', { code: input.value, device: deviceName() });
        S.status = await api('GET', '/api/hub/status');
        route();
      } catch (e) {
        clear(msg).append(errBox(e.status === 429 ? 'Too many wrong codes. Run lemmata hub pair-code again to get a new one.'
          : e.status === 400 || e.status === 401 || e.status === 403 ? 'That code is wrong or has expired. Codes last 10 minutes and work once.' : e.message));
        btn.disabled = input.value.length !== 8; btn.textContent = 'Pair this device';
      }
    };
    btn.addEventListener('click', go);
    input.addEventListener('keydown', ev => { if (ev.key === 'Enter') go(); });
    root.append(
      h('h1', null, 'Connect this device'),
      h('p', { class: 'muted' }, 'This Lemmata server only talks to devices you have paired.'),
      h('div', { class: 'card' },
        h('p', null, 'Run ', h('span', { class: 'cmd' }, 'lemmata hub pair-code'), ' on the Mac mini to get a code.'),
        msg, input, h('div', { class: 'acts' }, btn)));
    input.focus();
  }
  function deviceName() {
    const ua = navigator.userAgent || '';
    return /Macintosh|Mac OS/.test(ua) ? 'MacBook' : /Windows/.test(ua) ? 'Windows PC' : /Linux/.test(ua) ? 'Linux PC' : 'Browser';
  }

  /* ---------- GitHub sign-in (device flow) ---------- */
  function stopPoll() { clearTimeout(S.pollTimer); S.pollTimer = null; S.polling = false; }
  /* kind: 'github' = connect GitHub inside a session (private hub, or reconnect on the public site);
           'login'  = sign in to the public site (no session yet). onDone runs after GitHub approves. */
  function signInCard(box, err, opts) {
    opts = opts || S.flowOpts || {};
    S.flowOpts = opts;
    clear(box);
    if (S.flow) return flowCard(box);
    const priv = h('input', { type: 'radio', name: 'scope', id: 'scope-private', checked: S.privateRepos, onchange: () => { S.privateRepos = true; } });
    const pubOnly = h('input', { type: 'radio', name: 'scope', id: 'scope-public', checked: !S.privateRepos, onchange: () => { S.privateRepos = false; } });
    box.append(h('div', { class: 'card', id: 'signin-card' },
      h('h2', null, opts.title || 'Sign in with GitHub'),
      h('p', null, opts.text || 'Signing in lets Lemmata see your GitHub repositories, so you can pick your code and your paper from a list.'),
      opts.reconnect ? null : h('div', { class: 'scopes' },
        h('label', null, priv, h('span', null, h('b', null, 'Private and public repositories'), h('br'),
          h('span', { class: 'muted small' }, 'GitHub will ask for access to your repositories. Lemmata only ever reads them; it never pushes, opens issues or changes settings.'))),
        h('label', null, pubOnly, h('span', null, h('b', null, 'Public repositories only'), h('br'),
          h('span', { class: 'muted small' }, 'GitHub is asked only who you are. Choose this to try Lemmata on open-source work without granting repository access.')))),
      errBox(err),
      h('div', { class: 'acts' }, h('button', { class: 'btn primary', id: 'gh-start', onclick: () => startFlow(box) }, opts.button || 'Sign in with GitHub'))));
  }
  async function startFlow(box) {
    const o = S.flowOpts || {};
    try { S.flow = await api('POST', o.kind === 'login' ? '/api/hub/login/start' : '/api/hub/github/start', { private_repos: !!S.privateRepos }); }
    catch (e) { return signInCard(box, e.code === 'no_client_id' || e.status === 412 ? 'GitHub sign-in is not set up on the server yet. Run lemmata hub config --github-client-id <id> on the Mac mini.' : e.message); }
    S.flow.t0 = Date.now();
    flowCard(box);
    schedulePoll(box);
  }
  function flowCard(box, end) {
    clear(box);
    const f = S.flow;
    const copyBtn = h('button', { class: 'btn', id: 'gh-copy', onclick: async () => { await copyText(f.user_code); copyBtn.textContent = 'Copied'; setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1500); } }, 'Copy');
    const card = h('div', { class: 'card', 'aria-live': 'polite' }, h('h2', null, (S.flowOpts && S.flowOpts.title) || 'Sign in with GitHub'));
    if (end) {
      card.append(errBox(end), h('div', { class: 'acts' }, h('button', { class: 'btn primary', id: 'gh-retry', onclick: () => { S.flow = null; startFlow(box); } }, 'Retry')));
    } else {
      card.append(
        h('p', null, 'Open GitHub in a new tab, enter this code there and approve. This page continues on its own.'),
        h('div', { class: 'usercode', id: 'usercode' }, f.user_code),
        h('div', { class: 'row' }, copyBtn,
          h('a', { class: 'btn primary', id: 'gh-open', href: f.verification_uri, target: '_blank', rel: 'noopener noreferrer' }, 'Open GitHub ↗')),
        h('p', { class: 'muted', style: 'margin-top:12px' }, 'Waiting for you to approve on GitHub… ', h('button', { class: 'linkbtn', onclick: () => { S.flow = null; stopPoll(); signInCard(box); } }, 'Cancel')));
    }
    box.append(card);
  }
  async function copyText(t) {
    try { if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(t); return; } } catch (e) { /* fall through */ }
    const ta = h('textarea', { 'aria-hidden': 'true', style: 'position:fixed;left:-999px' }); ta.value = t; document.body.append(ta); ta.select();
    try { document.execCommand('copy'); } catch (e) { /* user can select the code by hand */ }
    ta.remove();
  }
  function schedulePoll(box) {
    stopPoll(); S.polling = true;
    const wait = Math.max(1, (S.flow && S.flow.interval) || 5) * 1000;
    S.pollTimer = setTimeout(async () => {
      if (!S.flow) return;
      if (Date.now() - S.flow.t0 > (S.flow.expires_in || 900) * 1000) return flowCard(box, 'The code expired before it was used.');
      let r;
      const o = S.flowOpts || {};
      try { r = await api('GET', o.kind === 'login' ? '/api/hub/login/poll?flow=' + encodeURIComponent(S.flow.flow) : '/api/hub/github/poll'); }
      catch (e) { if (e.network || e.status === 429) return schedulePoll(box); return flowCard(box, e.code === 'not_owner' ? 'This server belongs to another GitHub account.' : e.message); }
      if (r.state === 'ok') {
        S.flow = null; S.flowOpts = null; S.status = await api('GET', '/api/hub/status');
        if (o.onDone) return o.onDone();
        return route();
      }
      if (r.state === 'denied') return flowCard(box, 'GitHub sign-in was denied.');
      if (r.state === 'expired') return flowCard(box, 'The code expired before it was used.');
      if (r.state === 'error') return flowCard(box, r.message || 'GitHub reported an error.');
      schedulePoll(box);
    }, wait);
  }
  async function signOut() {
    try { await api('POST', '/api/hub/github/logout', {}); } catch (e) { /* show fresh status either way */ }
    S.flow = null; S.flowOpts = null;
    try { S.status = await api('GET', '/api/hub/status'); } catch (e) { return showFatal(e); }
    S.view = 'home'; route();
  }

  /* ---------- projects ---------- */
  function ago(t) {
    if (!t) return 'never';
    const d = (Date.now() - Date.parse(t)) / 1000;
    if (isNaN(d)) return t;
    if (d < 90) return 'just now';
    if (d < 3600) return Math.round(d / 60) + ' min ago';
    if (d < 86400) return Math.round(d / 3600) + ' h ago';
    return Math.round(d / 86400) + ' days ago';
  }
  /* The paper source, in words. */
  function paperWords(p) {
    const ps = p.paper_source || {}, v = p.paper_versions || 0;
    if (ps.kind === 'github') {
      const same = ps.repo === p.code_repo;
      if (ps.subdir) return 'Paper: the folder ' + ps.subdir + '/ ' + (same ? 'in your code repo' : 'in ' + ps.repo) + ' (GitHub)';
      return 'Paper: GitHub repo ' + ps.repo;
    }
    if (ps.kind === 'overleaf') return 'Paper: Overleaf project (no longer supported here)';
    return v ? 'Paper: uploaded zip, version ' + v : 'No paper yet';
  }
  async function viewHome() {
    clear(root);
    const user = ghUser(S.status);
    const head = h('div', { class: 'pagehead' }, h('h1', { class: 'grow' }, 'Projects'),
      user ? h('button', { class: 'btn primary', id: 'new-project', onclick: () => { S.view = 'new'; route(); } }, 'New project') : null);
    const signin = h('div', { id: 'signin' });
    const list = h('div', { id: 'plist' }, h('p', { class: 'muted' }, 'Loading…'));
    root.append(head);
    if (!user) { root.append(signin); signInCard(signin, null, { kind: 'github' }); }
    else if (S.status.github_needs_reauth) { root.append(signin); reconnectCard(signin, () => { S.view = 'home'; route(); }); }
    root.append(list);
    try {
      const r = await api('GET', '/api/hub/projects');
      clear(list);
      if (!r.projects.length) {
        list.append(h('div', { class: 'well' }, h('strong', null, 'No projects yet'), h('br'),
          user ? 'A project is your code on GitHub plus your paper. Press New project to start.' : 'Sign in with GitHub first, then pick your code repository.'));
      }
      for (const p of r.projects) list.append(projRow(p));
    } catch (e) {
      if (e.status === 401) { S.status = await api('GET', '/api/hub/status').catch(() => S.status); return route(); }
      clear(list).append(errBox(e.message));
    }
  }
  /* GitHub stopped accepting the saved sign-in (revoked, or expired by an organisation). The Lemmata session is fine:
     reconnect in place, no sign-out, nothing else is lost. */
  function reconnectCard(box, onDone) {
    const u = ghUser(S.status) || {};
    signInCard(box, null, { kind: 'github', reconnect: true, onDone, title: 'Reconnect GitHub', button: 'Reconnect GitHub',
      text: 'GitHub no longer accepts the sign-in Lemmata saved for ' + (u.login || 'you') + ', so your projects cannot sync. This happens when access was revoked on GitHub or an organisation expired it. Reconnecting takes a few seconds; you stay signed in here and your projects are untouched.' });
  }
  function claimChips(cl) {
    if (!cl || !cl.total) return null;
    return [cl.unsupported ? h('span', { class: 'chip bad' }, '✕ ' + plural(cl.unsupported, 'claim') + ' not backed up') : null,
      cl.partial ? h('span', { class: 'chip recheck' }, '◐ ' + cl.partial + ' partly') : null,
      h('span', { class: 'chip ok' }, '✓ ' + cl.supported + ' of ' + cl.total + ' claims supported')];
  }
  function projRow(p) {
    const c = p.counts || { recheck: 0, findings: 0 };
    const none = !(p.paper_source && p.paper_source.kind === 'github') && !(p.paper_versions || 0);
    return h('div', { class: 'proj' },
      h('div', { class: 'grow' },
        h('div', { class: 'nm' }, p.name),
        h('div', { class: 'meta' },
          h('span', null, 'Code: ', h('span', { class: 'mono' }, p.code_repo + (p.branch ? ' (' + p.branch + ')' : ''))),
          h('span', { class: none ? 'warn' : '' }, paperWords(p)),
          h('span', null, 'Last synced ' + ago(p.last_sync))),
        h('div', { class: 'meta' },
          c.recheck ? h('span', { class: 'chip recheck' }, '↻ ' + plural(c.recheck, 'thing') + ' to look at') : h('span', { class: 'chip ok' }, '✓ Nothing to look at'),
          c.findings ? h('span', { class: 'chip bad' }, plural(c.findings, 'check') + ' about your paper') : null, claimChips(c.claims)),
        h('label', { class: 'meta opt' },
          h('input', { type: 'checkbox', checked: !!p.online_refs, 'aria-label': 'Check references online',
            onchange: async ev => { const box = ev.target; box.disabled = true; try { await api('PATCH', '/api/hub/projects/' + encodeURIComponent(p.id), { online_refs: box.checked }); } catch (e) { box.checked = !box.checked; alert(e.message); } box.disabled = false; } }),
          ' Look up my references online (sends their titles and DOIs to OpenAlex and Crossref)')),
      h('a', { class: 'btn', href: '/p/' + encodeURIComponent(p.id) + '/', 'aria-label': 'Open ' + p.name, onclick: () => track('project_opened', { project: p.id }) }, 'Open'));
  }

  /* ---------- new project ---------- */
  function repoPicker(id, label, onPick) {
    const list = h('ul', { class: 'repos', id, 'aria-label': label });
    const search = h('input', { type: 'search', id: id + '-q', placeholder: 'Search your repositories', 'aria-label': 'Search: ' + label, autocomplete: 'off' });
    const refresh = h('button', { class: 'linkbtn small', onclick: () => load(search.value.trim(), true) }, 'Refresh the list from GitHub');
    const box = h('div', null, search, list, h('div', { class: 'errslot' }), h('div', { class: 'muted small' }, 'Missing a repository? ', refresh));
    let timer = null, seq = 0, picked = null;
    const errs = box.querySelector('.errslot');
    async function load(q, fresh) {
      const my = ++seq;
      clear(list).append(h('li', { class: 'muted pad' }, 'Loading repositories…'));
      try {
        const r = await api('GET', '/api/hub/github/repos?q=' + encodeURIComponent(q || '') + (fresh ? '&refresh=1' : ''));
        if (my !== seq) return;
        clear(list); clear(errs);
        if (!r.repos.length) list.append(h('li', { class: 'muted pad' }, q ? 'No repository matches “' + q + '”. Type part of its name, not a link.' :
          (S.status.user && S.status.user.private_repos === false ? 'No public repositories found. You signed in for public repositories only; sign out and choose private access to see the rest.' : 'No repositories found.')));
        for (const rp of r.repos) {
          const b = h('button', { 'aria-pressed': String(!!picked && picked.full_name === rp.full_name), onclick: () => {
            picked = rp; onPick(rp);
            for (const x of list.querySelectorAll('button')) x.setAttribute('aria-pressed', String(x === b)); } },
            h('span', { class: 'grow' }, h('div', { class: 'mono' }, rp.full_name), rp.description ? h('div', { class: 'desc' }, rp.description) : null),
            rp.private ? h('span', { class: 'chip plain' }, 'Private') : null,
            h('span', { class: 'muted small' }, rp.pushed_at ? 'updated ' + ago(rp.pushed_at) : ''));
          list.append(h('li', null, b));
        }
      } catch (e) {
        if (my !== seq) return;
        clear(list); clear(errs);
        if (e.code === 'github_token_invalid' || e.code === 'not_signed_in') {
          // reconnect right here: the half-filled form stays, and the list reloads when GitHub approves
          S.status.github_needs_reauth = true;
          S.reauthWaiters = S.reauthWaiters || [];
          S.reauthWaiters.push(() => { clear(errs); load(search.value.trim(), true); });
          if (document.getElementById('signin-card')) errs.append(h('div', { class: 'muted small' }, 'Waiting for GitHub to be reconnected (above).'));
          else {   // one card for the whole page, however many lists are waiting on it
            const slot = h('div'); errs.append(slot);
            reconnectCard(slot, () => { const w = S.reauthWaiters || []; S.reauthWaiters = []; S.status.github_needs_reauth = false; w.forEach(f => f()); });
          }
        } else if (e.status === 401) errs.append(errBox('Your Lemmata session ended. Reload the page and sign in again.'));
        else errs.append(errBox(e.message), h('button', { class: 'btn sm', onclick: () => load(search.value.trim(), true) }, 'Try again'));
      }
    }
    search.addEventListener('input', () => {
      const m = search.value.match(/github\.com\/([^\/\s]+\/[^\/\s#?]+)/i);   // a pasted GitHub link becomes owner/name
      if (m) search.value = m[1].replace(/\.git$/, '');
      clearTimeout(timer); timer = setTimeout(() => load(search.value.trim()), 250);
    });
    return { box, load, search, get picked() { return picked; } };
  }
  function viewNew() {
    clear(root);
    let zip = null, mode = 'repo', busy = false;
    const errs = h('div');
    const createBtn = h('button', { class: 'btn primary', id: 'create', disabled: true }, 'Create project');
    const code = repoPicker('repos', 'Your GitHub repositories', () => { createBtn.disabled = busy; });
    const paper = repoPicker('paper-repos', 'GitHub repositories for the paper', () => { clear(errs); });
    const sub = h('input', { type: 'text', id: 'paper-subdir', value: 'paper', autocomplete: 'off', spellcheck: 'false', 'aria-label': 'Folder of the paper inside the code repository' });
    const dropMsg = h('div'); const fileIn = h('input', { type: 'file', accept: '.zip,application/zip', class: 'hidden', id: 'zipfile' });
    const drop = h('div', { class: 'drop', id: 'drop' }, dropMsg);
    const progress = h('div', { class: 'hidden', id: 'progress' });
    const form = h('div');
    const repoBox = h('div', { id: 'paper-repo-box' }), folderBox = h('div', { id: 'paper-folder-box' }), zipBox = h('div', { id: 'zip-box' });
    const tabs = h('div', { class: 'seg', role: 'group', 'aria-label': 'Where your paper lives' });
    const MODES = [['repo', 'A GitHub repo of its own'], ['folder', 'A folder in the code repo'], ['zip', 'Upload a zip instead']];
    function paintMode() {
      clear(tabs).append(...MODES.map(([k, label]) =>
        h('button', { class: 'btn sm', 'aria-pressed': String(mode === k), onclick: () => { mode = k; clear(errs); paintMode(); } }, label)));
      repoBox.classList.toggle('hidden', mode !== 'repo'); folderBox.classList.toggle('hidden', mode !== 'folder'); zipBox.classList.toggle('hidden', mode !== 'zip');
    }
    function paintDrop() {
      clear(dropMsg);
      drop.classList.toggle('has', !!zip);
      if (zip) dropMsg.append(h('div', null, '✓ ', h('b', { class: 'mono' }, zip.name), ' ', h('span', { class: 'muted' }, '(' + (zip.size / 1048576).toFixed(1) + ' MB)')),
        h('div', { class: 'gap' }, h('button', { class: 'linkbtn', onclick: () => { zip = null; paintDrop(); } }, 'Remove')));
      else dropMsg.append(h('div', null, 'Drop the zip of your paper folder here'), h('div', { class: 'muted gap' }, 'or'),
        h('button', { class: 'btn sm', onclick: () => fileIn.click() }, 'Choose a zip file…'));
    }
    function setZip(f) {
      if (!f) return;
      if (!/\.zip$/i.test(f.name) && f.type !== 'application/zip') { clear(errs).append(errBox('That is not a .zip file. Zip the folder that holds your main .tex file and upload that.')); return; }
      if (f.size > 100 * 1048576) { clear(errs).append(errBox('That zip is larger than 100 MB. Leave large data or figures you do not need out of it.')); return; }
      clear(errs); zip = f; paintDrop();
    }
    fileIn.addEventListener('change', () => { setZip(fileIn.files[0]); fileIn.value = ''; });
    for (const ev of ['dragenter', 'dragover']) drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); });
    for (const ev of ['dragleave', 'drop']) drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); });
    drop.addEventListener('drop', e => setZip(e.dataTransfer.files[0]));
    // a drop outside the box must not navigate the window away to the zip
    for (const ev of ['dragover', 'drop']) window.addEventListener(ev, e => e.preventDefault());
    paintDrop();

    let paperKind = 'none';   // fixed when Create is pressed: none | github | zip
    function paintProgress(state, detail) {   // state: {clone, paper} each wait|active|done|fail|skip
      const rows = [['clone', 'Copying your code from GitHub and reading it'],
        ['paper', paperKind === 'github' ? 'Copying your paper from GitHub' : 'Uploading your paper']].filter(s => !(s[0] === 'paper' && paperKind !== 'zip'));
      clear(progress).append(h('h2', null, 'Creating ' + code.picked.full_name), h('ul', { class: 'steps', 'aria-live': 'polite' },
        rows.map(([k, label]) => {
          const st = state[k];
          return h('li', { class: st }, h('span', { class: 'ic' }, st === 'done' ? '✓' : st === 'fail' ? '✕' : st === 'active' ? '…' : '·'), label,
            k === 'paper' && st === 'active' && typeof detail === 'number' ? h('span', { class: 'bar', role: 'progressbar', 'aria-valuenow': String(detail) }, h('i', { style: 'width:' + detail + '%' })) : null);
        })), detail && typeof detail === 'object' ? detail : []);
    }
    const PLAIN = {
      paper_repo_not_found: 'GitHub has no repository with that name that you can read. Check the name, or sign in again.',
      paper_branch_not_found: 'That repository has no branch with that name.',
      paper_subdir_missing: 'The code repo has no folder with that name. Type the folder that holds your main .tex file, for example paper.',
      paper_too_large: 'That paper repository is too large to copy.',
      feature_disabled: 'That option is switched off.'
    };
    const plain = e => PLAIN[e.code] || e.message;
    function back() { busy = false; progress.classList.add('hidden'); form.classList.remove('hidden'); createBtn.disabled = false; }
    async function create() {
      const cp = code.picked;
      if (!cp || busy) return;
      const body = { code_repo: cp.full_name, branch: cp.default_branch };
      paperKind = 'none';
      if (mode === 'repo' && paper.picked) {
        paperKind = 'github'; body.paper_repo = paper.picked.full_name; body.paper_branch = paper.picked.default_branch;
      } else if (mode === 'folder') {
        const sd = sub.value.trim().replace(/^\/+|\/+$/g, '');
        if (!sd) { clear(errs).append(errBox('Type the name of the folder that holds your paper, for example paper.')); return; }
        paperKind = 'github'; body.paper_repo = cp.full_name; body.paper_subdir = sd;
      } else if (mode === 'zip' && zip) paperKind = 'zip';
      busy = true; createBtn.disabled = true; clear(errs);
      form.classList.add('hidden'); progress.classList.remove('hidden');
      const st = { clone: 'active', paper: 'wait' };
      paintProgress(st);
      let proj;
      try { const r = await api('POST', '/api/hub/projects', body); proj = r.project || r; }
      catch (e) {
        st.clone = 'fail'; paintProgress(st, h('div', null, errBox(plain(e)), h('div', { class: 'acts' }, h('button', { class: 'btn primary', id: 'back', onclick: back }, 'Back'))));
        return;
      }
      st.clone = 'done';
      if (paperKind !== 'zip') { st.paper = 'skip'; paintProgress(st); return openProject(proj); }
      const attempt = async () => {
        st.paper = 'active'; paintProgress(st, 0);
        try { await uploadZip(proj.id, zip, pct => paintProgress(st, pct)); st.paper = 'done'; paintProgress(st); openProject(proj); }
        catch (e) {
          st.paper = 'fail';
          paintProgress(st, h('div', null, errBox('Your project was created, but the paper could not be added. ' + e.message),
            h('div', { class: 'acts' }, h('a', { class: 'btn primary', href: '/p/' + encodeURIComponent(proj.id) + '/' }, 'Open the project anyway'),
              h('button', { class: 'btn', id: 'retry-paper', onclick: attempt }, 'Try again'))));
        }
      };
      attempt();
    }
    function openProject(p) { setTimeout(() => { location.href = '/p/' + encodeURIComponent(p.id) + '/'; }, 600); }
    createBtn.addEventListener('click', create);

    form.append(
      h('div', { class: 'crumb' }, h('button', { class: 'linkbtn', onclick: () => { S.view = 'home'; route(); } }, '← Projects')),
      h('h1', null, 'New project'),
      h('h3', null, 'Step 1 · Your code'),
      h('p', { class: 'muted' }, 'Pick the GitHub repository with your experiments: scripts, settings and results.'),
      code.box,
      h('h3', null, 'Step 2 · Your paper (you can add it later)'),
      h('p', { class: 'muted' }, 'Where is the LaTeX source of your paper?'),
      tabs, repoBox, folderBox, zipBox, errs,
      h('div', { class: 'acts' }, createBtn));
    repoBox.append(
      h('p', { class: 'muted' }, 'Your LaTeX paper in its own GitHub repo. Pick it below. Lemmata reads the .tex files as they are on GitHub; it does not compile them.'),
      paper.box);
    folderBox.append(
      h('p', { class: 'muted' }, 'Your paper sits in a folder inside the code repo you picked in step 1. Type that folder’s name.'),
      h('label', { class: 'field' }, h('span', null, 'Folder name'), sub));
    zipBox.append(h('p', { class: 'muted' }, 'For a paper that lives in Overleaf: in Overleaf choose Menu → Download → Source and drop that zip here. It is a snapshot. Lemmata reads the claims, proofs, tables and figures from it, but will not see later edits until you upload a new zip.'), drop, fileIn);
    paintMode();
    root.append(form, progress);
    code.load(''); paper.load('');
    code.search.focus();
  }
  function uploadZip(pid, file, onPct) {
    return new Promise((resolve, reject) => {
      const x = new XMLHttpRequest();
      x.open('POST', '/api/hub/projects/' + encodeURIComponent(pid) + '/paper');
      x.setRequestHeader('Content-Type', 'application/zip');
      x.upload.onprogress = e => { if (e.lengthComputable) onPct(Math.round(100 * e.loaded / e.total)); };
      x.onload = () => {
        let j = {}; try { j = JSON.parse(x.responseText); } catch (e) { /* keep empty */ }
        if (x.status >= 200 && x.status < 300) resolve(j); else reject(new Error((j.error && j.error.message) || ('HTTP ' + x.status)));
      };
      x.onerror = () => reject(new Error('Cannot reach the Lemmata server.'));
      x.send(file);
    });
  }

  /* ---------- landing (public site, not signed in) ---------- */
  function howSteps() {
    const steps = [
      ['1', 'Connect', 'Sign in with GitHub and pick the repository with your code, and your paper if it is on GitHub (or upload the LaTeX source as a zip).'],
      ['2', 'Lemmata reads', 'It reads the LaTeX and the repository and links them: claim → theorem and proof, claim → table → result file → script → settings. Nothing is run and nothing is changed.'],
      ['3', 'You confirm', 'Lemmata drafts the claims and what backs them. You accept, edit or reject each one. Only what you confirm counts.'],
      ['4', 'It keeps watch', 'When a commit changes something a claim rests on, Lemmata says which claims, tables and sections to recheck, and why.'],
    ];
    return h('ol', { class: 'how' }, steps.map(([n, t, d]) => h('li', null, h('span', { class: 'n' }, n), h('div', null, h('b', null, t), h('br'), h('span', { class: 'muted' }, d)))));
  }
  function waysGrid(sel, onPick) {
    return h('div', { class: 'ways', role: onPick ? 'radiogroup' : null }, VIEWS.map(v => {
      const body = [h('div', { class: 'wg' }, v.glyph), h('div', { class: 'wn' }, v.name), h('div', { class: 'wq' }, '“' + v.one + '”'), h('div', { class: 'muted small' }, v.what)];
      if (!onPick) return h('div', { class: 'way' }, body);
      return h('button', { class: 'way' + (sel === v.k ? ' on' : ''), role: 'radio', 'aria-checked': String(sel === v.k), id: 'way-' + v.k, onclick: () => onPick(v.k) }, body,
        sel === v.k ? h('div', { class: 'chip ok', style: 'margin-top:8px' }, '✓ Opens first') : null);
    }));
  }
  function privacyList() {
    return h('ul', { class: 'plain' },
      h('li', null, h('b', null, 'Read-only. '), 'Lemmata copies the repositories you pick and reads them. It never pushes, never runs your code and never compiles your paper.'),
      h('li', null, h('b', null, 'Yours only. '), 'Nobody else who signs in here can see your projects. The copies are stored on the research server that runs this site; delete a project or your whole account at any time from Account.'),
      h('li', null, h('b', null, 'No AI model reads your work here. '), 'The links and checks are computed with rules. If you want an AI to reason over them, connect your own Claude Code to Lemmata; it then runs on your plan, on your machine.'),
      h('li', null, h('b', null, 'What is counted. '), 'Which view you open and whether you confirm claims or add feedback, as anonymous counts, to learn which way of helping works. Never file names, text or code.'));
  }
  function viewLanding() {
    clear(root);
    document.body.classList.add('wide');
    const signin = h('div', { id: 'signin' });
    // S18: the tagline sits in the band; the page is one sentence, the numbered steps, then the one sign-in button
    const bsub = document.getElementById('bsub'); if (bsub) bsub.textContent = 'Know what your paper claims, and whether your repository still backs it up.';
    root.append(
      h('div', { class: 'hero' },
        h('p', { class: 'lede' }, 'Lemmata reads your LaTeX and your GitHub repository together. It lays out the core message, the claims under it, and the proof, experiment and result file behind each one, then tells you what to recheck when something changes.'),
        h('p', { class: 'muted' }, 'Use AI, don’t depend on it: Lemmata shows you the evidence and where it is missing. You decide what is true.')),
      h('h2', null, 'How it works'), howSteps(),
      signin,
      h('h2', null, 'Four ways it can help'), waysGrid(),
      h('h2', null, 'Before you sign in'), privacyList(),
      h('p', { class: 'muted small', style: 'margin-top:24px' }, S.status.signup === 'invite' ? 'This site is invite-only for now. If GitHub sign-in is refused, ask the person who sent you the link to add your GitHub name.' : ''));
    signInCard(signin, null, { kind: 'login', title: 'Start with GitHub', button: 'Sign in with GitHub',
      text: 'No separate account or password. Choose how much Lemmata may see:' });
  }

  /* ---------- welcome: tutorial + choose how Lemmata should help ---------- */
  function viewWelcome() {
    clear(root);
    document.body.classList.add('wide');
    const u = ghUser(S.status) || {};
    const first = !lsGet('lemmata.welcomed.' + u.login, false);
    let sel = S.status.start_view || 'claims';
    const assigned = S.status.variant;
    if (first) track('tutorial_shown', { view: sel });
    const grid = h('div');
    const paint = () => clear(grid).append(waysGrid(sel, async k => {
      if (k === sel) return;
      sel = k; paint();
      try { await api('POST', '/api/hub/prefs', { view: k }); S.status.start_view = k; } catch (e) { /* the choice still applies in this browser */ }
    }));
    paint();
    const done = (skipped) => {
      lsSet('lemmata.welcomed.' + u.login, true);
      if (first) track(skipped ? 'tutorial_skipped' : 'tutorial_done', { view: sel });
      S.view = 'home'; route();
    };
    root.append(
      h('div', { class: 'row' }, h('h1', { class: 'grow' }, first ? 'Welcome, ' + (u.name || u.login || '') + '.' : 'How Lemmata works'),
        h('button', { class: 'linkbtn', id: 'skip', onclick: () => done(true) }, first ? 'Skip' : 'Back to projects')),
      h('p', { class: 'lede' }, 'A research project is a chain: a message, the claims that carry it, and the proofs, experiments and files that carry the claims. Lemmata keeps that chain in view while the code and the paper keep changing.'),
      h('h3', null, 'What happens'), howSteps(),
      h('h3', null, 'An example'),
      h('div', { class: 'card example' },
        h('div', { class: 'ex-claim' }, h('span', { class: 'chip recheck' }, '↻ Recheck'), ' ', h('b', null, 'Contribution 2. '), '“Our delay-aware metric changes the ranking of the detectors.”'),
        h('div', { class: 'ex-chain mono' }, 'Table 3  ←  results/ranking.csv  ←  evaluate.py  ←  config.yaml'),
        h('div', { class: 'muted small' }, 'evaluate.py was changed on 8 Nov (“switch metric to delay-aware F1”), after results/ranking.csv was last written. The table may show old numbers. Rerun, or mark it as fine.')),
      h('h3', null, 'How should Lemmata help you first?'),
      h('p', { class: 'muted' }, 'All four are always available inside a project. Pick the one a project should open on.' +
        (assigned ? ' We started you on ' + viewOf(assigned).name + '; we are comparing which starting point is most useful, so change it if another fits you better.' : '')),
      grid,
      h('div', { class: 'acts' }, h('button', { class: 'btn primary', id: 'welcome-go', onclick: () => done(false) }, first ? 'Connect my first project' : 'Done')));
  }

  /* ---------- account ---------- */
  async function viewAccount() {
    clear(root);
    const u = ghUser(S.status) || {};
    const tokBox = h('div', null, h('p', { class: 'muted' }, 'Loading…')), abBox = h('div');
    let sel = S.status.start_view || 'claims';
    const grid = h('div');
    const paint = () => clear(grid).append(waysGrid(sel, async k => { sel = k; paint(); try { await api('POST', '/api/hub/prefs', { view: k }); S.status.start_view = k; } catch (e) { alert(e.message); } }));
    paint();
    async function paintTokens(shown) {
      let r;
      try { r = await api('GET', '/api/hub/tokens'); } catch (e) { clear(tokBox).append(errBox(e.message)); return; }
      const name = h('input', { type: 'text', value: 'Claude Code', 'aria-label': 'Token name', style: 'max-width:240px' });
      clear(tokBox).append(
        shown ? h('div', { class: 'notice' }, h('b', null, 'Copy this now. It is shown once.'),
          h('pre', { class: 'cmdblock', id: 'mcp-cmd' }, 'claude mcp add --scope user --transport http lemmata ' + shown.mcp_url + ' --header "Authorization: Bearer ' + shown.token + '"'),
          h('div', { class: 'muted small' }, 'Run it in a terminal. Then ask Claude Code, for example: “Use lemmata: which of my claims are not supported, and what would I need to add?” Keep --scope user so the token is never written into a repository.')) : null,
        r.tokens.length ? h('ul', { class: 'plain' }, r.tokens.map(t => h('li', null, h('b', null, t.name), ' ', h('span', { class: 'muted small' }, 'made ' + ago(t.created) + (t.last_used ? ', last used ' + ago(t.last_used) : ', never used')), ' ',
          h('button', { class: 'linkbtn small', onclick: async () => { try { await api('DELETE', '/api/hub/tokens/' + t.device_id); } catch (e) { alert(e.message); } paintTokens(); } }, 'Remove')))) : null,
        h('div', { class: 'row' }, name, h('button', { class: 'btn', id: 'new-token', onclick: async () => { try { paintTokens(await api('POST', '/api/hub/tokens', { name: name.value.trim() || 'Claude Code' })); } catch (e) { alert(e.message); } } }, 'Create a token')));
    }
    root.append(
      h('div', { class: 'crumb' }, h('button', { class: 'linkbtn', onclick: () => { S.view = 'home'; route(); } }, '← Projects')),
      h('h1', null, 'Account'),
      h('p', null, 'Signed in as ', h('b', null, u.login), u.private_repos === false ? ' (public repositories only).' : ' (private and public repositories).',
        S.status.is_admin ? ' You own this Lemmata server.' : ''),
      h('h3', null, 'A project opens on'), grid,
      h('h3', null, 'Your own Claude Code or VS Code'),
      h('p', { class: 'muted' }, 'Lemmata does not call an AI model. To have one reason over your claims and evidence, connect your own Claude Code over MCP with a personal token.'), tokBox,
      S.status.is_admin ? [h('h3', null, 'Start-view comparison (owner only)'), abBox] : null,
      S.status.is_admin ? null : [h('h3', null, 'Delete'), h('p', { class: 'muted' }, 'Removes your projects and their copies from the server, the saved GitHub sign-in and every session.'),
        h('button', { class: 'btn', id: 'delete-account', onclick: async () => {
          if (!confirm('Delete your Lemmata account, all your projects here and the saved GitHub sign-in? Your GitHub repositories are not touched.')) return;
          try { await api('DELETE', '/api/hub/account'); } catch (e) { return alert(e.message); }
          S.status = await api('GET', '/api/hub/status'); S.view = 'home'; route();
        } }, 'Delete my account')]);
    paintTokens();
    if (S.status.is_admin) {
      try {
        const r = await api('GET', '/api/hub/admin/ab');
        const cols = [['users', 'People'], ['created_project', 'Made a project'], ['confirmed_a_claim', 'Confirmed a claim'], ['added_feedback', 'Added feedback'], ['asked', 'Asked'], ['switched_view', 'Changed start view'], ['came_back_another_day', 'Came back'], ['useful_yes', '👍'], ['useful_no', '👎']];
        abBox.append(h('table', { class: 'tbl' }, h('thead', null, h('tr', null, h('th', null, 'Started on'), cols.map(c => h('th', null, c[1])))),
          h('tbody', null, r.variants.map(v => h('tr', null, h('td', null, viewOf(v.variant).name), cols.map(c => h('td', { class: 'mono' }, String(v[c[0]]))))))),
          h('p', { class: 'muted small' }, r.accounts + ' accounts. ' + r.note));
      } catch (e) { abBox.append(errBox(e.message)); }
    }
  }

  boot();
})();
