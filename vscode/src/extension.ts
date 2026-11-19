// Lemmata in VS Code: the experiment bench (S35, ADR-011).
// The website is where you read, decide and write. VS Code is where experiments run, so this extension shows runs,
// experiments, their setup and what to run next, in VS Code's own lists and status bar, and sends everything else to the website.
// The hub prepares the rows (GET /p/<pid>/api/bench); this file draws them and adds the runs made on this machine.
import * as vscode from 'vscode';
import * as fs from 'fs/promises';
import * as os from 'os';
import * as path from 'path';
import { execFile } from 'child_process';
import { HubClient, HubError } from './core/client';
import { Binding, FolderRemotes, matchProjects, parseGitConfigRemotes, unmatchedRepos } from './core/remotes';
import { mapPath } from './core/mapping';
import { isPrivateHost, normalizeServerUrl } from './core/url';
import { oneLine } from './core/text';
import { DEFAULT_URL, TOKEN_PREFIX, serverFromInspect, tokenFor, tokenKey } from './core/settings';
import { HubProject } from './core/types';
import { RunCapture } from './runs';
import { LemmataTab } from './tab';
import { View } from './core/embed';
import { parseOpenLink } from './core/link';
import { isoLocal } from './core/runs';
import { BENCH_VERSION, Bench, Conn, LocalRun, Row, RunNote, Target, asBench, barOf, clickOf, contextOf, dayPlus, flashOf, isBenchView, isRunning, newer, nowRows, siteUrl } from './core/bench';

interface Bound { binding: Binding; bench: Bench | null; error: string | null }
/** One line in one of the three lists: a row from the hub (or a run on this machine) and the project it belongs to. */
interface Node { row: Row; pid: string | null; path?: string }
type ViewId = 'now' | 'experiments' | 'torun';
const FLASH_MS = 5 * 60 * 1000, EXT_CHECK_MS = 6 * 3600 * 1000;
const VSIX_PATH = '/api/hub/extension.vsix', SKIP_KEY = 'lemmata.update.skipped';
const OLD_HUB = 'Your hub is older than this extension. Update the hub (on the Mac mini: lemmata hub update) to see experiments here.';

class RowTree implements vscode.TreeDataProvider<Node> {
  private readonly changed = new vscode.EventEmitter<Node | undefined>();
  readonly onDidChangeTreeData = this.changed.event;
  constructor(private readonly view: ViewId, private readonly roots: () => Node[]) { }
  refresh() { this.changed.fire(undefined); }
  dispose() { this.changed.dispose(); }
  /** A row's place in the list, not its id alone: the same experiment can stand under two claims, and VS Code needs every line to have its own id. */
  getChildren(n?: Node): Node[] {
    const list: Node[] = n ? (n.row.kids || []).map(k => ({ row: k, pid: k.pid || n.pid })) : this.roots();
    const seen = new Map<string, number>(), base = n ? (n.path || n.row.id) + '\n' : this.view + '\n';
    for (const k of list) {
      const i = seen.get(k.row.id) || 0;
      seen.set(k.row.id, i + 1);
      k.path = base + (k.pid || '') + '\n' + k.row.id + (i ? '\n#' + i : '');
    }
    return list;
  }
  getTreeItem(n: Node): vscode.TreeItem {
    const r = n.row, kids = !!(r.kids && r.kids.length), C = vscode.TreeItemCollapsibleState;
    const it = new vscode.TreeItem(r.label, kids ? (r.expanded ? C.Expanded : C.Collapsed) : C.None);
    it.id = n.path || this.view + '\n' + (n.pid || '') + '\n' + r.id;      // the list keeps its place and what is open across refreshes
    it.description = r.description;
    it.tooltip = r.tooltip || r.label + (r.description ? '\n' + r.description : '');      // plain text: hub text is never rendered as markdown
    if (r.icon) it.iconPath = new vscode.ThemeIcon(r.icon);
    it.contextValue = contextOf(r);
    const click = clickOf(r);
    if (click) it.command = { command: 'lemmata.row.' + click, title: 'Open', arguments: [n] };
    return it;
  }
}

class Controller {
  status: Conn = 'unconfigured';
  bound: Bound[] = [];
  projects: HubProject[] = [];
  runs: RunCapture | null = null;
  folderByKey = new Map<string, vscode.WorkspaceFolder>();
  /** the extension version the hub can hand out, when it is newer than this one */
  offer: { version: string; path: string } | null = null;
  private client: HubClient | null = null;
  private serverUrl = '';
  private busy: Promise<void> | null = null;
  private again = false;
  private timer: ReturnType<typeof setInterval> | undefined;
  private refreshSoon: ReturnType<typeof setTimeout> | undefined;
  private drawSoon: ReturnType<typeof setTimeout> | undefined;
  private flash: { id: string; until: number } | null = null;
  private flashTimer: ReturnType<typeof setTimeout> | undefined;
  private extChecked = 0;
  private lastRefresh = 0;
  private readonly bar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  private readonly out = vscode.window.createOutputChannel('Lemmata');
  private readonly trees: { [k in ViewId]: RowTree };
  private views: { [k in ViewId]?: vscode.TreeView<Node> } = {};

