// The bench (S35): the rows the hub sends are checked, the runs on this machine are grouped, and the manifest stays small.
import { test } from 'node:test';
import * as assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { BENCH_VERSION, LocalRun, Row, RunNote, asBench, asRow, barOf, clickOf, contextOf, dayPlus, flashOf, isBenchView, isRunning, newer, nowRows, siteUrl } from '../../src/core/bench';

const T = '2026-11-20', NOW = Date.parse('2026-11-20T15:00:00+09:00');
const run = (id: string, o: Partial<LocalRun> = {}): LocalRun => ({ id, command: 'python train.py --seed 3', source: 'terminal', host: 'srv', started: T + 'T14:00:00+09:00', ended: T + 'T14:05:00+09:00',
  exit: 0, sha: '9c1e2ab4f0', dirty: false, patch: false, metrics: { fp: 30 }, artifacts: ['results/main/a.csv'], configs: [], sent: true, file: '/w/.lemmata/runs/' + id + '.json', pid: 'p1', ...o });
const note: RunNote = { x: 'map:main', name: 'Main comparison', how: 'wrote', fields: { dataset: ['Covtype'] }, metric: 'fp', line: 'fp 30, was 31.2 (lower is better)',
  prev: { id: 'r0', t: '2026-11-19T10:00:00+09:00', sha: 'a1b2c3d', value: 31.2 } };

test('asRow keeps what can be drawn and drops what cannot', () => {
  const r = asRow({ id: 'map:main', label: 'Main\u001b[31m comparison\n', description: 'ours 30 · best other 38 (DDM)', icon: 'beaker', expanded: true, x: 'map:main',
    open: { repo: 'code', path: 'results/main/a.csv', line: 3 }, site: { view: 'experiments', sel: 'x:map:main' }, tab: { view: 'setup', sel: 'x:map:main' },
    copy: { what: 'a prompt for Claude Code', text: 'do it\nthen report' }, snooze: 'seeds:map:main', unknown: 1,
    kids: [{ id: 'k', label: 'Measure', description: 'fp · lower is better' }, { id: '', label: 'no id' }, 'junk', { id: 'k2' }] })!;
  assert.equal(r.label, 'Main comparison');                                  // escapes and line breaks are gone
  assert.deepEqual(r.open, { repo: 'code', path: 'results/main/a.csv', line: 3 });
  assert.deepEqual([r.site, r.tab], [{ view: 'experiments', sel: 'x:map:main' }, { view: 'setup', sel: 'x:map:main' }]);
  assert.equal(r.copy!.text, 'do it\nthen report');                          // what is copied is not shortened or reflowed
  assert.deepEqual(r.kids!.map(k => k.id), ['k']);
  assert.equal((r as any).unknown, undefined);
  // paths that leave the repository, odd icon names and odd targets are refused
  for (const p of ['../secret', '/etc/passwd', 'a/../../b', 'a\\..\\b', '']) assert.equal(asRow({ id: 'a', label: 'b', open: { repo: 'code', path: p } })!.open, undefined, p);
  assert.equal(asRow({ id: 'a', label: 'b', open: { repo: '../x', path: 'a' } })!.open, undefined);
  assert.equal(asRow({ id: 'a', label: 'b', icon: 'beaker) $(alert' })!.icon, undefined);
  assert.deepEqual(asRow({ id: 'a', label: 'b', site: { view: 'setup', sel: 'javascript:alert(1)' } })!.site, { view: 'setup' });
  assert.equal(asRow({ id: 'a', label: 'b', site: { view: 'https://evil' } })!.site, undefined);
  assert.equal(asRow({ id: 'a' }), null);
  assert.equal(asRow(null), null);
  let deep: any = { id: 'leaf', label: 'leaf' };
  for (let i = 0; i < 12; i++) deep = { id: 'n' + i, label: 'n', kids: [deep] };
  let d = 0; for (let r2: Row | undefined = asRow(deep)!; r2; r2 = r2.kids && r2.kids[0]) d++;
  assert.ok(d <= 6, 'depth is capped');
});

