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

test('the tab shows the hub\'s experiment pages with real data, with no network access of its own', { skip }, async () => {
  await tab.open(client, fx.url, fx.pid, 'Demo');
  await settle(3500);
  let t = await text();
  assert.match(t, /Setup/, 'the tab starts on Setup');
  await tab.open(client, fx.url, fx.pid, 'Demo', 'experiments');
  await settle(2500);
  t = await text();
  assert.match(t, /Thesis/);
  assert.doesNotMatch(t, /Can't reach Lemmata/);
  assert.doesNotMatch(t, /← Projects/);
  assert.equal(await page.evaluate(() => document.documentElement.classList.contains('embed')), true);
  assert.equal(await page.evaluate(() => getComputedStyle(document.getElementById('narrow') as HTMLElement).display), 'none');
  assert.ok(await page.evaluate(async () => (await document.fonts.load('1em KaTeX_Main')).length) > 0, 'math fonts are part of the page');
  assert.deepEqual(errors, []);
});

test('S35: Setup and Thesis switch in the same tab; every other page opens on the website', { skip }, async () => {
  const before = navigations;
  await tab.open(client, fx.url, fx.pid, 'Demo', 'setup', 'page');
  await settle(2500);
  assert.equal(await page.evaluate(() => (document.querySelector('.ptitle') as HTMLElement).innerText), 'Setup');
  await tab.open(client, fx.url, fx.pid, 'Demo', 'experiments');
  await settle(2500);
  assert.equal(await page.evaluate(() => (document.querySelector('.tab.active, [role=tab][aria-selected=true]') as HTMLElement | null)?.innerText.includes('Thesis') ?? null), true);
  assert.deepEqual(await page.evaluate(() => Array.from(document.querySelectorAll('.navtab')).map((e: any) => e.innerText.replace(/\s+\d+$/, '').trim())), ['Thesis', 'Setup'], 'two pages in the band');
  assert.deepEqual(await page.evaluate(() => Array.from(document.querySelectorAll('#status .flinks .flink')).map((e: any) => e.innerText.trim())), ['Open on website'], 'the footer no longer lists every page');
  assert.equal(await page.$('#side'), null, 'no sidebar inside VS Code');
  // a page that is not about experiments: the browser opens it, the tab stays where it is
  const site = fx.url.replace(/\/+$/, '') + '/p/' + encodeURIComponent(fx.pid) + '/';
  seen.external.length = 0;
  for (const v of ['review', 'digest', 'latex', 'baselines']) { await tab.open(client, fx.url, fx.pid, 'Demo', v as any); await settle(400); }
  await page.evaluate(() => openTab('history'));
  await settle(400);
  assert.deepEqual(seen.external, ['review', 'digest', 'latex', 'baselines', 'history'].map(v => site + '#go=' + v));
  assert.equal(await page.evaluate(() => (document.querySelector('.navtab.on .navl') as HTMLElement).innerText.trim()), 'Thesis', 'the tab did not move');
  seen.external.length = 0;
  assert.equal(navigations, before, 'the page was not rebuilt');
  assert.deepEqual(errors, []);
});

test('S35: Setup with a traced number; the map keeps its lines in a narrow tab and opens alone', { skip }, async () => {
  const shots = process.env.LEMMATA_SHOTS || '';
  await page.setViewportSize({ width: 960, height: 900 });
  await tab.open(client, fx.url, fx.pid, 'Demo', 'setup', 'page');
  await settle(3000);
  assert.match(await text(), /Setup/);
  const cell = await page.$('.su-g td:not(.miss) .su-cb');
  if (cell) { await cell.click(); await settle(1500); assert.ok(await page.$('.su-tr .su-st'), 'a number opens its trace'); }
  if (shots) await page.screenshot({ path: path.join(shots, 'vscode-setup.png'), fullPage: true });
  const map = () => page.evaluate(() => { const sc = document.querySelector('.bd-sc') as HTMLElement | null, de = document.documentElement; if (!sc) return null;
    const cols = Array.from(document.querySelectorAll('.bd-col')).map((c: any) => Math.round(c.getBoundingClientRect().left));
    return { wires: document.querySelectorAll('.bd-w path').length, side: cols.length === 4 && cols[1] - cols[0] > 40, scrolls: sc.scrollWidth > sc.clientWidth + 1, page: de.scrollWidth > de.clientWidth + 1,
      solo: !!document.querySelector('.bd-solo'), title: (document.querySelector('.ptitle') as HTMLElement).innerText }; });
  const wide = await map();
  assert.ok(wide, 'the sample project has a map');
  assert.ok(wide.wires > 0 && wide.side && !wide.scrolls, 'at 960px the map fits and its lines are drawn: ' + JSON.stringify(wide));
  await page.setViewportSize({ width: 420, height: 900 }); await settle(700);
  const narrow = await map();
  assert.ok(narrow.wires > 0, 'the lines are still drawn at 420px');
  assert.equal(narrow.side, true, 'the four columns stay side by side');
  assert.equal(narrow.scrolls, true, 'the map scrolls sideways inside its own frame');
  assert.equal(narrow.page, false, 'the page itself does not scroll sideways');
  if (shots) await page.screenshot({ path: path.join(shots, 'vscode-map-narrow.png') });
  await page.setViewportSize({ width: 1400, height: 900 });
  await tab.open(client, fx.url, fx.pid, 'Demo', 'setup', 'map');             // "Open the Map (large)"
  await settle(1200);
  const solo = await map();
  assert.deepEqual([solo.solo, solo.title, solo.wires > 0], [true, 'Map', true]);
  assert.equal(await page.$('.su-g'), null, 'the map alone: no result sheets under it');
  if (shots) await page.screenshot({ path: path.join(shots, 'vscode-map-large.png'), fullPage: true });
  await tab.open(client, fx.url, fx.pid, 'Demo', 'setup', 'page');            // "Open Setup" shows the whole page again
  await settle(1200);
  assert.equal((await map()).solo, false);
  assert.deepEqual(errors.filter(e => !/404/.test(e)), []);
});

test('editing works: the kind of study chosen in the tab is saved on the hub', { skip }, async () => {
  await tab.open(client, fx.url, fx.pid, 'Demo', 'setup', 'page');
  await settle(1500);
  const n = host.changes;
  const study = async () => JSON.parse((await client.raw('GET', '/p/' + encodeURIComponent(fx.pid) + '/api/study')).data.toString('utf8'));
  const was = (await study()).kind, to = was === 'benchmark' ? 'method' : 'benchmark';
  await page.selectOption('select.st-sel', to);
  await settle(2500);
  assert.equal((await study()).kind, to);
  assert.ok(host.changes > n, 'the extension is told so the lists can refresh');
  await page.selectOption('select.st-sel', 'auto');                          // back to Lemmata's own reading
  await settle(2500);
  assert.equal((await study()).kind, was);
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
  await tab.open(client, fx.url, fx.pid, 'Demo', 'experiments');
  await settle(2500);
  const before = navigations;
  const probe = () => page.evaluate(() => {
    const vis = (sel: string) => { const e = document.querySelector(sel); return !!e && getComputedStyle(e).display !== 'none'; };
    const de = document.documentElement;
    const bar = document.getElementById('topnav') as HTMLElement;
    return { tabs: Array.from(document.querySelectorAll('.navtab .navl')).map((b: HTMLElement) => b.innerText.trim()), active: (document.querySelector('.navtab.on .navl') as HTMLElement).innerText.trim(),
      tabsFit: bar.scrollWidth <= bar.clientWidth + 1, pad: getComputedStyle(document.getElementById('page') as HTMLElement).paddingLeft,
      wide: (document.getElementById('page') as HTMLElement).getBoundingClientRect().width, sideways: de.scrollWidth > de.clientWidth + 1, band: getComputedStyle(document.querySelector('#band .bt') as HTMLElement).display, embed: de.classList.contains('embed') };
  });
  await page.setViewportSize({ width: 300, height: 800 }); await settle(500);
  const narrow = await probe();
  assert.equal(narrow.embed, true);
  assert.equal(narrow.sideways, false, 'no sideways scrolling at 300px');
  assert.equal(narrow.pad, '12px');
  assert.equal(narrow.band, 'none', 'no header band in VS Code');
  assert.deepEqual(narrow.tabs, ['Thesis', 'Setup'], 'two tabs fit with their names even at 300px'); assert.equal(narrow.tabsFit, true); assert.equal(narrow.active, 'Thesis');
  await page.setViewportSize({ width: 500, height: 800 }); await settle(500);
  const medium = await probe();
  assert.equal(medium.pad, '16px'); assert.equal(medium.sideways, false);
  await page.setViewportSize({ width: 1200, height: 800 }); await settle(500);
  const wide = await probe();
  assert.equal(wide.sideways, false); assert.ok(wide.wide <= 1100, 'content is capped in a wide tab');
  assert.equal(navigations, before, 'the mode changed without a reload');
  assert.deepEqual(errors.filter(e => !/404/.test(e)), []);
});

test('S18 width modes on Thesis: usable at 300px, columns per mode, nothing cut off, no reload', { skip }, async () => {
  const probe = () => page.evaluate(() => {
    const de = document.documentElement, W = de.clientWidth;
    const shown = (e: any) => !!e && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0;
    const cut = Array.from(document.querySelectorAll('#page button, #page a, #page select, #page input, #page textarea, .navtab'))
      .filter((e: any) => shown(e) && !e.closest('.rx-math, .katex-display, .code, .rx-ev-tablewrap, .bd-sc') && e.getBoundingClientRect().right > W + 1).length;
    const row = document.querySelector('.rx-x-sec:not(.loose) .rx-x-r:not(.head)');
    return { sideways: de.scrollWidth > W + 1, cut, cols: row ? Array.from(row.children).filter(shown).length : -1, pad: getComputedStyle(document.getElementById('page') as HTMLElement).paddingLeft };
  });
  await page.setViewportSize({ width: 1200, height: 800 });
  await tab.open(client, fx.url, fx.pid, 'Demo', 'experiments');
  await settle(2500);
  const before = navigations;
  const got: any[] = [];
  for (const w of [300, 500, 1200]) { await page.setViewportSize({ width: w, height: 800 }); await settle(500); got.push(await probe()); }
  got.forEach((g, i) => {
    assert.equal(g.sideways, false, 'Thesis scrolls sideways at ' + [300, 500, 1200][i]);
    assert.equal(g.cut, 0, 'Thesis: a control is cut off at ' + [300, 500, 1200][i]);
    assert.equal(g.cols, [2, 4, 6][i], 'Thesis columns at ' + [300, 500, 1200][i]);
  });
  assert.deepEqual(got.map(g => g.pad), ['12px', '16px', '16px'], 'padding per mode');
  assert.equal(navigations, before, 'the mode changed without a reload');
  await page.setViewportSize({ width: 1400, height: 900 });
  assert.deepEqual(errors.filter(e => !/404/.test(e)), []);
});

test('S19: a website link opens Experiments with that item selected, and an experiment\'s files open in the editor', { skip }, async () => {
  const before = navigations;
  await tab.open(client, fx.url, fx.pid, 'Demo', 'experiments', 'q:h1');
  await settle(2500);
  assert.equal(await page.evaluate(() => (window as any).eval('RX.mapSel')), 'q:h1', 'the selection from the link reached the page');
  assert.equal(await page.evaluate(() => (document.querySelector('.tab.active, [role=tab][aria-selected=true]') as HTMLElement | null)?.innerText.includes('Thesis') ?? null), true);
  assert.equal(navigations, before, 'the page was not rebuilt');
  // an experiment's details: "Open in editor" buttons for its scripts, settings and result file
  await page.evaluate(() => { (window as any).eval("RX.mapSel = null; RX.exView = 'list'"); openTab('experiments'); });
  await settle(1500);
  const rows = await page.$$('.rx-x-main');
  assert.ok(rows.length > 0, 'the sample has experiments');
  let btn: any = null;
  for (const r of rows) { await r.click(); await settle(1200); btn = await page.$('.rx-x-ed button'); if (btn) break; await r.click(); await settle(300); }
  assert.ok(btn, 'an experiment with a script or result file offers Open in editor');
  const n = host.locs.length;
  await btn.click();
  await settle(300);
  assert.equal(host.locs.length, n + 1);
  assert.deepEqual([host.locs[n].pid, typeof host.locs[n].rel, host.locs[n].rel.length > 0], [fx.pid, 'string', true]);
  assert.equal(await page.$('a[href^="vscode://"]'), null, 'no "Open in VS Code" link inside VS Code');
  assert.deepEqual(errors.filter(e => !/404/.test(e)), []);
});

test('a hub that is too old, or unreachable, gets a plain message instead of a broken page', { skip }, async () => {
  const t2 = new LemmataTab({ subscriptions: [], extensionPath: path.resolve(__dirname, '..', '..', '..') } as any, host);
  await t2.open(new HubClient('http://127.0.0.1:9', fx.token), 'http://127.0.0.1:9', 'p-offline', 'X');
  await settle(800);
  assert.match(await page.evaluate(() => document.body.innerText), /cannot be reached/);
});
