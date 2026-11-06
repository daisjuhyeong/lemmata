// Shapes of the hub API responses the extension reads (wiki/architecture/data-model.md, S04/S05 briefs).
// Readers ignore unknown fields; everything optional is treated as untrusted text.

export interface HubProject {
  id: string;
  name: string;
  code_repo?: string | null;
  branch?: string | null;
  paper_source?: { kind: 'zip' | 'github' | 'overleaf'; repo?: string; branch?: string; subdir?: string; project_id?: string };
  last_sync?: string | null;
  counts?: { recheck: number; findings: number };
}

export interface GraphNode {
  id: string;
  kind: string;
  repo: string;
  name: string;
  loc?: { path: string; line?: number | null; end_line?: number | null } | null;
}

export interface Cause {
  event_id?: string;
  kind?: string;
  repo?: string;
  short?: string;
  subject?: string;
  files?: string[];
}
export interface AlarmGroup {
  id: string;
  display: string;
  cause: Cause;
  changed: { node_id: string; change?: string }[];
  removed?: { node_id: string; name?: string; path?: string; kind?: string }[];
  downstream: { node_id: string; depth?: number }[];
}
export interface Alarms {
  checkpoint: { id: string; note?: string } | null;
  groups: AlarmGroup[];
}

export interface Evidence { repo: string; path: string; line: number | null; text?: string; role?: string }
export interface Finding {
  id: string;
  check: string;
  severity: 'warning' | 'info' | string;
  title: string;
  message: string;
  evidence: Evidence[];
}
export interface Findings {
  checks: { check: string; title: string; status: string; count: number }[];
  findings: Finding[];
}

export interface TriageEntry { state?: string; effective_state?: string; outdated?: boolean; note?: string }
export interface Triage { entries: Record<string, TriageEntry> }
export interface Graph { nodes: GraphNode[] }

export interface Analysis {
  group_id: string;
  node_id: string;
  chain: { nodes: string[]; edges: string[] };
  diffs: { node_id: string; repo: string; path: string; from_label?: string; to_label?: string; binary?: boolean; truncated?: boolean; unified: string }[];
  explanation: string;
}

export type TriageState = 'reviewed' | 'needs_fixing' | 'ignored' | 'unreviewed';
export type Role = 'changed' | 'downstream';
export type Sev = 'error' | 'warning' | 'information';
