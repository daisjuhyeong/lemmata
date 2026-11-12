// S18: the tab's stylesheet switch and the three width modes (wiki/design/screens/S18-dais-ui.md, part 2).
import { test } from 'node:test';
import * as assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { ASSETS, FONT_DIR, TAB_CSS, TAB_FONTS, VIEWS, buildPage, fontNames, tabFonts } from '../../src/core/embed';

const MEDIA = path.resolve(__dirname, '..', '..', '..', 'media');
const WEB = path.resolve(__dirname, '..', '..', '..', '..', 'app', 'src', 'lemmata', 'web');
const vscodeCss = fs.readFileSync(path.join(MEDIA, 'vscode.css'), 'utf8');
const appCss = fs.readFileSync(path.join(WEB, 'app.css'), 'utf8');
const base = { nonce: 'n'.repeat(32), pid: 'demo', embedJs: 'EMBED()', katexJs: 'KATEX()', appJs: 'APP()', researchJs: 'RESEARCH()', katexCss: '.katex{}', appCss: '.app{}' };
const styles = (html: string) => [...html.matchAll(/<style>([\s\S]*?)<\/style>/g)].map(m => m[1]);

test('stylesheet switch: tokens before app.css, vscode.css after it, only when given', () => {
  const plain = styles(buildPage(base));
  assert.equal(plain.length, 3, 'an older hub or no vscode.css: katex, app and tab styles only');
  const full = styles(buildPage({ ...base, tokensCss: ':root{--bg:x}', vscodeCss: 'html.embed{--bg:y}' }));
  assert.deepEqual(full, ['.katex{}', ':root{--bg:x}', '.app{}', 'html.embed{--bg:y}', TAB_CSS], 'vscode.css comes after app.css so it wins');
  assert.equal(styles(buildPage({ ...base, vscodeCss: 'a{}</style><script>x</script>' })).some(s => s.includes('</style')), false, 'css cannot close its element');
});

test('the tab has no minimum width and no sideways scrolling of the page', () => {
  assert.equal(/min-width/.test(TAB_CSS), false);
  assert.match(TAB_CSS, /overflow-x: hidden/);
  assert.equal(/1024/.test(buildPage(base)), false);
});

