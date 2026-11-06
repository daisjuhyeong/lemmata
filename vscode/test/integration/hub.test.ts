// Integration: real hub server + fake GitHub (test/hub_fixture.py), token from `lemmata hub token`.
import { test, before, after } from 'node:test';
import * as assert from 'node:assert/strict';
import { spawn, execFileSync, ChildProcess } from 'node:child_process';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { HubClient, HubError } from '../../src/core/client';
import { loadModel } from '../../src/core/load';
import { matchProjects, parseGitConfigRemotes } from '../../src/core/remotes';
import { toDiagnostics, Diag } from '../../src/core/model';
import { formatWhy } from '../../src/core/why';

const REPO = path.resolve(__dirname, '../../../..');
let proc: ChildProcess; let fx: any; let tmp: string; let client: HubClient;
let wsCode: string, wsPaper: string;

const git = (cwd: string, ...a: string[]) => execFileSync('git', a, { cwd, encoding: 'utf8' });
function remotes(cwd: string) { try { return parseGitConfigRemotes(git(cwd, 'config', '--get-regexp', '^remote\\..*\\.url$')); } catch { return []; } }

before(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'lemmata-vsc-'));
  proc = spawn('python3', [path.join(REPO, 'vscode/test/hub_fixture.py'), path.join(tmp, 'fx')], { stdio: ['pipe', 'pipe', 'inherit'] });
  fx = await new Promise((res, rej) => {
    let buf = '';
    proc.stdout!.on('data', d => { buf += d; const i = buf.indexOf('\n'); if (i >= 0) { try { res(JSON.parse(buf.slice(0, i))); } catch (e) { rej(e); } } });
    proc.on('exit', c => rej(new Error('fixture exited ' + c)));
  });
  client = new HubClient(fx.url, fx.token);
  // "a checkout of it": clone the sample repos; set the remotes a real checkout would have
  wsCode = path.join(tmp, 'ws', 'code'); wsPaper = path.join(tmp, 'ws', 'paper');
  git(tmp, 'clone', '-q', path.join(fx.sample, 'code'), wsCode);
  git(tmp, 'clone', '-q', path.join(fx.sample, 'paper'), wsPaper);
  git(wsCode, 'remote', 'set-url', 'origin', 'git@github.com:Alice/Demo-Code.git');
  git(wsPaper, 'remote', 'set-url', 'origin', 'https://github.com/' + fx.paper_repo + '.git');
});
after(() => { try { proc.stdin!.end(); } catch { /* */ } try { proc.kill(); } catch { /* */ } fs.rmSync(tmp, { recursive: true, force: true }); });

async function bindAll() {
  const projects = await client.projects();
  const b = matchProjects([{ key: 'code', remotes: remotes(wsCode) }, { key: 'paper', remotes: remotes(wsPaper) }], projects);
  assert.equal(b.length, 1, 'one hub project matches the checkout');
  assert.equal(b[0].project.id, fx.pid);
  return b[0];
}
const wsOf = (d: Diag) => (d.folder === 'code' ? wsCode : wsPaper);
const lineText = (d: Diag) => fs.readFileSync(path.join(wsOf(d), d.rel), 'utf8').split('\n')[d.line0];

test('remote matching finds the project from the checkout (code and paper, both GitHub)', async () => {
  const b = await bindAll();
  assert.deepEqual(b.folders, { code: 'code', paper: 'paper' });
});