  constructor(private readonly ctx: vscode.ExtensionContext) {
    this.trees = { now: new RowTree('now', () => this.nowRoots()), experiments: new RowTree('experiments', () => this.hubRoots('experiments')), torun: new RowTree('torun', () => this.hubRoots('to_run')) };
    ctx.subscriptions.push(this.bar, this.out, this.trees.now, this.trees.experiments, this.trees.torun);
  }
  register() {
    for (const [k, id] of [['now', 'lemmata.now'], ['experiments', 'lemmata.experiments'], ['torun', 'lemmata.torun']] as [ViewId, string][]) {
      this.views[k] = vscode.window.createTreeView(id, { treeDataProvider: this.trees[k], showCollapseAll: k !== 'now' });
      this.ctx.subscriptions.push(this.views[k]!);
    }
  }

  log(msg: string) { this.out.appendLine(new Date().toISOString() + ' ' + msg); }   // never called with tokens or headers
  cfg() { return vscode.workspace.getConfiguration('lemmata'); }
  version(): string { return String((this.ctx.extension.packageJSON as { version?: unknown }).version || ''); }

  async start() {
    this.bar.show();
    await this.refresh();
    this.restartTimer();
  }
  restartTimer() {
    if (this.timer) clearInterval(this.timer);
    const s = Math.max(10, Number(this.cfg().get('refreshSeconds', 30)) || 30);
    this.timer = setInterval(() => { if (vscode.window.state.focused) void this.refresh(); }, s * 1000);      // a window nobody looks at does not ask the hub
  }
  dispose() { for (const t of [this.refreshSoon, this.drawSoon, this.flashTimer]) if (t) clearTimeout(t); if (this.timer) clearInterval(this.timer); }

  /* ---------- connection ---------- */
  async setup(): Promise<boolean> {
    const url = this.serverSetting();
    const token = url.ok ? await tokenFor(url.url, k => this.ctx.secrets.get(k)) : undefined;   // token of THIS origin only
    if (!token || !url.ok) { this.client = null; this.status = 'unconfigured'; return false; }
    if (!this.client || this.serverUrl !== url.url) { this.client = new HubClient(url.url, token); this.serverUrl = url.url; this.extChecked = 0; }
    return true;
  }
  ctx_secrets(): vscode.SecretStorage { return this.ctx.secrets; }
  /** serverUrl is application-scoped; also read via inspect() so workspace values can never win. */
  serverSetting() { return serverFromInspect(this.cfg().inspect<string>('serverUrl')); }
  serverBase(): string { return this.serverUrl; }
  clientOrNull(): HubClient | null { return this.client; }
  /** Runs are sent to the project whose code repository this workspace folder is. */
  projectFor(folderKey: string): { client: HubClient; pid: string } | null {
    const b = this.client && this.status === 'ok' ? this.bound.find(x => x.binding.folders.code === folderKey) : undefined;
    return b && this.client ? { client: this.client, pid: b.binding.project.id } : null;
  }
  resetClient() { this.client = null; }

  refresh(): Promise<void> {
    if (this.busy) { this.again = true; return this.busy; }
    this.busy = (async () => {
      try { await this.doRefresh(); } finally { this.busy = null; }
      if (this.again) { this.again = false; await this.refresh(); }
    })();
    return this.busy;
  }

  private async folderRemotes(): Promise<FolderRemotes[]> {
    const out: FolderRemotes[] = [];
    this.folderByKey.clear();
    for (const f of vscode.workspace.workspaceFolders || []) {
      if (f.uri.scheme !== 'file') continue;
      const key = f.uri.toString();
      this.folderByKey.set(key, f);
      out.push({ key, remotes: await gitRemotes(f.uri.fsPath) });
    }
    return out;
  }

  /** Coming back to the window refreshes the lists, but not more than once in ten seconds (the hub rebuilds the rows on every ask). */
  refreshIfOld() { if (Date.now() - this.lastRefresh > 10000) void this.refresh(); }

  private async doRefresh() {
    this.lastRefresh = Date.now();
    await vscode.commands.executeCommand('setContext', 'lemmata.connected', await this.setup());
    if (!this.client) { this.bound = []; this.draw(); return; }
    try {
      this.projects = await this.client.projects();
      const folders = await this.folderRemotes();
      const bindings = matchProjects(folders, this.projects, String(this.cfg().get('project', '')));
      const bound: Bound[] = [];
      for (const b of bindings) {
        try {
          const doc = asBench(await this.client.bench(b.project.id));
          bound.push({ binding: b, bench: doc, error: doc ? null : 'The hub\'s answer could not be read.' });
        } catch (e) {
          if (e instanceof HubError && (e.offline || e.unauthorized)) throw e;
          bound.push({ binding: b, bench: null, error: e instanceof HubError && e.status === 404 ? OLD_HUB : e instanceof Error ? e.message : String(e) });
        }
      }
      this.bound = bound;
      this.status = 'ok';
      if (Date.now() - this.extChecked > EXT_CHECK_MS) void this.checkExtension(false);
    } catch (e) {
      if (e instanceof HubError && e.unauthorized) { this.status = 'unauthorized'; this.bound = []; }
      else this.status = 'offline';   // keep the last rows so the lists do not go blank
      this.log('refresh failed: ' + (e instanceof HubError ? 'HTTP ' + e.status + ' ' + e.code : 'error'));
    }
    this.draw();
  }

