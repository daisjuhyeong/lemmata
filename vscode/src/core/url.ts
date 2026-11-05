/** Validate and normalise the server address. Only http(s); no credentials in the URL; no path, query or fragment. */
export function normalizeServerUrl(input: string): { ok: true; url: string } | { ok: false; reason: string } {
  let u: URL;
  try { u = new URL((input || '').trim()); } catch { return { ok: false, reason: 'Not a valid URL. Example: http://100.111.135.94:8765' }; }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') return { ok: false, reason: 'Only http:// or https:// addresses are allowed.' };
  if (u.username || u.password) return { ok: false, reason: 'Do not put a user name or password in the address; the token is asked separately.' };
  if ((u.pathname && u.pathname !== '/') || u.search || u.hash) return { ok: false, reason: 'Give only the server address, e.g. http://100.111.135.94:8765' };
  return { ok: true, url: u.origin };
}

/** True for loopback, RFC1918, Tailscale CGNAT (100.64/10), Tailscale ULA, link-local and *.ts.net / .local names. */
export function isPrivateHost(host: string): boolean {
  const h = host.replace(/^\[|\]$/g, '').toLowerCase();
  if (h === 'localhost' || h.endsWith('.ts.net') || h.endsWith('.local') || h === '::1') return true;
  const m = /^(\d+)\.(\d+)\.(\d+)\.(\d+)$/.exec(h);
  if (m) {
    const [a, b] = [Number(m[1]), Number(m[2])];
    return a === 127 || a === 10 || (a === 192 && b === 168) || (a === 172 && b >= 16 && b <= 31) || (a === 100 && b >= 64 && b <= 127) || (a === 169 && b === 254);
  }
  return /^(fd|fe80)/.test(h);
}
