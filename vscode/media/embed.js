/* Lemmata tab in VS Code: runs inside the webview BEFORE the hub's own app.js.
   The page has no network access of its own (the webview's CSP forbids it). Every request the app makes is handed to
   the extension, which calls the hub with the stored token and returns the answer. The token never enters this page. */
(function () {
  'use strict';
  const vscode = acquireVsCodeApi();
  const cfg = window.__LEMMATA_TAB__ || {};
  const pending = new Map();
  let seq = 0;

  const b64ToBytes = b64 => { const bin = atob(b64 || ''); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; };
  function bytesToB64(buf) {
    const u = new Uint8Array(buf); let s = '';
    for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));
    return btoa(s);
  }
  function ask(msg) {
    return new Promise((resolve, reject) => {
      const id = ++seq;
      pending.set(id, { resolve, reject });
      vscode.postMessage(Object.assign({ id }, msg));
    });
  }
  window.addEventListener('message', ev => {
    const m = ev.data || {};
    if (m.t === 'reply' && pending.has(m.id)) {
      const p = pending.get(m.id); pending.delete(m.id);
      if (m.error) p.reject(new TypeError(m.error)); else p.resolve(m);
    } else if (m.t === 'view' && typeof window.openTab === 'function') {
      try { window.openTab(m.k); } catch (e) { /* the app is still starting */ }
    }
  });

  /* fetch(): hub paths only ("/api/hub/..." and "/p/<pid>/api/..."); the extension checks them again. */
  async function hubFetch(input, init) {
    init = init || {};
    const url = typeof input === 'string' ? input : (input && input.url) || String(input);
    if (!url.startsWith('/')) throw new TypeError('This page can only talk to your Lemmata hub.');
    const method = String(init.method || 'GET').toUpperCase();
    const headers = init.headers || {};
    const contentType = headers['Content-Type'] || headers['content-type'] || null;
    let bodyText = null, bodyB64 = null;
    const b = init.body;
    if (typeof b === 'string') bodyText = b;
    else if (b instanceof Blob) bodyB64 = bytesToB64(await b.arrayBuffer());
    else if (b instanceof ArrayBuffer) bodyB64 = bytesToB64(b);
    else if (b != null) bodyText = String(b);
    const r = await ask({ t: 'fetch', method, path: url, contentType, bodyText, bodyB64 });
    const bytes = b64ToBytes(r.b64);
    const empty = r.status === 204 || r.status === 304 || method === 'HEAD';
    return new Response(empty ? null : bytes, { status: r.status, headers: r.contentType ? { 'Content-Type': r.contentType } : {} });
  }
  window.fetch = hubFetch;

  /* images: <img src="/p/…/api/thumb…"> and <image href="…"> are fetched through the same bridge */
  const seen = new WeakSet();
  async function fill(el, attr) {
    const v = el.getAttribute(attr);
    if (!v || !v.startsWith('/') || seen.has(el)) return;
    seen.add(el);
    el.dataset.hubSrc = v;
    el.setAttribute(attr, 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==');
    try {
      const r = await ask({ t: 'fetch', method: 'GET', path: v });
      if (r.status === 200 && /^image\//.test(r.contentType || '')) el.setAttribute(attr, 'data:' + r.contentType.split(';')[0] + ';base64,' + r.b64);
      else el.dispatchEvent(new Event('error'));      // lets the app show its own "no preview"
    } catch (e) { el.dispatchEvent(new Event('error')); }
  }
  function scan(root) {
    if (!root || root.nodeType !== 1) return;
    const list = [];
    if (root.matches && root.matches('img[src], image[href]')) list.push(root);
    if (root.querySelectorAll) root.querySelectorAll('img[src], image[href]').forEach(e => list.push(e));
    for (const el of list) fill(el, el.tagName.toLowerCase() === 'img' ? 'src' : 'href');
  }
  new MutationObserver(muts => {
    for (const m of muts) {
      if (m.type === 'attributes') { seen.delete(m.target); scan(m.target); }
      else m.addedNodes.forEach(scan);
    }
  }).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['src', 'href'] });

  /* links: hub files open in the editor or are saved by the extension; web links open in your browser */
  document.addEventListener('click', ev => {
    const a = ev.target && ev.target.closest ? ev.target.closest('a[href]') : null;
    if (!a) return;
    const href = a.getAttribute('href') || '';
    const hub = href.startsWith('/') ? href : null;
    if (hub) { ev.preventDefault(); vscode.postMessage({ t: 'open', path: hub }); }
    else if (/^https?:\/\//i.test(href)) { ev.preventDefault(); vscode.postMessage({ t: 'external', url: href }); }
  }, true);

  window.LEMMATA_EMBED = {
    pid: cfg.pid,
    open: path => vscode.postMessage({ t: 'open', path: String(path) }),
    openFile: (repo, path, line) => vscode.postMessage({ t: 'openFile', repo: String(repo || ''), path: String(path || ''), line: Number(line) || 1 }),
  };
  document.documentElement.classList.add('embed');
  window.addEventListener('load', () => { setTimeout(() => vscode.postMessage({ t: 'ready' }), 400); });
})();
