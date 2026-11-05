import { test } from 'node:test';
import * as assert from 'node:assert/strict';
import { matchProjects, parseGitConfigRemotes, parseRemote } from '../../src/core/remotes';
import { HubProject } from '../../src/core/types';

test('parseRemote: github forms', () => {
  for (const u of ['https://github.com/Alice/Demo-Code.git', 'https://github.com/alice/demo-code', 'git@github.com:alice/demo-code.git',
    'ssh://git@github.com/alice/demo-code.git', 'https://x-access-token:abc@github.com/alice/demo-code.git', 'https://github.com/alice/demo-code/', 'git@github.com:alice/demo-code']) {
    assert.deepEqual(parseRemote(u), { kind: 'github', repo: 'alice/demo-code' }, u);
  }
});
test('parseRemote: overleaf forms', () => {
  const id = '65a1b2c3d4e5f60718293a4b';
  assert.deepEqual(parseRemote('https://git.overleaf.com/' + id), { kind: 'overleaf', id });
  assert.deepEqual(parseRemote('https://git@git.overleaf.com/' + id.toUpperCase()), { kind: 'overleaf', id });
  assert.deepEqual(parseRemote('https://git:olp_x@git.overleaf.com/' + id + '.git'), { kind: 'overleaf', id });
});
test('parseRemote: lookalikes and junk are refused', () => {
  for (const u of ['https://github.com.evil.example/alice/demo', 'https://evilgithub.com/alice/demo', 'https://git.overleaf.com.evil.io/65a1b2c3d4e5f60718293a4b',
    'https://git.overleaf.com/short', 'https://gitlab.com/alice/demo', '', '/local/path', 'https://github.com/alice', 'ftp://github.com/a/b']) {
    assert.equal(parseRemote(u), null, u);
  }
});
test('parseGitConfigRemotes', () => {
  const out = 'remote.origin.url https://github.com/alice/demo-code.git\nremote.overleaf.url https://git.overleaf.com/65a1b2c3d4e5f60718293a4b\nremote.up.url  git@github.com:x/y.git\n';
  assert.deepEqual(parseGitConfigRemotes(out), ['https://github.com/alice/demo-code.git', 'https://git.overleaf.com/65a1b2c3d4e5f60718293a4b', 'git@github.com:x/y.git']);
  assert.deepEqual(parseGitConfigRemotes(''), []);
});

const P: HubProject[] = [
  { id: 'demo-1', name: 'Demo', code_repo: 'alice/demo-code', paper_source: { kind: 'overleaf', project_id: '65a1b2c3d4e5f60718293a4b' } },
  { id: 'other-2', name: 'Other', code_repo: 'alice/other', paper_source: { kind: 'zip' } },
];
test('matchProjects: code by github, paper by overleaf, case-insensitive', () => {
  const b = matchProjects([{ key: 'f1', remotes: ['git@github.com:Alice/Demo-Code.git'] }, { key: 'f2', remotes: ['https://git.overleaf.com/65a1b2c3d4e5f60718293a4b'] }], P);
  assert.equal(b.length, 1);
  assert.equal(b[0].project.id, 'demo-1');
  assert.deepEqual(b[0].folders, { code: 'f1', paper: 'f2' });
});
test('matchProjects: one folder with both remotes; no match; zip project has no paper match', () => {
  const b = matchProjects([{ key: 'f', remotes: ['https://github.com/alice/other.git', 'https://git.overleaf.com/65a1b2c3d4e5f60718293a4b'] }], P);
  assert.deepEqual(b.map(x => [x.project.id, x.folders]), [['demo-1', { paper: 'f' }], ['other-2', { code: 'f' }]]);
  assert.deepEqual(matchProjects([{ key: 'f', remotes: ['https://github.com/nobody/nothing'] }], P), []);
});
test('matchProjects: override restricts to one project, even with no matching folder', () => {
  const b = matchProjects([{ key: 'f', remotes: ['https://github.com/alice/other.git'] }], P, 'demo-1');
  assert.equal(b.length, 1);
  assert.deepEqual(b[0].folders, {});
  assert.deepEqual(matchProjects([], P, 'nope'), []);
});
