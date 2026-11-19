// S35: the whole extension (src/extension.ts) against a real hub, with a stand-in for the VS Code API (no editor needed).
// It activates the extension in a checkout of the sample project, reads the three lists the way VS Code would
// (getChildren / getTreeItem), and uses what a row offers: copy, snooze, attach, open the file, open the website.
import { test, before, after } from 'node:test';
import * as assert from 'node:assert/strict';
import { spawn, execFileSync, ChildProcess } from 'node:child_process';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import Module = require('node:module');

/* eslint-disable @typescript-eslint/no-explicit-any */
const REPO = path.resolve(__dirname, '../../../..');
const disposable = { dispose() { /* */ } };
const S = {
  folders: [] as any[], config: {} as Record<string, unknown>, secrets: {} as Record<string, string>, context: {} as Record<string, unknown>,
  commands: new Map<string, (...a: any[]) => any>(), views: {} as Record<string, any>, bar: null as any,
  picks: [] as ((items: any[], o: any) => any)[], info: [] as string[], warn: [] as string[], error: [] as string[], statusMsg: [] as string[],
  clipboard: '', external: [] as string[], shown: [] as any[], executed: [] as any[][], panels: 0,
};
class Uri {
  scheme = 'file';
  constructor(public fsPath: string, private readonly raw?: string) { }
  static file(p: string) { return new Uri(p); }
  static parse(u: string) { return new Uri('', u); }
  static joinPath(b: Uri, ...segs: string[]) { return new Uri(path.join(b.fsPath, ...segs)); }
  toString() { return this.raw || 'file://' + this.fsPath; }
}
class EventEmitter { private fns: ((v: any) => void)[] = []; event = (fn: (v: any) => void) => { this.fns.push(fn); return disposable; }; fire(v: any) { for (const f of this.fns) f(v); } dispose() { /* */ } }
class TreeItem { id?: string; description?: string; tooltip?: string; iconPath?: any; command?: any; contextValue?: string; constructor(public label: string, public collapsibleState = 0) { } }
class ThemeIcon { constructor(public id: string) { } }
class ThemeColor { constructor(public id: string) { } }
class Range { constructor(public a: number, public b: number, public c: number, public d: number) { } }
const cfg = () => ({ get: (k: string, d?: unknown) => (k in S.config ? S.config[k] : d), inspect: (k: string) => ({ globalValue: S.config[k] }), update: async (k: string, v: unknown) => { S.config[k] = v; } });
const fake = {
  Uri, EventEmitter, TreeItem, ThemeIcon, ThemeColor, Range,
  TreeItemCollapsibleState: { None: 0, Collapsed: 1, Expanded: 2 }, StatusBarAlignment: { Left: 1 }, ViewColumn: { Active: -1, Beside: -2 },
  QuickPickItemKind: { Separator: -1 }, ConfigurationTarget: { Global: 1 }, ProgressLocation: { Notification: 15 },
  workspace: {
    get workspaceFolders() { return S.folders; },
    getWorkspaceFolder: (u: Uri) => S.folders.find(f => u.fsPath === f.uri.fsPath || u.fsPath.startsWith(f.uri.fsPath + path.sep)),
    getConfiguration: cfg,
    createFileSystemWatcher: () => ({ onDidCreate: () => disposable, onDidChange: () => disposable, onDidDelete: () => disposable, dispose() { /* */ } }),
    onDidChangeWorkspaceFolders: () => disposable, onDidChangeConfiguration: () => disposable, asRelativePath: (u: Uri) => u.fsPath,
  },
  window: {
    state: { focused: true },
    createStatusBarItem: () => (S.bar = { show() { /* */ }, hide() { /* */ }, dispose() { /* */ }, text: '', tooltip: '', command: '', backgroundColor: undefined }),
    createOutputChannel: () => ({ appendLine() { /* */ }, dispose() { /* */ } }),
    createTreeView: (id: string, o: any) => (S.views[id] = { provider: o.treeDataProvider, message: undefined, badge: undefined, description: undefined, dispose() { /* */ } }),
    createWebviewPanel: () => { S.panels++; return { webview: { html: '', onDidReceiveMessage: () => disposable, postMessage: async () => true }, reveal() { /* */ }, onDidDispose: () => disposable, dispose() { /* */ } }; },
    registerUriHandler: () => disposable, onDidChangeWindowState: () => disposable,
    onDidStartTerminalShellExecution: () => disposable, onDidEndTerminalShellExecution: () => disposable,
    showQuickPick: async (items: any[], o: any) => { const f = S.picks.shift(); return f ? f(items, o) : undefined; },
    showInformationMessage: async (m: string) => { S.info.push(m); return undefined; }, showWarningMessage: async (m: string) => { S.warn.push(m); return undefined; },
    showErrorMessage: async (m: string) => { S.error.push(m); return undefined; }, setStatusBarMessage: (m: string) => { S.statusMsg.push(m); return disposable; },
    showTextDocument: async (u: any, o: any) => { S.shown.push([u, o]); return {}; }, withProgress: async (_o: any, fn: () => Promise<unknown>) => fn(),
  },
  commands: {
    registerCommand: (id: string, fn: (...a: any[]) => any) => { S.commands.set(id, fn); return disposable; },
    executeCommand: async (id: string, ...a: any[]) => { if (id === 'setContext') { S.context[a[0]] = a[1]; return; } S.executed.push([id, ...a]); const f = S.commands.get(id); return f ? f(...a) : undefined; },
  },
  env: { clipboard: { writeText: async (t: string) => { S.clipboard = t; } }, openExternal: async (u: any) => { S.external.push(u.toString()); return true; } },
};
const load = (Module as any)._load;
(Module as any)._load = function (request: string, ...rest: unknown[]) { return request === 'vscode' ? fake : load.call(this, request, ...rest); };
// eslint-disable-next-line @typescript-eslint/no-var-requires
const ext = require('../../src/extension') as typeof import('../../src/extension');
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { HubClient } = require('../../src/core/client') as typeof import('../../src/core/client');
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { tokenKey } = require('../../src/core/settings') as typeof import('../../src/core/settings');
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { isoLocal, runId, sha256 } = require('../../src/core/runs') as typeof import('../../src/core/runs');