  /* ---------- what the lists show ---------- */
  private note(id: string): { note: RunNote; pid: string } | undefined {
    for (const b of this.bound) if (b.bench && b.bench.runs[id]) return { note: b.bench.runs[id], pid: b.binding.project.id };
    return undefined;
  }
  private locals(): LocalRun[] { return this.runs ? this.runs.locals() : []; }
  private nowRoots(): Node[] {
    const elsewhere: Row[] = [];
    for (const b of this.bound) if (b.bench) for (const r of b.bench.elsewhere) elsewhere.push({ ...r, pid: b.binding.project.id, attach: true });
    const today = isoLocal(new Date()).slice(0, 10);
    return nowRows({ local: this.locals(), note: id => { const n = this.note(id); return n && n.note; }, elsewhere, today, nowMs: Date.now(), hubKnows: this.status === 'ok' })
      .map(row => ({ row, pid: null }));
  }
  private hubRoots(which: 'experiments' | 'to_run'): Node[] {
    const out: Node[] = [];
    const many = this.bound.length > 1;
    for (const b of this.bound) {
      const pid = b.binding.project.id, name = oneLine(b.binding.project.name, 60);
      const rows: Row[] = b.bench ? b.bench[which] : [{ id: 'err', label: oneLine(b.error || 'Not available', 160), icon: 'warning', tooltip: b.error || '' }];
      if (b.bench && b.bench.version > BENCH_VERSION && which === 'experiments')
        rows.unshift({ id: 'newer', label: 'The hub is newer than this extension: some rows may be missing', icon: 'info', tooltip: 'Use "Lemmata: Go to…" → Install the newer extension.' });
      if (many) out.push({ row: { id: 'p|' + pid, label: name, icon: 'repo', kids: rows, expanded: true }, pid });
      else for (const row of rows) out.push({ row, pid });
    }
    return out;
  }
  /** Is this file of the project open in the workspace? */
  mapped(pid: string, repo: string, rel: string): vscode.Uri | null {
    const b = this.bound.find(x => x.binding.project.id === pid);
    const m = b ? mapPath(b.binding.folders, repo, rel, b.binding.subdirs) : null;
    const f = m && this.folderByKey.get(m.folder);
    return m && f ? vscode.Uri.joinPath(f.uri, ...m.rel.split('/')) : null;
  }
  /** Open a hub location (repo "code" or "paper", repo-relative path) of project `pid` in the editor. */
  async openLocation(pid: string, repo: string, rel: string, line: number, beside = true): Promise<boolean> {
    const uri = this.mapped(pid, repo, rel);
    if (!uri) return false;
    const l0 = Math.max(0, Math.floor(line) - 1);
    try { await vscode.window.showTextDocument(uri, { selection: new vscode.Range(l0, 0, l0, 0), preview: true, viewColumn: beside ? vscode.ViewColumn.Beside : vscode.ViewColumn.Active }); return true; }
    catch { return false; }
  }
  /** Something changed on the hub (the tab saved something, runs arrived): fetch the rows again shortly after. */
  hubChanged() { if (this.refreshSoon) clearTimeout(this.refreshSoon); this.refreshSoon = setTimeout(() => { void this.refresh(); }, 1500); }

  /* ---------- runs on this machine (RunHost) ---------- */
  runsChanged() { if (this.drawSoon) clearTimeout(this.drawSoon); this.drawSoon = setTimeout(() => this.draw(), 150); }
  runsSent() { this.hubChanged(); }
  runEnded(runId: string) {
    this.flash = { id: runId, until: Date.now() + FLASH_MS };
    if (this.flashTimer) clearTimeout(this.flashTimer);
    this.flashTimer = setTimeout(() => { this.flash = null; this.draw(); }, FLASH_MS + 500);
    this.draw();
  }

