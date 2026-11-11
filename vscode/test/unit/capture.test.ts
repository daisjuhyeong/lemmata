// RunCapture against a real temporary git repository, with a small stand-in for the VS Code API (no editor needed).
import { test } from 'node:test';
import * as assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import Module = require('node:module');

/* ---------- stand-in for 'vscode' ---------- */
const disposable = { dispose() { /* */ } };
const state = { folders: [] as any[], config: {} as Record<string, unknown>, context: {} as Record<string, unknown> };
class Uri {
  scheme = 'file';
  constructor(public fsPath: string) { }
  static file(p: string) { return new Uri(p); }
  toString() { return 'file://' + this.fsPath; }
}
class EventEmitter { event = () => disposable; fire() { /* */ } dispose() { /* */ } }
class TreeItem { description?: string; tooltip?: string; iconPath?: unknown; command?: unknown; contextValue?: string; constructor(public label: string) { } }
class ThemeIcon { constructor(public id: string) { } }
const fake = {
  Uri, EventEmitter, TreeItem, ThemeIcon, StatusBarAlignment: { Left: 1 },
  workspace: {
    get workspaceFolders() { return state.folders; },
    getWorkspaceFolder: (u: Uri) => state.folders.find(f => u.fsPath === f.uri.fsPath || u.fsPath.startsWith(f.uri.fsPath + path.sep)),
    getConfiguration: () => ({ get: (k: string, d?: unknown) => (k in state.config ? state.config[k] : d) }),
    createFileSystemWatcher: () => ({ onDidCreate: () => disposable, onDidChange: () => disposable, onDidDelete: () => disposable, dispose() { /* */ } }),
    onDidChangeWorkspaceFolders: () => disposable,
  },
  window: {
    createStatusBarItem: () => ({ show() { /* */ }, hide() { /* */ }, dispose() { /* */ }, text: '', tooltip: '', command: '' }),
    onDidStartTerminalShellExecution: () => disposable, onDidEndTerminalShellExecution: () => disposable,
    createTreeView: () => disposable, showInformationMessage: async () => undefined, showWarningMessage: async () => undefined, showErrorMessage: async () => undefined,
  },
  commands: { registerCommand: () => disposable, executeCommand: async (_c: string, k: string, v: unknown) => { state.context[k] = v; } },
};
const load = (Module as any)._load;
(Module as any)._load = function (request: string, ...rest: unknown[]) { return request === 'vscode' ? fake : load.call(this, request, ...rest); };
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { RunCapture } = require('../../src/runs') as typeof import('../../src/runs');
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { HubError } = require('../../src/core/client') as typeof import('../../src/core/client');

/* ---------- helpers ---------- */
function repo() {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'lemmata-cap-')));
  const g = (...a: string[]) => execFileSync('git', ['-C', root, '-c', 'user.name=t', '-c', 'user.email=t@example.com', ...a], { stdio: 'pipe' }).toString();
  g('init', '-q');
  fs.mkdirSync(path.join(root, 'configs'));
  fs.mkdirSync(path.join(root, 'results', 'old'), { recursive: true });
  fs.writeFileSync(path.join(root, 'configs', 'mcd.yaml'), 'lr: 0.001\n');
  fs.writeFileSync(path.join(root, 'train.py'), 'print(1)\n');
  fs.writeFileSync(path.join(root, 'results', 'old', 'metrics.json'), '{"f1": 0.5}');
  g('add', '.'); g('commit', '-q', '-m', 'init');
  return { root, g };
}
function setup(root: string) {
  state.folders = [{ uri: Uri.file(root), name: 'code', index: 0 }];
  state.config = {};
  const ws: Record<string, unknown> = {};
  const posted: any[][] = [];
  const mode = { target: true, offline: false };
  const client = { postRuns: async (_pid: string, runs: any[]) => { if (mode.offline) throw new HubError(0, 'offline', 'offline'); posted.push(runs); return { added: runs.length, updated: 0, total: 0 }; } };
  const ctx = { subscriptions: [] as unknown[], extensionPath: path.resolve(__dirname, '..', '..', '..'),
    workspaceState: { get: (k: string, d: unknown) => (k in ws ? ws[k] : d), update: async (k: string, v: unknown) => { ws[k] = v; } } };
  const cap = new RunCapture(ctx as any, { log() { /* */ }, serverBase: () => 'http://hub', projectFor: () => (mode.target ? { client: client as any, pid: 'p1' } : null) }) as any;
  const exec = (cmd: string, cwd: string) => ({ commandLine: { value: cmd }, cwd: Uri.file(cwd) });
  const runs = () => { const d = path.join(root, '.lemmata', 'runs'); return fs.existsSync(d) ? fs.readdirSync(d).filter(n => n.endsWith('.json')).sort().map(n => JSON.parse(fs.readFileSync(path.join(d, n), 'utf8'))) : []; };
  return { cap, exec, runs, posted, mode };
}
const stopTimers = (cap: any) => { clearTimeout(cap.syncTimer); clearInterval(cap.retryTimer); };