let proc: ChildProcess, fx: any, tmp: string, ws: string, client: InstanceType<typeof HubClient>;
const subs: any[] = [];
const git = (cwd: string, ...a: string[]) => execFileSync('git', a, { cwd, encoding: 'utf8' });
const pkg = JSON.parse(fs.readFileSync(path.join(REPO, 'vscode/package.json'), 'utf8'));
const run = (id: string, ...a: any[]) => { const f = S.commands.get(id); assert.ok(f, id + ' is registered'); return f!(...a); };
const wait = (ms: number) => new Promise(r => setTimeout(r, ms));

/** Read a list the way VS Code does: every row, with the tree item it is drawn as. */
function read(view: string): { node: any; item: any; depth: number }[] {
  const p = S.views[view].provider, out: { node: any; item: any; depth: number }[] = [];
  const walk = (n: any, depth: number) => { for (const k of p.getChildren(n)) { out.push({ node: k, item: p.getTreeItem(k), depth }); walk(k, depth + 1); } };
  walk(undefined, 0);
  return out;
}

before(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'lemmata-views-'));
  proc = spawn('python3', [path.join(REPO, 'vscode/test/hub_fixture.py'), path.join(tmp, 'fx')], { stdio: ['pipe', 'pipe', 'inherit'] });
  fx = await new Promise((res, rej) => {
    let buf = '';
    proc.stdout!.on('data', d => { buf += d; const i = buf.indexOf('\n'); if (i >= 0) { try { res(JSON.parse(buf.slice(0, i))); } catch (e) { rej(e); } } });
    proc.on('exit', c => rej(new Error('fixture exited ' + c)));
  });
  client = new HubClient(fx.url, fx.token);
  ws = path.join(tmp, 'ws', 'code');
  git(tmp, 'clone', '-q', path.join(fx.sample, 'code'), ws);
  git(ws, 'remote', 'set-url', 'origin', 'git@github.com:Alice/Demo-Code.git');
  // a run made on this machine before VS Code started: it wrote the metrics file the hub tracks
  const started = new Date(Date.now() - 60000), id = runId(started, 'python train.py --seed 7', ws);
  const text = fs.readFileSync(path.join(ws, 'results/metrics.json'), 'utf8');
  fs.mkdirSync(path.join(ws, '.lemmata', 'runs'), { recursive: true });
  fs.writeFileSync(path.join(ws, '.lemmata', '.gitignore'), '*\n');
  fs.writeFileSync(path.join(ws, '.lemmata', 'runs', id + '.json'), JSON.stringify({ run_id: id, source: 'terminal', command: 'python train.py --seed 7', cwd: ws, host: 'test',
    git_sha: git(ws, 'rev-parse', 'HEAD').trim(), dirty: false, diff_hash: null, configs: [], metrics: { f1: 0.8 }, artifacts: [{ path: 'results/metrics.json', hash: sha256(text) }],
    started: isoLocal(started), ended: isoLocal(new Date(Date.now() - 30000)), exit_code: 0 }));
  S.folders = [{ uri: Uri.file(ws), name: 'code', index: 0 }];
  S.config = { serverUrl: fx.url, refreshSeconds: 3600 };
  S.secrets[tokenKey(fx.url)] = fx.token;
  const state = (o: Record<string, unknown>) => ({ get: (k: string, d?: unknown) => (k in o ? o[k] : d), update: async (k: string, v: unknown) => { o[k] = v; } });
  await ext.activate({ subscriptions: subs, extensionPath: path.join(REPO, 'vscode'), extension: { packageJSON: pkg }, globalState: state({}), workspaceState: state({}),
    secrets: { get: async (k: string) => S.secrets[k], store: async (k: string, v: string) => { S.secrets[k] = v; }, delete: async (k: string) => { delete S.secrets[k]; }, onDidChange: () => disposable } } as any);
  await S.commands.get('lemmata.runs.sync')!();      // send the run, then read the hub again
  await S.commands.get('lemmata.refresh')!();
  await wait(400);
});
after(() => { for (const s of subs) { try { s.dispose(); } catch { /* */ } } try { proc.stdin!.end(); } catch { /* */ } try { proc.kill(); } catch { /* */ } fs.rmSync(tmp, { recursive: true, force: true }); });

