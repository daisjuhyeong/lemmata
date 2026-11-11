// Run capture: log the experiments that never reach GitHub, where they happen.
//   1. the integrated terminal (shell integration tells us each command, its folder and exit code);
//   2. a watcher on the results folders (catches tmux / sbatch / overnight jobs the terminal never sees end);
//   3. manifests written by the coding agent's hook (.lemmata/hooks/log_run.py).
// All three write one format, <repo>/.lemmata/runs/<run_id>.json, and this module sends new or changed manifests to the hub.
import * as vscode from 'vscode';
import * as fs from 'fs/promises';
import * as os from 'os';
import * as path from 'path';
import { execFile } from 'child_process';
import { HubClient, HubError } from './core/client';
import { oneLine } from './core/text';
import { AGENT_RULES_BEGIN, DEFAULT_COMMAND_PATTERN, DEFAULT_METRIC_FILES, DEFAULT_RESULT_GLOBS, RunManifest, RunWindow, addArtifact, asManifest, configArgs,
  experimentPart, isMetricFile, isoLocal, mergeAgentRules, mergeHookSettings, metricsLine, parseMetrics, pickRun, runId, sameRun, sha256 } from './core/runs';

export interface RunHost {
  log(msg: string): void;
  /** The hub client and project for a workspace folder that is a project's code repository, or null. */
  projectFor(folderKey: string): { client: HubClient; pid: string } | null;
  serverBase(): string;
}

interface Entry { man: RunManifest; folder: string; root: string; file: string; digest: string }
const MAX_FILE = 512 * 1024, MAX_PATCH = 2 * 1024 * 1024, KEEP = 300, STALE_RUN_MS = 7 * 24 * 3600 * 1000;
const SYNCED_KEY = 'lemmata.runs.synced';

function git(cwd: string, args: string[], maxBuffer = 4 * 1024 * 1024): Promise<Buffer | null> {
  return new Promise(resolve => {
    execFile('git', args, { cwd, timeout: 8000, windowsHide: true, encoding: 'buffer', maxBuffer }, (err, stdout) => resolve(err ? null : stdout as Buffer));
  });
}