  /* ---------- the lists, their counts, and the one status-bar item ---------- */
  private draw() {
    const local = this.locals(), now = Date.now();
    const running = local.filter(r => isRunning(r, now)).length, unsent = local.filter(r => !r.sent && !isRunning(r, now)).length;
    const toRun = this.bound.reduce((s, b) => s + (b.bench ? b.bench.counts.to_run : 0), 0);
    let flash: string | null = null;
    if (this.flash && now < this.flash.until) {
      const r = local.find(x => x.id === this.flash!.id), n = this.note(this.flash.id);
      if (r) flash = flashOf(r, n && n.note);
    }
    const b = barOf({ conn: this.status, server: this.serverUrl, projects: this.bound.length, running, unsent, toRun, flash });
    this.bar.text = b.text; this.bar.tooltip = b.tooltip; this.bar.command = b.command;
    this.bar.backgroundColor = b.warn ? new vscode.ThemeColor('statusBarItem.warningBackground') : undefined;
    const set = (k: string, v: boolean) => { void vscode.commands.executeCommand('setContext', k, v); };
    set('lemmata.hasProject', this.bound.length > 0);
    set('lemmata.hasExperiments', this.bound.some(x => !x.bench || x.bench.experiments.length > 0));
    set('lemmata.hasToRun', this.bound.some(x => !x.bench || x.bench.to_run.length > 0));
    const note = this.status === 'offline' ? 'Offline: showing what was last read from the hub.' : this.status === 'unauthorized' ? 'The hub did not accept the token. Connect again.' : undefined;
    for (const k of ['now', 'experiments', 'torun'] as ViewId[]) {
      const v = this.views[k];
      if (v) v.message = k === 'now' && this.status === 'offline' ? 'Offline: runs are still logged here and sent when the hub is back.' : k === 'now' ? undefined : note;
      this.trees[k].refresh();
    }
    if (this.views.now) this.views.now.badge = running ? { value: running, tooltip: running + ' running' } : undefined;
    if (this.views.torun) this.views.torun.description = toRun ? String(toRun) : undefined;
  }

  /* ---------- a newer extension on the hub ---------- */
  async checkExtension(manual: boolean) {
    const client = this.client;
    if (!client) return;
    this.extChecked = Date.now();
    try {
      const ext = (await client.status()).extension, own = this.version();
      this.offer = ext && typeof ext.version === 'string' && ext.path === VSIX_PATH && newer(ext.version, own) ? { version: ext.version, path: VSIX_PATH } : null;
      if (!this.offer) { if (manual) void vscode.window.showInformationMessage('Lemmata: this extension (' + own + ') is the newest your hub has.'); return; }
      if (!manual && this.ctx.globalState.get<string>(SKIP_KEY) === this.offer.version) return;      // asked once per version
      const a = await vscode.window.showInformationMessage('Lemmata: your hub has a newer version of this extension (' + this.offer.version + '; this is ' + own + ').', 'Install', 'Not now');
      if (a === 'Install') await this.installExtension();
      else if (a === 'Not now') await this.ctx.globalState.update(SKIP_KEY, this.offer.version);
    } catch (e) { if (manual) void fail('could not ask the hub', e); }
  }
  async installExtension() {
    const client = this.client, offer = this.offer;
    if (!client || !offer) return;
    let file = '';
    try {
      const r = await client.raw('GET', offer.path, undefined, 40 * 1024 * 1024);
      if (r.status !== 200 || r.data.length < 1000 || r.data[0] !== 0x50 || r.data[1] !== 0x4b) throw new Error('the hub did not send an extension file (HTTP ' + r.status + ')');
      const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'lemmata-ext-'));
      file = path.join(dir, 'lemmata-' + offer.version + '.vsix');
      await fs.writeFile(file, r.data);
      await vscode.commands.executeCommand('workbench.extensions.installExtension', vscode.Uri.file(file));
      const a = await vscode.window.showInformationMessage('Lemmata ' + offer.version + ' is installed. Reload the window to use it.', 'Reload window');
      if (a) await vscode.commands.executeCommand('workbench.action.reloadWindow');
    } catch (e) {
      void vscode.window.showErrorMessage('Lemmata: the newer extension could not be installed (' + (e instanceof Error ? oneLine(e.message, 200) : 'error') + ').'
        + (file ? ' Install it by hand: Extensions → ⋯ → Install from VSIX…, file ' + file : ''));
    }
  }
}

let CTRL: Controller;
let TAB: LemmataTab;

/* ---------- git remotes ---------- */
function gitRemotes(cwd: string): Promise<string[]> {
  return new Promise(resolve => {
    execFile('git', ['config', '--get-regexp', '^remote\\..*\\.url$'], { cwd, timeout: 5000, windowsHide: true }, (err, stdout) => {
      resolve(err ? [] : parseGitConfigRemotes(String(stdout)));
    });
  });
}

function gitOut(cwd: string, args: string[]): Promise<string> {
  return new Promise(resolve => {
    execFile('git', args, { cwd, timeout: 5000, windowsHide: true }, (err, stdout) => resolve(err ? '' : String(stdout).trim()));
  });
}