test('alarms: the golden set (A1 = config + run + table2.csv + Table 2, A2 = App. B), at real file:line', async () => {
  const b = await bindAll();
  const m = await loadModel(client, fx.pid);
  assert.deepEqual(m.groups.map(g => g.display), ['A1', 'A2']);
  const names = (i: number) => m.groups[i].nodes.map(n => n.name + ' [' + n.role + ']');
  assert.deepEqual(names(0), ['configs/default.yaml [changed]', 'run train_main [downstream]', 'results/table2.csv [downstream]', 'Table 2 [downstream]']);
  assert.deepEqual(names(1), ['App. B Hyperparameters [changed]']);
  assert.equal(m.recheck, 5);
  const d = toDiagnostics(m, b.folders).filter(x => x.kind === 'alarm');
  assert.equal(d.length, 5);
  for (const x of d) {
    assert.ok(fs.existsSync(path.join(wsOf(x), x.rel)), 'mapped file exists in the checkout: ' + x.rel);
    assert.equal(x.severity, 'warning');
    assert.equal(x.source, 'Lemmata');
  }
  const byRel = (r: string) => d.find(x => x.rel === r)!;
  assert.match(byRel('main.tex').message, /^Recheck: Table 2 — [0-9a-f]{7} change learning rate 3e-4 to 1e-3 \(downstream of configs\/default\.yaml\)$/);
  assert.match(lineText(byRel('main.tex')), /\\begin\{table/);
  assert.match(byRel('appendix.tex').message, /^Recheck: App\. B Hyperparameters — [0-9a-f]{7} .*\(changed\)$/);
  assert.equal(byRel('appendix.tex').code, 'A2');
  assert.equal(byRel('configs/default.yaml').code, 'A1');
});

test('findings: evidence locations land on the quoted lines', async () => {
  const b = await bindAll();
  const m = await loadModel(client, fx.pid);
  const d = toDiagnostics(m, b.folders).filter(x => x.kind === 'finding');
  assert.ok(d.length >= 8, 'got ' + d.length);
  const lr = d.filter(x => x.code === 'main_appendix_mismatch' && /[Ll]earning rate/.test(x.message));
  assert.equal(lr.length, 2);
  for (const x of lr) assert.match(lineText(x), /[Ll]earning rate/);
  const unc = d.filter(x => x.code === 'uncited_reference');
  assert.equal(unc.length, 1);
  assert.equal(unc[0].severity, 'information');
  assert.match(lineText(unc[0]), /unused2019/);
  const undef = d.filter(x => x.code === 'undefined_cite');
  assert.match(lineText(undef[0]), /nobody2020/);
});

test('without the paper checkout, only code-repo diagnostics are published (paper rows stay panel-only)', async () => {
  const projects = await client.projects();
  const b = matchProjects([{ key: 'code', remotes: remotes(wsCode) }], projects)[0];
  const m = await loadModel(client, fx.pid);
  const d = toDiagnostics(m, b.folders);
  assert.ok(d.length >= 2 && d.every(x => x.folder === 'code'));
  assert.ok(m.groups[1].nodes.length === 1);   // A2 still in the model
});

test('triage over the API changes diagnostics: reviewed hides, needs fixing is an error', async () => {
  const b = await bindAll();
  await client.setTriage(fx.pid, 'node', 'tex:tab:main', 'reviewed', 'checked');
  let m = await loadModel(client, fx.pid);
  let d = toDiagnostics(m, b.folders).filter(x => x.kind === 'alarm');
  assert.equal(d.length, 4); assert.equal(m.recheck, 4);
  assert.ok(!d.some(x => x.rel === 'main.tex'));
  const hp = m.groups[1].nodes[0].nodeId;
  await client.setTriage(fx.pid, 'node', hp, 'needs_fixing', '');
  m = await loadModel(client, fx.pid);
  d = toDiagnostics(m, b.folders);
  assert.equal(d.find(x => x.rel === 'appendix.tex' && x.kind === 'alarm')!.severity, 'error');
  const f = m.checks.find(c => c.check === 'uncited_reference')!.items[0];
  await client.setTriage(fx.pid, 'finding', f.id, 'ignored', '');
  m = await loadModel(client, fx.pid);
  assert.ok(!toDiagnostics(m, b.folders).some(x => x.code === 'uncited_reference'));
  await client.setTriage(fx.pid, 'node', 'tex:tab:main', 'unreviewed', '');
});

test('why: analyze returns the chain and the diff', async () => {
  const m = await loadModel(client, fx.pid);
  const g = m.groups[0];
  const a = await client.analyze(fx.pid, g.id, 'tex:tab:main');
  const names = new Map(g.nodes.map(n => [n.nodeId, n.name]));
  const text = formatWhy(a, id => names.get(id) || id);
  assert.match(text, /learning_rate/);
  assert.match(text, /Chain/);
  assert.match(text, /\+learning_rate: 1\.0e-3/);
});

test('auth: wrong token is unauthorized, closed port is offline, token is not in error text', async () => {
  const bad = new HubClient(fx.url, 'not-a-token');
  await assert.rejects(bad.projects(), (e: any) => e instanceof HubError && e.unauthorized && !String(e.message).includes('not-a-token'));
  const off = new HubClient('http://127.0.0.1:9', fx.token, 3000);
  await assert.rejects(off.projects(), (e: any) => e instanceof HubError && e.offline && !String(e.message).includes(fx.token));
});

test('paper inside the code repo (subdir): paper/<rel> lands in <code folder>/<subdir>/<rel>', async () => {
  const wsMono = path.join(tmp, 'ws', 'mono');
  git(tmp, 'clone', '-q', path.join(fx.sample, 'code'), wsMono);
  git(wsMono, 'remote', 'set-url', 'origin', 'git@github.com:Alice/Demo-Code.git');
  fs.cpSync(wsPaper, path.join(wsMono, 'docs', 'paper'), { recursive: true, filter: s => path.basename(s) !== '.git' });
  const projects = (await client.projects()).map(p => ({ ...p, paper_source: { kind: 'github' as const, repo: 'alice/demo-code', subdir: 'docs/paper' } }));
  const b = matchProjects([{ key: 'mono', remotes: remotes(wsMono) }], projects)[0];
  assert.deepEqual(b.folders, { code: 'mono', paper: 'mono' });
  const m = await loadModel(client, fx.pid);
  const d = toDiagnostics(m, b.folders, b.subdirs).filter(x => x.kind === 'alarm');
  const tex = d.find(x => x.rel === 'docs/paper/main.tex');
  assert.ok(tex, 'Table 2 maps to docs/paper/main.tex');
  assert.match(fs.readFileSync(path.join(wsMono, tex!.rel), 'utf8').split('\n')[tex!.line0], /\\begin\{table/);
});

test('sync works and returns code/paper results; checkpoint resets the alarms', async () => {
  const r = await client.sync(fx.pid);
  assert.ok(r.code && typeof r.code.changed === 'boolean', JSON.stringify(r));
  await client.checkpoint(fx.pid, 'from extension test');
  const m = await loadModel(client, fx.pid);
  assert.equal(m.recheck, 0);
  assert.equal(m.groups.length, 0);
});
