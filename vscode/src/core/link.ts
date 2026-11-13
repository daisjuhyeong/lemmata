// Links from the Lemmata website into VS Code: vscode://lemmata-local.lemmata/open?pid=<project>&view=<page>&sel=<q:… | x:…>
// The link comes from outside VS Code, so everything in it is checked here. It can only open a Lemmata page; it never
// changes anything on the hub, and the project must be one the connected hub lists.
import { VIEWS, View } from './embed';

export const LINK_AUTHORITY = 'lemmata-local.lemmata';
export interface OpenLink { pid: string; view: View; sel: string | null }

const PID_RE = /^[a-z0-9-]{1,64}$/;
/** q:<claim or question id>, x:<experiment id>, or on Setup i:<metric, dataset or method>, c:<claim>; ids are node ids, which may hold ':' '/' '.' but no spaces, quotes or control characters. */
const SEL_RE = /^[qxic]:[^\s<>"'`\\\x00-\x1f\x7f]{1,300}$/;

export function parseOpenLink(path: string, query: string): OpenLink | null {
  if (path !== '/open' && path !== '/open/') return null;
  let q: URLSearchParams;
  try { q = new URLSearchParams(query || ''); } catch { return null; }
  const pid = q.get('pid') || '', view = q.get('view') || 'review', sel = q.get('sel');
  if (!PID_RE.test(pid) || !(VIEWS as readonly string[]).includes(view)) return null;
  if (sel != null && sel !== '' && !SEL_RE.test(sel)) return null;
  return { pid, view: view as View, sel: sel || null };
}

/** The link the website puts on its "Open in VS Code" buttons (kept here so the tests pin both sides to one format). */
export const openLink = (pid: string, view: View, sel?: string): string =>
  'vscode://' + LINK_AUTHORITY + '/open?pid=' + encodeURIComponent(pid) + '&view=' + view + (sel ? '&sel=' + encodeURIComponent(sel) : '');
