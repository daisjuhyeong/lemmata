// Run capture, the parts that need no VS Code API (unit-tested in test/unit/runs.test.ts).
// A run manifest is the only thing that leaves the machine: the command, the commit, hashes, numbers and file paths.
// It never holds file contents, data or weights.
import { createHash } from 'crypto';

export type RunSource = 'terminal' | 'watcher' | 'agent';
export interface FileRef { path: string; hash: string | null }
export interface RunManifest {
  run_id: string;
  source: RunSource;
  command: string | null;
  cwd: string | null;
  host: string | null;
  git_sha: string | null;
  dirty: boolean | null;
  diff_hash: string | null;
  configs: FileRef[];
  metrics: Record<string, number>;
  artifacts: FileRef[];
  started: string | null;
  ended: string | null;
  exit_code: number | null;
  note?: string | null;
}

export const sha256 = (data: string | Buffer): string => 'sha256:' + createHash('sha256').update(data).digest('hex');

/* ---------- which commands are experiments ---------- */
// Launchers that start a script, optionally behind env assignments (CUDA_VISIBLE_DEVICES=0 ...) and a runner (uv run, nohup ...).
export const DEFAULT_COMMAND_PATTERN =
  '^\\s*(?:[A-Za-z_][A-Za-z0-9_]*=\\S*\\s+)*(?:(?:nohup|time|env|caffeinate)\\s+)*(?:(?:uv|poetry|pdm|pixi|hatch)\\s+run\\s+|conda\\s+run\\s+(?:-\\S+\\s+\\S+\\s+)*)?' +
  '(?:python[0-9.]*|accelerate\\s+launch|torchrun|sbatch|srun|julia|Rscript|(?:ba|z)?sh\\s+\\S+\\.sh|\\./\\S+\\.(?:sh|py))(?:\\s|$)';
// Things that start with a launcher but are not experiments.
const NOT_A_RUN = /(?:^|\s)python[0-9.]*\s+(?:-V\b|--version\b|-c\b|-m\s+(?:pip|venv|ensurepip|http\.server|pytest|unittest|ipykernel|jupyter|notebook|black|ruff|mypy|build|twine)\b)|(?:^|\s)python[0-9.]*\s*$/;

/** The part of a command line that launches an experiment ("cd exp && python train.py" -> "python train.py"), or null. */
export function experimentPart(cmd: string, pattern = DEFAULT_COMMAND_PATTERN): string | null {
  const c = (cmd || '').trim();
  if (!c || c.length > 4000) return null;
  let re: RegExp;
  try { re = new RegExp(pattern || DEFAULT_COMMAND_PATTERN); } catch { re = new RegExp(DEFAULT_COMMAND_PATTERN); }
  for (const seg of c.split(/&&|\|\||\||;|\n/).map(s => s.trim()).filter(Boolean)) if (re.test(seg) && !NOT_A_RUN.test(seg)) return seg;
  return null;
}
export const isExperimentCommand = (cmd: string, pattern = DEFAULT_COMMAND_PATTERN): boolean => experimentPart(cmd, pattern) !== null;

