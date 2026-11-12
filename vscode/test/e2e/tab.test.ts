// End to end without an editor: the real LemmataTab (src/tab.ts), a stand-in for the VS Code API whose "webview" is a
// headless Chrome page, and a real hub (test/hub_fixture.py). Needs Playwright and Chrome; skipped when they are missing.
//   npm run test:e2e        (set PLAYWRIGHT_DIR / CHROME_PATH if they are somewhere unusual)
import { test, before, after } from 'node:test';
import * as assert from 'node:assert/strict';
import { spawn, ChildProcess } from 'node:child_process';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import Module = require('node:module');

// code passed to page.evaluate runs in the browser; the project is compiled without the DOM library
/* eslint-disable @typescript-eslint/no-explicit-any */
declare const window: any; declare const document: any; declare const getComputedStyle: any; declare const S: any; declare const PID: string; declare const openTab: any;
type HTMLElement = any;

function findPlaywright(): any {
  for (const p of [process.env.PLAYWRIGHT_DIR, 'playwright', '/opt/npm-tools/node_modules/playwright'].filter(Boolean) as string[]) {
    try { return require(p); } catch { /* next */ }
  }
  return null;
}
const pw = findPlaywright();
const chrome = [process.env.CHROME_PATH, '/usr/bin/google-chrome', '/usr/bin/chromium', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'].find(p => p && fs.existsSync(p));
const skip = !pw ? 'Playwright is not installed' : false;

/* ---------- stand-in for 'vscode' ---------- */
const disposable = { dispose() { /* */ } };
const seen = { docs: [] as any[], external: [] as string[], opened: [] as any[], info: [] as string[], saved: [] as any[] };
let page: any;                                   // the Chrome page that plays the webview
let receive: ((m: any) => void) | null = null;    // the extension's message handler
let navigations = 0;
const webview = {
  set html(v: string) { navigations++; pending = pending.then(async () => { await page.unroute('http://lemmata.test/').catch(() => undefined); await page.route('http://lemmata.test/', (r: any) => r.fulfill({ status: 200, contentType: 'text/html', body: v })); await page.goto('http://lemmata.test/', { waitUntil: 'load' }); }); },
  onDidReceiveMessage(fn: (m: any) => void) { receive = fn; return disposable; },
  postMessage(m: any) { pending = pending.then(() => page.evaluate((x: any) => window.postMessage(x, '*'), m)); return Promise.resolve(true); },
};
let pending: Promise<unknown> = Promise.resolve();
const fake = {
  ViewColumn: { Active: -1, Beside: -2 },
  Uri: { file: (p: string) => ({ scheme: 'file', fsPath: p }), parse: (u: string) => ({ toString: () => u }) },
  window: {
    createWebviewPanel: () => ({ webview, reveal() { /* */ }, onDidDispose: () => disposable, dispose() { /* */ } }),
    showTextDocument: async (d: any) => d, showInformationMessage: async (m: string) => { seen.info.push(m); }, showWarningMessage: async (m: string) => { seen.info.push(m); },
    showSaveDialog: async () => undefined,
  },
  workspace: { openTextDocument: async (o: any) => { seen.docs.push(o); return o; }, fs: { writeFile: async (u: any, d: any) => { seen.saved.push([u, d]); } } },
  env: { openExternal: async (u: any) => { seen.external.push(u.toString()); return true; } },
  commands: { executeCommand: async (...a: any[]) => { seen.opened.push(a); } },
};
const load = (Module as any)._load;
(Module as any)._load = function (request: string, ...rest: unknown[]) { return request === 'vscode' ? fake : load.call(this, request, ...rest); };
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { LemmataTab } = require('../../src/tab') as typeof import('../../src/tab');
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { HubClient } = require('../../src/core/client') as typeof import('../../src/core/client');

const REPO = path.resolve(__dirname, '../../../..');
let proc: ChildProcess, fx: any, tmp: string, browser: any, client: InstanceType<typeof HubClient>, tab: InstanceType<typeof LemmataTab>;
const errors: string[] = [];
const host = { logs: [] as string[], locs: [] as any[], changes: 0,
  log(m: string) { host.logs.push(m); }, async openLocation(pid: string, repo: string, rel: string, line: number) { host.locs.push({ pid, repo, rel, line }); return repo === 'code'; }, hubChanged() { host.changes++; } };
const settle = async (ms = 600) => { await pending; await page.waitForTimeout(ms); await pending; };
const text = () => page.evaluate(() => (document.getElementById('app') as HTMLElement).innerText);
/** fetch() inside the page, as the app would call it. */
const inPage = (p: string, init?: any) => page.evaluate(async ([u, i]: [string, any]) => { try { const r = await fetch(u, i); return { status: r.status, type: r.headers.get('content-type'), body: await r.text() }; } catch (e) { return { error: String(e) }; } }, [p, init || {}]);

before(async () => {
  if (skip) return;
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'lemmata-tab-'));
  proc = spawn('python3', [path.join(REPO, 'vscode/test/hub_fixture.py'), path.join(tmp, 'fx')], { stdio: ['pipe', 'pipe', 'inherit'] });
  fx = await new Promise((res, rej) => { let buf = ''; proc.stdout!.on('data', d => { buf += d; const i = buf.indexOf('\n'); if (i >= 0) { try { res(JSON.parse(buf.slice(0, i))); } catch (e) { rej(e); } } }); proc.on('exit', c => rej(new Error('fixture exited ' + c))); });
  client = new HubClient(fx.url, fx.token);
  browser = await pw.chromium.launch({ executablePath: chrome, args: ['--no-sandbox'] });
  page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  page.on('pageerror', (e: Error) => errors.push('pageerror: ' + e.message));
  page.on('console', (m: any) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('request', (r: any) => { const u = r.url(); if (!u.startsWith('http://lemmata.test/') && !u.startsWith('data:') && !u.startsWith('blob:')) errors.push('network request from the page: ' + u); });
  await page.exposeFunction('__toExtension', (m: any) => { if (receive) receive(m); });
  await page.addInitScript(() => { (window as any).acquireVsCodeApi = () => ({ postMessage: (m: any) => (window as any).__toExtension(m) }); });
  tab = new LemmataTab({ subscriptions: [], extensionPath: path.resolve(__dirname, '..', '..', '..') } as any, host);
});
after(async () => { if (skip) return; try { await browser.close(); } catch { /* */ } try { proc.stdin!.end(); proc.kill(); } catch { /* */ } fs.rmSync(tmp, { recursive: true, force: true }); });