test('security settings are unchanged by the new stylesheets', () => {
  const html = buildPage({ ...base, tokensCss: ':root{}', vscodeCss: 'html.embed{}', site: 'http://hub.example:8765/p/demo/' });
  const csp = /Content-Security-Policy" content="([^"]+)"/.exec(html)![1];
  assert.equal(csp, "default-src 'none'; script-src 'nonce-" + 'n'.repeat(32) + "'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; base-uri 'none'; form-action 'none'");
  assert.ok(html.includes('{"pid":"demo","site":"http://hub.example:8765/p/demo/"}'));
  assert.equal((buildPage(base).match(/"site"/g) || []).length, 0);
});

test('vscode.css: scoped to the tab, follows the editor theme, defines no colour of its own', () => {
  assert.equal(/#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(/.test(vscodeCss), false, 'no colour values');
  for (const v of ['--vscode-editor-background', '--vscode-foreground', '--vscode-descriptionForeground', '--vscode-panel-border', '--vscode-list-hoverBackground', '--vscode-editorWidget-background', '--vscode-font-family', '--vscode-font-size', '--vscode-editor-font-family'])
    assert.ok(vscodeCss.includes(v), v + ' is mapped');
  // every top-level rule starts with html.embed (or is a container query whose rules do)
  const noComments = vscodeCss.replace(/\/\*[\s\S]*?\*\//g, '');
  const selectors = [...noComments.matchAll(/(^|\})\s*([^{}@]+)\{/g)].map(m => m[2].trim()).filter(Boolean);
  assert.ok(selectors.length > 30);
  for (const sel of selectors) for (const part of sel.split(',')) assert.match(part.trim(), /^html\.embed\b/, 'unscoped selector: ' + part.trim());
  assert.match(vscodeCss, /body\.vscode-dark[^{]*\{ --accent-dark: var\(--accent-light\); \}/, 'links stay readable on dark');
});

test('three width modes: container queries on #app, the same thresholds in the hub stylesheet and in vscode.css', () => {
  assert.match(appCss, /container-type:inline-size; container-name:app/);
  for (const css of [appCss, vscodeCss]) {
    assert.match(css, /@container app \(max-width: 700px\)/, 'medium and narrow: 700px');
    assert.match(css, /@container app \(max-width: 359px\)/, 'narrow: under 360px');
    assert.equal(/@media[^{]*(max|min)-width/.test(css.replace(/prefers-reduced-motion/g, '')), false, 'width modes never use the window width');
  }
  // narrow: no bracket tag on screen, two Experiments columns; medium: four columns
  const narrow = appCss.slice(appCss.indexOf('@container app (max-width: 359px)'));
  assert.match(narrow, /\.rtag \{ display:none; \}/);
  assert.match(narrow, /grid-template-columns:minmax\(0,1fr\) 72px/);
  const medium = appCss.slice(appCss.indexOf('@container app (max-width: 700px)'), appCss.indexOf('@container app (max-width: 359px)'));
  assert.match(medium, /grid-template-columns:minmax\(0,1fr\) 84px 96px 56px/);
});

test('views: Digest is a page the extension can open; hub fonts are the headline serif only', () => {
  assert.ok((VIEWS as readonly string[]).includes('digest'));
  assert.deepEqual(['/tokens.css', '/fonts.css'], [ASSETS.tokensCss, ASSETS.fontsCss]);
  const fontsCss = fs.readFileSync(path.join(WEB, 'fonts.css'), 'utf8');
  const wanted = fontNames(fontsCss).filter(n => TAB_FONTS.test(n));
  assert.deepEqual(wanted.sort(), ['SourceSerif4-Bold.woff2', 'SourceSerif4-Italic.woff2', 'SourceSerif4-Regular.woff2']);
  assert.equal(FONT_DIR, '/fonts/');
  const out = tabFonts(fontsCss, Object.fromEntries(wanted.map(n => [n, 'QUJD'])));
  assert.equal((out.match(/data:font\/woff2;base64,QUJD/g) || []).length, 3, 'the webview allows font-src data: only');
  assert.equal((out.match(/@font-face/g) || []).length, 3, 'only the inlined serif faces are left');
  assert.equal(/url\((?!data:)/.test(out), false, 'no @font-face points at a file the CSP would block');
  assert.equal(out.includes('Source Sans 3'), false, 'the sans font is not sent to the tab (it uses the editor font)');
  // a font that could not be fetched is dropped too, so the page falls back to Georgia instead of asking for it
  const partial = tabFonts(fontsCss, { 'SourceSerif4-Bold.woff2': 'QUJD' });
  assert.equal((partial.match(/@font-face/g) || []).length, 1);
  assert.equal(/url\((?!data:)/.test(partial), false);
});

test('Claims tree per width mode: the vertical graph (circles on lines) when wide and medium, four-word labels from 700px, an outline with arrows under 360px', () => {
  const medium = appCss.slice(appCss.indexOf('@container app (max-width: 700px)'), appCss.indexOf('@container app (max-width: 359px)'));
  const narrow = appCss.slice(appCss.indexOf('@container app (max-width: 359px)'));
  assert.match(appCss, /\.rxt-w4 \{ display:none; \}/, 'wide: six-word labels');
  assert.match(medium, /\.rxt-w6 \{ display:none; \} \.rxt-w4 \{ display:inline; \}/, 'medium: four-word labels');
  assert.doesNotMatch(medium, /\.rxt-caret/, 'medium keeps the graph: no collapse arrows');
  assert.match(appCss, /\.rxt-caret \{[^}]*display:none;/, 'no arrows by default');
  assert.match(narrow, /\.rxt-caret \{ display:inline-block; \}/, 'narrow: collapse arrows, as in the file explorer');
  assert.match(narrow, /border-left-color:transparent/, 'narrow: no lines, an indented outline');
  assert.match(narrow, /\.rx-rv-r \{ grid-template-columns:32px minmax\(0,1fr\); \}/, 'narrow: Review rows keep two columns');
});
