import { Alarms, Findings, Graph, GraphNode, Triage, TriageState, Role, Sev, Evidence } from './types';
import { mapPath } from './mapping';
import { clean, oneLine } from './text';

export interface LocRef { repo: string; path: string; line: number | null }
export interface NodeItem {
  nodeId: string; name: string; role: Role | 'removed'; relation: string; loc: LocRef | null;
  triage: TriageState; outdated: boolean;
}
export interface GroupItem { id: string; display: string; short: string; subject: string; causeKind: string; nodes: NodeItem[] }
export interface FindingItem {
  id: string; check: string; title: string; message: string; severity: 'warning' | 'info'; triage: TriageState; outdated: boolean; locs: LocRef[];
}
export interface CheckItem { check: string; title: string; items: FindingItem[] }
export interface Model {
  groups: GroupItem[]; checks: CheckItem[];
  /** distinct nodes to recheck (reviewed and ignored ones are not counted) */
  recheck: number;
  checkpoint: string | null;
}

const STATES = new Set(['reviewed', 'needs_fixing', 'ignored', 'unreviewed']);
function stateOf(triage: Triage | null | undefined, type: 'node' | 'finding', id: string): { state: TriageState; outdated: boolean } {
  const e = triage && triage.entries ? triage.entries[type + ':' + id] : undefined;
  if (!e) return { state: 'unreviewed', outdated: false };
  const s = e.effective_state || e.state || 'unreviewed';
  return { state: (STATES.has(s) ? s : 'unreviewed') as TriageState, outdated: !!e.outdated };
}

function locOf(n: GraphNode | undefined): LocRef | null {
  if (!n || !n.loc || !n.loc.path) return null;
  const line = typeof n.loc.line === 'number' && n.loc.line >= 1 ? Math.floor(n.loc.line) : null;
  return { repo: n.repo, path: n.loc.path, line };
}

export function buildModel(alarms: Alarms | null, findings: Findings | null, graph: Graph | null, triage: Triage | null): Model {
  const byId = new Map<string, GraphNode>();
  for (const n of (graph && graph.nodes) || []) byId.set(n.id, n);
  const nameOf = (id: string) => oneLine((byId.get(id) || ({} as GraphNode)).name || id, 80);

  const counted = new Set<string>();
  const groups: GroupItem[] = [];
  for (const g of (alarms && alarms.groups) || []) {
    const causeKind = clean(g.cause && g.cause.kind, 30);
    const short = oneLine(g.cause && g.cause.short, 12);
    const subject = oneLine(g.cause && g.cause.subject, 120) || (causeKind === 'worktree' ? 'uncommitted changes' : causeKind || 'change');
    const changedNames = g.changed.map(c => nameOf(c.node_id));
    const upTo = changedNames.slice(0, 3).join(', ') + (changedNames.length > 3 ? ', …' : '');
    const nodes: NodeItem[] = [];
    const add = (id: string, role: Role) => {
      const t = stateOf(triage, 'node', id);
      if (t.state !== 'reviewed' && t.state !== 'ignored') counted.add(id);
      nodes.push({ nodeId: id, name: nameOf(id), role, relation: role === 'changed' ? 'changed' : 'downstream of ' + upTo,
        loc: locOf(byId.get(id)), triage: t.state, outdated: t.outdated });
    };
    for (const c of g.changed) add(c.node_id, 'changed');
    for (const d of g.downstream) add(d.node_id, 'downstream');
    for (const r of g.removed || []) {
      nodes.push({ nodeId: r.node_id, name: oneLine(r.name || r.node_id, 80), role: 'removed', relation: 'removed', loc: null, triage: 'unreviewed', outdated: false });
    }
    groups.push({ id: g.id, display: oneLine(g.display, 8) || g.id, short, subject, causeKind, nodes });
  }

  const checks: CheckItem[] = [];
  const byCheck = new Map<string, CheckItem>();
  for (const c of (findings && findings.checks) || []) {
    const ci = { check: c.check, title: oneLine(c.title, 80) || c.check, items: [] as FindingItem[] };
    byCheck.set(c.check, ci); checks.push(ci);
  }
  for (const f of (findings && findings.findings) || []) {
    let ci = byCheck.get(f.check);
    if (!ci) { ci = { check: f.check, title: oneLine(f.title, 80) || f.check, items: [] }; byCheck.set(f.check, ci); checks.push(ci); }
    const t = stateOf(triage, 'finding', f.id);
    const seen = new Set<string>();
    const locs: LocRef[] = [];
    for (const ev of f.evidence || []) {
      if (!ev || !ev.path) continue;
      const line = typeof ev.line === 'number' && ev.line >= 1 ? Math.floor(ev.line) : null;
      const k = ev.repo + '\0' + ev.path + '\0' + line;
      if (seen.has(k)) continue;
      seen.add(k); locs.push({ repo: ev.repo, path: ev.path, line });
    }
    ci.items.push({ id: f.id, check: f.check, title: oneLine(f.title, 120), message: oneLine(f.message, 600),
      severity: f.severity === 'info' ? 'info' : 'warning', triage: t.state, outdated: t.outdated, locs });
  }
  return { groups, checks: checks.filter(c => c.items.length), recheck: counted.size, checkpoint: alarms && alarms.checkpoint ? alarms.checkpoint.id : null };
}

/* ---------- diagnostics ---------- */
export interface Diag {
  folder: string;        // workspace folder key
  rel: string;           // path inside that folder (posix)
  line0: number;         // 0-based
  severity: Sev;
  message: string;
  code: string;
  source: 'Lemmata';
  kind: 'alarm' | 'finding';
  targetId: string;      // node id or finding id (for triage lookups)
}

function sevFor(base: Sev, state: TriageState): Sev | null {
  if (state === 'reviewed' || state === 'ignored') return null;   // hidden
  if (state === 'needs_fixing') return 'error';
  return base;
}

/** Diagnostics for the repos that matched a workspace folder (`folders`: repo id -> folder key). Others are panel-only. */
export function toDiagnostics(model: Model, folders: { [repo: string]: string | undefined }): Diag[] {
  const out: Diag[] = [];
  for (const g of model.groups) {
    for (const n of g.nodes) {
      if (n.role === 'removed' || !n.loc) continue;
      const sev = sevFor('warning', n.triage);
      const m = mapPath(folders, n.loc.repo, n.loc.path);
      if (!sev || !m) continue;
      out.push({ folder: m.folder, rel: m.rel, line0: (n.loc.line || 1) - 1, severity: sev, source: 'Lemmata', kind: 'alarm', targetId: n.nodeId, code: g.display,
        message: 'Recheck: ' + n.name + ' — ' + [g.short, g.subject].filter(Boolean).join(' ') + ' (' + n.relation + ')' });
    }
  }
  for (const c of model.checks) {
    for (const f of c.items) {
      const sev = sevFor(f.severity === 'info' ? 'information' : 'warning', f.triage);
      if (!sev) continue;
      for (const l of f.locs) {
        const m = mapPath(folders, l.repo, l.path);
        if (!m) continue;
        out.push({ folder: m.folder, rel: m.rel, line0: (l.line || 1) - 1, severity: sev, source: 'Lemmata', kind: 'finding', targetId: f.id, code: f.check, message: f.message });
      }
    }
  }
  return out;
}

export type { Evidence };
