/* Lemmata launcher. Static page; talks to the Rust shell through window.__TAURI__ (withGlobalTauri). */
'use strict';
(function () {
  const T = window.__TAURI__;
  const invoke = T && T.core ? T.core.invoke : null;
  const $ = (s) => document.querySelector(s);
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const k in attrs || {}) {
      const v = attrs[k];
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const c of kids.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : document.createTextNode(String(c)));
    return el;
  }
  const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); return el; };

  let state = null;
  let paper = '', code = '';
  let installClicked = false;
  let showDetails = false;
  let openingSince = 0, slowTimer = null;
  let lastErrKey = '';

  const FRIENDLY = {
    not_found: 'That folder no longer exists.',
    no_project: 'No LaTeX files or git repository were found in that folder. Choose the folder that holds your paper or code.',
    scan_failed: 'Lemmata could not read this project. Your files were not changed.',
  };

  function rel(sec) {
    if (!sec) return '';
    const d = Math.max(0, Date.now() / 1000 - sec);
    const f = (n, u) => 'Opened ' + n + ' ' + u + (n === 1 ? '' : 's') + ' ago';
    if (d < 60) return 'Opened just now';
    if (d < 3600) return f(Math.floor(d / 60), 'minute');
    if (d < 86400) return f(Math.floor(d / 3600), 'hour');
    if (d < 86400 * 60) return f(Math.floor(d / 86400), 'day');
    return f(Math.floor(d / 86400 / 30), 'month');
  }

  async function refresh() {
    if (!invoke) { $('#foot').textContent = 'Launcher must run inside the Lemmata app.'; return; }
    try { state = await invoke('launcher_state'); } catch (e) { return; }
    render();
  }

  function render() {
    const busy = !!state.opening;
    const gitOk = state.git.ok;
    const off = busy || !gitOk;
    for (const id of ['#btn-open', '#btn-sample']) {
      const b = $(id); b.disabled = off; b.title = !gitOk ? 'Install git first.' : '';
    }
    $('#adv-open').disabled = off || !(paper || code);

    // banner: git missing takes precedence; otherwise the sidecar error
    const bn = clear($('#banner'));
    if (!gitOk) {
      bn.append(h('div', { class: 'banner git' },
        h('span', { class: 'chipx' }, '∅ git not found'),
        h('h3', null, 'Git is not installed'),
        h('p', null, "Lemmata reads your project history with git. Install Apple's Command Line Tools to continue."),
        h('div', { class: 'btns' },
          h('button', { class: 'btn', disabled: installClicked, onclick: () => { installClicked = true; invoke('install_git'); render(); } }, 'Install Command Line Tools')),
        installClicked ? h('p', null, 'Waiting for the installer. Return here when it finishes. ', h('button', { class: 'linkbtn', onclick: refresh }, 'Check again')) : null));
    } else if (state.error && !busy) {
      const e = state.error;
      const key = e.code + '|' + e.message;
      if (key !== lastErrKey) { lastErrKey = key; showDetails = false; }
      const friendly = FRIENDLY[e.code] || (e.code === 'git_missing' ? '' : 'The Lemmata engine stopped unexpectedly. Your files were not changed.');
      const det = h('div', { class: 'details', id: 'details' }, e.details || 'No details were captured.');
      det.classList.toggle('hidden', !showDetails);
      const box = h('div', { class: 'banner err', role: 'alert' },
        h('span', { class: 'chipx' }, '✕ Could not open'),
        h('h3', { tabindex: '-1', id: 'err-h' }, 'Lemmata could not open this project'),
        h('p', null, e.message),
        friendly ? h('p', null, friendly) : null,
        h('div', { class: 'btns' },
          h('button', { class: 'btn sm', onclick: () => { showDetails = !showDetails; render(); } }, showDetails ? 'Hide details' : 'Show details'),
          h('button', { class: 'btn sm', onclick: () => invoke('retry_open') }, 'Try again'),
          h('button', { class: 'btn sm', onclick: () => { invoke('dismiss_error'); invoke('open_project_dialog'); } }, 'Choose another folder…'),
          showDetails ? h('button', { class: 'btn sm', onclick: (ev) => { navigator.clipboard.writeText(e.details || e.message).then(() => { ev.target.textContent = 'Copied'; }); } }, 'Copy details') : null),
        det);
      bn.append(box);
      if (key !== bn.dataset.focused) { bn.dataset.focused = key; setTimeout(() => { const x = $('#err-h'); if (x) x.focus(); }, 0); }
    }

    // opening line
    const op = $('#opening');
    clearTimeout(slowTimer);
    if (busy) {
      if (!openingSince) openingSince = Date.now();
      const text = () => 'Opening ' + state.opening + '…' + (Date.now() - openingSince > 10000 ? ' Still working. Large projects take longer the first time.' : '');
      op.textContent = text(); op.classList.remove('hidden');
      slowTimer = setTimeout(() => { if (state && state.opening) { op.textContent = text(); } }, 10100);
    } else { openingSince = 0; op.classList.add('hidden'); }

    // recent
    const ul = clear($('#recent'));
    const list = state.recent || [];
    $('#empty').classList.toggle('hidden', list.length > 0);
    list.forEach((p, i) => {
      const li = h('li');
      const missing = !p.exists;
      const b = h('button', { class: missing ? 'missing' : '', disabled: busy || (!gitOk && !missing), onclick: () => onRecent(i, p) },
        h('span', { class: 'nm' }, p.name, missing ? h('span', { class: 'chip' }, '? Not found') : null),
        h('span', { class: 'when' }, rel(p.opened_at)),
        h('span', { class: 'pt', title: p.path }, '‎' + p.path));
      li.append(b); ul.append(li);
    });

    // footer
    $('#foot').textContent = 'Lemmata ' + state.version + ' · ' + (gitOk ? state.git.version.replace(/^git version /, 'git ') : 'git not found');
  }

  async function onRecent(i, p) {
    if (!p.exists) {
      // Confirm inline with the native confirm of the web view.
      if (window.confirm('Remove from recent projects?')) invoke('remove_recent', { index: i });
      return;
    }
    invoke('open_recent_cmd', { index: i });
  }

  $('#btn-open').addEventListener('click', () => invoke('open_project_dialog'));
  $('#btn-sample').addEventListener('click', () => invoke('open_sample_cmd'));
  $('#adv-toggle').addEventListener('click', (ev) => {
    const adv = $('#adv'); const open = adv.classList.toggle('hidden') === false;
    ev.target.setAttribute('aria-expanded', String(open));
  });
  async function choose(kind) {
    const p = await invoke('pick_folder_cmd', { title: kind === 'paper' ? 'Choose the paper folder (.tex)' : 'Choose the code folder (git)' });
    if (!p) return;
    if (kind === 'paper') { paper = p; $('#paper-path').textContent = '‎' + p; } else { code = p; $('#code-path').textContent = '‎' + p; }
    render();
  }
  $('#pick-paper').addEventListener('click', () => choose('paper'));
  $('#pick-code').addEventListener('click', () => choose('code'));
  $('#adv-open').addEventListener('click', () => invoke('open_project', { path: paper || code, paper: paper || null, code: code || null }));

  if (T && T.event) T.event.listen('state-changed', refresh);
  window.addEventListener('focus', refresh);   // picks up git being installed
  refresh();
})();
