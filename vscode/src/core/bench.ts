// The bench (S35, ADR-011): VS Code shows runs, experiments, their setup and what to run next, and nothing else.
// The hub prepares every row (label, description, tooltip, icon, what can be done with it) in GET /p/<pid>/api/bench,
// because the hub updates itself and this extension does not. This file only checks those rows, adds the runs that
// exist on this machine, and works out the one status-bar line. No VS Code API here (unit-tested in test/unit/bench.test.ts).
import { clean, oneLine } from './text';
import { metricsLine } from './runs';

/** The newest bench document this extension knows how to draw. A hub that sends a higher number is newer than the extension. */
export const BENCH_VERSION = 1;

export interface Target { view: string; sel?: string }
export interface Row {
  id: string; label: string; description?: string; tooltip?: string; icon?: string; kids?: Row[]; expanded?: boolean;
  /** experiment id, run id, to-do kind */
  x?: string; run?: string; kind?: string;
  /** what can be done with the row */
  open?: { repo: string; path: string; line: number }; site?: Target; tab?: Target; copy?: { what: string; text: string }; snooze?: string;
  /** set by this extension for runs on this machine */
  file?: string; attach?: boolean; pid?: string;
}
export interface RunNote { x: string; name: string; how: string; fields: { [k: string]: string[] }; metric: string | null; line: string | null;
  prev: { id: string; t: string; sha: string | null; value: number } | null }
export interface Pick { id: string; label: string; description: string }
export interface Bench {
  version: number; today: string; project: string;
  runs: { [id: string]: RunNote }; elsewhere: Row[]; experiments: Row[]; to_run: Row[]; pick: Pick[];
  counts: { experiments: number; to_run: number; stale: number; runs_today: number; unattached: number; snoozed: number };
}

