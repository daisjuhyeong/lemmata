import { HubProject } from './types';

export type RemoteRef = { kind: 'github'; repo: string } | { kind: 'overleaf'; id: string };

const GITHUB = /^(?:(?:https?|ssh|git):\/\/(?:[^@/\s]+@)?|[^@/\s]+@)github\.com[:/]+([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+?)(?:\.git)?\/?$/i;
const OVERLEAF = /^https?:\/\/(?:[^@/\s]+(?::[^@/\s]*)?@)?git\.overleaf\.com\/([0-9a-f]{24})(?:\.git)?\/?$/i;

/** Parse one git remote URL. Credentials in the URL are ignored and never returned. */
export function parseRemote(url: string): RemoteRef | null {
  const u = (url || '').trim();
  let m = GITHUB.exec(u);
  if (m) return { kind: 'github', repo: (m[1] + '/' + m[2]).toLowerCase() };
  m = OVERLEAF.exec(u);
  if (m) return { kind: 'overleaf', id: m[1].toLowerCase() };
  return null;
}

/** Output of `git config --get-regexp ^remote\..*\.url` -> list of URLs. */
export function parseGitConfigRemotes(out: string): string[] {
  const urls: string[] = [];
  for (const line of out.split(/\r?\n/)) {
    const m = /^remote\.[^\s]+\.url\s+(.+)$/.exec(line.trim());
    if (m) urls.push(m[1].trim());
  }
  return urls;
}

export interface FolderRemotes { key: string; remotes: string[] }
export interface Binding { project: HubProject; folders: { code?: string; paper?: string } }

/**
 * Match workspace folders to hub projects.
 *  - a github remote equal to project.code_repo binds the folder as the project's "code" repo;
 *  - an Overleaf remote equal to project.paper_source.project_id binds it as "paper";
 *  - `override` (setting lemmata.project) restricts the result to that project id.
 * Returns one binding per project that has at least one matching folder; with an override, a binding is returned even
 * when no folder matches (the panel still works, nothing is mapped).
 */
export function matchProjects(folders: FolderRemotes[], projects: HubProject[], override?: string): Binding[] {
  const wanted = (override || '').trim();
  const out: Binding[] = [];
  for (const p of projects) {
    if (wanted && p.id !== wanted) continue;
    const b: Binding = { project: p, folders: {} };
    const repo = (p.code_repo || '').toLowerCase();
    const ol = p.paper_source && p.paper_source.kind === 'overleaf' ? (p.paper_source.project_id || '').toLowerCase() : '';
    for (const f of folders) {
      for (const url of f.remotes) {
        const r = parseRemote(url);
        if (!r) continue;
        if (r.kind === 'github' && repo && r.repo === repo && !b.folders.code) b.folders.code = f.key;
        if (r.kind === 'overleaf' && ol && r.id === ol && !b.folders.paper) b.folders.paper = f.key;
      }
    }
    if (wanted || b.folders.code || b.folders.paper) out.push(b);
  }
  return out;
}
