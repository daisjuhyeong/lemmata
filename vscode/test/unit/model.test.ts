import { test } from 'node:test';
import * as assert from 'node:assert/strict';
import { buildModel, toDiagnostics } from '../../src/core/model';
import { formatWhy } from '../../src/core/why';
import { Alarms, Findings, Graph, Triage } from '../../src/core/types';

const graph: Graph = { nodes: [
  { id: 'file:code/configs/default.yaml', kind: 'config', repo: 'code', name: 'configs/default.yaml', loc: { path: 'configs/default.yaml', line: null } },
  { id: 'run:code/train_main', kind: 'run', repo: 'code', name: 'run train_main', loc: { path: 'runs/train_main.json', line: null } },
  { id: 'tex:tab:main', kind: 'table', repo: 'paper', name: 'Table 2', loc: { path: 'main.tex', line: 88, end_line: 101 } },
  { id: 'tex:app:hparams', kind: 'section', repo: 'paper', name: 'App. B Hyperparameters', loc: { path: 'appendix.tex', line: 3 } },
] };
const alarms: Alarms = { checkpoint: { id: 'cp1' }, groups: [
  { id: 'ev:commit:code:9f1c2e7a4b3d', display: 'A1', cause: { kind: 'commit', repo: 'code', short: '9f1c2e7', subject: 'change learning rate 3e-4 to 1e-3', files: ['configs/default.yaml'] },
    changed: [{ node_id: 'file:code/configs/default.yaml', change: 'content_changed' }],
    downstream: [{ node_id: 'run:code/train_main', depth: 1 }, { node_id: 'tex:tab:main', depth: 3 }] },
  { id: 'ev:commit:paper:2b7e5d1c9a0f', display: 'A2', cause: { kind: 'commit', repo: 'paper', short: '2b7e5d1', subject: 'appendix B: learning rate 1e-3' },
    changed: [{ node_id: 'tex:app:hparams' }], downstream: [] },
] };
const findings: Findings = {
  checks: [{ check: 'main_appendix_mismatch', title: 'Main text and appendix differ', status: 'ran', count: 1 }, { check: 'uncited_reference', title: 'Reference is never cited', status: 'ran', count: 1 }, { check: 'undefined_ref', title: 'x', status: 'not_applicable', count: 0 }],
  findings: [
    { id: 'main_appendix_mismatch/learning_rate', check: 'main_appendix_mismatch', severity: 'warning', title: 'Main text and appendix differ', message: 'Learning rate differs between the main text (3e-4) and the appendix (1e-3).',
      evidence: [{ repo: 'paper', path: 'main.tex', line: 57, role: 'main' }, { repo: 'paper', path: 'appendix.tex', line: 14, role: 'appendix' }, { repo: 'paper', path: 'main.tex', line: 57, role: 'dup' }] },
    { id: 'uncited_reference/unused2019', check: 'uncited_reference', severity: 'info', title: 'Reference is never cited', message: 'unused2019 is never cited.', evidence: [{ repo: 'paper', path: 'refs.bib', line: 30 }] },
  ] };
const none: Triage = { entries: {} };

test('model: groups, relation text, counts', () => {
  const m = buildModel(alarms, findings, graph, none);
  assert.equal(m.recheck, 4);
  assert.deepEqual(m.groups.map(g => g.display), ['A1', 'A2']);
  assert.deepEqual(m.groups[0].nodes.map(n => [n.name, n.relation]), [
    ['configs/default.yaml', 'changed'], ['run train_main', 'downstream of configs/default.yaml'], ['Table 2', 'downstream of configs/default.yaml']]);
  assert.deepEqual(m.checks.map(c => c.check), ['main_appendix_mismatch', 'uncited_reference']);   // not_applicable / empty checks dropped
});