/** Settings files named on the command line (configs/a.yaml, --config=b.toml): candidates to hash, relative as typed. */
export function configArgs(cmd: string): string[] {
  const out: string[] = [];
  for (const tok of (cmd || '').split(/\s+/)) {
    const t = tok.replace(/^[^=\s]*=/, '').replace(/^["']|["']$/g, '');
    if (/^[\w./@+-]+\.(?:ya?ml|toml|json|cfg|ini|conf)$/i.test(t) && !t.includes('..') && !out.includes(t)) out.push(t);
  }
  return out.slice(0, 20);
}

/* ---------- ids and time ---------- */
const pad = (n: number) => String(n).padStart(2, '0');
/** Local time with its UTC offset, e.g. 2026-11-11T21:04:13+09:00. */
export function isoLocal(d: Date): string {
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? '+' : '-';
  const a = Math.abs(off);
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds()) +
    sign + pad(Math.floor(a / 60)) + ':' + pad(a % 60);
}
/** 2026-11-11T21-04-13_a3f9: sortable, safe as a file name, stable for the same command, folder and start time. */
export function runId(started: Date, command: string, cwd: string): string {
  const stamp = isoLocal(started).slice(0, 19).replace(/:/g, '-');
  return stamp + '_' + createHash('sha256').update(command + '\0' + cwd + '\0' + started.getTime()).digest('hex').slice(0, 4);
}
export const RUN_ID = /^[A-Za-z0-9][A-Za-z0-9_.:-]{5,79}$/;

/* ---------- numbers from a metrics file ---------- */
const MAX_METRICS = 200;
function flatten(o: unknown, prefix: string, out: Record<string, number>, depth: number) {
  if (Object.keys(out).length >= MAX_METRICS) return;
  if (typeof o === 'number' && Number.isFinite(o)) { if (prefix) out[prefix.slice(0, 120)] = o; return; }
  if (!o || typeof o !== 'object' || Array.isArray(o) || depth > 3) return;
  for (const [k, v] of Object.entries(o as Record<string, unknown>)) flatten(v, prefix ? prefix + '.' + k : k, out, depth + 1);
}
/**
 * Numbers in a small metrics file. JSON: every number, nested keys joined with dots. CSV/TSV: only a file with a header
 * and exactly one data row (a table of several rows is a result table, which the hub reads from the repository instead).
 */
export function parseMetrics(path: string, text: string): Record<string, number> {
  const out: Record<string, number> = {};
  const low = path.toLowerCase();
  if (text.length > 512 * 1024) return out;
  if (low.endsWith('.json')) {
    try { flatten(JSON.parse(text), '', out, 0); } catch { /* not JSON yet (still being written) */ }
    return out;
  }
  if (low.endsWith('.jsonl')) {       // a training log: the last complete line is the latest state
    const lines = text.split(/\r?\n/).filter(l => l.trim());
    for (let i = lines.length - 1; i >= 0 && i >= lines.length - 3; i--) {
      try { flatten(JSON.parse(lines[i]), '', out, 0); return out; } catch { /* try the line before */ }
    }
    return out;
  }
  if (low.endsWith('.csv') || low.endsWith('.tsv')) {
    const rows = text.split(/\r?\n/).filter(l => l.trim());
    if (rows.length !== 2) return out;
    const sep = low.endsWith('.tsv') || (rows[0].includes('\t') && !rows[0].includes(',')) ? '\t' : ',';
    const head = rows[0].split(sep), vals = rows[1].split(sep);
    head.forEach((h, i) => {
      const v = Number((vals[i] || '').trim());
      if (h.trim() && (vals[i] || '').trim() !== '' && Number.isFinite(v) && Object.keys(out).length < MAX_METRICS) out[h.trim().slice(0, 120)] = v;
    });
  }
  return out;
}

/* ---------- globs ---------- */
/** Minimal glob: ** (any folders), * (within one path part), ? (one character). Paths use forward slashes. */
export function globToRegExp(glob: string): RegExp {
  let re = '';
  const g = glob.replace(/\\/g, '/').replace(/^\.\//, '');
  for (let i = 0; i < g.length; i++) {
    const c = g[i];
    if (c === '*') {
      if (g[i + 1] === '*') { re += g[i + 2] === '/' ? '(?:.*/)?' : '.*'; i += g[i + 2] === '/' ? 2 : 1; }
      else re += '[^/]*';
    } else if (c === '?') re += '[^/]';
    else re += c.replace(/[.+^${}()|[\]\\]/g, '\\$&');
  }
  return new RegExp('^' + re + '$');
}
export const matchAny = (rel: string, globs: string[]): boolean => globs.some(g => globToRegExp(g).test(rel.replace(/\\/g, '/')));
export const DEFAULT_RESULT_GLOBS = ['results/**', 'outputs/**', 'output/**', 'runs/**', 'logs/**', 'experiments/**', 'exp/**', 'checkpoints/**'];
export const DEFAULT_METRIC_FILES = ['*metric*.json', '*result*.json', '*score*.json', '*eval*.json', 'summary.json', '*metric*.csv', '*result*.csv', '*score*.csv', '*eval*.csv', '*metric*.jsonl'];
/** Is this repo-relative path a metrics file inside one of the results folders? */
export function isMetricFile(rel: string, resultGlobs = DEFAULT_RESULT_GLOBS, metricFiles = DEFAULT_METRIC_FILES): boolean {
  const p = rel.replace(/\\/g, '/');
  if (p.startsWith('.lemmata/') || p.includes('/.lemmata/') || p.startsWith('.git/') || p.includes('node_modules/')) return false;
  return matchAny(p, resultGlobs) && matchAny(p.split('/').pop() || '', metricFiles);
}

/* ---------- which run wrote this file ---------- */
export interface RunWindow { run_id: string; startedMs: number; endedMs: number | null }
/**
 * The run a result file belongs to: one that started before the file was written and is still going, or ended at most
 * `graceMs` before. With several candidates the most recently started wins. null: no run explains the file (a detached job).
 */
export function pickRun(fileMs: number, runs: RunWindow[], graceMs = 15000): string | null {
  let best: RunWindow | null = null;
  for (const r of runs) {
    if (r.startedMs > fileMs + 1000) continue;
    if (r.endedMs !== null && fileMs > r.endedMs + graceMs) continue;
    if (!best || r.startedMs > best.startedMs) best = r;
  }
  return best ? best.run_id : null;
}

/** The same run reported twice (e.g. by the terminal and by a hook): same command and folder, started within 5 s. */
export function sameRun(a: RunManifest, b: RunManifest): boolean {
  if (a.run_id === b.run_id) return true;
  if (!a.command || a.command !== b.command || (a.cwd || '') !== (b.cwd || '')) return false;
  const ta = Date.parse(a.started || ''), tb = Date.parse(b.started || '');
  return Number.isFinite(ta) && Number.isFinite(tb) && Math.abs(ta - tb) <= 5000;
}

/**
 * Add one written file to a manifest (replacing an older entry for the same path) and fold its numbers in.
 * The first file's numbers keep their names; numbers of further files are prefixed with "<folder>/<file>:" so two
 * seeds written by one command do not overwrite each other.
 */
export function addArtifact(m: RunManifest, rel: string, hash: string | null, metrics: Record<string, number>): RunManifest {
  const first = !m.artifacts.length || m.artifacts[0].path === rel;
  const artifacts = m.artifacts.some(a => a.path === rel) ? m.artifacts.map(a => (a.path === rel ? { path: rel, hash } : a)) : m.artifacts.concat([{ path: rel, hash }]).slice(0, 50);
  const prefix = first ? '' : rel.replace(/\.[^./]+$/, '').split('/').slice(-2).join('/') + ':';
  const merged: Record<string, number> = { ...m.metrics };
  for (const [k, v] of Object.entries(metrics)) merged[(prefix + k).slice(0, 120)] = v;
  return { ...m, artifacts, metrics: Object.fromEntries(Object.entries(merged).slice(0, MAX_METRICS)) };
}

/** Validate a manifest read back from disk (a hook or another tool may have written it). */
export function asManifest(o: unknown): RunManifest | null {
  if (!o || typeof o !== 'object') return null;
  const m = o as Record<string, unknown>;
  if (typeof m.run_id !== 'string' || !RUN_ID.test(m.run_id)) return null;
  if (m.source !== 'terminal' && m.source !== 'watcher' && m.source !== 'agent') return null;
  const str = (v: unknown, n: number) => (typeof v === 'string' && v ? v.slice(0, n) : null);
  const files = (v: unknown, n: number): FileRef[] => (Array.isArray(v) ? v : []).filter(f => f && typeof f.path === 'string' && f.path)
    .slice(0, n).map(f => ({ path: String(f.path).replace(/\\/g, '/').slice(0, 300), hash: typeof f.hash === 'string' && /^(sha256:)?[0-9a-f]{8,64}$/.test(f.hash) ? f.hash : null }));
  const metrics: Record<string, number> = {};
  if (m.metrics && typeof m.metrics === 'object') for (const [k, v] of Object.entries(m.metrics as object).slice(0, MAX_METRICS)) if (typeof v === 'number' && Number.isFinite(v)) metrics[k.slice(0, 120)] = v;
  const sha = typeof m.git_sha === 'string' && /^[0-9a-f]{7,64}$/.test(m.git_sha) ? m.git_sha : null;
  const time = (v: unknown) => (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(v) ? v.slice(0, 40) : null);
  const man: RunManifest = { run_id: m.run_id, source: m.source, command: str(m.command, 2000), cwd: str(m.cwd, 500), host: str(m.host, 100), git_sha: sha,
    dirty: typeof m.dirty === 'boolean' ? m.dirty : null, diff_hash: typeof m.diff_hash === 'string' && /^(sha256:)?[0-9a-f]{8,64}$/.test(m.diff_hash) ? m.diff_hash : null,
    configs: files(m.configs, 20), metrics, artifacts: files(m.artifacts, 50), started: time(m.started), ended: time(m.ended),
    exit_code: typeof m.exit_code === 'number' && Number.isInteger(m.exit_code) ? m.exit_code : null, note: str(m.note, 500) };
  return man.command || man.artifacts.length ? man : null;
}

/** One line for the panel: "f1=0.851 auroc=0.912". */
export function metricsLine(metrics: Record<string, number>, n = 3): string {
  return Object.entries(metrics).slice(0, n).map(([k, v]) => k + '=' + Number(v.toPrecision(4))).join(' ');
}

/* ---------- coding agent set-up (Claude Code) ---------- */
export const HOOK_COMMAND = 'python3 "$CLAUDE_PROJECT_DIR/.lemmata/hooks/log_run.py"';
const HOOK_EVENTS = ['PreToolUse', 'PostToolUse', 'PostToolUseFailure'];
/** Add the Lemmata hook to a Claude Code settings object without touching anything else. Idempotent. */
export function mergeHookSettings(existing: unknown): { settings: Record<string, unknown>; changed: boolean } {
  const settings: Record<string, any> = existing && typeof existing === 'object' && !Array.isArray(existing) ? JSON.parse(JSON.stringify(existing)) : {};
  if (!settings.hooks || typeof settings.hooks !== 'object' || Array.isArray(settings.hooks)) settings.hooks = {};
  let changed = false;
  for (const ev of HOOK_EVENTS) {
    const groups: any[] = Array.isArray(settings.hooks[ev]) ? settings.hooks[ev] : (settings.hooks[ev] = []);
    const has = groups.some(g => g && Array.isArray(g.hooks) && g.hooks.some((h: any) => h && typeof h.command === 'string' && h.command.includes('.lemmata/hooks/log_run.py')));
    if (!has) { groups.push({ matcher: 'Bash', hooks: [{ type: 'command', command: HOOK_COMMAND, timeout: 20 }] }); changed = true; }
  }
  return { settings, changed };
}

export const AGENT_RULES_BEGIN = '<!-- lemmata:begin -->';
export const AGENT_RULES_END = '<!-- lemmata:end -->';
export const AGENT_RULES = [AGENT_RULES_BEGIN, '## Lemmata',
  '- Experiments you run are logged by a hook into `.lemmata/runs/`. Do not edit or delete those files.',
  '- When asked about past results ("which run produced this number?", "what did we run last week?"), use the Lemmata `runs` and `experiments` tools. Do not guess from memory or old logs.',
  '- Before editing method or evaluation code, check the Lemmata `alarms` and `node` tools and say which tables, figures and claims depend on it.',
  '- Never type a result into the paper by hand without naming the run it came from.',
  '- You may propose (project map, confounds). The researcher confirms.', AGENT_RULES_END].join('\n');
/** Insert or refresh the Lemmata section of a CLAUDE.md. Text outside the markers is kept as it is. */
export function mergeAgentRules(existing: string): string {
  const a = existing.indexOf(AGENT_RULES_BEGIN), b = existing.indexOf(AGENT_RULES_END);
  if (a >= 0 && b > a) return existing.slice(0, a) + AGENT_RULES + existing.slice(b + AGENT_RULES_END.length);
  return (existing.trimEnd() ? existing.trimEnd() + '\n\n' : '') + AGENT_RULES + '\n';
}