test('activation: three lists, one status-bar item, and every contributed command registered', () => {
  assert.deepEqual(Object.keys(S.views).sort(), ['lemmata.experiments', 'lemmata.now', 'lemmata.torun']);
  for (const c of pkg.contributes.commands) assert.ok(S.commands.has(c.command), c.command + ' is registered');
  assert.deepEqual([S.context['lemmata.connected'], S.context['lemmata.hasProject'], S.context['lemmata.hasRuns']], [true, true, true]);
  assert.match(S.bar.text, /^\$\(beaker\) /);
  assert.doesNotMatch(S.bar.text, /not sent|offline|no project|connect/);
  assert.equal(S.bar.command, 'lemmata.showPanel');
  assert.deepEqual(S.error, []);
});

test('every row of every list can be drawn: unique ids, plain-text tooltips, commands that exist', () => {
  for (const v of ['lemmata.now', 'lemmata.experiments', 'lemmata.torun']) {
    const rows = read(v);
    const ids = rows.map(r => r.item.id);
    assert.equal(new Set(ids).size, ids.length, v + ': a tree item id is used twice');
    for (const r of rows) {
      assert.ok(r.item.label && typeof r.item.label === 'string', v + ': a row has no label');
      assert.equal(typeof r.item.tooltip, 'string', 'tooltips are plain text, never markdown');
      assert.match(r.item.contextValue, /^row(-(open|site|tab|copy|snooze|attach|record))*$/);
      if (r.item.command) assert.ok(S.commands.has(r.item.command.command), r.item.command.command);
      if (r.item.iconPath) assert.match(r.item.iconPath.id, /^[a-z][a-z0-9~-]*$/);
    }
  }
});