/* "Add this repository to Lemmata": the hub copies it from GitHub, following the branch checked out here. */
async function addProject() {
  const client = CTRL.clientOrNull();
  if (!client) { void vscode.window.showWarningMessage('Lemmata: connect to your server first.', 'Connect').then(a => a && vscode.commands.executeCommand('lemmata.connect')); return; }
  let projects: HubProject[];
  try { projects = await client.projects(); } catch (e) { void fail('could not reach the server', e); return; }
  const cands: { folder: vscode.WorkspaceFolder; repo: string }[] = [];
  for (const f of vscode.workspace.workspaceFolders || []) {
    if (f.uri.scheme !== 'file') continue;
    for (const repo of unmatchedRepos(await gitRemotes(f.uri.fsPath), projects)) cands.push({ folder: f, repo });
  }
  if (!cands.length) {
    const open = (vscode.workspace.workspaceFolders || []).length;
    void vscode.window.showInformationMessage(open
      ? 'Lemmata: no folder here has a GitHub remote that is not already a project. Lemmata reads projects from GitHub: push the folder to a GitHub repository first (git remote add origin …, then git push -u origin HEAD).'
      : 'Lemmata: open the project\'s folder first (File → Open Folder).');
    return;
  }
  let pick = cands[0];
  if (cands.length > 1) {
    const q = await vscode.window.showQuickPick(cands.map(c => ({ label: c.repo, description: c.folder.name, c })), { placeHolder: 'Which repository should become a Lemmata project?' });
    if (!q) return;
    pick = q.c;
  }
  const cwd = pick.folder.uri.fsPath;
  const branch = await gitOut(cwd, ['rev-parse', '--abbrev-ref', 'HEAD']);
  const upstream = branch && branch !== 'HEAD' ? await gitOut(cwd, ['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}']) : '';
  const items: (vscode.QuickPickItem & { b: string | null })[] = [];
  if (branch && branch !== 'HEAD') items.push({ label: 'Follow ' + branch, description: 'the branch checked out here' + (upstream ? '' : ' (not pushed yet)'), b: branch });
  items.push({ label: 'Follow the default branch', description: 'as set on GitHub', b: null });
  const choice = await vscode.window.showQuickPick(items, { placeHolder: 'Add ' + pick.repo + ' to Lemmata: which branch should it follow?' });
  if (!choice) return;
  if (choice.b && !upstream) {
    const go = await vscode.window.showWarningMessage('Lemmata reads ' + choice.b + ' from GitHub, but it is not pushed yet. Push it first (git push -u origin ' + choice.b + '), then add the project.', 'Add anyway');
    if (go !== 'Add anyway') return;
  }
  const name = pick.repo.split('/')[1] || pick.repo;
  try {
    const p = await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: 'Lemmata: copying ' + pick.repo + ' from GitHub…' },
      () => client.createProject(pick.repo, choice.b, name));
    await CTRL.refresh();
    const a = await vscode.window.showInformationMessage('Lemmata: added ' + name + '. Next, let Claude Code map its questions and experiments: open the project and copy the map prompt.', 'Open in Lemmata');
    if (a) await TAB.open(client, CTRL.serverBase(), p.id, oneLine(p.name || name, 40), 'experiments');
  } catch (e) {
    const code = e instanceof HubError ? e.code : '';
    if (code === 'branch_not_found' || /branch/i.test(e instanceof Error ? e.message : '')) void vscode.window.showErrorMessage('Lemmata: GitHub has no branch ' + (choice.b || '') + ' in ' + pick.repo + '. Push it first: git push -u origin ' + (choice.b || 'HEAD'));
    else void fail('could not add the project', e);
  }
}

/* ---------- commands ---------- */
const needConnect = () => { void vscode.window.showWarningMessage('Lemmata: connect to a server first.', 'Connect').then(a => a && vscode.commands.executeCommand('lemmata.connect')); };
/** The project a command is about: the row's own, the only one, or the one you pick. */
async function pickProject(pid?: string | null): Promise<{ client: HubClient; pid: string; name: string } | null> {
  const client = CTRL.clientOrNull();
  if (!client) { needConnect(); return null; }
  const nameOf = (id: string) => { const b = CTRL.bound.find(x => x.binding.project.id === id); return b ? oneLine(b.binding.project.name, 40) : ''; };
  if (pid) return { client, pid, name: nameOf(pid) };
  if (!CTRL.bound.length) { void vscode.window.showInformationMessage('Lemmata: no hub project matches this workspace. Open the project\'s GitHub clone, add it with "Lemmata: Add This Repository", or set "lemmata.project".'); return null; }
  if (CTRL.bound.length === 1) return { client, pid: CTRL.bound[0].binding.project.id, name: nameOf(CTRL.bound[0].binding.project.id) };
  const pick = await vscode.window.showQuickPick(CTRL.bound.map(b => ({ label: oneLine(b.binding.project.name, 60), pid: b.binding.project.id })), { placeHolder: 'Which Lemmata project?' });
  return pick ? { client, pid: pick.pid, name: pick.label } : null;
}
const fail = (what: string, e: unknown) => vscode.window.showErrorMessage('Lemmata: ' + what + ': ' + (e instanceof Error ? e.message : String(e)));