test('asBench reads the hub document and survives a broken one', () => {
  assert.equal(asBench(null), null);
  assert.equal(asBench({ schema: 'lemmata.todo/1' }), null);
  const b = asBench({ schema: 'lemmata.bench/1', version: 1, today: T, project: 'mcd', runs: { r1: note, bad: 'x', r2: { x: '' } }, elsewhere: [{ id: 'r9', label: 'python a.py', run: 'r9' }],
    experiments: [{ id: 'q|q1', label: 'C1 · a claim', kids: [{ id: 'map:main', label: 'Main comparison' }] }], to_run: 'nope',
    pick: [{ id: 'map:main', label: 'Main comparison', description: 'C1' }, { label: 'no id' }], counts: { to_run: 2, stale: -1, experiments: '4' } })!;
  assert.deepEqual(Object.keys(b.runs), ['r1']);
  assert.equal(b.runs.r1.line, 'fp 30, was 31.2 (lower is better)');
  assert.deepEqual([b.to_run, b.pick.length, b.counts.to_run, b.counts.stale, b.counts.experiments], [[], 1, 2, 0, 0]);
  assert.equal(b.experiments[0].kids![0].id, 'map:main');
  assert.equal(asBench({ schema: 'lemmata.bench/2', version: BENCH_VERSION + 1 })!.version, BENCH_VERSION + 1);     // a newer hub is still read; the list says the extension is older
});

test('contextOf and clickOf: what a row offers', () => {
  assert.equal(contextOf({ id: 'a', label: 'a' }), 'row');
  assert.equal(contextOf({ id: 'a', label: 'a', site: { view: 'setup' }, copy: { what: 'x', text: 'y' }, snooze: 'k' }), 'row-site-copy-snooze');
  assert.equal(contextOf({ id: 'a', label: 'a', file: '/f', attach: true }), 'row-attach-record');
  assert.equal(clickOf({ id: 'a', label: 'a', file: '/f', open: { repo: 'code', path: 'a', line: 1 } }), 'record');
  assert.equal(clickOf({ id: 'a', label: 'a', open: { repo: 'code', path: 'a', line: 1 } }), 'open');
  assert.equal(clickOf({ id: 'a', label: 'a', tab: { view: 'setup' }, kids: [{ id: 'k', label: 'k' }] }), null);      // a click on a row with rows under it opens it
  assert.equal(clickOf({ id: 'a', label: 'a', tab: { view: 'setup' } }), 'tab');
});

test('nowRows: every run on this machine is in exactly one group', () => {
  const local = [
    run('r1', { ended: null, started: T + 'T14:50:00+09:00', sent: false, metrics: {}, artifacts: [] }),          // running (not sent yet, still under Running)
    run('r2', { sent: false }),                                                                                  // finished, not sent
    run('r3', { exit: 2, metrics: {}, artifacts: [] }),                                                          // failed today
    run('r4'),                                                                                                   // finished, no experiment
    run('r5'),                                                                                                   // finished, belongs to Main comparison
    run('r6', { metrics: {}, artifacts: [] }),                                                                   // finished, wrote nothing: not an experiment, so not "unattached"
    run('r7', { started: '2026-11-18T10:00:00+09:00', ended: '2026-11-18T10:05:00+09:00' }),                      // earlier
    run('r8', { ended: null, started: '2026-11-01T10:00:00+09:00' }),                                             // no end after a week: not running
    run('r9', { source: 'watcher', started: null, command: null }),                                              // seen by the results watcher today
  ];
  const elsewhere: Row[] = [{ id: 'r5', label: 'dup of a local run', run: 'r5' }, { id: 'x1', label: 'python other.py', run: 'x1', description: 'gpu2 · 13:00' }];
  const rows = nowRows({ local, note: id => (id === 'r5' || id === 'r9' ? note : undefined), elsewhere, today: T, nowMs: NOW, hubKnows: true });
  const by = Object.fromEntries(rows.map(g => [g.id, g.kids!.map(k => k.id)]));
  assert.deepEqual(by, { 'g|running': ['r1'], 'g|unsent': ['r2'], 'g|failed': ['r3'], 'g|loose': ['r4'], 'g|done': ['r9', 'r6', 'r5'], 'g|elsewhere': ['x1'], 'g|earlier': ['r8', 'r7'] });
  assert.deepEqual(rows.map(g => g.id), ['g|running', 'g|unsent', 'g|failed', 'g|loose', 'g|done', 'g|elsewhere', 'g|earlier']);     // the order the questions come up
  assert.deepEqual(rows.filter(g => !g.expanded).map(g => g.id), ['g|elsewhere', 'g|earlier']);
  const all = rows.flatMap(g => g.kids!.map(k => k.id));
  assert.equal(new Set(all).size, all.length);
  const r5 = rows.find(g => g.id === 'g|done')!.kids!.find(k => k.id === 'r5')!;
  assert.equal(r5.description, '14:00 · Main comparison · fp 30, was 31.2 (lower is better) · 9c1e2ab');
  assert.match(r5.tooltip!, /Compared with the run of 2026-11-19 10:00 at a1b2c3d: same experiment, same dataset, method and seed\./);
  assert.deepEqual([r5.attach, r5.pid, r5.file, r5.x], [true, 'p1', '/w/.lemmata/runs/r5.json', 'map:main']);
  const r1 = rows[0].kids![0];
  assert.deepEqual([r1.icon, r1.attach, /running · not sent yet$/.test(r1.description!)], ['sync~spin', undefined, true]);
  assert.equal(rows.find(g => g.id === 'g|earlier')!.kids![1].description!.startsWith('11-18 10:00'), true);
  // before the hub has been read, nothing is called "not attached"
  const off = nowRows({ local: [run('r4')], note: () => undefined, elsewhere: [], today: T, nowMs: NOW, hubKnows: false });
  assert.deepEqual(off.map(g => g.id), ['g|done']);
  assert.deepEqual(nowRows({ local: [], note: () => undefined, elsewhere: [], today: T, nowMs: NOW, hubKnows: true }), []);
  assert.equal(isRunning(local[7], NOW), false);
});

