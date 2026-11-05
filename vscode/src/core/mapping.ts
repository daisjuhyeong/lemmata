import * as path from 'path';

/**
 * Map a hub (repo id, repo-relative path) such as code/configs/default.yaml onto a workspace folder.
 * Paths come from the server and are untrusted: absolute paths, `..` and backslashes are refused, so a path can
 * never point outside the workspace folder that matched the repo.
 */
export function safeRel(rel: string): string | null {
  if (typeof rel !== 'string' || !rel || rel.includes('\0') || rel.includes('\\')) return null;
  if (rel.startsWith('/') || /^[A-Za-z]:/.test(rel)) return null;
  const n = path.posix.normalize(rel);
  if (n === '..' || n.startsWith('../') || n === '.' || path.posix.isAbsolute(n)) return null;
  return n;
}

export interface Mapped { folder: string; rel: string }

/** `folders` is the binding's role -> folder key table ({code: key, paper: key}). */
export function mapPath(folders: { [role: string]: string | undefined }, repo: string, rel: string): Mapped | null {
  const key = folders[repo];
  const r = safeRel(rel);
  if (!key || !r) return null;
  return { folder: key, rel: r };
}

/** Display form used in the panel for paths that are not mapped: code/configs/default.yaml. */
export function hubPath(repo: string, rel: string): string {
  return repo + '/' + rel;
}