async function connect() {
  const curS = CTRL.serverSetting();
  const cur = curS.ok ? curS.url : DEFAULT_URL;
  const typed = await vscode.window.showInputBox({ title: 'Lemmata: server address', prompt: 'Address of your Lemmata hub', value: cur || DEFAULT_URL, ignoreFocusOut: true,
    validateInput: v => { const r = normalizeServerUrl(v); return r.ok ? undefined : r.reason; } });
  if (typed === undefined) return;
  const norm = normalizeServerUrl(typed);
  if (!norm.ok) return;
  if (norm.url.startsWith('http:') && !isPrivateHost(new URL(norm.url).hostname)) {
    const ok = await vscode.window.showWarningMessage('This address is not a private or Tailscale address and uses plain http, so the token would travel unencrypted.', { modal: true }, 'Connect anyway');
    if (ok !== 'Connect anyway') return;
  }
  const token = await vscode.window.showInputBox({ title: 'Lemmata: token', prompt: 'On the Mac mini run: lemmata hub token --device "VS Code"  and paste the token', password: true, ignoreFocusOut: true,
    validateInput: v => (v.trim() ? undefined : 'Paste the token') });
  if (!token) return;
  try {
    const projects = await new HubClient(norm.url, token.trim()).projects();   // proves the token works
    await CTRL.ctx_secrets().store(tokenKey(norm.url), token.trim());
    await CTRL.cfg().update('serverUrl', norm.url, vscode.ConfigurationTarget.Global);
    CTRL.resetClient(); TAB.reset(); TAB.closeAll();
    void vscode.window.showInformationMessage('Lemmata: connected. ' + projects.length + ' project' + (projects.length === 1 ? '' : 's') + ' on the server.');
    await CTRL.refresh();
  } catch (e) {
    if (e instanceof HubError && e.unauthorized) void vscode.window.showErrorMessage('Lemmata: the server did not accept that token. Create a new one with lemmata hub token.');
    else void fail('could not connect', e);
  }
}

/** Open a page: the experiment pages in VS Code's tab, every other page on the website. */
async function openPage(t: Target, pid?: string | null, where: 'tab' | 'site' | 'auto' = 'auto') {
  const p = await pickProject(pid); if (!p) return;
  if (where !== 'site' && isBenchView(t.view)) await TAB.open(p.client, CTRL.serverBase(), p.pid, p.name, t.view as View, t.sel || (t.view === 'setup' ? 'page' : null));
  else await vscode.env.openExternal(vscode.Uri.parse(siteUrl(CTRL.serverBase(), p.pid, t), true));
}
/** The map alone, in a wide editor tab (or a window of its own). On the hub the map is the top of Setup; "map" asks the page for it alone. */
async function openMap(ownWindow: boolean, pid?: string | null) {
  const p = await pickProject(pid); if (!p) return;
  await TAB.open(p.client, CTRL.serverBase(), p.pid, p.name, 'setup', 'map');
  if (!ownWindow) return;
  try { await vscode.commands.executeCommand('workbench.action.moveEditorToNewWindow'); }
  catch { void vscode.window.showInformationMessage('Lemmata: this VS Code cannot move a tab into its own window. Drag the tab out of the window instead.'); }
}

/** "Open in VS Code" on the website: an experiment page opens in the tab with the claim or experiment selected; any other page opens on the website. */
async function openFromLink(u: vscode.Uri) {
  const l = parseOpenLink(u.path, u.query);
  if (!l) { void vscode.window.showWarningMessage('Lemmata: that link is not one Lemmata understands.'); return; }
  const client = CTRL.clientOrNull();
  if (!client) { void vscode.window.showWarningMessage('Lemmata: connect to your server first, then click the link again.', 'Connect').then(a => a && vscode.commands.executeCommand('lemmata.connect')); return; }
  let projects = CTRL.projects;
  if (!projects.some(p => p.id === l.pid)) { try { projects = await client.projects(); } catch (e) { void fail('could not reach the server', e); return; } }
  const p = projects.find(x => x.id === l.pid);
  if (!p) { void vscode.window.showWarningMessage('Lemmata: that project is not on the server this VS Code is connected to (' + CTRL.serverBase() + ').'); return; }
  if (isBenchView(l.view)) await TAB.open(client, CTRL.serverBase(), p.id, oneLine(p.name, 40), l.view, l.sel);
  else await vscode.env.openExternal(vscode.Uri.parse(siteUrl(CTRL.serverBase(), p.id, { view: l.view, sel: l.sel || undefined }), true));
}

async function syncHub(pid?: string | null) {
  const t = await pickProject(pid); if (!t) return;
  await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: 'Lemmata: the hub is reading your code and paper from GitHub…' }, async () => {
    try {
      const r = await t.client.sync(t.pid);
      const code = r.code ? r.code.changed : !!r.changed, paper = !!(r.paper && r.paper.changed);
      const perr = r.paper && r.paper.error;
      if (perr) void vscode.window.showWarningMessage('Lemmata: paper sync: ' + oneLine(perr, 200) + (code ? ' (code was synced)' : ''));
      else void vscode.window.showInformationMessage(code || paper ? 'Lemmata: synced' + (code ? ' code' : '') + (paper ? ' paper' : '') + ' and rescanned.' : 'Lemmata: already up to date.');
      await CTRL.refresh();
    } catch (e) { void fail('sync failed', e); }
  });
}

