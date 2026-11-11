import { test } from 'node:test';
import * as assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { AGENT_RULES_BEGIN, AGENT_RULES_END, HOOK_COMMAND, RunManifest, addArtifact, asManifest, configArgs, experimentPart, globToRegExp, isExperimentCommand, isMetricFile,
  isoLocal, mergeAgentRules, mergeHookSettings, metricsLine, parseMetrics, pickRun, runId, sameRun, RUN_ID } from '../../src/core/runs';

const base: RunManifest = { run_id: '2026-11-11T21-04-13_a3f9', source: 'terminal', command: 'python train.py', cwd: '/w', host: 'h', git_sha: '9c1e2ab', dirty: false,
  diff_hash: null, configs: [], metrics: {}, artifacts: [], started: '2026-11-11T21:04:13+09:00', ended: null, exit_code: null };

test('isExperimentCommand: launchers', () => {
  for (const c of ['python train.py --lr 3e-4', 'python3.11 -m src.train', 'CUDA_VISIBLE_DEVICES=0 python train.py', 'uv run python eval.py', 'nohup python train.py &',
    'accelerate launch train.py', 'torchrun --nproc_per_node 2 train.py', 'sbatch jobs/train.sh', 'bash scripts/run_all.sh', './run.sh', 'cd exp && python train.py',
    'conda run -n tad python main.py', 'poetry run python main.py', 'WANDB_MODE=offline SEED=2 python main.py']) assert.equal(isExperimentCommand(c), true, c);
});
test('isExperimentCommand: everyday commands are not runs', () => {
  for (const c of ['ls', 'git status', 'python', 'python --version', 'python -V', 'python -c "print(1)"', 'python -m pip install torch', 'python -m pytest', 'pip install -e .',
    'cd results', 'cat results/metrics.json', 'bash', 'nvidia-smi', 'echo python train.py', 'vim train.py', '', 'python -m venv .venv']) assert.equal(isExperimentCommand(c), false, c);
});
test('experimentPart: custom and broken patterns', () => {
  assert.equal(experimentPart('make train', '^make\\s'), 'make train');
  assert.equal(experimentPart('python train.py', '^make\\s'), null);
  assert.equal(experimentPart('python train.py', '(unclosed'), 'python train.py');      // falls back to the built-in pattern
  assert.equal(experimentPart('cd a; python b.py --x 1 | tee log.txt'), 'python b.py --x 1');
});
test('configArgs', () => {
  assert.deepEqual(configArgs('python train.py --config configs/mcd.yaml --override=exp/a.toml -o out.txt "b.json" ../secret.yaml'), ['configs/mcd.yaml', 'exp/a.toml', 'b.json']);
  assert.deepEqual(configArgs('python train.py'), []);
});
test('runId and isoLocal', () => {
  const d = new Date(2026, 10, 11, 21, 4, 13);
  const id = runId(d, 'python train.py', '/w');
  assert.match(id, /^2026-11-11T21-04-13_[0-9a-f]{4}$/);
  assert.match(id, RUN_ID);
  assert.equal(runId(d, 'python train.py', '/w'), id);
  assert.notEqual(runId(d, 'python eval.py', '/w'), id);
  assert.match(isoLocal(d), /^2026-11-11T21:04:13[+-]\d\d:\d\d$/);
});
test('parseMetrics', () => {
  assert.deepEqual(parseMetrics('results/metrics.json', '{"f1": 0.851, "test": {"auroc": 0.912, "n": 3}, "name": "mcd", "ok": true, "list": [1, 2]}'), { f1: 0.851, 'test.auroc': 0.912, 'test.n': 3 });
  assert.deepEqual(parseMetrics('m.json', '{"f1": 0.8'), {});                 // still being written
  assert.deepEqual(parseMetrics('m.csv', 'f1,auroc,method\n0.85,0.91,mcd\n'), { f1: 0.85, auroc: 0.91 });
  assert.deepEqual(parseMetrics('m.tsv', 'f1\tauroc\n0.85\t0.91\n'), { f1: 0.85, auroc: 0.91 });
  assert.deepEqual(parseMetrics('table2.csv', 'method,f1\nmcd,0.85\nbase,0.80\n'), {});     // a table of several rows is not one run's numbers
  assert.deepEqual(parseMetrics('log_metrics.jsonl', '{"epoch":1,"loss":0.9}\n{"epoch":2,"loss":0.5}\n{"epoch":3,"lo'), { epoch: 2, loss: 0.5 });
  assert.deepEqual(parseMetrics('m.json', '[1,2,3]'), {});
  assert.equal(Object.keys(parseMetrics('m.json', JSON.stringify(Object.fromEntries(Array.from({ length: 500 }, (_, i) => ['k' + i, i]))))).length, 200);
});
test('globs and isMetricFile', () => {
  assert.equal(globToRegExp('results/**').test('results/a/b/metrics.json'), true);
  assert.equal(globToRegExp('results/**').test('other/results/x.json'), false);
  assert.equal(globToRegExp('**/out/*.json').test('a/b/out/m.json'), true);
  assert.equal(globToRegExp('**/out/*.json').test('out/m.json'), true);
  assert.equal(globToRegExp('*.json').test('a/m.json'), false);
  assert.equal(isMetricFile('results/mcd_s2/metrics.json'), true);
  assert.equal(isMetricFile('outputs/2026-11-11/eval_results.csv'), true);
  assert.equal(isMetricFile('results/config.json'), false);
  assert.equal(isMetricFile('src/metrics.json'), false);
  assert.equal(isMetricFile('.lemmata/runs/metrics.json'), false);
  assert.equal(isMetricFile('out/final.json', ['out/**'], ['final.json']), true);
});
test('pickRun: a file belongs to the run that was going when it was written', () => {
  const runs = [{ run_id: 'a', startedMs: 10000, endedMs: 50000 }, { run_id: 'b', startedMs: 60000, endedMs: null }, { run_id: 'c', startedMs: 500000, endedMs: 600000 }];
  assert.equal(pickRun(40000, runs), 'a');
  assert.equal(pickRun(55000, runs), 'a');            // written just after the command returned
  assert.equal(pickRun(59500, runs), 'b');            // file times can be rounded down by up to a second: b had just started
  assert.equal(pickRun(62000, runs), 'b');            // both a (within the grace time) and b fit: the later start wins
  assert.equal(pickRun(400000, runs), 'b');           // still running
  assert.equal(pickRun(5000, runs), null);            // before any run started
  assert.equal(pickRun(700000, [runs[0], runs[2]]), null);     // long after everything ended: a detached job
});
test('sameRun', () => {
  assert.equal(sameRun(base, { ...base, run_id: 'x-other-id', source: 'agent', started: '2026-11-11T21:04:16+09:00' }), true);
  assert.equal(sameRun(base, { ...base, run_id: 'x-other-id', started: '2026-11-11T21:05:16+09:00' }), false);
  assert.equal(sameRun(base, { ...base, run_id: 'x-other-id', command: 'python eval.py' }), false);
});
test('addArtifact: numbers of further files are prefixed, rewrites update in place', () => {
  let m = addArtifact(base, 'results/s1/metrics.json', 'sha256:' + 'a'.repeat(64), { f1: 0.8 });
  assert.deepEqual(m.metrics, { f1: 0.8 });
  m = addArtifact(m, 'results/s2/metrics.json', null, { f1: 0.9 });
  assert.deepEqual(m.metrics, { f1: 0.8, 's2/metrics:f1': 0.9 });
  m = addArtifact(m, 'results/s1/metrics.json', 'sha256:' + 'b'.repeat(64), { f1: 0.85 });
  assert.deepEqual(m.metrics, { f1: 0.85, 's2/metrics:f1': 0.9 });
  assert.deepEqual(m.artifacts.map(a => a.path), ['results/s1/metrics.json', 'results/s2/metrics.json']);
  assert.equal(m.artifacts[0].hash, 'sha256:' + 'b'.repeat(64));
  assert.deepEqual(base.artifacts, []);               // the input is not changed
});
test('asManifest: untrusted files are validated', () => {
  assert.deepEqual(asManifest(JSON.parse(JSON.stringify(base))), { ...base, note: null });
  assert.equal(asManifest({ ...base, run_id: '../../etc/passwd' }), null);
  assert.equal(asManifest({ ...base, source: 'web' }), null);
  assert.equal(asManifest({ ...base, command: null, artifacts: [] }), null);
  assert.equal(asManifest(null), null);
  const m = asManifest({ ...base, git_sha: 'not a sha', dirty: 'yes', metrics: { a: 1, b: 'x', c: Infinity }, artifacts: [{ path: 'r\\m.json', hash: 'zz' }, { nope: 1 }], exit_code: 1.5, extra: 1 })!;
  assert.deepEqual([m.git_sha, m.dirty, m.metrics, m.artifacts, m.exit_code], [null, null, { a: 1 }, [{ path: 'r/m.json', hash: null }], null]);
  assert.equal('extra' in m, false);
});
test('metricsLine', () => {
  assert.equal(metricsLine({ f1: 0.85123456, auroc: 0.912, n: 3, more: 1 }), 'f1=0.8512 auroc=0.912 n=3');
  assert.equal(metricsLine({}), '');
});
test('mergeHookSettings keeps other settings and is idempotent', () => {
  const start = { permissions: { deny: ['Read(./.env)'] }, hooks: { PostToolUse: [{ matcher: 'Edit', hooks: [{ type: 'command', command: 'fmt' }] }] } };
  const a = mergeHookSettings(start);
  assert.equal(a.changed, true);
  const s = a.settings as any;
  assert.deepEqual(s.permissions, start.permissions);
  assert.equal(s.hooks.PostToolUse.length, 2);
  assert.equal(s.hooks.PostToolUse[0].hooks[0].command, 'fmt');
  for (const ev of ['PreToolUse', 'PostToolUse', 'PostToolUseFailure']) {
    const g = s.hooks[ev][s.hooks[ev].length - 1];
    assert.deepEqual(g, { matcher: 'Bash', hooks: [{ type: 'command', command: HOOK_COMMAND, timeout: 20 }] });
  }
  assert.equal((start.hooks.PostToolUse as unknown[]).length, 1);      // the input is not changed
  const b = mergeHookSettings(a.settings);
  assert.equal(b.changed, false);
  assert.deepEqual(b.settings, a.settings);
  assert.equal(mergeHookSettings(undefined).changed, true);
  assert.equal(mergeHookSettings([1, 2]).changed, true);
});
test('mergeAgentRules adds once and refreshes in place', () => {
  const one = mergeAgentRules('# Project\n\nRules.\n');
  assert.ok(one.startsWith('# Project\n\nRules.\n\n' + AGENT_RULES_BEGIN));
  assert.equal(mergeAgentRules(one), one);
  const edited = one.replace('## Lemmata', '## Old heading') + '\n## After\n';
  const two = mergeAgentRules(edited);
  assert.ok(two.includes('## Lemmata') && !two.includes('## Old heading') && two.endsWith('\n## After\n'));
  assert.equal(two.split(AGENT_RULES_END).length, 2);
  assert.ok(mergeAgentRules('').startsWith(AGENT_RULES_BEGIN));
});

