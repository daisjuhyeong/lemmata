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

/**
 * `folders` is the binding's role -> folder key table ({code: key, paper: key}).
 * `subdirs` (role -> folder inside the workspace folder): when the paper lives in a subfolder of a repo, hub path
 * paper/<rel> becomes <folder>/<subdir>/<rel>. The subdir comes from the server too, so it gets the same checks.
 */
export function mapPath(folders: { [role: string]: string | undefined }, repo: string, rel: string, subdirs?: { [role: string]: string | undefined }): Mapped | null {
  const key = Object.prototype.hasOwnProperty.call(folders, repo) ? folders[repo] : undefined;
  const r = safeRel(rel);
  if (!key || !r) return null;
  const sd = subdirs && Object.prototype.hasOwnProperty.call(subdirs, repo) ? subdirs[repo] : undefined;
  if (sd === undefined || sd === '') return { folder: key, rel: r };
  const s = safeRel(sd.replace(/\/+$/, ''));
  if (!s) return null;
  return { folder: key, rel: s + '/' + r };
}

/** Display form used in the panel for paths that are not mapped: code/configs/default.yaml. */
export function hubPath(repo: string, rel: string): string {
  return repo + '/' + rel;
}
