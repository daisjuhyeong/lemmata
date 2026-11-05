// Repository text is untrusted. Strip control characters and ANSI escapes, cap the length. Never render as markdown.
const ANSI = /\u001b\[[0-9;?]*[ -/]*[@-~]|\u001b\][^\u0007\u001b]*(?:\u0007|\u001b\\)|\u001b./g;
// eslint-disable-next-line no-control-regex
const CTRL = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f‪-‮⁦-⁩]/g;

export function clean(s: unknown, max = 400): string {
  if (typeof s !== 'string') return '';
  let t = s.replace(ANSI, '').replace(CTRL, '').replace(/\r\n?/g, '\n');
  if (t.length > max) t = t.slice(0, max - 1) + '…';
  return t;
}
export function oneLine(s: unknown, max = 200): string {
  return clean(s, max * 2).replace(/\s+/g, ' ').trim().slice(0, max);
}
