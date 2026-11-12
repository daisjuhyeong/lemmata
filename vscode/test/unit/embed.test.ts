import { test } from 'node:test';
import * as assert from 'node:assert/strict';
import { allowedRequest, buildPage, fontNames, inlineFonts, openKind, safeInlineScript, safeJson, suggestedName } from '../../src/core/embed';

test('allowedRequest: the project\'s own API and the few hub routes the app uses', () => {
  const ok = (m: string, p: string) => allowedRequest('demo-1', m, p);
  assert.deepEqual(ok('GET', '/p/demo-1/api/graph'), { method: 'GET', path: '/p/demo-1/api/graph' });
  assert.deepEqual(ok('get', '/p/demo-1/api/thumb?node=fig%3A1'), { method: 'GET', path: '/p/demo-1/api/thumb?node=fig%3A1' });
  assert.ok(ok('POST', '/p/demo-1/api/review'));
  assert.ok(ok('GET', '/api/hub/status'));
  assert.ok(ok('GET', '/api/hub/projects'));
  assert.ok(ok('GET', '/api/hub/projects/demo-1'));
  assert.ok(ok('POST', '/api/hub/projects/demo-1/sync'));
  assert.ok(ok('POST', '/api/hub/projects/demo-1/digest/send'));
  assert.ok(ok('POST', '/api/hub/events'));
  assert.ok(allowedRequest('a b', 'GET', '/p/a%20b/api/graph'), 'ids are compared after decoding');
});
test('allowedRequest: everything else is refused', () => {
  const no = (m: string, p: unknown) => assert.equal(allowedRequest('demo-1', m, p), null, m + ' ' + String(p));
  no('GET', '/p/other/api/graph');                       // another project
  no('GET', '/p/demo-1/api/../../other/api/graph');
  no('GET', '/p/demo-1/api/%2e%2e/%2e%2e/api/hub/devices');
  no('GET', '/p/demo-1/api/x%2F..%2Fy');
  no('GET', '/p/demo-1/api/');
  no('GET', '/p/demo-1/');
  no('GET', '/api/hub/devices');                          // tokens and devices
  no('POST', '/api/hub/token');
  no('GET', '/api/hub/users');
  no('POST', '/api/hub/logout');
  no('POST', '/api/hub/projects');                        // creating a project
  no('DELETE', '/api/hub/projects/demo-1');               // deleting this one
  no('POST', '/api/hub/projects/demo-1');
  no('DELETE', '/api/hub/projects/demo-1/paper');
  no('GET', '/api/hub/projects/other/sync');
  no('GET', '/api/hub/events');
  no('GET', '//evil.example/p/demo-1/api/graph');
  no('GET', 'http://evil.example/p/demo-1/api/graph');
  no('GET', 'p/demo-1/api/graph');
  no('GET', '/p/demo-1/api/graph\r\nX: y');
  no('GET', '/p/demo-1\\api\\graph');
  no('PATCH', '/p/demo-1/api/graph');
  no('GET', null);
  no('GET', '/p/demo-1/api/' + 'a'.repeat(5000));
  assert.equal(allowedRequest('', 'GET', '/p//api/graph'), null);
});
test('inline text cannot end its element', () => {
  assert.equal(safeInlineScript('a = "</script><script>x()</SCRIPT>"; // <!-- c'), 'a = "<\\/script><script>x()<\\/SCRIPT>"; // <\\!-- c');
  assert.equal(safeJson({ pid: '</script>' }), '{"pid":"\\u003c/script>"}');
  assert.deepEqual(JSON.parse(safeJson({ pid: 'a\u2028b' })), { pid: 'a\u2028b' });
  assert.equal(safeJson({ pid: 'a\u2028b' }).includes('\u2028'), false);
});
test('KaTeX fonts are inlined; other formats are dropped', () => {
  const css = '@font-face{font-family:KaTeX_AMS;src:url(fonts/KaTeX_AMS-Regular.woff2) format("woff2"),url(fonts/KaTeX_AMS-Regular.woff) format("woff"),url(fonts/KaTeX_AMS-Regular.ttf) format("truetype")}' +
    '@font-face{font-family:KaTeX_Main;src:url(fonts/KaTeX_Main-Bold.woff2) format("woff2"),url(fonts/KaTeX_Main-Bold.woff) format("woff")}.katex{font:1em KaTeX_Main}';
  assert.deepEqual(fontNames(css), ['KaTeX_AMS-Regular.woff2', 'KaTeX_Main-Bold.woff2']);
  const out = inlineFonts(css, { 'KaTeX_AMS-Regular.woff2': 'QUJD' });
  assert.ok(out.includes('src:url(data:font/woff2;base64,QUJD) format("woff2")}'));
  assert.ok(out.includes('url(fonts/KaTeX_Main-Bold.woff2) format("woff2")}'), 'a font that could not be fetched keeps its reference');
  assert.equal(/\.woff\)|\.ttf\)/.test(out), false);
  assert.ok(out.endsWith('.katex{font:1em KaTeX_Main}'));
});
test('buildPage: no network, scripts only with the nonce, in the right order', () => {
  const html = buildPage({ nonce: 'n'.repeat(32), pid: 'demo</script>', embedJs: 'EMBED()', katexJs: 'KATEX()', appJs: 'APP("</script>")', researchJs: 'RESEARCH()', katexCss: '.k{}', appCss: '.a{}</style>' });
  const csp = /Content-Security-Policy" content="([^"]+)"/.exec(html)![1];
  assert.match(csp, /^default-src 'none'; script-src 'nonce-n{32}'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:;/);
  assert.equal(/connect-src|https?:/.test(csp), false);
  assert.equal((html.match(/<script/g) || []).length, 5);
  assert.equal((html.match(/<script nonce="n{32}">/g) || []).length, 5);
  assert.equal((html.match(/<\/script>/g) || []).length, 5, 'script text cannot close its element');
  assert.equal((html.match(/<\/style>/g) || []).length, 3);
  const order = ['__LEMMATA_TAB__', 'EMBED()', 'KATEX()', 'APP(', 'RESEARCH()'].map(s => html.indexOf(s));
  assert.deepEqual(order, [...order].sort((a, b) => a - b));
  assert.ok(html.includes('{"pid":"demo\\u003c/script>"}'));
  assert.ok(html.includes('<div id="app"></div>'));
  assert.throws(() => buildPage({ nonce: 'x"y', pid: 'p', embedJs: '', katexJs: '', appJs: '', researchJs: '', katexCss: '', appCss: '' }));
});
test('openKind and suggestedName', () => {
  assert.equal(openKind('/p/a/api/thumb?node=x', 'image/png'), 'image');
  assert.equal(openKind('/p/a/api/claims.md', 'text/markdown; charset=utf-8'), 'text');
  assert.equal(openKind('/p/a/api/export', 'text/html; charset=utf-8'), 'save');
  assert.equal(openKind('/p/a/api/thing', 'application/octet-stream'), 'save');
  assert.equal(openKind('/p/a/api/x.svg', 'text/html'), 'save', 'an HTML answer is never treated as a picture');
  assert.equal(suggestedName('/p/a/api/claims.md', 'text/markdown'), 'claims.md');
  assert.equal(suggestedName('/p/a/api/export', 'text/html'), 'lemmata-report.html');
  assert.equal(suggestedName('/p/a/api/thumb?node=fig%3A1', 'image/png'), 'thumb.png');
  assert.equal(suggestedName('/p/a/api/we ird"name', ''), 'we_ird_name');
});
