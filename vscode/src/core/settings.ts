import { normalizeServerUrl } from './url';

export const DEFAULT_URL = 'http://100.111.135.94:8765';
export const TOKEN_PREFIX = 'lemmata.token@';

/** The token is stored per origin, so it can only ever be sent to the origin it was issued for. */
export const tokenKey = (origin: string): string => TOKEN_PREFIX + origin;

interface Inspected { defaultValue?: string; globalValue?: string; globalLocalValue?: string; globalRemoteValue?: string }

/**
 * Server address from `config.inspect('serverUrl')`. Only the user-level (machine-wide) value or the default counts:
 * workspace and workspace-folder values (a repo's .vscode/settings.json) are ignored on purpose.
 */
export function serverFromInspect(i: Inspected | undefined): { ok: true; url: string } | { ok: false; reason: string } {
  const raw = (i && (i.globalLocalValue ?? i.globalRemoteValue ?? i.globalValue)) ?? (i && i.defaultValue) ?? DEFAULT_URL;
  return normalizeServerUrl(String(raw));
}

/** The token to use for `origin`: only the one stored under that origin's key. */
export async function tokenFor(origin: string, get: (key: string) => Thenable<string | undefined> | Promise<string | undefined>): Promise<string | undefined> {
  return (await get(tokenKey(origin))) || undefined;
}
