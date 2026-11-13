import { test } from 'node:test';
import * as assert from 'node:assert/strict';
import { matchProjects, parseGitConfigRemotes, parseRemote, unmatchedRepos } from '../../src/core/remotes';
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
  { id: 'demo-1', name: 'Demo', code_repo: 'alice/demo-code', paper_source: { kind: 'github', repo: 'alice/demo-paper', branch: 'main' } },
  { id: 'other-2', name: 'Other', code_repo: 'alice/other', paper_source: { kind: 'zip' } },
];
test('matchProjects: code and paper both by github remote, case-insensitive', () => {
  const b = matchProjects([{ key: 'f1', remotes: ['git@github.com:Alice/Demo-Code.git'] }, { key: 'f2', remotes: ['https://github.com/alice/DEMO-paper'] }], P);
  assert.equal(b.length, 1);
  assert.equal(b[0].project.id, 'demo-1');
  assert.deepEqual(b[0].folders, { code: 'f1', paper: 'f2' });
  assert.deepEqual(b[0].subdirs, {});
});
test('matchProjects: paper in a folder of the code repo -> one folder, subdir recorded', () => {
  const mono: HubProject[] = [{ id: 'm', name: 'Mono', code_repo: 'alice/mono', paper_source: { kind: 'github', repo: 'alice/mono', subdir: 'paper' } }];
  const b = matchProjects([{ key: 'f', remotes: ['https://github.com/alice/mono.git'] }], mono);
  assert.deepEqual(b[0].folders, { code: 'f', paper: 'f' });
  assert.deepEqual(b[0].subdirs, { paper: 'paper' });
});
test('matchProjects: only the paper repo is open; zip project has no paper match; unrelated remotes match nothing', () => {
  const b = matchProjects([{ key: 'f', remotes: ['https://github.com/alice/demo-paper.git', 'https://github.com/alice/other.git'] }], P);
  assert.deepEqual(b.map(x => [x.project.id, x.folders]), [['demo-1', { paper: 'f' }], ['other-2', { code: 'f' }]]);
  assert.deepEqual(matchProjects([{ key: 'f', remotes: ['https://github.com/nobody/nothing'] }], P), []);
});
test('matchProjects: Overleaf remotes are ignored unless the project data says overleaf', () => {
  const id = '65a1b2c3d4e5f60718293a4b';
  const ol: HubProject = { id: 'old', name: 'Old', code_repo: 'alice/old', paper_source: { kind: 'overleaf', project_id: id } };
  assert.deepEqual(matchProjects([{ key: 'f', remotes: ['https://git.overleaf.com/' + id] }], P), []);
  const b = matchProjects([{ key: 'f', remotes: ['https://git.overleaf.com/' + id] }], [ol]);
  assert.deepEqual(b[0].folders, { paper: 'f' });
});
test('matchProjects: override restricts to one project, even with no matching folder', () => {
  const b = matchProjects([{ key: 'f', remotes: ['https://github.com/alice/other.git'] }], P, 'demo-1');
  assert.equal(b.length, 1);
  assert.deepEqual(b[0].folders, {});
  assert.deepEqual(matchProjects([], P, 'nope'), []);
});

test('S22: repositories a folder could add as a new project', () => {
  const projects = [{ id: 'mcd', name: 'mcd', code_repo: 'daisjuhyeong/mcd_extension' }] as any;
  assert.deepEqual(unmatchedRepos(['git@github.com:daisjuhyeong/temporal_dependency.git', 'https://github.com/daisjuhyeong/temporal_dependency', 'https://x:secret@github.com/Other/Repo.git'], projects),
    ['daisjuhyeong/temporal_dependency', 'other/repo']);
  assert.deepEqual(unmatchedRepos(['https://github.com/DaisJuhyeong/mcd_extension.git'], projects), [], 'already a project');
  assert.deepEqual(unmatchedRepos(['https://gitlab.com/a/b.git', 'https://git.overleaf.com/0123456789abcdef01234567'], projects), [], 'only GitHub repos can be added');
});