test('terminal run: commit, settings hash, numbers from the metrics file, exit code, then sent once', async () => {
  const { root, g } = repo();
  const { cap, exec, runs, posted } = setup(root);
  try {
    const head = g('rev-parse', 'HEAD').trim();
    const e = exec('CUDA_VISIBLE_DEVICES=0 python train.py --config configs/mcd.yaml', root);
    await cap.onStart({ execution: e, shellIntegration: { cwd: Uri.file(root) } });
    let r = runs();
    assert.equal(r.length, 1);
    assert.deepEqual([r[0].source, r[0].git_sha, r[0].dirty, r[0].diff_hash, r[0].ended], ['terminal', head, false, null, null]);
    assert.deepEqual(r[0].configs.map((c: any) => c.path), ['configs/mcd.yaml']);
    assert.match(r[0].configs[0].hash, /^sha256:[0-9a-f]{64}$/);
    // the run writes its numbers
    fs.mkdirSync(path.join(root, 'results', 's2'), { recursive: true });
    const mfile = path.join(root, 'results', 's2', 'metrics.json');
    fs.writeFileSync(mfile, '{"f1": 0.851, "auroc": 0.912}');
    await cap.onResult(mfile);
    await cap.onResult(mfile);                         // the same content again changes nothing
    await cap.onEnd({ execution: e, exitCode: 0 });
    r = runs();
    assert.equal(r.length, 1);
    assert.deepEqual([r[0].metrics, r[0].artifacts.map((a: any) => a.path), r[0].exit_code], [{ f1: 0.851, auroc: 0.912 }, ['results/s2/metrics.json'], 0]);
    assert.match(r[0].ended, /^\d{4}-\d{2}-\d{2}T/);
    assert.equal(fs.readFileSync(path.join(root, '.lemmata', '.gitignore'), 'utf8'), '*\n');
    assert.equal(g('status', '--porcelain', '--', '.lemmata'), '');
    assert.deepEqual(await cap.sync(), { sent: 1, waiting: 0, reason: undefined });
    assert.deepEqual(await cap.sync(), { sent: 0, waiting: 0, reason: undefined });
    assert.equal(posted.length, 1);
    assert.equal(posted[0][0].run_id, r[0].run_id);
    assert.equal(JSON.stringify(posted).includes('lr: 0.001'), false, 'file contents are never sent');
    // the tree shows it
    const item = cap.getTreeItem(cap.getChildren()[0]);
    assert.match(item.description, /f1=0\.851 auroc=0\.912/);
    assert.equal(state.context['lemmata.hasRuns'], true);
  } finally { stopTimers(cap); fs.rmSync(root, { recursive: true, force: true }); }
});

test('uncommitted changes: the run is marked dirty and the patch is kept locally', async () => {
  const { root } = repo();
  const { cap, exec, runs } = setup(root);
  try {
    fs.writeFileSync(path.join(root, 'train.py'), 'print(2)\n');
    await cap.onStart({ execution: exec('python train.py', root), shellIntegration: { cwd: undefined } });
    const r = runs();
    assert.equal(r[0].dirty, true);
    assert.match(r[0].diff_hash, /^sha256:[0-9a-f]{64}$/);
    const patches = fs.readdirSync(path.join(root, '.lemmata', 'patches'));
    assert.equal(patches.length, 1);
    assert.match(fs.readFileSync(path.join(root, '.lemmata', 'patches', patches[0]), 'utf8'), /\+print\(2\)/);
  } finally { stopTimers(cap); fs.rmSync(root, { recursive: true, force: true }); }
});

test('not logged: everyday commands, commands outside the workspace, capture switched off', async () => {
  const { root } = repo();
  const { cap, exec, runs } = setup(root);
  try {
    await cap.onStart({ execution: exec('git status', root), shellIntegration: {} });
    await cap.onStart({ execution: exec('python -m pip install torch', root), shellIntegration: {} });
    await cap.onStart({ execution: exec('python train.py', os.tmpdir()), shellIntegration: {} });
    state.config = { capture: false };
    await cap.onStart({ execution: exec('python train.py', root), shellIntegration: {} });
    assert.equal(runs().length, 0);
    state.config = { commandPattern: '^make\\s' };
    await cap.onStart({ execution: exec('make train', root), shellIntegration: {} });
    assert.equal(runs().length, 1);
  } finally { stopTimers(cap); fs.rmSync(root, { recursive: true, force: true }); }
});