test('the tab shows the hub\'s pages with real data, with no network access of its own', { skip }, async () => {
  await tab.open(client, fx.url, fx.pid, 'Demo');
  await settle(3500);
  const t = await text();
  assert.match(t, /Claims/);
  assert.match(t, /A Tiny Transformer for Sequence Labelling/, 'the claims tree of the sample project is drawn');
  assert.doesNotMatch(t, /Can't reach Lemmata/);
  assert.doesNotMatch(t, /← Projects/);
  assert.equal(await page.evaluate(() => document.documentElement.classList.contains('embed')), true);
  assert.equal(await page.evaluate(() => getComputedStyle(document.getElementById('narrow') as HTMLElement).display), 'none');
  assert.ok(await page.evaluate(async () => (await document.fonts.load('1em KaTeX_Main')).length) > 0, 'math fonts are part of the page');
  assert.deepEqual(errors, []);
});

test('Open Review / Experiments switch the page in the same tab', { skip }, async () => {
  const before = navigations;
  await tab.open(client, fx.url, fx.pid, 'Demo', 'review');
  await settle(2500);
  assert.match(await text(), /Hoped conclusion/);
  await tab.open(client, fx.url, fx.pid, 'Demo', 'experiments');
  await settle(2500);
  assert.equal(await page.evaluate(() => (document.querySelector('.tab.active, [role=tab][aria-selected=true]') as HTMLElement | null)?.innerText.includes('Experiments') ?? null), true);
  assert.equal(navigations, before, 'the page was not rebuilt');
  assert.deepEqual(errors, []);
});

test('editing works: the hoped conclusion typed in the tab is saved on the hub', { skip }, async () => {
  await tab.open(client, fx.url, fx.pid, 'Demo', 'review');
  await settle(1500);
  const n = host.changes;
  await page.fill('textarea.rx-rv-hoped', 'A tiny model matches the baseline.');
  await page.dispatchEvent('textarea.rx-rv-hoped', 'change');
  await settle(1500);
  const r = await client.raw('GET', '/p/' + encodeURIComponent(fx.pid) + '/api/review');
  assert.equal(JSON.parse(r.data.toString('utf8')).hoped, 'A tiny model matches the baseline.');
  assert.ok(host.changes > n, 'the extension is told so the panel can refresh');
  assert.deepEqual(errors, []);
});

test('the page can reach only its own project', { skip }, async () => {
  const ok = await inPage('/p/' + encodeURIComponent(fx.pid) + '/api/project');
  assert.equal(ok.status, 200);
  assert.match(ok.type, /json/);
  for (const [p, init] of [['/p/another-project/api/graph', {}], ['/api/hub/devices', {}], ['/api/hub/projects/' + fx.pid, { method: 'DELETE' }], ['https://example.com/', {}],
    ['/p/' + fx.pid + '/api/../../../api/hub/devices', {}]] as [string, any][]) {
    const r = await inPage(p, init);
    assert.ok(r.error, p + ' is refused');
  }
  const missing = await inPage('/p/' + encodeURIComponent(fx.pid) + '/api/no-such-route');
  assert.equal(missing.status, 404, 'hub errors reach the app as ordinary answers');
  assert.equal(JSON.stringify(await page.evaluate(() => document.documentElement.outerHTML)).includes(fx.token), false, 'the token is not in the page');
  assert.deepEqual(errors.filter(e => !/404/.test(e)), []);
});

test('links: a file opens in the editor, claims.md opens as a document, web links go to the browser', { skip }, async () => {
  // an item with a place in the paper
  const id = await page.evaluate(() => { const n = (S.graph.nodes as any[]).find(x => x.repo === 'code' && x.loc && x.loc.path); openTab('node', n.id); return n.id; });
  await settle(2000);
  const link = await page.$('a.ghl:has-text("Open in editor")');
  assert.ok(link, 'a file place has an "Open in editor" link (' + id + ')');
  await link.click();
  await settle(300);
  assert.equal(host.locs.length, 1);
  assert.deepEqual([host.locs[0].pid, host.locs[0].repo, typeof host.locs[0].rel, host.locs[0].line >= 1], [fx.pid, 'code', 'string', true]);
  await page.evaluate(() => (window as any).LEMMATA_EMBED.open('/p/' + encodeURIComponent(PID) + '/api/claims.md'));
  await settle(1200);
  assert.equal(seen.docs.length, 1);
  assert.equal(seen.docs[0].language, 'markdown');
  assert.match(seen.docs[0].content, /RQ1|Claims|#/);
  await page.evaluate(() => { const a = document.createElement('a'); a.href = 'https://github.com/alice/demo-code'; a.id = 'ext'; a.textContent = 'x'; document.body.append(a); a.click(); a.remove(); });
  await settle(300);
  assert.deepEqual(seen.external, ['https://github.com/alice/demo-code']);
  await page.evaluate(() => (window as any).LEMMATA_EMBED.open('/api/hub/devices'));
  await settle(500);
  assert.equal(seen.docs.length, 1, 'a file outside the project is not fetched');
  assert.deepEqual(errors.filter(e => !/404/.test(e)), []);
});

test('S18 width modes: narrow, medium and wide switch without a reload, and the page never scrolls sideways', { skip }, async () => {
  await tab.open(client, fx.url, fx.pid, 'Demo', 'claims');
  await settle(2500);
  const before = navigations;
  const probe = () => page.evaluate(() => {
    const vis = (sel: string) => { const e = document.querySelector(sel); return !!e && getComputedStyle(e).display !== 'none'; };
    const de = document.documentElement;
    const bar = document.getElementById('topnav') as HTMLElement;
    return { tag: vis('.rtag'), tabs: Array.from(document.querySelectorAll('.navtab .navl')).map((b: HTMLElement) => b.innerText.trim()), active: (document.querySelector('.navtab.on .navl') as HTMLElement).innerText.trim(),
      tabsFit: bar.scrollWidth <= bar.clientWidth + 1, outline: vis('.rxt-caret'), pad: getComputedStyle(document.getElementById('page') as HTMLElement).paddingLeft,
      wide: (document.getElementById('page') as HTMLElement).getBoundingClientRect().width, sideways: de.scrollWidth > de.clientWidth + 1, band: getComputedStyle(document.querySelector('#band .bt') as HTMLElement).display, embed: de.classList.contains('embed') };
  });
  await page.setViewportSize({ width: 300, height: 800 }); await settle(500);
  const narrow = await probe();
  assert.equal(narrow.embed, true);
  assert.equal(narrow.sideways, false, 'no sideways scrolling at 300px');
  assert.equal(narrow.pad, '12px'); assert.equal(narrow.tag, false, 'no bracket tag on screen when narrow');
  assert.equal(narrow.band, 'none', 'no header band in VS Code');
  assert.equal(narrow.tabs.length, 4); assert.equal(narrow.tabsFit, true, 'the four tabs fit on one row'); assert.equal(narrow.active, 'Claims', 'the active tab keeps its name');
  assert.ok(narrow.tabs.every((t: string) => t.length === 1 || ['Claims', 'Experiments', 'Digest', 'Review'].includes(t)), 'a tab is either its full name or its first letter');
  assert.equal(narrow.outline, true, 'Claims is an outline with collapse arrows when narrow');
  await page.setViewportSize({ width: 500, height: 800 }); await settle(500);
  const medium = await probe();
  assert.equal(medium.pad, '16px'); assert.equal(medium.sideways, false); assert.equal(medium.tag, true, 'bracket tags are back from 360px');
  assert.deepEqual(medium.tabs, ['Claims', 'Experiments', 'Digest', 'Review'], 'all four names fit from 360px');
  assert.equal(medium.outline, false, 'medium keeps the vertical graph: no collapse arrows');
  await page.setViewportSize({ width: 1200, height: 800 }); await settle(500);
  const wide = await probe();
  assert.equal(wide.sideways, false); assert.ok(wide.wide <= 800, 'content is capped at 800px in a wide tab');
  assert.equal(navigations, before, 'the mode changed without a reload');
  assert.deepEqual(errors.filter(e => !/404/.test(e)), []);
});

test('S18 width modes on Experiments, Digest and Review: usable at 300px, columns per mode, nothing cut off, no reload', { skip }, async () => {
  const probe = () => page.evaluate(() => {
    const de = document.documentElement, W = de.clientWidth;
    const shown = (e: any) => !!e && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0;
    const cut = Array.from(document.querySelectorAll('#page button, #page a, #page select, #page input, #page textarea, .navtab'))
      .filter((e: any) => shown(e) && !e.closest('.rx-math, .katex-display, .code, .rx-ev-tablewrap') && e.getBoundingClientRect().right > W + 1).length;
    const row = document.querySelector('.rx-x-sec:not(.loose) .rx-x-r:not(.head)') || document.querySelector('button.rx-rv-r');
    return { sideways: de.scrollWidth > W + 1, cut, cols: row ? Array.from(row.children).filter(shown).length : -1, digest: document.querySelectorAll('.rx-dg-l button').length,
      pad: getComputedStyle(document.getElementById('page') as HTMLElement).paddingLeft };
  });
  const want: { [v: string]: number[] } = { experiments: [2, 4, 6], review: [2, 3, 4], digest: [-1, -1, -1] };
  for (const view of ['experiments', 'review', 'digest']) {
    await page.setViewportSize({ width: 1200, height: 800 });
    await tab.open(client, fx.url, fx.pid, 'Demo', view as any);
    await settle(2500);
    const before = navigations;
    const got: any[] = [];
    for (const w of [300, 500, 1200]) { await page.setViewportSize({ width: w, height: 800 }); await settle(500); got.push(await probe()); }
    got.forEach((g, i) => {
      assert.equal(g.sideways, false, view + ' scrolls sideways at ' + [300, 500, 1200][i]);
      assert.equal(g.cut, 0, view + ': a control is cut off at ' + [300, 500, 1200][i]);
      assert.equal(g.cols, want[view][i], view + ' columns at ' + [300, 500, 1200][i]);
    });
    assert.deepEqual(got.map(g => g.pad), ['12px', '16px', '16px'], view + ' padding per mode');
    if (view === 'digest') assert.ok(got[0].digest >= 3, 'the digest is lines, each a link');
    assert.equal(navigations, before, view + ': the mode changed without a reload');
  }
  await page.setViewportSize({ width: 1400, height: 900 });
  assert.deepEqual(errors.filter(e => !/404/.test(e)), []);
});

test('a hub that is too old, or unreachable, gets a plain message instead of a broken page', { skip }, async () => {
  const t2 = new LemmataTab({ subscriptions: [], extensionPath: path.resolve(__dirname, '..', '..', '..') } as any, host);
  await t2.open(new HubClient('http://127.0.0.1:9', fx.token), 'http://127.0.0.1:9', 'p-offline', 'X');
  await settle(800);
  assert.match(await page.evaluate(() => document.body.innerText), /cannot be reached/);
});