/** One picker instead of a command per page. */
async function goTo() {
  type It = vscode.QuickPickItem & { run?: () => unknown };
  const sep = (label: string): It => ({ label, kind: vscode.QuickPickItemKind.Separator });
  const focus = (id: string) => () => vscode.commands.executeCommand(id + '.focus');
  const site = (view: string) => () => openPage({ view }, null, 'site');
  const cmd = (id: string) => () => vscode.commands.executeCommand(id);
  const connected = !!CTRL.clientOrNull();
  const items: It[] = [
    sep('In VS Code'),
    { label: '$(beaker) Now', description: 'runs on this machine', run: focus('lemmata.now') },
    { label: '$(target) Experiments', description: 'each claim, its experiments and their setup', run: focus('lemmata.experiments') },
    { label: '$(checklist) To run', description: 'what to run next', run: focus('lemmata.torun') },
    { label: '$(type-hierarchy) Map', description: 'thesis, claims, experiments and what they use, in a wide tab', run: () => openMap(false) },
    { label: '$(empty-window) Map in its own window', run: () => openMap(true) },
    { label: '$(table) Setup', description: 'measures, datasets, methods and coverage, in a tab', run: () => openPage({ view: 'setup' }) },
    { label: '$(list-tree) Thesis', description: 'claims and experiments, top down, in a tab', run: () => openPage({ view: 'experiments' }) },
    sep('On the website (opens your browser)'),
    { label: 'Home', description: 'thesis, calendar, next to do', run: site('digest') },
    { label: 'Baselines', description: 'paper, code, idea and published numbers', run: site('baselines') },
    { label: 'Key numbers', run: site('numbers') },
    { label: 'LaTeX', description: 'tables, paragraphs and captions to paste', run: site('latex') },
    { label: 'Review', description: 'paper checks and changes', run: site('review') },
    { label: 'Trail', description: 'deadlines and what was done', run: site('history') },
    { label: 'Settings and FAQ', run: site('settings') },
    sep('Do'),
    { label: '$(cloud-upload) Send runs to the hub now', run: cmd('lemmata.runs.sync') },
    { label: '$(sync) Sync the hub with GitHub now', run: () => syncHub() },
    { label: '$(hubot) Set up the coding agent (Claude Code)', run: cmd('lemmata.setupAgent') },
    { label: '$(add) Add this repository to Lemmata', run: cmd('lemmata.addProject') },
    CTRL.offer ? { label: '$(arrow-up) Install the newer extension from the hub', description: CTRL.offer.version, run: () => CTRL.installExtension() }
      : { label: '$(arrow-up) Check the hub for a newer extension', description: 'this is ' + CTRL.version(), run: () => CTRL.checkExtension(true) },
    connected ? { label: '$(debug-disconnect) Disconnect (forget the token)', run: cmd('lemmata.disconnect') } : { label: '$(plug) Connect to your server', run: cmd('lemmata.connect') },
  ];
  const pick = await vscode.window.showQuickPick(items, { placeHolder: 'Lemmata: go to…', matchOnDescription: true });
  if (pick && pick.run) await pick.run();
}

/* ---------- what a row can do ---------- */
const rowOf = (n?: Node): Row | null => (n && n.row && typeof n.row.id === 'string' ? n.row : null);

