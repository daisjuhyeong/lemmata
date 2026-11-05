/* Lemmata hub pages: pair, sign in with GitHub, projects, new project. Plain JS, no build, no CDN.
   Contract: wiki/sprints/S04/S04-brief.md. */
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
      const e = new Error((j.error && j.error.message) || ('HTTP ' + r.status));
      e.status = r.status; e.code = j.error && j.error.code; throw e;
    }
    return j;
  }

  /* ---------- state ---------- */
  const S = { status: null, view: 'home', gh: null, flow: null, pollTimer: null, error: null };

  function pairedOf(st) { return st.paired !== undefined ? !!st.paired : (st.authenticated !== undefined ? !!st.authenticated : !!st.session); }
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
    renderWho();
    if (!pairedOf(S.status)) return viewPair();
    if (S.view === 'new') return viewNew();
    return viewHome();
  }
  function renderWho() {
    clear(who);
    const u = pairedOf(S.status) && ghUser(S.status);
    if (!u) return;
    who.append(...[u.avatar_url ? h('img', { src: u.avatar_url, alt: '', onerror: ev => ev.target.remove() }) : null, h('span', null, h('b', null, u.login)),
      h('button', { class: 'btn sm', onclick: signOut }, 'Sign out')].filter(Boolean));
  }
  function showFatal(e) {
    clear(root).append(h('h1', null, 'Lemmata'), h('div', { class: 'alert', role: 'alert' }, h('b', null, '✕ Server unreachable. '), e.message),
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
  function signInCard(box, err) {
    clear(box);
    if (S.flow) return flowCard(box);
    box.append(h('div', { class: 'card' },
      h('h2', null, 'Sign in with GitHub'),
      h('p', null, 'Signing in connects your GitHub repositories. Lemmata can then list them and clone the one you pick.'),
      errBox(err),
      h('div', { class: 'acts' }, h('button', { class: 'btn primary', id: 'gh-start', onclick: () => startFlow(box) }, 'Sign in with GitHub'))));
  }
  async function startFlow(box) {
    try { S.flow = await api('POST', '/api/hub/github/start', {}); }
    catch (e) { return signInCard(box, e.code === 'no_client_id' || e.status === 412 ? 'GitHub sign-in is not set up on the server yet. Run lemmata hub config --github-client-id <id> on the Mac mini.' : e.message); }
    S.flow.t0 = Date.now();
    flowCard(box);
    schedulePoll(box);
  }
  function flowCard(box, end) {
    clear(box);
    const f = S.flow;
    const copyBtn = h('button', { class: 'btn', id: 'gh-copy', onclick: async () => { await copyText(f.user_code); copyBtn.textContent = 'Copied'; setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1500); } }, 'Copy');
    const card = h('div', { class: 'card', 'aria-live': 'polite' }, h('h2', null, 'Sign in with GitHub'));
    if (end) {
      card.append(errBox(end), h('div', { class: 'acts' }, h('button', { class: 'btn primary', id: 'gh-retry', onclick: () => { S.flow = null; startFlow(box); } }, 'Retry')));
    } else {
      card.append(
        h('p', null, 'Open GitHub, then enter this code:'),
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
      try { r = await api('GET', '/api/hub/github/poll'); }
      catch (e) { if (e.network) return schedulePoll(box); return flowCard(box, e.code === 'not_owner' ? 'This server belongs to another GitHub account.' : e.message); }
      if (r.state === 'ok') { S.flow = null; S.status = await api('GET', '/api/hub/status'); return route(); }
      if (r.state === 'denied') return flowCard(box, 'GitHub sign-in was denied.');
      if (r.state === 'expired') return flowCard(box, 'The code expired before it was used.');
      if (r.state === 'error') return flowCard(box, r.message || 'GitHub reported an error.');
      schedulePoll(box);
    }, wait);
  }
  async function signOut() {
    try { await api('POST', '/api/hub/github/logout', {}); } catch (e) { /* show fresh status either way */ }
    S.flow = null;
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
    return Math.round(d / 86400) + ' d ago';
  }
  async function viewHome() {
    clear(root);
    const user = ghUser(S.status);
    const head = h('div', { class: 'row wrap' }, h('h1', { class: 'grow', style: 'margin:0' }, 'Projects'),
      user ? h('button', { class: 'btn primary', id: 'new-project', onclick: () => { S.view = 'new'; route(); } }, 'New project') : null);
    const signin = h('div', { id: 'signin' });
    const list = h('div', { id: 'plist' }, h('p', { class: 'muted' }, 'Loading…'));
    root.append(head);
    if (!user) { root.append(signin); signInCard(signin); }
    root.append(list);
    try {
      const r = await api('GET', '/api/hub/projects');
      clear(list);
      if (!r.projects.length) {
        list.append(h('div', { class: 'well' }, h('strong', null, 'No projects yet'), h('br'),
          user ? 'Pick a GitHub repository to start.' : 'Sign in with GitHub, then pick a repository.'));
      }
      for (const p of r.projects) list.append(projRow(p));
    } catch (e) {
      if (e.status === 401) { S.status = await api('GET', '/api/hub/status').catch(() => S.status); return viewPair(); }
      clear(list).append(errBox(e.message));
    }
  }
  function projRow(p) {
    const c = p.counts || { recheck: 0, findings: 0 };
    const v = p.paper_versions || 0;
    return h('div', { class: 'proj' },
      h('div', { class: 'grow' },
        h('div', { class: 'nm' }, p.name),
        h('div', { class: 'meta' },
          h('span', { class: 'mono' }, p.code_repo + (p.branch ? '@' + p.branch : '')),
          c.recheck ? h('span', { class: 'chip recheck' }, '↻ ' + c.recheck + ' Recheck') : h('span', { class: 'chip ok' }, '✓ 0 Recheck'),
          h('span', { class: 'chip ' + (c.findings ? 'bad' : 'plain') }, (c.findings ? '≠ ' : '') + plural(c.findings, 'finding')),
          v ? h('span', { class: 'chip plain' }, 'Paper v' + v) : h('span', { class: 'chip none' }, '∅ No paper yet'),
          h('span', null, 'Last sync ' + ago(p.last_sync)))),
      h('a', { class: 'btn', href: '/p/' + encodeURIComponent(p.id) + '/', 'aria-label': 'Open ' + p.name }, 'Open'));
  }

  /* ---------- new project ---------- */
  function viewNew() {
    clear(root);
    let picked = null, zip = null, busy = false, reposTimer = null, seq = 0;
    const errs = h('div');
    const list = h('ul', { class: 'repos', id: 'repos', 'aria-label': 'Your GitHub repositories' });
    const search = h('input', { type: 'search', id: 'repo-q', placeholder: 'Search your repositories', 'aria-label': 'Search repositories', autocomplete: 'off' });
    const createBtn = h('button', { class: 'btn primary', id: 'create', disabled: true }, 'Create project');
    const dropMsg = h('div'); const fileIn = h('input', { type: 'file', accept: '.zip,application/zip', class: 'hidden', id: 'zipfile' });
    const drop = h('div', { class: 'drop', id: 'drop' }, dropMsg);
    const progress = h('div', { class: 'hidden', id: 'progress' });
    const form = h('div');

    function paintDrop() {
      clear(dropMsg);
      drop.classList.toggle('has', !!zip);
      if (zip) dropMsg.append(h('div', null, '✓ ', h('b', { class: 'mono' }, zip.name), ' ', h('span', { class: 'muted' }, '(' + (zip.size / 1048576).toFixed(1) + ' MB)')),
        h('div', { style: 'margin-top:8px' }, h('button', { class: 'linkbtn', onclick: () => { zip = null; paintDrop(); } }, 'Remove')));
      else dropMsg.append(h('div', null, 'Drop your Overleaf source zip here'), h('div', { class: 'muted', style: 'margin:4px 0 8px' }, 'or'),
        h('button', { class: 'btn sm', onclick: () => fileIn.click() }, 'Choose zip file…'));
    }
    function setZip(f) {
      if (!f) return;
      if (!/\.zip$/i.test(f.name) && f.type !== 'application/zip') { clear(errs).append(errBox('That is not a .zip file. In Overleaf choose Menu → Download → Source.')); return; }
      if (f.size > 100 * 1048576) { clear(errs).append(errBox('That zip is larger than 100 MB. Remove large figures or data from the Overleaf project first.')); return; }
      clear(errs); zip = f; paintDrop();
    }
    fileIn.addEventListener('change', () => { setZip(fileIn.files[0]); fileIn.value = ''; });
    for (const ev of ['dragenter', 'dragover']) drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); });
    for (const ev of ['dragleave', 'drop']) drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); });
    drop.addEventListener('drop', e => setZip(e.dataTransfer.files[0]));
    // a drop outside the box must not navigate the window away to the zip
    for (const ev of ['dragover', 'drop']) window.addEventListener(ev, e => e.preventDefault());
    paintDrop();

    async function loadRepos(q) {
      const my = ++seq;
      clear(list).append(h('li', { class: 'muted', style: 'padding:12px' }, 'Loading repositories…'));
      try {
        const r = await api('GET', '/api/hub/github/repos?q=' + encodeURIComponent(q || ''));
        if (my !== seq) return;
        clear(list);
        if (!r.repos.length) list.append(h('li', { class: 'muted', style: 'padding:12px' }, q ? 'No repository matches “' + q + '”.' : 'No repositories found.'));
        for (const rp of r.repos) {
          const b = h('button', { 'aria-pressed': String(!!picked && picked.full_name === rp.full_name), onclick: () => { picked = rp; createBtn.disabled = busy; for (const x of list.querySelectorAll('button')) x.setAttribute('aria-pressed', String(x === b)); } },
            h('span', { class: 'grow' }, h('div', { class: 'mono' }, rp.full_name), rp.description ? h('div', { class: 'desc' }, rp.description) : null),
            rp.private ? h('span', { class: 'chip plain' }, 'Private') : null,
            h('span', { class: 'muted', style: 'font-size:12px' }, rp.pushed_at ? 'pushed ' + ago(rp.pushed_at) : ''));
          list.append(h('li', null, b));
        }
      } catch (e) {
        if (my !== seq) return;
        clear(list); clear(errs).append(errBox(e.status === 401 || e.status === 403 ? 'GitHub is not connected. Sign in from the Projects page.' : e.message));
      }
    }
    search.addEventListener('input', () => { clearTimeout(reposTimer); reposTimer = setTimeout(() => loadRepos(search.value.trim()), 250); });

    const steps = [['clone', 'Cloning and scanning the repository'], ['paper', 'Uploading paper and rescanning']];
    function paintProgress(state, detail) {   // state: {clone, paper} each wait|active|done|fail|skip
      clear(progress).append(h('h2', null, 'Creating ' + picked.full_name), h('ul', { class: 'steps', 'aria-live': 'polite' },
        steps.filter(s => !(s[0] === 'paper' && !zip)).map(([k, label]) => {
          const st = state[k];
          return h('li', { class: st }, h('span', { class: 'ic' }, st === 'done' ? '✓' : st === 'fail' ? '✕' : st === 'active' ? '…' : '·'), label,
            k === 'paper' && st === 'active' && typeof detail === 'number' ? h('span', { class: 'bar', role: 'progressbar', 'aria-valuenow': String(detail) }, h('i', { style: 'width:' + detail + '%' })) : null);
        })), detail && typeof detail === 'object' ? detail : []);
    }
    async function create() {
      if (!picked || busy) return;
      busy = true; createBtn.disabled = true; clear(errs);
      form.classList.add('hidden'); progress.classList.remove('hidden');
      const st = { clone: 'active', paper: 'wait' };
      paintProgress(st);
      let proj;
      try { const r = await api('POST', '/api/hub/projects', { code_repo: picked.full_name, branch: picked.default_branch }); proj = r.project || r; }
      catch (e) {
        st.clone = 'fail'; paintProgress(st, h('div', null, errBox(e.message), h('div', { class: 'acts' },
          h('button', { class: 'btn primary', onclick: () => { busy = false; progress.classList.add('hidden'); form.classList.remove('hidden'); createBtn.disabled = false; } }, 'Back'))));
        return;
      }
      st.clone = 'done';
      if (!zip) { st.paper = 'skip'; paintProgress(st); return openProject(proj); }
      st.paper = 'active'; paintProgress(st, 0);
      try {
        await uploadZip(proj.id, zip, pct => paintProgress(st, pct));
        st.paper = 'done'; paintProgress(st); openProject(proj);
      } catch (e) {
        st.paper = 'fail';
        paintProgress(st, h('div', null, errBox('The project was created, but the paper zip could not be added. ' + e.message),
          h('div', { class: 'acts' }, h('a', { class: 'btn primary', href: '/p/' + encodeURIComponent(proj.id) + '/' }, 'Open project anyway'),
            h('button', { class: 'btn', onclick: () => { st.paper = 'active'; paintProgress(st, 0); uploadZip(proj.id, zip, pct => paintProgress(st, pct)).then(() => { st.paper = 'done'; paintProgress(st); openProject(proj); }).catch(() => { st.paper = 'fail'; paintProgress(st, errBox('Upload failed again.')); }); } }, 'Retry upload'))));
      }
    }
    function openProject(p) { setTimeout(() => { location.href = '/p/' + encodeURIComponent(p.id) + '/'; }, 600); }
    createBtn.addEventListener('click', create);

    form.append(
      h('div', { class: 'crumb' }, h('button', { class: 'linkbtn', onclick: () => { S.view = 'home'; route(); } }, '← Projects')),
      h('h1', null, 'New project'),
      h('h3', null, '1. Code: choose a GitHub repository'), search, list,
      h('h3', null, '2. Paper (optional now): Overleaf source zip'),
      h('p', { class: 'muted' }, 'In Overleaf: Menu → Download → Source. You can also add it later from the project page.'),
      drop, fileIn, errs,
      h('div', { class: 'acts' }, createBtn));
    root.append(form, progress);
    loadRepos('');
    search.focus();
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

  boot();
})();