test('an experiment that tests two claims stands under both, and every line still has its own id', () => {
  const { RowTree } = ext.internals() as any;
  const x = { id: 'map:cost', label: 'Compute cost', kids: [{ id: 'map:cost|measure', label: 'Measure' }] };
  const tree = new RowTree('experiments', () => [
    { row: { id: 'q|q1', label: 'C1', kids: [x, { id: 'map:main', label: 'Main comparison' }] }, pid: 'p1' },
    { row: { id: 'q|q3', label: 'C3', kids: [x, x] }, pid: 'p1' },              // even the same row twice under one parent
    { row: { id: 'q|q1', label: 'C1 in another project', kids: [x] }, pid: 'p2' }]);
  const ids: string[] = [];
  const walk = (n?: any) => { for (const k of tree.getChildren(n)) { ids.push(tree.getTreeItem(k).id); walk(k); } };
  walk();
  assert.equal(ids.length, 3 + 3 + 4 + 2);
  assert.equal(new Set(ids).size, ids.length, 'every line has its own id');
  const again: string[] = [];
  const walk2 = (n?: any) => { for (const k of tree.getChildren(n)) { again.push(tree.getTreeItem(k).id); walk2(k); } };
  walk2();
  assert.deepEqual(again, ids, 'and keeps it from one refresh to the next');
});

test('the lists as text (set LEMMATA_DUMP to a file to keep them)', () => {
  const out: string[] = ['status bar: ' + S.bar.text, ''];
  for (const [v, name] of [['lemmata.now', 'NOW'], ['lemmata.experiments', 'EXPERIMENTS'], ['lemmata.torun', 'TO RUN']]) {
    out.push(name);
    for (const r of read(v)) out.push('  '.repeat(r.depth + 1) + (r.item.collapsibleState === 2 ? '▾ ' : r.item.collapsibleState === 1 ? '▸ ' : '· ') + r.item.label + (r.item.description ? '   — ' + r.item.description : ''));
    out.push('');
  }
  if (process.env.LEMMATA_DUMP) fs.writeFileSync(process.env.LEMMATA_DUMP, out.join('\n'));
  assert.ok(out.length > 6);
});

test('Now: the run made on this machine is there once, sent, with its numbers, and opens its record', async () => {
  const rows = read('lemmata.now');
  const groups = rows.filter(r => r.depth === 0).map(r => r.item.label);
  assert.ok(groups.length > 0 && groups.every(g => ['Running', 'Not sent to the hub', 'Failed today', 'Not attached to an experiment', 'Finished today', 'On other machines today', 'Earlier'].includes(g)), groups.join(', '));
  const mine = rows.filter(r => r.node.row.run && /seed 7/.test(r.item.label));
  assert.equal(mine.length, 1, 'the hub\'s copy of a local run is not listed a second time');
  assert.doesNotMatch(mine[0].item.description, /not sent yet/);
  assert.match(mine[0].item.tooltip, /Sent to the hub\./);
  assert.equal(mine[0].item.command.command, 'lemmata.row.record');
  await run('lemmata.row.record', mine[0].node);
  assert.match(S.shown[S.shown.length - 1][0].fsPath, /\.lemmata[\\/]runs[\\/].+\.json$/);
});