test('barOf: one status-bar item', () => {
  const base = { conn: 'ok' as const, server: 'http://hub', projects: 1, running: 0, unsent: 0, toRun: 0, flash: null };
  assert.deepEqual([barOf({ ...base, conn: 'unconfigured' }).text, barOf({ ...base, conn: 'unconfigured' }).command], ['Lemmata: connect', 'lemmata.connect']);
  assert.equal(barOf({ ...base, conn: 'unauthorized' }).warn, true);
  assert.equal(barOf({ ...base, conn: 'offline', running: 1, unsent: 2 }).text, '$(beaker) offline · 1 running · 2 not sent');
  assert.equal(barOf({ ...base, projects: 0 }).command, 'lemmata.addProject');
  assert.equal(barOf(base).text, '$(beaker) Lemmata');
  assert.equal(barOf({ ...base, running: 2, unsent: 1, toRun: 3 }).text, '$(beaker) 2 running · 1 not sent · 3 to run');
  assert.equal(barOf({ ...base, running: 2, flash: 'fp 30, was 31.2 (lower is better) · Main comparison' }).text, '$(beaker) fp 30, was 31.2 (lower is better) · Main comparison');
  assert.equal(barOf({ ...base, flash: 'x' }).warn, false);                   // a result is shown, never judged
});

test('flashOf: the line when a run ends', () => {
  assert.equal(flashOf(run('r'), note), 'fp 30, was 31.2 (lower is better) · Main comparison');
  assert.equal(flashOf(run('r'), undefined), 'fp=30 · python train.py --seed 3');
  assert.equal(flashOf(run('r', { exit: 137 }), note), 'failed (exit 137) · Main comparison');
  assert.equal(flashOf(run('r', { metrics: {} }), { ...note, line: null }), 'finished · Main comparison');
});

