import { test } from 'node:test';
import * as assert from 'node:assert/strict';
import { DEFAULT_URL, serverFromInspect, tokenFor, tokenKey } from '../../src/core/settings';
import { matchProjects } from '../../src/core/remotes';

test('serverUrl: workspace and folder values are ignored; user value or default is used', () => {
  const evil = { defaultValue: DEFAULT_URL, workspaceValue: 'http://evil.example:1', workspaceFolderValue: 'http://evil2.example' } as any;
  assert.deepEqual(serverFromInspect(evil), { ok: true, url: 'http://100.111.135.94:8765' });
  assert.deepEqual(serverFromInspect({ defaultValue: DEFAULT_URL, globalValue: 'http://10.0.0.5:9', workspaceValue: 'http://evil.example' } as any), { ok: true, url: 'http://10.0.0.5:9' });
  assert.deepEqual(serverFromInspect(undefined), { ok: true, url: 'http://100.111.135.94:8765' });
  assert.equal(serverFromInspect({ globalValue: 'file:///x' }).ok, false);
});
test('token is looked up per origin: a different origin has no token', async () => {
  const store = new Map([[tokenKey('http://100.111.135.94:8765'), 'SECRET']]);
  const get = async (k: string) => store.get(k);
  assert.equal(await tokenFor('http://100.111.135.94:8765', get), 'SECRET');
  assert.equal(await tokenFor('http://evil.example', get), undefined);
  assert.equal(await tokenFor('http://100.111.135.94:8766', get), undefined);   // port counts
  assert.equal(await tokenFor('https://100.111.135.94:8765', get), undefined);  // scheme counts
});
test('lemmata.project is validated against the hub project list', () => {
  const projects = [{ id: 'demo-1', name: 'Demo', code_repo: 'a/b' }];
  assert.deepEqual(matchProjects([], projects, '../../etc').length, 0);
  assert.equal(matchProjects([], projects, 'demo-1').length, 1);
});