test('results watcher: a detached job gets one entry per file and commit; files that came from git get none', async () => {
  const { root, g } = repo();
  const { cap, runs } = setup(root);
  try {
    await cap.onResult(path.join(root, 'results', 'old', 'metrics.json'));        // committed and unchanged: arrived by git
    await cap.onResult(path.join(root, 'configs', 'mcd.yaml'));                    // not a metrics file
    assert.equal(runs().length, 0);
    fs.mkdirSync(path.join(root, 'results', 'night'), { recursive: true });
    const f = path.join(root, 'results', 'night', 'eval_results.json');
    fs.writeFileSync(f, '{"f1": 0.7}');
    await cap.onResult(f);
    let r = runs();
    assert.equal(r.length, 1);
    assert.deepEqual([r[0].source, r[0].command, r[0].started, r[0].metrics, r[0].git_sha], ['watcher', null, null, { f1: 0.7 }, g('rev-parse', 'HEAD').trim()]);
    fs.writeFileSync(f, '{"f1": 0.75}');                                           // the job writes again (next epoch): same entry
    await cap.onResult(f);
    r = runs();
    assert.equal(r.length, 1);
    assert.deepEqual(r[0].metrics, { f1: 0.75 });
    fs.writeFileSync(path.join(root, 'results', 'old', 'metrics.json'), '{"f1": 0.6}');     // a committed result file is rewritten: that is a run
    await cap.onResult(path.join(root, 'results', 'old', 'metrics.json'));
    assert.equal(runs().length, 2);
    assert.match(cap.getTreeItem(cap.getChildren()[0]).label, /^Results watcher: results\//);
  } finally { stopTimers(cap); fs.rmSync(root, { recursive: true, force: true }); }
});

test('sync: runs wait while the hub is unreachable or the folder is not a hub project, then go out', async () => {
  const { root } = repo();
  const { cap, exec, runs, posted, mode } = setup(root);
  try {
    const e = exec('python train.py', root);
    await cap.onStart({ execution: e, shellIntegration: {} });
    mode.offline = true;
    let s = await cap.sync();
    assert.deepEqual([s.sent, s.waiting], [0, 1]);
    assert.match(s.reason, /cannot be reached/);
    mode.offline = false; mode.target = false;
    s = await cap.sync();
    assert.deepEqual([s.sent, s.waiting], [0, 1]);
    assert.match(s.reason, /not the code repository/);
    mode.target = true;
    assert.deepEqual(await cap.sync(), { sent: 1, waiting: 0, reason: undefined });
    await cap.onEnd({ execution: e, exitCode: 2 });                                // the run changes after it was sent: it goes out again
    assert.equal(runs()[0].exit_code, 2);
    assert.deepEqual(await cap.sync(), { sent: 1, waiting: 0, reason: undefined });
    assert.equal(posted.length, 2);
    assert.equal(posted[1][0].exit_code, 2);
    assert.match(cap.getTreeItem(cap.getChildren()[0]).description, /exit 2/);
  } finally { stopTimers(cap); fs.rmSync(root, { recursive: true, force: true }); }
});

test('hook manifests on disk are picked up; a terminal run the hook already logged is not logged twice', async () => {
  const { root } = repo();
  const { cap, exec, runs } = setup(root);
  try {
    execFileSync('python3', [path.resolve(__dirname, '..', '..', '..', 'media', 'hooks', 'log_run.py')],
      { input: JSON.stringify({ tool_name: 'Bash', tool_use_id: 't1', cwd: root, hook_event_name: 'PreToolUse', tool_input: { command: 'python train.py --seed 7' } }), env: { ...process.env, CLAUDE_PROJECT_DIR: root } });
    fs.writeFileSync(path.join(root, '.lemmata', 'runs', 'junk.json'), '{"not": "a run"}');
    await cap.reload();
    assert.equal(cap.getChildren().length, 1);
    assert.equal(cap.getChildren()[0].man.source, 'agent');
    assert.equal(cap.pending().length, 1);
    await cap.onStart({ execution: exec('python train.py --seed 7', root), shellIntegration: {} });
    assert.equal(runs().filter((r: any) => r.run_id).length, 1);
    // a result file written while the agent's run is going is attached to the agent's run
    fs.mkdirSync(path.join(root, 'outputs'), { recursive: true });
    fs.writeFileSync(path.join(root, 'outputs', 'metrics.json'), '{"acc": 0.93}');
    await cap.onResult(path.join(root, 'outputs', 'metrics.json'));
    const agent = runs().find((r: any) => r.source === 'agent');
    assert.deepEqual([agent.metrics, agent.artifacts.length], [{ acc: 0.93 }, 1]);
    assert.equal(runs().filter((r: any) => r.source === 'watcher').length, 0);
  } finally { stopTimers(cap); fs.rmSync(root, { recursive: true, force: true }); }
});