test('newer, siteUrl, dayPlus, isBenchView', () => {
  assert.deepEqual([newer('0.8.1', '0.8.0'), newer('0.10.0', '0.9.9'), newer('1.0.0', '0.99.99'), newer('0.8.0', '0.8.0'), newer('0.7.9', '0.8.0')], [true, true, true, false, false]);
  for (const bad of ['', '0.8', 'v0.9.0', '0.9.0-beta', null, 9, '../x']) assert.equal(newer(bad, '0.8.0'), false, String(bad));
  assert.equal(siteUrl('http://hub:8765/', 'mcd'), 'http://hub:8765/p/mcd/');
  assert.equal(siteUrl('http://hub:8765', 'mcd', { view: 'setup', sel: 'x:map:main' }), 'http://hub:8765/p/mcd/#go=setup&sel=x%3Amap%3Amain');
  assert.equal(siteUrl('http://hub:8765', 'mcd', { view: 'latex' }), 'http://hub:8765/p/mcd/#go=latex');
  assert.equal(siteUrl('http://hub:8765', 'mcd', { view: 'setup', sel: 'x: y' }), 'http://hub:8765/p/mcd/#go=setup');
  assert.equal(siteUrl('http://hub:8765', 'mcd', { view: '../admin' }), 'http://hub:8765/p/mcd/');
  assert.deepEqual([dayPlus('2026-11-20', 1), dayPlus('2026-11-20', 7), dayPlus('2026-12-28', 7), dayPlus('2026-02-27', 30)], ['2026-11-21', '2026-11-27', '2027-01-04', '2026-03-29']);
  assert.deepEqual([isBenchView('setup'), isBenchView('experiments'), isBenchView('review'), isBenchView('latex'), isBenchView(undefined)], [true, true, false, false, false]);
});

/* ---------- the manifest: few commands, nothing dangling ---------- */
const root = path.resolve(__dirname, '..', '..', '..');
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const src = ['extension.ts', 'runs.ts', 'tab.ts', 'core/bench.ts'].map(f => fs.readFileSync(path.join(root, 'src', f), 'utf8')).join('\n');

test('the command palette shows at most 8 Lemmata commands', () => {
  const all: string[] = pkg.contributes.commands.map((c: any) => c.command);
  const hidden = new Set(pkg.contributes.menus.commandPalette.filter((m: any) => m.when === 'false').map((m: any) => m.command));
  const shown = all.filter(c => !hidden.has(c));
  assert.ok(shown.length <= 8, shown.join(', '));
  assert.deepEqual(shown.sort(), ['lemmata.addProject', 'lemmata.connect', 'lemmata.disconnect', 'lemmata.goto', 'lemmata.openMap', 'lemmata.refresh', 'lemmata.runs.sync', 'lemmata.setupAgent']);
  for (const c of pkg.contributes.commands) assert.equal(c.category, 'Lemmata', c.command);
});
test('every contributed command is registered, and every menu or welcome link names a contributed command', () => {
  const all = new Set<string>(pkg.contributes.commands.map((c: any) => c.command));
  for (const c of all) assert.ok(src.includes("c('" + c + "'"), c + ' is contributed but not registered');
  for (const list of Object.values(pkg.contributes.menus) as any[][]) for (const m of list) assert.ok(all.has(m.command), m.command);
  for (const w of pkg.contributes.viewsWelcome) for (const m of String(w.contents).matchAll(/\(command:([a-zA-Z.]+)\)/g)) assert.ok(all.has(m[1]), m[1]);
  // every hidden command can still be reached: from a row, a list's title bar, a welcome link, or "Go to…"
  const reach = JSON.stringify([pkg.contributes.menus['view/title'], pkg.contributes.menus['view/item/context'], pkg.contributes.viewsWelcome]) + src;
  for (const m of pkg.contributes.menus.commandPalette) assert.ok(reach.split("c('" + m.command + "'").join('').includes(m.command), m.command + ' cannot be reached');
});
test('three lists, and nothing of the website in them', () => {
  assert.deepEqual(pkg.contributes.views.lemmata.map((v: any) => v.id), ['lemmata.now', 'lemmata.experiments', 'lemmata.torun']);
  assert.equal(pkg.contributes.views.lemmata[2].visibility, 'collapsed');
  for (const gone of ['lemmata.checkpoint', 'markReviewed', 'markNeedsFixing', 'markIgnored', 'lemmata.why', 'openTab.review', 'openTab.claims', 'openTab.digest', 'openTab.history', 'lemmata.panel'])
    assert.equal(JSON.stringify(pkg.contributes).includes(gone), false, gone);
  for (const row of pkg.contributes.menus['view/item/context']) assert.match(row.when, /viewItem =~ \/-(copy|site|record|open|tab|attach|snooze)\//);
  assert.match(pkg.version, /^0\.8\.\d+$/);
});