export class RunCapture implements vscode.TreeDataProvider<Entry> {
  private readonly entries = new Map<string, Entry>();            // run_id -> entry
  private readonly open = new Map<vscode.TerminalShellExecution, string>();   // execution -> run_id
  private readonly roots = new Map<string, string>();             // folder key -> repository root (fs path)
  private readonly fileTimers = new Map<string, ReturnType<typeof setTimeout>>();
  private syncTimer: ReturnType<typeof setTimeout> | undefined;
  private retryTimer: ReturnType<typeof setInterval> | undefined;
  private syncing = false;
  private readonly changed = new vscode.EventEmitter<Entry | undefined>();
  readonly onDidChangeTreeData = this.changed.event;
  private readonly bar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 49);

  constructor(private readonly ctx: vscode.ExtensionContext, private readonly host: RunHost) {
    this.bar.command = 'lemmata.runs.show';
    ctx.subscriptions.push(this.changed, this.bar);
  }

  private cfg() { return vscode.workspace.getConfiguration('lemmata.runs'); }
  private enabled(): boolean { return this.cfg().get<boolean>('capture', true); }
  private list<T>(key: string, fallback: T[]): T[] { const v = this.cfg().get<T[]>(key); return Array.isArray(v) && v.length ? v : fallback; }

  async start() {
    const w = vscode.workspace.createFileSystemWatcher('**/*.{json,jsonl,csv,tsv}');
    this.ctx.subscriptions.push(w,
      w.onDidCreate(u => this.onFile(u)), w.onDidChange(u => this.onFile(u)),
      w.onDidDelete(u => { if (/[\\/]\.lemmata[\\/]runs[\\/][^\\/]+\.json$/.test(u.fsPath)) void this.reload(); }),
      vscode.window.onDidStartTerminalShellExecution(e => { void this.onStart(e); }),
      vscode.window.onDidEndTerminalShellExecution(e => { void this.onEnd(e); }),
      vscode.workspace.onDidChangeWorkspaceFolders(() => { this.roots.clear(); void this.reload(); }),
      { dispose: () => { if (this.syncTimer) clearTimeout(this.syncTimer); if (this.retryTimer) clearInterval(this.retryTimer); for (const t of this.fileTimers.values()) clearTimeout(t); } });
    this.retryTimer = setInterval(() => this.syncSoon(0), 60000);
    await this.reload();
    this.syncSoon();
  }

  /* ---------- folders ---------- */
  private async rootOf(folder: vscode.WorkspaceFolder): Promise<string> {
    const key = folder.uri.toString();
    let r = this.roots.get(key);
    if (!r) {
      const top = await git(folder.uri.fsPath, ['rev-parse', '--show-toplevel']);
      r = top ? top.toString('utf8').trim() || folder.uri.fsPath : folder.uri.fsPath;
      this.roots.set(key, r);
    }
    return r;
  }
  private folderOf(fsPath: string): vscode.WorkspaceFolder | undefined {
    const f = vscode.workspace.getWorkspaceFolder(vscode.Uri.file(fsPath));
    return f && f.uri.scheme === 'file' ? f : undefined;
  }
  private rel(root: string, fsPath: string): string | null {
    const r = path.relative(root, fsPath);
    return !r || r.startsWith('..') || path.isAbsolute(r) ? null : r.split(path.sep).join('/');
  }

  /* ---------- the local store ---------- */
  private async reload() {
    const seen = new Set<string>();
    for (const folder of vscode.workspace.workspaceFolders || []) {
      if (folder.uri.scheme !== 'file') continue;
      const root = await this.rootOf(folder);
      const dir = path.join(root, '.lemmata', 'runs');
      let names: string[] = [];
      try { names = (await fs.readdir(dir)).filter(n => n.endsWith('.json') && !n.startsWith('.')).sort().slice(-KEEP); } catch { /* no runs yet */ }
      for (const n of names) {
        const file = path.join(dir, n);
        try {
          const text = await fs.readFile(file, 'utf8');
          const man = asManifest(JSON.parse(text));
          if (!man || man.run_id + '.json' !== n) continue;
          seen.add(man.run_id);
          this.entries.set(man.run_id, { man, folder: folder.uri.toString(), root, file, digest: sha256(JSON.stringify(man)) });
        } catch { /* half-written or not ours */ }
      }
    }
    for (const id of [...this.entries.keys()]) if (!seen.has(id)) this.entries.delete(id);
    this.render();
  }

  private async save(man: RunManifest, folder: string, root: string) {
    const dir = path.join(root, '.lemmata', 'runs');
    await fs.mkdir(dir, { recursive: true });
    const ignore = path.join(root, '.lemmata', '.gitignore');
    try { await fs.access(ignore); } catch { await fs.writeFile(ignore, '*\n', 'utf8'); }     // run logs stay out of git unless you decide otherwise
    const file = path.join(dir, man.run_id + '.json');
    const tmp = path.join(dir, '.' + man.run_id + '.tmp');
    await fs.writeFile(tmp, JSON.stringify(man, null, 1), 'utf8');
    await fs.rename(tmp, file);
    this.entries.set(man.run_id, { man, folder, root, file, digest: sha256(JSON.stringify(man)) });
    this.render();
    this.syncSoon();
  }

  /* ---------- 1. terminal ---------- */
  private async onStart(e: vscode.TerminalShellExecutionStartEvent) {
    try {
      if (!this.enabled()) return;
      const cmd = e.execution.commandLine.value;
      const part = experimentPart(cmd, String(this.cfg().get('commandPattern', '') || DEFAULT_COMMAND_PATTERN));
      const cwdUri = e.execution.cwd || e.shellIntegration.cwd;
      if (!part || !cwdUri || cwdUri.scheme !== 'file') return;
      const folder = this.folderOf(cwdUri.fsPath);
      if (!folder) return;       // a command outside the workspace is not this project's experiment
      const started = new Date();
      const id = runId(started, cmd, cwdUri.fsPath);
      this.open.set(e.execution, id);
      const root = await this.rootOf(folder);
      const man: RunManifest = { run_id: id, source: 'terminal', command: cmd.slice(0, 2000), cwd: cwdUri.fsPath, host: os.hostname().slice(0, 100),
        ...(await this.gitState(root)), configs: await this.configs(part, cwdUri.fsPath, root), metrics: {}, artifacts: [],
        started: isoLocal(started), ended: null, exit_code: null };
      if ([...this.entries.values()].some(x => x.man.source === 'agent' && sameRun(x.man, man))) { this.open.delete(e.execution); return; }   // the hook already has it
      await this.save(man, folder.uri.toString(), root);      // onEnd waits for this entry when the command ends while git is still being read
    } catch (err) { this.host.log('run capture (start) failed: ' + (err instanceof Error ? err.message : String(err))); }
  }

  private async onEnd(e: vscode.TerminalShellExecutionEndEvent) {
    try {
      const id = this.open.get(e.execution);
      if (!id) return;
      this.open.delete(e.execution);
      const ended = isoLocal(new Date());
      let entry = this.entries.get(id);
      for (let i = 0; !entry && i < 20; i++) { await new Promise(r => setTimeout(r, 250)); entry = this.entries.get(id); }   // onStart still reading git
      if (!entry) return;
      await this.save({ ...entry.man, ended, exit_code: typeof e.exitCode === 'number' ? e.exitCode : null }, entry.folder, entry.root);
    } catch (err) { this.host.log('run capture (end) failed: ' + (err instanceof Error ? err.message : String(err))); }
  }

  private async gitState(root: string): Promise<Pick<RunManifest, 'git_sha' | 'dirty' | 'diff_hash'>> {
    const head = await git(root, ['rev-parse', 'HEAD']);
    const status = await git(root, ['status', '--porcelain', '--untracked-files=no']);
    const dirty = status ? status.toString('utf8').trim().length > 0 : null;
    let diff_hash: string | null = null;
    if (dirty) {
      const patch = await git(root, ['diff', 'HEAD'], 16 * 1024 * 1024);
      if (patch && patch.length) {
        diff_hash = sha256(patch);
        if (patch.length <= MAX_PATCH) {      // kept on this machine only, so the run can be reproduced later
          const dir = path.join(root, '.lemmata', 'patches');
          await fs.mkdir(dir, { recursive: true });
          await fs.writeFile(path.join(dir, diff_hash.slice(7, 23) + '.patch'), patch);
        }
      }
    }
    const sha = head ? head.toString('utf8').trim() : '';
    return { git_sha: /^[0-9a-f]{7,64}$/.test(sha) ? sha : null, dirty, diff_hash };
  }

  private async configs(part: string, cwd: string, root: string) {
    const out: { path: string; hash: string | null }[] = [];
    for (const a of configArgs(part)) {
      const abs = path.resolve(cwd, a);
      const rel = this.rel(root, abs);
      if (!rel) continue;
      try {
        const st = await fs.stat(abs);
        if (st.isFile() && st.size <= MAX_PATCH) out.push({ path: rel, hash: sha256(await fs.readFile(abs)) });
      } catch { /* an output path or a file that does not exist yet */ }
    }
    return out;
  }

  /* ---------- 2. results watcher (and 3. hook manifests) ---------- */
  private onFile(uri: vscode.Uri) {
    if (uri.scheme !== 'file') return;
    const p = uri.fsPath;
    if (/[\\/]\.lemmata[\\/]runs[\\/][^\\/.][^\\/]*\.json$/.test(p)) {       // written by the agent's hook (or by us)
      const id = path.basename(p, '.json');
      const known = this.entries.get(id);
      const t = this.fileTimers.get(p);
      if (t) clearTimeout(t);
      this.fileTimers.set(p, setTimeout(() => { this.fileTimers.delete(p); void (async () => {
        try { if (known && sha256(JSON.stringify(asManifest(JSON.parse(await fs.readFile(p, 'utf8'))))) === known.digest) return; } catch { /* reload decides */ }
        await this.reload(); this.syncSoon();
      })(); }, 400));
      return;
    }
    if (!this.enabled() || /[\\/](\.lemmata|\.git|node_modules)[\\/]/.test(p)) return;
    const t = this.fileTimers.get(p);
    if (t) clearTimeout(t);
    this.fileTimers.set(p, setTimeout(() => { this.fileTimers.delete(p); void this.onResult(p); }, 1500));    // wait until the file stops changing
  }

  private windows(folder: string, now: number): RunWindow[] {
    const out: RunWindow[] = [];
    for (const e of this.entries.values()) {
      if (e.folder !== folder || e.man.source === 'watcher') continue;
      const s = Date.parse(e.man.started || '');
      if (!Number.isFinite(s)) continue;
      const end = e.man.ended ? Date.parse(e.man.ended) : (now - s > STALE_RUN_MS ? s : null);     // a run with no end after a week is not running
      out.push({ run_id: e.man.run_id, startedMs: s, endedMs: end !== null && Number.isFinite(end) ? end : null });
    }
    return out;
  }

  private async onResult(fsPath: string) {
    try {
      const folder = this.folderOf(fsPath);
      if (!folder) return;
      const root = await this.rootOf(folder);
      const rel = this.rel(root, fsPath);
      if (!rel || !isMetricFile(rel, this.list('resultFolders', DEFAULT_RESULT_GLOBS), this.list('metricFiles', DEFAULT_METRIC_FILES))) return;
      const st = await fs.stat(fsPath);
      if (!st.isFile() || st.size > MAX_FILE || st.size === 0) return;
      // a file that is identical to the committed version arrived by git (pull, checkout), not from a run
      const tracked = await git(root, ['ls-files', '--error-unmatch', '--', rel]);
      if (tracked) { const s = await git(root, ['status', '--porcelain', '--', rel]); if (s && !s.toString('utf8').trim()) return; }
      const data = await fs.readFile(fsPath);
      const metrics = parseMetrics(rel, data.toString('utf8'));
      const hash = sha256(data);
      const key = folder.uri.toString();
      const id = pickRun(st.mtimeMs, this.windows(key, Date.now()));
      const owner = id ? this.entries.get(id) : undefined;
      if (owner) {
        if (owner.man.artifacts.some(a => a.path === rel && a.hash === hash)) return;
        await this.save(addArtifact(owner.man, rel, hash, metrics), key, owner.root);
        return;
      }
      // No run in the terminal explains this file: a detached job (tmux, sbatch, cron). One watcher entry per file and commit.
      const state = await this.gitState(root);
      const prev = [...this.entries.values()].find(e => e.folder === key && e.man.source === 'watcher' && e.man.artifacts[0] && e.man.artifacts[0].path === rel
        && e.man.git_sha === state.git_sha && e.man.diff_hash === state.diff_hash);
      if (prev) {
        if (prev.man.artifacts[0].hash === hash) return;
        await this.save({ ...addArtifact({ ...prev.man, metrics: {} }, rel, hash, metrics), ended: isoLocal(new Date(st.mtimeMs)) }, key, root);
        return;
      }
      const when = new Date(st.mtimeMs);
      const man: RunManifest = { run_id: runId(when, 'watcher:' + rel, root), source: 'watcher', command: null, cwd: root, host: os.hostname().slice(0, 100), ...state,
        configs: [], metrics, artifacts: [{ path: rel, hash }], started: null, ended: isoLocal(when), exit_code: null,
        note: 'Seen by the results watcher: the command was not run in this editor\'s terminal.' };
      await this.save(man, key, root);
    } catch (err) { this.host.log('run capture (results) failed: ' + (err instanceof Error ? err.message : String(err))); }
  }

  /* ---------- sync to the hub ---------- */
  private synced(): Record<string, string> { return this.ctx.workspaceState.get<Record<string, string>>(SYNCED_KEY, {}); }
  pending(): Entry[] { const s = this.synced(); return [...this.entries.values()].filter(e => s[e.man.run_id] !== e.digest); }
  syncSoon(ms = 2000) {
    if (this.syncTimer) clearTimeout(this.syncTimer);
    this.syncTimer = setTimeout(() => { void this.sync(); }, ms);
  }
  async sync(): Promise<{ sent: number; waiting: number; reason?: string }> {
    if (this.syncing) return { sent: 0, waiting: this.pending().length, reason: 'a sync is already running' };
    this.syncing = true;
    let sent = 0, reason: string | undefined;
    try {
      const byFolder = new Map<string, Entry[]>();
      for (const e of this.pending()) byFolder.set(e.folder, (byFolder.get(e.folder) || []).concat([e]));
      for (const [folder, list] of byFolder) {
        const target = this.host.projectFor(folder);
        if (!target) { reason = 'this folder is not the code repository of a hub project (or you are not connected)'; continue; }
        list.sort((a, b) => a.man.run_id.localeCompare(b.man.run_id));
        let batch: Entry[] = [], size = 0;
        const flush = async () => {
          if (!batch.length) return;
          await target.client.postRuns(target.pid, batch.map(b => b.man));
          const s = { ...this.synced() };
          for (const b of batch) s[b.man.run_id] = b.digest;
          const keys = Object.keys(s).sort();
          for (const k of keys.slice(0, Math.max(0, keys.length - 2000))) delete s[k];
          await this.ctx.workspaceState.update(SYNCED_KEY, s);
          sent += batch.length; batch = []; size = 0;
        };
        try {
          for (const e of list) {
            const n = JSON.stringify(e.man).length;
            if (batch.length >= 20 || size + n > 40000) await flush();
            batch.push(e); size += n;
          }
          await flush();
        } catch (err) {
          reason = err instanceof HubError ? (err.offline ? 'the hub cannot be reached from this machine' : err.message) : String(err);
          this.host.log('run sync failed: ' + (err instanceof HubError ? 'HTTP ' + err.status + ' ' + err.code : 'error'));
        }
      }
    } finally { this.syncing = false; }
    this.render();
    return { sent, waiting: this.pending().length, reason };
  }

  /* ---------- panel and status bar ---------- */
  private render() {
    const today = isoLocal(new Date()).slice(0, 10);
    const all = [...this.entries.values()];
    const n = all.filter(e => (e.man.started || e.man.ended || '').slice(0, 10) === today).length;
    const waiting = this.pending().length;
    this.bar.text = '$(beaker) ' + n + (waiting ? ' $(cloud-upload) ' + waiting : '');
    this.bar.tooltip = 'Lemmata runs: ' + n + ' logged today' + (waiting ? ', ' + waiting + ' waiting to be sent to the hub' : ', all sent to the hub') + '. Click to open the list.';
    if (all.length || !this.enabled()) this.bar.show(); else this.bar.hide();
    void vscode.commands.executeCommand('setContext', 'lemmata.hasRuns', all.length > 0);
    this.changed.fire(undefined);
  }
  getChildren(e?: Entry): Entry[] {
    if (e) return [];
    return [...this.entries.values()].sort((a, b) => b.man.run_id.localeCompare(a.man.run_id)).slice(0, 100);
  }
  getTreeItem(e: Entry): vscode.TreeItem {
    const m = e.man;
    const running = m.source !== 'watcher' && !m.ended;
    const waiting = this.synced()[m.run_id] !== e.digest;
    const it = new vscode.TreeItem(oneLine(m.command || 'Results watcher: ' + (m.artifacts[0] ? m.artifacts[0].path : ''), 80));
    it.iconPath = new vscode.ThemeIcon(running ? 'sync' : m.exit_code ? 'error' : m.source === 'agent' ? 'hubot' : m.source === 'watcher' ? 'eye' : 'pass');
    const when = (m.started || m.ended || '').slice(5, 16).replace('T', ' ');
    it.description = [when, (m.git_sha || 'no commit').slice(0, 7) + (m.dirty ? '+changes' : ''), metricsLine(m.metrics), running ? 'running' : m.exit_code ? 'exit ' + m.exit_code : '',
      waiting ? 'not sent yet' : ''].filter(Boolean).join(' · ');
    it.tooltip = [oneLine(m.command || '(command not seen)', 400), 'Source: ' + m.source + (m.host ? ' on ' + oneLine(m.host, 60) : ''),
      'Commit: ' + (m.git_sha || 'unknown') + (m.dirty ? ' with uncommitted changes' + (m.diff_hash ? ' (patch kept in .lemmata/patches)' : '') : ''),
      m.configs.length ? 'Settings: ' + m.configs.map(c => c.path).join(', ') : '', m.artifacts.length ? 'Wrote: ' + m.artifacts.map(a => a.path).slice(0, 8).join(', ') : '',
      Object.keys(m.metrics).length ? 'Numbers: ' + metricsLine(m.metrics, 12) : '', waiting ? 'Not sent to the hub yet.' : 'Sent to the hub.'].filter(Boolean).join('\n');
    it.contextValue = 'run';
    it.command = { command: 'lemmata.runs.open', title: 'Open the run record', arguments: [e] };
    return it;
  }

  /* ---------- commands ---------- */
  register() {
    const c = vscode.commands.registerCommand;
    this.ctx.subscriptions.push(
      vscode.window.createTreeView('lemmata.runs', { treeDataProvider: this }),
      c('lemmata.runs.show', () => vscode.commands.executeCommand('lemmata.runs.focus')),
      c('lemmata.runs.refresh', async () => { await this.reload(); this.syncSoon(0); }),
      c('lemmata.runs.open', async (e?: Entry) => { if (e) await vscode.window.showTextDocument(vscode.Uri.file(e.file), { preview: true }); }),
      c('lemmata.runs.sync', async () => {
        await this.reload();
        const r = await this.sync();
        if (r.waiting) void vscode.window.showWarningMessage('Lemmata: ' + r.sent + ' run' + (r.sent === 1 ? '' : 's') + ' sent, ' + r.waiting + ' still waiting' + (r.reason ? ': ' + oneLine(r.reason, 200) : '') + '.');
        else void vscode.window.showInformationMessage(r.sent ? 'Lemmata: ' + r.sent + ' run' + (r.sent === 1 ? '' : 's') + ' sent to the hub.' : 'Lemmata: every run is already on the hub.');
      }),
      c('lemmata.setupAgent', () => this.setupAgent()));
  }

  /** Install the Claude Code hook in one repository and show how to connect the hub's MCP server. Touches only files it names. */
  private async setupAgent() {
    const folders = (vscode.workspace.workspaceFolders || []).filter(f => f.uri.scheme === 'file');
    if (!folders.length) { void vscode.window.showInformationMessage('Lemmata: open your code repository as a folder first.'); return; }
    const folder = folders.length === 1 ? folders[0] : await vscode.window.showWorkspaceFolderPick({ placeHolder: 'Which repository does the coding agent work in?' });
    if (!folder || folder.uri.scheme !== 'file') return;
    const root = await this.rootOf(folder);
    const ok = await vscode.window.showInformationMessage('Set up the coding agent in ' + path.basename(root) + '?',
      { modal: true, detail: 'This writes two files in the repository:\n\n• .lemmata/hooks/log_run.py — logs the experiments Claude Code runs (git-ignored)\n• .claude/settings.local.json — registers that hook (your personal, uncommitted settings)\n\nNothing is sent anywhere by the hook. Existing settings are kept.' }, 'Set up');
    if (ok !== 'Set up') return;
    try {
      const hookDir = path.join(root, '.lemmata', 'hooks');
      await fs.mkdir(hookDir, { recursive: true });
      const ignore = path.join(root, '.lemmata', '.gitignore');
      try { await fs.access(ignore); } catch { await fs.writeFile(ignore, '*\n', 'utf8'); }
      await fs.copyFile(path.join(this.ctx.extensionPath, 'media', 'hooks', 'log_run.py'), path.join(hookDir, 'log_run.py'));
      const settingsFile = path.join(root, '.claude', 'settings.local.json');
      let existing: unknown = {};
      try { existing = JSON.parse(await fs.readFile(settingsFile, 'utf8')); }
      catch (err) { if ((err as NodeJS.ErrnoException).code !== 'ENOENT') throw new Error('.claude/settings.local.json is not valid JSON; fix it and run the command again'); }
      const merged = mergeHookSettings(existing);
      if (merged.changed) { await fs.mkdir(path.dirname(settingsFile), { recursive: true }); await fs.writeFile(settingsFile, JSON.stringify(merged.settings, null, 2) + '\n', 'utf8'); }
      const py = await new Promise<boolean>(res => execFile('python3', ['--version'], { timeout: 5000 }, err => res(!err)));
      if (!py) void vscode.window.showWarningMessage('Lemmata: python3 was not found on this machine. The hook needs Python 3.8 or newer on the PATH.');

      const mdFile = path.join(root, 'CLAUDE.md');
      let md = '';
      try { md = await fs.readFile(mdFile, 'utf8'); } catch { /* no CLAUDE.md yet */ }
      const rules = await vscode.window.showInformationMessage('Hook installed. Also add the Lemmata rules for the agent to CLAUDE.md?',
        { modal: true, detail: (md.includes(AGENT_RULES_BEGIN) ? 'The Lemmata section in CLAUDE.md will be refreshed.' : 'A short "## Lemmata" section will be added at the end of CLAUDE.md.') + ' This file is usually committed, so your co-authors will see it.' }, 'Add rules', 'Skip');
      if (rules === 'Add rules') await fs.writeFile(mdFile, mergeAgentRules(md), 'utf8');

      const base = this.host.serverBase() || 'http://<your-hub>:8765';
      const cmd = 'claude mcp add --scope user --transport http lemmata ' + base + '/mcp --header "Authorization: Bearer <token>"';
      const pick = await vscode.window.showInformationMessage('Last step: connect Claude Code to the hub (once per machine).',
        { modal: true, detail: 'Run this in a terminal, with a token from the hub in place of <token> (on the Mac mini: lemmata hub token --device "Claude Code"):\n\n' + cmd + '\n\nKeep --scope user so the token never lands in the repository.' }, 'Copy command');
      if (pick === 'Copy command') await vscode.env.clipboard.writeText(cmd);
    } catch (err) { void vscode.window.showErrorMessage('Lemmata: could not set up the coding agent: ' + (err instanceof Error ? err.message : String(err))); }
  }
}
