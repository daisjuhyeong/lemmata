// The Lemmata tab: the parts that need no VS Code API (unit-tested in test/unit/embed.test.ts).
// The tab shows the hub's own web app inside a webview. The page gets no network access; each request it makes is
// passed to the extension, checked here, and sent to the hub with the stored token.

/** Files the extension itself fetches from the hub to build the page (public code, no project data). */
export const ASSETS = { appJs: '/app.js', researchJs: '/research.js', appCss: '/app.css', tokensCss: '/tokens.css', fontsCss: '/fonts.css', katexJs: '/vendor/katex/katex.min.js', katexCss: '/vendor/katex/katex.min.css' };
export const KATEX_FONT_DIR = '/vendor/katex/fonts/';
/** Where the hub keeps its own fonts (Source Serif 4 for headings). The sans font is not sent: the tab uses the editor's font. */
export const FONT_DIR = '/fonts/';
export const TAB_FONTS = /^SourceSerif4-/;
export const VIEWS = ['review', 'claims', 'experiments', 'digest', 'timeline', 'tasks', 'notation', 'changes', 'graph', 'ask'] as const;
export type View = typeof VIEWS[number];

export type Method = 'GET' | 'POST' | 'PUT' | 'DELETE';
const METHODS: Method[] = ['GET', 'POST', 'PUT', 'DELETE'];

/**
 * May the page, showing project `pid`, send this request? Returns the cleaned path (with query) or null.
 * Allowed: the project's own API (/p/<pid>/api/...), and the few hub routes the app uses: status, the project list,
 * this project's hub actions (read it, sync, paper source, upload, digest) and the usage-event counter.
 * Everything else is refused: other projects, tokens, devices, users, sign-in and admin routes.
 */
export function allowedRequest(pid: string, method: string, rawPath: unknown): { method: Method; path: string } | null {
  const m = String(method || '').toUpperCase() as Method;
  if (!METHODS.includes(m) || typeof rawPath !== 'string' || !pid) return null;
  if (!rawPath.startsWith('/') || rawPath.startsWith('//') || rawPath.length > 4000 || /[\\\0\r\n]/.test(rawPath)) return null;
  let u: URL;
  try { u = new URL(rawPath, 'http://hub.invalid'); } catch { return null; }
  if (u.origin !== 'http://hub.invalid' || u.username || u.password) return null;
  let segs: string[];
  try { segs = u.pathname.split('/').slice(1).map(s => decodeURIComponent(s)); } catch { return null; }
  if (segs.some(s => s === '..' || s === '.' || s.includes('/') || s.includes('\\'))) return null;
  const path = u.pathname + u.search;
  if (segs[0] === 'p' && segs[1] === pid && segs[2] === 'api' && segs.length >= 4 && segs[3] !== '') return { method: m, path };
  if (segs[0] === 'api' && segs[1] === 'hub') {
    const rest = segs.slice(2);
    if (rest.length === 1 && rest[0] === 'status' && m === 'GET') return { method: m, path };
    if (rest.length === 1 && rest[0] === 'projects' && m === 'GET') return { method: m, path };
    if (rest.length === 1 && rest[0] === 'events' && m === 'POST') return { method: m, path };
    if (rest.length === 2 && rest[0] === 'projects' && rest[1] === pid && m === 'GET') return { method: m, path };              // never DELETE the project
    if (rest.length >= 3 && rest[0] === 'projects' && rest[1] === pid && (m === 'GET' || m === 'POST')) return { method: m, path };   // sync, paper, digest
  }
  return null;
}

/** Text placed inside <script>…</script> must not be able to end the element. */
export const safeInlineScript = (js: string): string => js.replace(/<\/(script)/gi, '<\\/$1').replace(/<!--/g, '<\\!--');
export const safeInlineStyle = (css: string): string => css.replace(/<\/(style)/gi, '<\\/$1');
/** JSON for an inline script. */
export const safeJson = (v: unknown): string => JSON.stringify(v).replace(/</g, '\\u003c').split(String.fromCharCode(0x2028)).join('\\u2028').split(String.fromCharCode(0x2029)).join('\\u2029');