/* ---------- the Claude Code hook, run for real against a temporary git repository ---------- */
const HOOK = path.resolve(__dirname, '..', '..', '..', 'media', 'hooks', 'log_run.py');
function hook(root: string, input: object, env: Record<string, string> = {}) {
  execFileSync('python3', [HOOK], { input: JSON.stringify(input), env: { ...process.env, CLAUDE_PROJECT_DIR: root, ...env } });
}
function repo(): string {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'lemmata-hook-')));
  const g = (...a: string[]) => execFileSync('git', ['-C', root, '-c', 'user.name=t', '-c', 'user.email=t@example.com', ...a], { stdio: 'pipe' });
  g('init', '-q');
  fs.mkdirSync(path.join(root, 'configs'));
  fs.writeFileSync(path.join(root, 'configs', 'mcd.yaml'), 'lr: 0.001\n');
  fs.writeFileSync(path.join(root, 'train.py'), 'print(1)\n');
  g('add', '.'); g('commit', '-q', '-m', 'init');
  return root;
}
const runsIn = (root: string): RunManifest[] => {
  const dir = path.join(root, '.lemmata', 'runs');
  return fs.existsSync(dir) ? fs.readdirSync(dir).filter(n => n.endsWith('.json')).sort().map(n => JSON.parse(fs.readFileSync(path.join(dir, n), 'utf8'))) : [];
};