test('Experiments: claims, experiments under them, and each experiment\'s setup one line each; a row offers the website, Setup and a prompt', async () => {
  const rows = read('lemmata.experiments');
  assert.ok(rows.length > 0, 'the sample project has experiments');
  assert.equal(S.context['lemmata.hasExperiments'], true);
  const exps = rows.filter(r => r.node.row.x && r.node.row.kids && /-tab/.test(r.item.contextValue));
  assert.ok(exps.length > 0, 'an experiment row');
  const x = exps[0];
  assert.match(x.item.contextValue, /-site/); assert.match(x.item.contextValue, /-copy/);
  assert.equal(x.item.command, undefined, 'clicking an experiment opens its rows; it does not jump away');
  const kids = S.views['lemmata.experiments'].provider.getChildren(x.node).map((k: any) => k.row.label);
  assert.ok(kids.some((k: string) => /^Tests /.test(k)), 'what it tests: ' + kids.join(', '));
  // copy the prompt for Claude Code
  await run('lemmata.row.copy', x.node);
  assert.match(S.clipboard, /experiment_brief/);
  assert.match(S.clipboard, new RegExp('x:' + x.node.row.x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.match(S.statusMsg[S.statusMsg.length - 1], /copied a prompt for Claude Code\. Paste it into Claude Code\./);
  // the website, with this experiment selected
  S.external.length = 0;
  await run('lemmata.row.site', x.node);
  assert.equal(S.external[0], fx.url + '/p/' + fx.pid + '/#go=experiments&sel=' + encodeURIComponent('x:' + x.node.row.x));
  // Setup in the tab
  const n = S.panels;
  await run('lemmata.row.tab', x.node);
  assert.equal(S.panels, n + 1, 'a tab is opened for Setup');
  // a row that names a file opens it in the editor
  const file = rows.find(r => /-open/.test(r.item.contextValue));
  if (file) {
    const before = S.shown.length;
    await run('lemmata.row.open', file.node);
    assert.equal(S.shown.length + S.info.filter(m => /is not in a folder open in this window/.test(m)).length > before, true);
  }
});

test('Attach: a run on this machine is tied to an experiment by hand, and the hub keeps it', async () => {
  const mine = read('lemmata.now').find(r => r.node.row.run && /seed 7/.test(r.item.label))!;
  assert.match(mine.item.contextValue, /-attach/);
  const b = JSON.parse((await client.raw('GET', '/p/' + fx.pid + '/api/bench')).data.toString('utf8'));
  const target = b.pick[b.pick.length - 1];
  let offered: any[] = [];
  S.picks.push(items => { offered = items; return items.find((i: any) => i.x === target.id); });
  await run('lemmata.run.attach', mine.node);
  assert.deepEqual(offered.filter(i => i.x).map(i => i.x), b.pick.map((p: any) => p.id));
  const after = JSON.parse((await client.raw('GET', '/p/' + fx.pid + '/api/bench')).data.toString('utf8'));
  assert.deepEqual([after.runs[mine.node.row.run].x, after.runs[mine.node.row.run].how], [target.id, 'attached']);
  const again = read('lemmata.now').find(r => r.node.row.run === mine.node.row.run)!;
  assert.match(again.item.description, new RegExp(target.label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.match(again.item.tooltip, /attached by you/);
  // take it back
  S.picks.push(items => items.find((i: any) => i.x === null));
  await run('lemmata.run.attach', again.node);
  const back = JSON.parse((await client.raw('GET', '/p/' + fx.pid + '/api/bench')).data.toString('utf8'));
  assert.notEqual((back.runs[mine.node.row.run] || {}).how, 'attached');
  assert.deepEqual(S.error, []);
});

test('To run: an item can be snoozed from VS Code and leaves the hub\'s list too', async () => {
  const rows = read('lemmata.torun');
  const item = rows.find(r => /-snooze/.test(r.item.contextValue));
  if (!item) { assert.equal(S.context['lemmata.hasToRun'], false, 'nothing to run in the sample: the list shows its welcome text'); return; }
  const key = item.node.row.snooze;
  let asked = '';
  S.picks.push((items, o) => { asked = o.placeHolder; return items[1]; });      // "For a week"
  await run('lemmata.row.snooze', item.node);
  assert.match(asked, /Hide ".+" from the list for how long\?/);
  assert.equal(read('lemmata.torun').some(r => r.node.row.snooze === key), false);
  const todo = JSON.parse((await client.raw('GET', '/p/' + fx.pid + '/api/todo')).data.toString('utf8'));
  assert.equal(todo.items.some((i: any) => i.key === key), false);
  assert.ok(todo.counts.snoozed >= 1);
});

test('Go to…: one picker; experiment pages open here, every other page on the website', async () => {
  let items: any[] = [];
  S.picks.push(list => { items = list; return list.find((i: any) => i.label === 'LaTeX'); });
  S.external.length = 0;
  await run('lemmata.goto');
  assert.equal(S.external[0], fx.url + '/p/' + fx.pid + '/#go=latex');
  const labels = items.filter(i => i.kind !== -1).map(i => i.label.replace(/^\$\([a-z-]+\) /, ''));
  for (const want of ['Now', 'Experiments', 'To run', 'Map', 'Setup', 'Thesis', 'Home', 'Baselines', 'LaTeX', 'Review', 'Trail', 'Settings and FAQ', 'Send runs to the hub now', 'Sync the hub with GitHub now'])
    assert.ok(labels.includes(want), want + ' is in Go to…');
  assert.deepEqual(items.filter(i => i.kind === -1).map(i => i.label), ['In VS Code', 'On the website (opens your browser)', 'Do']);
  const n = S.panels;
  S.picks.push(list => list.find((i: any) => /Map$/.test(i.label)));
  await run('lemmata.goto');
  assert.equal(S.panels + S.executed.filter(e => e[0] === 'workbench.action.moveEditorToNewWindow').length >= n, true);
  S.picks.push(list => list.find((i: any) => / Now$/.test(i.label)));
  await run('lemmata.goto');
  assert.deepEqual(S.executed[S.executed.length - 1], ['lemmata.now.focus']);
});

test('a run that ends is said once in the status bar, with its experiment when the hub knows it', async () => {
  const mine = read('lemmata.now').find(r => r.node.row.run && /seed 7/.test(r.item.label))!;
  const b = JSON.parse((await client.raw('GET', '/p/' + fx.pid + '/api/bench')).data.toString('utf8'));
  const ctrl = ext.internals().controller as any;
  ctrl.runEnded(mine.node.row.run);
  const note = b.runs[mine.node.row.run];
  assert.equal(S.bar.text, '$(beaker) ' + (note && note.line ? note.line + ' · ' + note.name : 'f1=0.8 · ' + (note ? note.name : 'python train.py --seed 7')));
  assert.equal(S.bar.backgroundColor, undefined, 'a result is shown, never coloured as good or bad');
  ctrl.flash = null; ctrl.draw();
  assert.doesNotMatch(S.bar.text, /f1/);
});

test('a hub without the bench (older than S35) is named, not shown as an empty list; offline keeps the last rows', async () => {
  const { HubError } = require('../../src/core/client') as typeof import('../../src/core/client');
  const ctrl = ext.internals().controller as any, c = ctrl.clientOrNull(), real = c.bench;
  const had = read('lemmata.experiments').length;
  try {
    c.bench = async () => { throw new HubError(404, 'not_found', 'unknown route'); };
    await ctrl.refresh();
    const rows = read('lemmata.experiments');
    assert.equal(rows.length, 1);
    assert.match(rows[0].item.label, /Your hub is older than this extension\. Update the hub/);
    assert.equal(S.context['lemmata.hasExperiments'], true, 'the message is a row, so the "no experiments yet" text does not show');
    // runs on this machine are still listed: the Now list does not depend on the bench
    assert.ok(read('lemmata.now').some(r => r.node.row.run));
    c.bench = real;
    await ctrl.refresh();
    assert.equal(read('lemmata.experiments').length, had);
    c.bench = async () => { throw new HubError(0, 'offline', 'offline'); };
    await ctrl.refresh();
    assert.equal(read('lemmata.experiments').length, had, 'the last rows stay while the hub cannot be reached');
    assert.match(S.bar.text, /offline/);
    assert.match(S.views['lemmata.experiments'].message, /Offline/);
  } finally { c.bench = real; await ctrl.refresh(); }
  assert.equal(S.views['lemmata.experiments'].message, undefined);
  assert.doesNotMatch(S.bar.text, /offline/);
});