const both = { code: 'C', paper: 'P' };
test('diagnostics: alarms at node file:line, finding evidence at each location (deduped)', () => {
  const d = toDiagnostics(buildModel(alarms, findings, graph, none), both);
  const a = d.filter(x => x.kind === 'alarm');
  assert.equal(a.length, 4);
  assert.deepEqual(a.map(x => [x.folder, x.rel, x.line0, x.severity, x.code]), [
    ['C', 'configs/default.yaml', 0, 'warning', 'A1'], ['C', 'runs/train_main.json', 0, 'warning', 'A1'], ['P', 'main.tex', 87, 'warning', 'A1'], ['P', 'appendix.tex', 2, 'warning', 'A2']]);
  assert.equal(a[2].message, 'Recheck: Table 2 — 9f1c2e7 change learning rate 3e-4 to 1e-3 (downstream of configs/default.yaml)');
  assert.equal(a[0].message, 'Recheck: configs/default.yaml — 9f1c2e7 change learning rate 3e-4 to 1e-3 (changed)');
  const f = d.filter(x => x.kind === 'finding');
  assert.deepEqual(f.map(x => [x.rel, x.line0, x.severity, x.code]), [['main.tex', 56, 'warning', 'main_appendix_mismatch'], ['appendix.tex', 13, 'warning', 'main_appendix_mismatch'], ['refs.bib', 29, 'information', 'uncited_reference']]);
  assert.ok(d.every(x => x.source === 'Lemmata'));
});
test('diagnostics: unmatched repo is panel-only (no diagnostics), still in the model', () => {
  const m = buildModel(alarms, findings, graph, none);
  const d = toDiagnostics(m, { code: 'C' });
  assert.deepEqual(d.filter(x => x.kind === 'alarm').map(x => x.rel), ['configs/default.yaml', 'runs/train_main.json']);
  assert.ok(d.filter(x => x.kind === 'finding').length === 0);
  assert.equal(m.groups[1].nodes.length, 1);
});
test('triage: reviewed/ignored hide, needs_fixing is an error, outdated (unreviewed) stays', () => {
  const t: Triage = { entries: {
    'node:tex:tab:main': { state: 'reviewed', effective_state: 'reviewed' },
    'node:run:code/train_main': { state: 'ignored', effective_state: 'ignored' },
    'node:tex:app:hparams': { state: 'needs_fixing', effective_state: 'needs_fixing' },
    'node:file:code/configs/default.yaml': { state: 'reviewed', effective_state: 'unreviewed', outdated: true },
    'finding:main_appendix_mismatch/learning_rate': { state: 'needs_fixing', effective_state: 'needs_fixing' },
    'finding:uncited_reference/unused2019': { state: 'ignored', effective_state: 'ignored' } } };
  const m = buildModel(alarms, findings, graph, t);
  const d = toDiagnostics(m, both);
  assert.deepEqual(d.filter(x => x.kind === 'alarm').map(x => [x.rel, x.severity]), [['configs/default.yaml', 'warning'], ['appendix.tex', 'error']]);
  assert.deepEqual(d.filter(x => x.kind === 'finding').map(x => x.severity), ['error', 'error']);
  assert.equal(m.recheck, 2);   // config (outdated triage counts again) + app:hparams
});
test('model: repo text is cleaned; control chars never reach messages', () => {
  const al: Alarms = { checkpoint: null, groups: [{ id: 'g', display: 'A1', cause: { kind: 'commit', short: 'abc1234', subject: 'fix\u001b[31m red\u0007\nnewline' }, changed: [{ node_id: 'tex:tab:main' }], downstream: [] }] };
  const d = toDiagnostics(buildModel(al, null, graph, none), both);
  assert.equal(d[0].message, 'Recheck: Table 2 — abc1234 fix red newline (changed)');
});
test('formatWhy: plain text with chain and diff', () => {
  const s = formatWhy({ group_id: 'g', node_id: 'n', chain: { nodes: ['a', 'b'], edges: [] }, explanation: 'a changed.\u001b[1m', diffs: [{ node_id: 'a', repo: 'code', path: 'x.yaml', unified: '-lr: 1\n+lr: 2\n' }] }, id => id.toUpperCase());
  assert.match(s, /1\. A\n  2\. B/);
  assert.match(s, /Diff: code\/x\.yaml/);
  assert.ok(!s.includes('\u001b'));
});
