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
export interface Binding { project: HubProject; folders: { code?: string; paper?: string }; subdirs: { paper?: string } }

/**
 * Match workspace folders to hub projects.
 *  - a github remote equal to project.code_repo binds the folder as the project's "code" repo;
 *  - paper, project.paper_source.kind "github": a folder whose remote equals paper_source.repo binds as "paper"
 *    (its own repo; or, when that repo is the code repo, the code folder again). With paper_source.subdir the hub path
 *    paper/<rel> maps to <folder>/<subdir>/<rel> (`subdirs.paper`);
 *  - paper, kind "overleaf" (only data from an old setup): a git.overleaf.com remote equal to project_id binds as "paper";
 *  - `override` (setting lemmata.project) restricts the result to that project id.
 * Returns one binding per project that has at least one matching folder; with an override, a binding is returned even
 * when no folder matches (the panel still works, nothing is mapped).
 */
export function matchProjects(folders: FolderRemotes[], projects: HubProject[], override?: string): Binding[] {
  const wanted = (override || '').trim();
  const out: Binding[] = [];
  for (const p of projects) {
    if (wanted && p.id !== wanted) continue;
    const b: Binding = { project: p, folders: {}, subdirs: {} };
    const repo = (p.code_repo || '').toLowerCase();
    const ps = p.paper_source;
    const ghPaper = ps && ps.kind === 'github' ? (ps.repo || '').toLowerCase() : '';
    const ol = ps && ps.kind === 'overleaf' ? (ps.project_id || '').toLowerCase() : '';
    for (const f of folders) {
      for (const url of f.remotes) {
        const r = parseRemote(url);
        if (!r) continue;
        if (r.kind === 'github' && repo && r.repo === repo && !b.folders.code) b.folders.code = f.key;
        if (r.kind === 'github' && ghPaper && r.repo === ghPaper && !b.folders.paper) {
          b.folders.paper = f.key;
          if (ps && ps.subdir) b.subdirs.paper = ps.subdir;
        }
        if (r.kind === 'overleaf' && ol && r.id === ol && !b.folders.paper) b.folders.paper = f.key;
      }
    }
    if (wanted || b.folders.code || b.folders.paper) out.push(b);
  }
  return out;
}