async function rowOpen(n?: Node) {
  const r = rowOf(n); if (!r || !r.open || !n || !n.pid) return;
  if (!(await CTRL.openLocation(n.pid, r.open.repo, r.open.path, r.open.line, false)))
    void vscode.window.showInformationMessage('Lemmata: ' + r.open.path + ' is not in a folder open in this window (or this checkout is older than the hub\'s copy: pull).');
}
async function rowCopy(n?: Node) {
  const r = rowOf(n); if (!r || !r.copy) return;
  await vscode.env.clipboard.writeText(r.copy.text);
  vscode.window.setStatusBarMessage('Lemmata: copied ' + r.copy.what + (/prompt/.test(r.copy.what) ? '. Paste it into Claude Code.' : '.'), 5000);
  const client = CTRL.clientOrNull();
  if (client && n && n.pid && r.kind === 'plan' && r.id.startsWith('plan:')) { try { await client.planCopied(n.pid, r.id.slice(5)); CTRL.hubChanged(); } catch { /* the prompt is on the clipboard either way */ } }
}
async function rowSnooze(n?: Node) {
  const r = rowOf(n), client = CTRL.clientOrNull(); if (!r || !r.snooze || !n || !n.pid || !client) return;
  const b = CTRL.bound.find(x => x.binding.project.id === n.pid);
  const today = (b && b.bench && /^\d{4}-\d{2}-\d{2}$/.test(b.bench.today) ? b.bench.today : isoLocal(new Date()).slice(0, 10));
  const pick = await vscode.window.showQuickPick([{ label: 'Until tomorrow', days: 1 }, { label: 'For a week', days: 7 }, { label: 'For a month', days: 30 }].map(o => ({ ...o, description: 'back on ' + dayPlus(today, o.days) })),
    { placeHolder: 'Hide "' + oneLine(r.label, 60) + '" from the list for how long? (It also leaves the website\'s to-do list.)' });
  if (!pick) return;
  try { await client.snooze(n.pid, r.snooze, dayPlus(today, pick.days)); await CTRL.refresh(); }
  catch (e) { void fail('could not snooze it', e); }
}
async function runAttach(n?: Node) {
  const r = rowOf(n), client = CTRL.clientOrNull(); if (!r || !r.run || !n || !client) return;
  const pid = n.pid || r.pid; if (!pid) return;
  const b = CTRL.bound.find(x => x.binding.project.id === pid);
  if (!b || !b.bench) { void vscode.window.showInformationMessage('Lemmata: ' + (b && b.error ? b.error : 'the hub has not been read yet.')); return; }
  if (r.file && CTRL.runs && !(await CTRL.runs.ensureSent(r.run))) { void vscode.window.showWarningMessage('Lemmata: this run is not on the hub yet, so it cannot be attached. Try "Send runs to the hub now".'); return; }
  const cur = b.bench.runs[r.run];
  const items: (vscode.QuickPickItem & { x: string | null })[] = b.bench.pick.map(p => ({ label: p.label, description: p.description + (cur && cur.x === p.id ? ' · now' : ''), x: p.id }));
  if (!items.length) { void vscode.window.showInformationMessage('Lemmata: this project has no experiments yet. Confirm the project map on the website first.'); return; }
  if (cur && cur.how === 'attached') items.push({ label: 'Take my choice back', description: 'let Lemmata\'s rules decide again', x: null });
  const pick = await vscode.window.showQuickPick(items, { placeHolder: 'Which experiment does this run belong to?', matchOnDescription: true });
  if (!pick) return;
  try { await client.attachRun(pid, r.run, pick.x); await CTRL.refresh(); }
  catch (e) { void fail('could not attach the run', e); }
}

export async function activate(ctx: vscode.ExtensionContext) {
  CTRL = new Controller(ctx);
  const c = vscode.commands.registerCommand;
  ctx.subscriptions.push(vscode.window.registerUriHandler({ handleUri: u => { void openFromLink(u); } }));
  CTRL.register();
  ctx.subscriptions.push(
    c('lemmata.connect', connect),
    c('lemmata.disconnect', async () => { const u = CTRL.serverSetting(); if (u.ok) await ctx.secrets.delete(tokenKey(u.url)); CTRL.resetClient(); await CTRL.refresh(); void vscode.window.showInformationMessage('Lemmata: token removed from this computer.'); }),
    c('lemmata.refresh', async () => { if (CTRL.runs) await CTRL.runs.refresh(); await CTRL.refresh(); }),
    c('lemmata.showPanel', async () => { await vscode.commands.executeCommand('workbench.view.extension.lemmata'); void CTRL.refresh(); }),
    c('lemmata.goto', goTo),
    c('lemmata.addProject', addProject),
    c('lemmata.openMap', () => openMap(false)),
    c('lemmata.openSetup', () => openPage({ view: 'setup' })),
    c('lemmata.openWebsite', () => openPage({ view: 'digest' }, null, 'site')),
    c('lemmata.row.record', async (n?: Node) => { const r = rowOf(n); if (r && r.file) await vscode.window.showTextDocument(vscode.Uri.file(r.file), { preview: true }); }),
    c('lemmata.row.open', rowOpen),
    c('lemmata.row.tab', async (n?: Node) => { const r = rowOf(n); if (r && r.tab && n) await openPage(r.tab, n.pid, 'tab'); }),
    c('lemmata.row.site', async (n?: Node) => { const r = rowOf(n); if (r && r.site && n) await openPage(r.site, n.pid || r.pid, 'site'); }),
    c('lemmata.row.copy', rowCopy),
    c('lemmata.row.snooze', rowSnooze),
    c('lemmata.run.attach', runAttach),
    vscode.window.onDidChangeWindowState(s => { if (s.focused) CTRL.refreshIfOld(); }),
    vscode.workspace.onDidChangeWorkspaceFolders(() => void CTRL.refresh()),
    vscode.workspace.onDidChangeConfiguration(e => {
      if (e.affectsConfiguration('lemmata.refreshSeconds')) CTRL.restartTimer();
      if (e.affectsConfiguration('lemmata')) { CTRL.resetClient(); void CTRL.refresh(); }   // a changed address has no token until you Connect again
    }),
    ctx.secrets.onDidChange(e => { if (e.key.startsWith(TOKEN_PREFIX)) { CTRL.resetClient(); void CTRL.refresh(); } }),
    { dispose: () => CTRL.dispose() },
  );
  TAB = new LemmataTab(ctx, CTRL);
  const runs = new RunCapture(ctx, CTRL);
  CTRL.runs = runs;
  runs.register();
  await CTRL.start();
  await runs.start();
}

export function deactivate() { /* disposables are registered on the context */ }
/** For the tests only: the controller behind the lists and the status bar. */
export const internals = () => ({ controller: CTRL, RowTree });
