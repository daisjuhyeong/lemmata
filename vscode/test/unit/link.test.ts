import { test } from 'node:test';
import * as assert from 'node:assert/strict';
import * as fs from 'fs';
import * as path from 'path';
import { LINK_AUTHORITY, openLink, parseOpenLink } from '../../src/core/link';

const parse = (link: string) => { const u = new URL(link); return parseOpenLink(u.pathname, u.search.slice(1)); };

test('website link: claim and experiment selections round-trip', () => {
  assert.deepEqual(parse(openLink('mcd-extension-5f70', 'experiments', 'q:h1')), { pid: 'mcd-extension-5f70', view: 'experiments', sel: 'q:h1' });
  const x = 'x:code:results/mcd_s2/metrics.json';
  assert.deepEqual(parse(openLink('mcd-extension-5f70', 'experiments', x)), { pid: 'mcd-extension-5f70', view: 'experiments', sel: x });
  assert.deepEqual(parseOpenLink('/open', 'pid=demo-1'), { pid: 'demo-1', view: 'review', sel: null });
});

test('website link: anything else is refused', () => {
  const no = (p: string, q: string) => assert.equal(parseOpenLink(p, q), null, p + '?' + q);
  no('/delete', 'pid=demo-1');
  no('/open', '');
  no('/open', 'pid=../x');
  no('/open', 'pid=Demo');
  no('/open', 'pid=' + 'a'.repeat(65));
  no('/open', 'pid=demo-1&view=tokens');
  no('/open', 'pid=demo-1&view=experiments&sel=z:1');
  no('/open', 'pid=demo-1&view=experiments&sel=' + encodeURIComponent('q:a b'));
  no('/open', 'pid=demo-1&view=experiments&sel=' + encodeURIComponent('x:"><script>'));
  no('/open', 'pid=demo-1&view=experiments&sel=' + encodeURIComponent('x:a\nb'));
  no('/open', 'pid=demo-1&view=experiments&sel=x:' + 'a'.repeat(301));
});

test('the website builds the same link the extension reads', () => {
  const js = fs.readFileSync(path.join(__dirname, '..', '..', '..', '..', 'app', 'src', 'lemmata', 'web', 'research.js'), 'utf8');
  assert.ok(js.includes("'vscode://" + LINK_AUTHORITY + "/open?pid='"), 'research.js link prefix');
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', '..', 'package.json'), 'utf8'));
  assert.equal(pkg.publisher + '.' + pkg.name, LINK_AUTHORITY);
  assert.ok(pkg.activationEvents.includes('onUri'));
});

test('S23: the Setup page opens from a link with a metric, dataset, method or claim selected', () => {
  for (const sel of ['i:dataset:electricity', 'i:method:mcd-dd', 'c:mine:1', 'x:map:main']) assert.deepEqual(parse(openLink('mcd-extension-5f70', 'setup', sel)), { pid: 'mcd-extension-5f70', view: 'setup', sel });
  assert.equal(parse('vscode://' + LINK_AUTHORITY + '/open?pid=mcd-extension-5f70&view=setup&sel=z:nope'), null);
});