test('hook: logs an experiment the agent runs, start to end', () => {
  const root = repo();
  try {
    const head = execFileSync('git', ['-C', root, 'rev-parse', 'HEAD']).toString().trim();
    fs.writeFileSync(path.join(root, 'train.py'), 'print(2)\n');           // an uncommitted change
    const call = { tool_name: 'Bash', tool_use_id: 'toolu_01', cwd: root, tool_input: { command: 'cd . && python train.py --config configs/mcd.yaml' } };
    hook(root, { ...call, hook_event_name: 'PreToolUse' });
    let runs = runsIn(root);
    assert.equal(runs.length, 1);
    const m = asManifest(runs[0])!;
    assert.ok(m, 'the hook writes a manifest the extension accepts');
    assert.deepEqual([m.source, m.git_sha, m.dirty, m.ended, m.exit_code], ['agent', head, true, null, null]);
    assert.deepEqual(m.configs.map(c => c.path), ['configs/mcd.yaml']);
    assert.match(m.diff_hash || '', /^sha256:[0-9a-f]{64}$/);
    assert.equal(fs.readdirSync(path.join(root, '.lemmata', 'patches')).length, 1);
    assert.equal(fs.readFileSync(path.join(root, '.lemmata', '.gitignore'), 'utf8'), '*\n');
    // the extension adds a result file while the command runs; the hook must keep it when the command ends
    const file = path.join(root, '.lemmata', 'runs', m.run_id + '.json');
    fs.writeFileSync(file, JSON.stringify(addArtifact(m, 'results/metrics.json', null, { f1: 0.9 })));
    hook(root, { ...call, hook_event_name: 'PostToolUse', tool_response: { stdout: 'ok', exit_code: 0 } });
    runs = runsIn(root);
    assert.equal(runs.length, 1);
    assert.deepEqual([runs[0].exit_code, runs[0].metrics, runs[0].artifacts.length], [0, { f1: 0.9 }, 1]);
    assert.match(runs[0].ended || '', /^\d{4}-\d{2}-\d{2}T/);
    assert.deepEqual(fs.readdirSync(path.join(root, '.lemmata', 'pending')), []);
    assert.equal(execFileSync('git', ['-C', root, 'status', '--porcelain', '--', '.lemmata']).toString(), '');      // nothing of it shows up in git
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});
test('hook: failures, background commands, and commands that are not experiments', () => {
  const root = repo();
  try {
    hook(root, { tool_name: 'Bash', tool_use_id: 'a', cwd: root, hook_event_name: 'PreToolUse', tool_input: { command: 'git status' } });
    hook(root, { tool_name: 'Bash', tool_use_id: 'a', cwd: root, hook_event_name: 'PostToolUse', tool_input: { command: 'git status' } });
    hook(root, { tool_name: 'Edit', tool_use_id: 'b', cwd: root, hook_event_name: 'PreToolUse', tool_input: { command: 'python train.py' } });
    assert.equal(runsIn(root).length, 0);
    const fail = { tool_name: 'Bash', tool_use_id: 'c', cwd: root, tool_input: { command: 'python train.py' } };
    hook(root, { ...fail, hook_event_name: 'PreToolUse' });
    hook(root, { ...fail, hook_event_name: 'PostToolUseFailure', error: 'exit 1' });
    const bg = { tool_name: 'Bash', tool_use_id: 'd', cwd: root, tool_input: { command: 'python train.py --seed 2', run_in_background: true } };
    hook(root, { ...bg, hook_event_name: 'PreToolUse' });
    hook(root, { ...bg, hook_event_name: 'PostToolUse' });
    const runs = runsIn(root).map(r => asManifest(r)!);
    assert.equal(runs.length, 2);
    const failed = runs.find(r => r.command === 'python train.py')!, back = runs.find(r => r.command !== 'python train.py')!;
    assert.deepEqual([failed.exit_code, failed.dirty, failed.diff_hash], [1, false, null]);
    assert.deepEqual([back.ended, back.exit_code, back.note], [null, null, 'started in the background']);
    hook(root, { tool_name: 'Bash', tool_use_id: 'e', cwd: root, hook_event_name: 'PreToolUse', tool_input: { command: 'make train' } }, { LEMMATA_RUN_PATTERN: '^make\\s' });
    assert.equal(runsIn(root).length, 3);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});
test('hook: bad input never fails', () => {
  const root = repo();
  try {
    execFileSync('python3', [HOOK], { input: 'not json', env: { ...process.env, CLAUDE_PROJECT_DIR: root } });
    execFileSync('python3', [HOOK], { input: '[]', env: { ...process.env, CLAUDE_PROJECT_DIR: root } });
    execFileSync('python3', [HOOK], { input: '{"tool_name":"Bash","hook_event_name":"PostToolUse"}', env: { ...process.env, CLAUDE_PROJECT_DIR: '/nonexistent-dir' } });
    assert.equal(runsIn(root).length, 0);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});