/** Names of the .woff2 font files a KaTeX stylesheet refers to (fonts/Name.woff2). */
export function fontNames(css: string): string[] {
  const out: string[] = [];
  for (const m of css.matchAll(/url\(\s*["']?fonts\/([A-Za-z0-9_-]+\.woff2)["']?\s*\)/g)) if (!out.includes(m[1])) out.push(m[1]);
  return out;
}
/**
 * Make a KaTeX stylesheet self-contained: .woff2 files become data: URLs; the .woff and .ttf fallbacks are dropped
 * (the webview cannot fetch them, and every VS Code version reads woff2).
 */
export function inlineFonts(css: string, fonts: { [name: string]: string }): string {
  return css
    .replace(/,\s*url\(\s*["']?fonts\/[A-Za-z0-9_-]+\.(?:woff|ttf)["']?\s*\)\s*format\(\s*["'][a-z0-9]+["']\s*\)/g, '')
    .replace(/url\(\s*["']?fonts\/([A-Za-z0-9_-]+\.woff2)["']?\s*\)/g, (all, name: string) =>
      Object.prototype.hasOwnProperty.call(fonts, name) ? 'url(data:font/woff2;base64,' + fonts[name] + ')' : all);
}

export interface PageParts {
  nonce: string; pid: string; embedJs: string; katexJs: string; appJs: string; researchJs: string; katexCss: string; appCss: string;
  /** The hub's tokens.css and fonts.css (fonts as data: URLs), put before app.css. Left out by an older hub. */
  tokensCss?: string;
  /** media/vscode.css: the editor-theme mapping and the compact layout. Placed after app.css so it wins; every rule is under html.embed. */
  vscodeCss?: string;
  /** The hub's web address, for the "Open on website" link. */
  site?: string;
}

/** Styles only the tab needs. There is no minimum width: the page follows the width of the view (three modes, see media/vscode.css). */
export const TAB_CSS = 'html.embed, html.embed body { height: 100%; } html.embed body { padding: 0; overflow-x: hidden; } html.embed #narrow { display: none !important; }';

/** The whole page. Scripts run only with the nonce; nothing can be loaded from the network. */
export function buildPage(p: PageParts): string {
  if (!/^[A-Za-z0-9]{16,64}$/.test(p.nonce)) throw new Error('bad nonce');
  const s = (js: string) => '<script nonce="' + p.nonce + '">' + safeInlineScript(js) + '</script>';
  const csp = "default-src 'none'; script-src 'nonce-" + p.nonce + "'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; base-uri 'none'; form-action 'none'";
  return ['<!doctype html>', '<html lang="en">', '<head>', '<meta charset="utf-8">',
    '<meta http-equiv="Content-Security-Policy" content="' + csp + '">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">', '<title>Lemmata</title>',
    '<style>' + safeInlineStyle(p.katexCss) + '</style>', ...(p.tokensCss ? ['<style>' + safeInlineStyle(p.tokensCss) + '</style>'] : []), '<style>' + safeInlineStyle(p.appCss) + '</style>',
    ...(p.vscodeCss ? ['<style>' + safeInlineStyle(p.vscodeCss) + '</style>'] : []), '<style>' + TAB_CSS + '</style>',
    '</head>', '<body>', '<div id="app"></div>', '<div id="narrow" role="alert"></div>',
    s('window.__LEMMATA_TAB__ = ' + safeJson(p.site ? { pid: p.pid, site: p.site } : { pid: p.pid }) + ';'), s(p.embedJs), s(p.katexJs), s(p.appJs), s(p.researchJs),
    '</body>', '</html>'].join('\n');
}

/** What to do with a hub file the user clicked, by its content type and path. */
export function openKind(path: string, contentType: string): 'image' | 'text' | 'save' {
  const ct = (contentType || '').split(';')[0].trim().toLowerCase();
  const p = path.split('?')[0].toLowerCase();
  if (/^image\/(png|jpeg|gif|webp|svg\+xml)$/.test(ct)) return 'image';
  if (p.endsWith('/export') || ct === 'text/html') return 'save';
  if (ct === 'text/markdown' || ct === 'text/plain' || ct === 'application/json' || /\.(md|txt|json|bib|tex|csv)$/.test(p)) return 'text';
  return 'save';
}
export function suggestedName(path: string, contentType: string): string {
  const base = (path.split('?')[0].split('/').pop() || 'lemmata').replace(/[^A-Za-z0-9._-]/g, '_') || 'lemmata';
  if (/\.[A-Za-z0-9]{1,5}$/.test(base)) return base;
  const ct = (contentType || '').split(';')[0].trim().toLowerCase();
  const ext: { [k: string]: string } = { 'text/html': '.html', 'image/png': '.png', 'image/jpeg': '.jpg', 'image/gif': '.gif', 'image/webp': '.webp', 'image/svg+xml': '.svg', 'text/markdown': '.md', 'application/json': '.json', 'application/zip': '.zip' };
  return (base === 'export' ? 'lemmata-report' : base) + (ext[ct] || '');
}
