import { test } from 'node:test';
import * as assert from 'node:assert/strict';
import { mapPath, safeRel } from '../../src/core/mapping';
import { isPrivateHost, normalizeServerUrl } from '../../src/core/url';
import { clean } from '../../src/core/text';

test('mapPath maps code/ and paper/ onto the matched folders', () => {
  const f = { code: 'A', paper: 'B' };
  assert.deepEqual(mapPath(f, 'code', 'configs/default.yaml'), { folder: 'A', rel: 'configs/default.yaml' });
  assert.deepEqual(mapPath(f, 'paper', 'appendix.tex'), { folder: 'B', rel: 'appendix.tex' });
  assert.deepEqual(mapPath(f, 'paper', 'sec/./intro.tex'), { folder: 'B', rel: 'sec/intro.tex' });
});
test('mapPath: unmatched repo is not mapped', () => {
  assert.equal(mapPath({ code: 'A' }, 'paper', 'main.tex'), null);
  assert.equal(mapPath({}, 'code', 'a.py'), null);
});
test('mapPath refuses escapes from the workspace folder', () => {
  for (const p of ['../x', 'a/../../x', '/etc/passwd', 'C:\\x', 'a\\b', '..', '.', '', 'a\0b', 'C:/x']) {
    assert.equal(safeRel(p), null, JSON.stringify(p));
    assert.equal(mapPath({ code: 'A' }, 'code', p), null);
  }
});
test('normalizeServerUrl', () => {
  assert.deepEqual(normalizeServerUrl('http://100.111.135.94:8765/'), { ok: true, url: 'http://100.111.135.94:8765' });
  assert.deepEqual(normalizeServerUrl(' https://hub.example.ts.net '), { ok: true, url: 'https://hub.example.ts.net' });
  for (const u of ['file:///etc/passwd', 'ftp://x', 'javascript:alert(1)', 'http://u:p@host:1', 'http://h/path', 'http://h/?q=1', 'nonsense', '']) {
    assert.equal(normalizeServerUrl(u).ok, false, u);
  }
});
test('isPrivateHost', () => {
  for (const h of ['100.111.135.94', '127.0.0.1', '10.1.2.3', '192.168.0.4', '172.20.0.1', 'localhost', 'mini.tail1234.ts.net', '[fd7a:115c:a1e0::1]', '::1']) assert.ok(isPrivateHost(h), h);
  for (const h of ['8.8.8.8', '100.128.0.1', '172.32.0.1', 'example.com']) assert.ok(!isPrivateHost(h), h);
});
test('clean strips ANSI and control characters', () => {
  assert.equal(clean('a\u001b[31mred\u001b[0m\u0007b\u202ex'), 'aredbx');
  assert.equal(clean('x'.repeat(10), 5), 'xxxx…');
  assert.equal(clean(undefined), '');
});
test('mapPath ignores inherited keys such as __proto__', () => {
  assert.equal(mapPath({ code: 'A' }, '__proto__', 'x.py'), null);
  assert.equal(mapPath({ code: 'A' }, 'constructor', 'x.py'), null);
});
test('mapPath with a paper subdir: paper/<rel> -> <folder>/<subdir>/<rel>; code is untouched', () => {
  const f = { code: 'A', paper: 'A' }, sd = { paper: 'docs/paper/' };
  assert.deepEqual(mapPath(f, 'paper', 'sec/intro.tex', sd), { folder: 'A', rel: 'docs/paper/sec/intro.tex' });
  assert.deepEqual(mapPath(f, 'code', 'train.py', sd), { folder: 'A', rel: 'train.py' });
  assert.deepEqual(mapPath(f, 'paper', 'main.tex', {}), { folder: 'A', rel: 'main.tex' });
});
test('mapPath refuses a hostile subdir from the server', () => {
  for (const s of ['..', '../x', '/etc', 'a/../../b', 'C:/x', 'a\\b']) assert.equal(mapPath({ paper: 'A' }, 'paper', 'main.tex', { paper: s }), null, s);
});