/* ---------- reading what the hub sent (untrusted text: capped, cleaned, never rendered as markdown) ---------- */
const ICON = /^[a-z][a-z0-9-]{0,40}$/;
const SEL = /^[qxic]:[^\s<>"'`\\\x00-\x1f\x7f]{1,300}$/;
const VIEW = /^[a-z]{2,20}$/;
const isObj = (v: unknown): v is { [k: string]: unknown } => !!v && typeof v === 'object' && !Array.isArray(v);
const str = (v: unknown, max: number): string | undefined => { const s = typeof v === 'string' ? clean(v, max) : ''; return s || undefined; };

function asTarget(v: unknown): Target | undefined {
  if (!isObj(v) || typeof v.view !== 'string' || !VIEW.test(v.view)) return undefined;
  return typeof v.sel === 'string' && SEL.test(v.sel) ? { view: v.view, sel: v.sel } : { view: v.view };
}

export function asRow(v: unknown, depth = 0): Row | null {
  if (!isObj(v) || depth > 5) return null;
  const id = str(v.id, 400), label = typeof v.label === 'string' ? oneLine(v.label, 160) : '';
  if (!id || !label) return null;
  const r: Row = { id, label };
  if (typeof v.description === 'string' && v.description) r.description = oneLine(v.description, 200);
  const tip = str(v.tooltip, 1600); if (tip) r.tooltip = tip;
  if (typeof v.icon === 'string' && ICON.test(v.icon)) r.icon = v.icon;
  if (v.expanded === true) r.expanded = true;
  for (const k of ['x', 'run', 'kind', 'snooze'] as const) { const s = str(v[k], 400); if (s && !/[\r\n]/.test(s)) r[k] = s; }
  if (isObj(v.open) && typeof v.open.repo === 'string' && typeof v.open.path === 'string' && /^[A-Za-z0-9_.-]{1,60}$/.test(v.open.repo)
    && v.open.path && v.open.path.length <= 1000 && !v.open.path.startsWith('/') && !v.open.path.split(/[\\/]/).includes('..') && !/[\0\r\n]/.test(v.open.path))
    r.open = { repo: v.open.repo, path: v.open.path, line: Math.max(1, Math.floor(Number(v.open.line)) || 1) };
  const site = asTarget(v.site); if (site) r.site = site;
  const tab = asTarget(v.tab); if (tab) r.tab = tab;
  if (isObj(v.copy) && typeof v.copy.text === 'string' && v.copy.text && v.copy.text.length <= 60000)
    r.copy = { what: oneLine(v.copy.what, 60) || 'the text', text: v.copy.text };
  if (Array.isArray(v.kids)) { const kids = v.kids.slice(0, 400).map(k => asRow(k, depth + 1)).filter((k): k is Row => !!k); if (kids.length) r.kids = kids; }
  return r;
}
const rows = (v: unknown): Row[] => (Array.isArray(v) ? v.slice(0, 400).map(x => asRow(x)).filter((x): x is Row => !!x) : []);
const count = (v: unknown): number => (typeof v === 'number' && Number.isFinite(v) && v >= 0 ? Math.floor(v) : 0);

export function asBench(v: unknown): Bench | null {
  if (!isObj(v) || typeof v.schema !== 'string' || !v.schema.startsWith('lemmata.bench/')) return null;
  const runs: { [id: string]: RunNote } = {};
  if (isObj(v.runs)) for (const [id, n] of Object.entries(v.runs).slice(0, 2000)) {
    if (!isObj(n) || typeof n.x !== 'string' || !n.x) continue;
    const fields: { [k: string]: string[] } = {};
    if (isObj(n.fields)) for (const [k, list] of Object.entries(n.fields).slice(0, 12)) if (Array.isArray(list)) fields[oneLine(k, 40)] = list.slice(0, 6).map(s => oneLine(s, 60));
    const p = isObj(n.prev) && typeof n.prev.id === 'string' && typeof n.prev.value === 'number'
      ? { id: n.prev.id, t: oneLine(n.prev.t, 40), sha: typeof n.prev.sha === 'string' ? oneLine(n.prev.sha, 12) : null, value: n.prev.value } : null;
    runs[id] = { x: n.x, name: oneLine(n.name, 120) || n.x, how: oneLine(n.how, 20), fields, metric: typeof n.metric === 'string' ? oneLine(n.metric, 80) : null,
      line: typeof n.line === 'string' && n.line ? oneLine(n.line, 160) : null, prev: p };
  }
  const c = isObj(v.counts) ? v.counts : {};
  const pick: Pick[] = Array.isArray(v.pick) ? v.pick.slice(0, 500).filter(isObj).filter(p => typeof p.id === 'string' && p.id)
    .map(p => ({ id: p.id as string, label: oneLine(p.label, 120) || (p.id as string), description: oneLine(p.description, 120) })) : [];
  return { version: count(v.version) || 1, today: oneLine(v.today, 10), project: oneLine(v.project, 80),
    runs, elsewhere: rows(v.elsewhere), experiments: rows(v.experiments), to_run: rows(v.to_run), pick,
    counts: { experiments: count(c.experiments), to_run: count(c.to_run), stale: count(c.stale), runs_today: count(c.runs_today), unattached: count(c.unattached), snoozed: count(c.snoozed) } };
}

/** What a row offers, as the text VS Code's menus test (view/item/context "when": viewItem =~ /-copy/). */
export function contextOf(r: Row): string {
  return 'row' + (r.open ? '-open' : '') + (r.site ? '-site' : '') + (r.tab ? '-tab' : '') + (r.copy ? '-copy' : '') + (r.snooze ? '-snooze' : '')
    + (r.attach ? '-attach' : '') + (r.file ? '-record' : '');
}
/** What a click on the row does: the first thing it can do, in this order. */
export function clickOf(r: Row): 'record' | 'open' | 'tab' | null {
  return r.file ? 'record' : r.open ? 'open' : r.tab && !(r.kids && r.kids.length) ? 'tab' : null;
}

/* ---------- the runs on this machine ---------- */
export interface LocalRun {
  id: string; command: string | null; source: string; host: string | null; started: string | null; ended: string | null; exit: number | null;
  sha: string | null; dirty: boolean | null; patch: boolean; metrics: { [k: string]: number }; artifacts: string[]; configs: string[];
  /** has the hub received this exact record; the record's file on this machine; the hub project of its folder, when there is one */
  sent: boolean; file: string; pid: string | null;
}
const WEEK = 7 * 24 * 3600 * 1000;
export const whenOf = (r: LocalRun): string => r.started || r.ended || '';
export function isRunning(r: LocalRun, nowMs: number): boolean {
  if (r.source === 'watcher' || r.ended) return false;
  const s = Date.parse(r.started || '');
  return Number.isFinite(s) && nowMs - s < WEEK;      // a run with no end after a week is not running
}
/** Did it do something an experiment does: write a file, report a number, or fail? (The hub uses the same rule.) */
export const isExperiment = (r: LocalRun): boolean => r.artifacts.length > 0 || Object.keys(r.metrics).length > 0 || (r.exit !== null && r.exit !== 0);
const clock = (t: string, today: string): string => (t.slice(0, 10) === today ? t.slice(11, 16) : t.slice(5, 16).replace('T', ' '));

export function localRow(r: LocalRun, note: RunNote | undefined, today: string, nowMs: number): Row {
  const running = isRunning(r, nowMs), failed = r.exit !== null && r.exit !== 0;
  const numbers = (note && note.line) || metricsLine(r.metrics);
  const row: Row = {
    id: r.id, run: r.id, file: r.file,
    label: oneLine(r.command || 'Results watcher: ' + (r.artifacts[0] || ''), 80) || 'run',
    description: [clock(whenOf(r), today), note ? note.name : '', numbers, (r.sha || 'no commit').slice(0, 7) + (r.dirty ? '+changes' : ''),
      running ? 'running' : failed ? 'exit ' + r.exit : '', r.sent ? '' : 'not sent yet'].filter(Boolean).join(' · '),
    icon: running ? 'sync~spin' : failed ? 'error' : r.source === 'agent' ? 'hubot' : r.source === 'watcher' ? 'eye' : 'pass',
    tooltip: [oneLine(r.command || '(command not seen)', 400), 'Source: ' + r.source + (r.host ? ' on ' + oneLine(r.host, 60) : ''),
      'Commit: ' + (r.sha || 'unknown') + (r.dirty ? ' with uncommitted changes' + (r.patch ? ' (patch kept in .lemmata/patches)' : '') : ''),
      r.configs.length ? 'Settings: ' + r.configs.join(', ') : '', r.artifacts.length ? 'Wrote: ' + r.artifacts.slice(0, 8).join(', ') : '',
      Object.keys(r.metrics).length ? 'Numbers: ' + metricsLine(r.metrics, 12) : '',
      note ? 'Experiment: ' + note.name + (note.how === 'attached' ? ' (attached by you)' : note.how === 'wrote' ? ' (it wrote this experiment\'s result files)' : '') : '',
      note && note.prev ? 'Compared with the run of ' + note.prev.t.slice(0, 16).replace('T', ' ') + (note.prev.sha ? ' at ' + note.prev.sha : '') + ': same experiment, same dataset, method and seed.' : '',
      r.sent ? 'Sent to the hub.' : 'Not sent to the hub yet.'].filter(Boolean).join('\n'),
  };
  if (r.pid) { row.pid = r.pid; if (r.sent && isExperiment(r)) row.attach = true; }
  if (note) row.x = note.x;
  return row;
}

export interface NowInput { local: LocalRun[]; note: (id: string) => RunNote | undefined; elsewhere: Row[]; today: string; nowMs: number; hubKnows: boolean }
/**
 * The "Now" list: every run on this machine in exactly one group, in the order the questions come up.
 * Was my run captured and sent? What is running? What failed? What belongs to no experiment? What finished?
 */
export function nowRows(i: NowInput): Row[] {
  const sorted = [...i.local].sort((a, b) => b.id.localeCompare(a.id));
  const g: { [k: string]: Row[] } = { running: [], unsent: [], failed: [], loose: [], done: [], earlier: [] };
  for (const r of sorted) {
    const note = i.note(r.id), row = localRow(r, note, i.today, i.nowMs), today = whenOf(r).slice(0, 10) === i.today || (r.ended || '').slice(0, 10) === i.today;
    if (isRunning(r, i.nowMs)) g.running.push(row);
    else if (!r.sent) g.unsent.push(row);
    else if (!today) { if (g.earlier.length < 40) g.earlier.push(row); }
    else if (r.exit !== null && r.exit !== 0) g.failed.push(row);
    else if (i.hubKnows && r.pid && isExperiment(r) && !note) g.loose.push(row);
    else g.done.push(row);
  }
  const mine = new Set(i.local.map(r => r.id));
  const other = i.elsewhere.filter(r => !mine.has(r.run || r.id));
  const out: Row[] = [];
  const add = (id: string, label: string, kids: Row[], icon: string, tooltip: string, expanded = true) => {
    if (kids.length) out.push({ id: 'g|' + id, label, description: String(kids.length), icon, tooltip, kids, expanded });
  };
  add('running', 'Running', g.running, 'sync', 'Started in this editor\'s terminal or by the coding agent, and not ended yet.');
  add('unsent', 'Not sent to the hub', g.unsent, 'cloud-upload', 'These run records are only on this machine. They are retried every minute; "Send runs to the hub now" says why they wait.');
  add('failed', 'Failed today', g.failed, 'error', 'Ended with an error code today.');
  add('loose', 'Not attached to an experiment', g.loose, 'question', 'These runs wrote files or numbers that match no experiment\'s result files. Right-click a run to attach it.');
  add('done', 'Finished today', g.done, 'pass', 'Ended today and sent to the hub.');
  add('elsewhere', 'On other machines today', other, 'remote', 'Runs the hub received today from another machine or window.', false);
  add('earlier', 'Earlier', g.earlier, 'history', 'The most recent runs before today that are on this machine.', false);
  return out;
}

/* ---------- the one status-bar line ---------- */
export type Conn = 'unconfigured' | 'offline' | 'unauthorized' | 'ok';
export interface BarInput { conn: Conn; server: string; projects: number; running: number; unsent: number; toRun: number; flash: string | null }
export interface Bar { text: string; tooltip: string; warn: boolean; command: string }
const plural = (n: number, w: string) => n + ' ' + w;
export function barOf(i: BarInput): Bar {
  if (i.conn === 'unconfigured') return { text: 'Lemmata: connect', tooltip: 'Click to connect to your Lemmata server.', warn: false, command: 'lemmata.connect' };
  if (i.conn === 'unauthorized') return { text: 'Lemmata: token rejected', tooltip: 'The server did not accept the token. Click to connect again.', warn: true, command: 'lemmata.connect' };
  const local = [i.running ? plural(i.running, 'running') : '', i.unsent ? plural(i.unsent, 'not sent') : ''].filter(Boolean);
  if (i.conn === 'offline') return { text: '$(beaker) ' + ['offline'].concat(local).join(' · '), tooltip: 'Cannot reach ' + i.server + '. Runs are still logged on this machine and sent when the hub is back. Click to open Lemmata.',
    warn: true, command: 'lemmata.showPanel' };
  if (!i.projects) return { text: 'Lemmata: no project', tooltip: 'No Lemmata project matches this repository yet. Click to add it.', warn: false, command: 'lemmata.addProject' };
  if (i.flash) return { text: '$(beaker) ' + i.flash, tooltip: 'A run just ended. Click to open the list of runs.', warn: false, command: 'lemmata.showPanel' };
  const parts = local.concat(i.toRun ? [plural(i.toRun, 'to run')] : []);
  return { text: '$(beaker) ' + (parts.join(' · ') || 'Lemmata'),
    tooltip: ['Lemmata', i.running ? plural(i.running, 'run') + ' going' : 'nothing running', i.unsent ? plural(i.unsent, 'run record') + ' waiting to be sent to the hub' : 'every run is on the hub',
      i.toRun ? plural(i.toRun, 'thing') + ' to run next' : ''].filter(Boolean).join(' · ') + '. Click to open the lists.',
    warn: false, command: 'lemmata.showPanel' };
}

/** The line shown for a few minutes when a run ends: its number next to the last comparable one, never a verdict. */
export function flashOf(r: LocalRun, note: RunNote | undefined): string {
  const what = note ? note.name : oneLine(r.command || r.artifacts[0] || 'run', 40);
  if (r.exit !== null && r.exit !== 0) return 'failed (exit ' + r.exit + ') · ' + what;
  const numbers = (note && note.line) || metricsLine(r.metrics, 2);
  return (numbers || 'finished') + ' · ' + what;
}

/* ---------- small things ---------- */
/** Is version a newer than b? ("0.8.1" vs "0.8.0"); anything that is not three numbers is never newer. */
export function newer(a: unknown, b: unknown): boolean {
  const p = (v: unknown) => (typeof v === 'string' && /^\d{1,5}\.\d{1,5}\.\d{1,5}$/.test(v) ? v.split('.').map(Number) : null);
  const x = p(a), y = p(b);
  if (!x || !y) return false;
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] > y[i];
  return false;
}
/** The website address of a page, with something selected: <hub>/p/<project>/#go=<page>&sel=<…> (web/app.js goFromLink reads it). */
export function siteUrl(base: string, pid: string, t?: Target): string {
  const root = base.replace(/\/+$/, '') + '/p/' + encodeURIComponent(pid) + '/';
  if (!t || !VIEW.test(t.view)) return root;
  return root + '#go=' + t.view + (t.sel && SEL.test(t.sel) ? '&sel=' + encodeURIComponent(t.sel) : '');
}
/** today + days, as YYYY-MM-DD (calendar arithmetic on the date the hub gave, not on this machine's clock). */
export function dayPlus(today: string, days: number): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(today);
  const d = m ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])) : new Date();
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
/** The pages that open inside VS Code's tab; every other page opens on the website. */
export const BENCH_VIEWS = ['experiments', 'setup'] as const;
export const isBenchView = (v: unknown): v is typeof BENCH_VIEWS[number] => typeof v === 'string' && (BENCH_VIEWS as readonly string[]).includes(v);
