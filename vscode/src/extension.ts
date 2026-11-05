import * as vscode from 'vscode';
import { execFile } from 'child_process';
import { HubClient, HubError } from './core/client';
import { Binding, FolderRemotes, matchProjects, parseGitConfigRemotes } from './core/remotes';
import { Diag, LocRef, Model, NodeItem, FindingItem, toDiagnostics } from './core/model';
import { loadModel } from './core/load';
import { mapPath, hubPath } from './core/mapping';
import { formatWhy } from './core/why';
import { isPrivateHost, normalizeServerUrl } from './core/url';
import { oneLine } from './core/text';
import { HubProject, TriageState } from './core/types';

const TOKEN_KEY = 'lemmata.token';
const WHY_SCHEME = 'lemmata-why';
const DEFAULT_URL = 'http://100.111.135.94:8765';

interface Bound { binding: Binding; model: Model | null; error: string | null }
type Status = 'unconfigured' | 'offline' | 'unauthorized' | 'ok';

class Controller implements vscode.TreeDataProvider<Item>, vscode.TextDocumentContentProvider {
  status: Status = 'unconfigured';
  bound: Bound[] = [];
  projects: HubProject[] = [];
  names = new Map<string, string>();   // node id -> name, for "Why?" documents
  private client: HubClient | null = null;
  private serverUrl = '';
  private busy: Promise<void> | null = null;
  private again = false;
  private timer: ReturnType<typeof setInterval> | undefined;
  private saveTimer: ReturnType<typeof setTimeout> | undefined;
  private readonly diags = vscode.languages.createDiagnosticCollection('lemmata');
  private readonly bar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  private readonly out = vscode.window.createOutputChannel('Lemmata');
  private readonly changed = new vscode.EventEmitter<Item | undefined>();
  readonly onDidChangeTreeData = this.changed.event;
  private readonly docChanged = new vscode.EventEmitter<vscode.Uri>();
  readonly onDidChange = this.docChanged.event;
  folderByKey = new Map<string, vscode.WorkspaceFolder>();

  constructor(private readonly ctx: vscode.ExtensionContext) {
    this.bar.command = 'lemmata.showPanel';
    ctx.subscriptions.push(this.diags, this.bar, this.out, this.changed, this.docChanged);
  }

  log(msg: string) { this.out.appendLine(new Date().toISOString() + ' ' + msg); }   // never called with tokens or headers
  cfg() { return vscode.workspace.getConfiguration('lemmata'); }

  async start() {
    this.bar.show();
    await this.refresh();
    this.restartTimer();
  }
  restartTimer() {
    if (this.timer) clearInterval(this.timer);
    const s = Math.max(10, Number(this.cfg().get('refreshSeconds', 30)) || 30);
    this.timer = setInterval(() => { void this.refresh(); }, s * 1000);
  }
  dispose() { if (this.timer) clearInterval(this.timer); if (this.saveTimer) clearTimeout(this.saveTimer); }
  scheduleSaveRefresh() {
    if (this.saveTimer) clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => { void this.refresh(); }, 1000);
  }

  /* ---------- connection ---------- */
  async setup(): Promise<boolean> {
    const token = await this.ctx.secrets.get(TOKEN_KEY);
    const url = normalizeServerUrl(String(this.cfg().get('serverUrl', DEFAULT_URL)));
    if (!token || !url.ok) { this.client = null; this.status = 'unconfigured'; return false; }
    if (!this.client || this.serverUrl !== url.url) { this.client = new HubClient(url.url, token); this.serverUrl = url.url; }
    return true;
  }
  ctx_secrets(): vscode.SecretStorage { return this.ctx.secrets; }
  serverBase(): string { return this.serverUrl; }
  clientOrNull(): HubClient | null { return this.client; }
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

  private async doRefresh() {
    await vscode.commands.executeCommand('setContext', 'lemmata.connected', await this.setup());
    if (!this.client) { this.bound = []; this.diags.clear(); this.render(); return; }
    try {
      this.projects = await this.client.projects();
      const folders = await this.folderRemotes();
      const bindings = matchProjects(folders, this.projects, String(this.cfg().get('project', '')));
      const bound: Bound[] = [];
      this.names.clear();
      for (const b of bindings) {
        try {
          const model = await loadModel(this.client, b.project.id);
          for (const g of model.groups) for (const n of g.nodes) this.names.set(b.project.id + '\0' + n.nodeId, n.name);
          bound.push({ binding: b, model, error: null });
        } catch (e) {
          if (e instanceof HubError && (e.offline || e.unauthorized)) throw e;
          bound.push({ binding: b, model: null, error: e instanceof Error ? e.message : String(e) });
        }
      }
      this.bound = bound;
      this.status = 'ok';
      this.publish();
    } catch (e) {
      if (e instanceof HubError && e.unauthorized) { this.status = 'unauthorized'; this.diags.clear(); this.bound = []; }
      else this.status = 'offline';   // keep the last diagnostics so the editor does not flicker
      this.log('refresh failed: ' + (e instanceof HubError ? 'HTTP ' + e.status + ' ' + e.code : 'error'));
    }
    this.render();
  }

  /* ---------- diagnostics ---------- */
  diagnosticsFor(b: Bound): Diag[] {
    return b.model ? toDiagnostics(b.model, b.binding.folders) : [];
  }
  private publish() {
    const per = new Map<string, { uri: vscode.Uri; list: vscode.Diagnostic[] }>();
    for (const b of this.bound) {
      for (const d of this.diagnosticsFor(b)) {
        const folder = this.folderByKey.get(d.folder);
        if (!folder) continue;
        const uri = vscode.Uri.joinPath(folder.uri, ...d.rel.split('/'));
        const diag = new vscode.Diagnostic(new vscode.Range(d.line0, 0, d.line0, 10000), d.message,
          d.severity === 'error' ? vscode.DiagnosticSeverity.Error : d.severity === 'information' ? vscode.DiagnosticSeverity.Information : vscode.DiagnosticSeverity.Warning);
        diag.source = d.source; diag.code = d.code;
        const k = uri.toString();
        if (!per.has(k)) per.set(k, { uri, list: [] });
        per.get(k)!.list.push(diag);
      }
    }
    this.diags.clear();
    for (const { uri, list } of per.values()) this.diags.set(uri, list);
  }

  /* ---------- status bar ---------- */
  private render() {
    const n = this.bound.reduce((s, b) => s + (b.model ? b.model.recheck : 0), 0);
    let text: string, tip: string, warn = false;
    if (this.status === 'unconfigured') { text = 'Lemmata: connect'; tip = 'Click to connect to your Lemmata server'; this.bar.command = 'lemmata.connect'; }
    else if (this.status === 'unauthorized') { text = 'Lemmata: token rejected'; tip = 'The server did not accept the token. Click to connect again.'; warn = true; this.bar.command = 'lemmata.connect'; }
    else if (this.status === 'offline') { text = 'Lemmata: offline'; tip = 'Cannot reach ' + this.serverUrl + '. Showing the last results. Click to open the panel.'; warn = true; this.bar.command = 'lemmata.showPanel'; }
    else if (!this.bound.length) { text = 'Lemmata: no project'; tip = 'No hub project matches this workspace\'s git remotes. Click for details.'; this.bar.command = 'lemmata.showPanel'; }
    else { text = 'Lemmata: ' + n + ' to recheck'; tip = n + ' to recheck since ' + (this.bound[0].model && this.bound[0].model.checkpoint ? 'checkpoint ' + this.bound[0].model.checkpoint.toUpperCase() : 'the checkpoint') + '. Click to open the panel.'; warn = n > 0; this.bar.command = 'lemmata.showPanel'; }
    this.bar.text = text; this.bar.tooltip = tip;
    this.bar.backgroundColor = warn ? new vscode.ThemeColor('statusBarItem.warningBackground') : undefined;
    this.changed.fire(undefined);
  }

  /* ---------- tree ---------- */
  getTreeItem(e: Item) { return e; }
  getChildren(e?: Item): Item[] {
    if (!e) return this.roots();
    return e.kids();
  }
  private roots(): Item[] {
    if (this.status === 'unconfigured') return [];
    const items: Item[] = [];
    if (this.status === 'offline') items.push(new Item('Offline: showing the last results', 'message', { kind: 'info' }, 'warning'));
    if (this.status === 'unauthorized') items.push(new Item('Token rejected: connect again', 'message', { kind: 'info' }, 'error'));
    if (this.status === 'ok' && !this.bound.length) {
      const o = String(this.cfg().get('project', ''));
      items.push(new Item(o ? 'Project "' + oneLine(o, 40) + '" was not found on the server' : 'No hub project matches this workspace', 'message', { kind: 'info' }, 'info'));
      items.push(new Item('Hub projects: ' + (this.projects.map(p => oneLine(p.name, 30)).join(', ') || 'none'), 'message', { kind: 'info' }, 'list-unordered'));
      items.push(new Item('Open the project\'s GitHub clone, or set lemmata.project', 'command', { kind: 'settings' }, 'gear'));
    }
    for (const b of this.bound) {
      if (b.error) { items.push(new Item(oneLine(b.binding.project.name, 40) + ': ' + oneLine(b.error, 80), 'message', { kind: 'info' }, 'error')); continue; }
      if (!b.model) continue;
      const wrap = this.bound.length > 1;
      const kids = new Item(oneLine(b.binding.project.name, 60), 'project', { kind: 'project', b }, 'repo', this.bound.length > 1 ? vscode.TreeItemCollapsibleState.Expanded : vscode.TreeItemCollapsibleState.None);
      items.push(...(wrap ? [kids] : kids.kids()));
    }
    return items;
  }
  /** Is this repo of the project open in the workspace? Used to dim panel-only rows. */
  mapped(b: Bound, loc: LocRef | null): vscode.Uri | null {
    if (!loc) return null;
    const m = mapPath(b.binding.folders, loc.repo, loc.path);
    const f = m && this.folderByKey.get(m.folder);
    return m && f ? vscode.Uri.joinPath(f.uri, ...m.rel.split('/')) : null;
  }

  /* ---------- virtual document for "Why?" ---------- */
  async provideTextDocumentContent(uri: vscode.Uri): Promise<string> {
    const q = new URLSearchParams(uri.query);
    const pid = q.get('pid') || '', group = q.get('group') || '', node = q.get('node') || '';
    if (!this.client || !pid || !group || !node) return 'Not connected to a Lemmata server.\n';
    try {
      const a = await this.client.analyze(pid, group, node);
      return formatWhy(a, id => this.names.get(pid + '\0' + id) || id);
    } catch (e) {
      return 'Could not load the explanation: ' + (e instanceof Error ? e.message : String(e)) + '\n';
    }
  }
}

type Data =
  | { kind: 'info' } | { kind: 'settings' }
  | { kind: 'project'; b: Bound }
  | { kind: 'alarms'; b: Bound } | { kind: 'findings'; b: Bound }
  | { kind: 'group'; b: Bound; gi: number }
  | { kind: 'check'; b: Bound; ci: number }
  | { kind: 'node'; b: Bound; n: NodeItem; groupId: string; uri: vscode.Uri | null }
  | { kind: 'finding'; b: Bound; f: FindingItem; uri: vscode.Uri | null };

let CTRL: Controller;

const STATE_LABEL: Record<TriageState, string> = { unreviewed: '', reviewed: 'reviewed', needs_fixing: 'needs fixing', ignored: 'ignored' };

class Item extends vscode.TreeItem {
  constructor(label: string, ctx: string, public data: Data, icon?: string, collapsible = vscode.TreeItemCollapsibleState.None) {
    super(label, collapsible);
    this.contextValue = ctx;
    if (icon) this.iconPath = new vscode.ThemeIcon(icon);
    if (data.kind === 'settings') this.command = { command: 'workbench.action.openSettings', title: 'Open settings', arguments: ['lemmata.project'] };
  }
  kids(): Item[] {
    const d = this.data;
    const C = vscode.TreeItemCollapsibleState;
    if (d.kind === 'project') {
      return [this.mk('Alarms (' + (d.b.model ? d.b.model.groups.reduce((s, g) => s + g.nodes.length, 0) : 0) + ')', 'alarms', { kind: 'alarms', b: d.b }, 'history', C.Expanded),
        this.mk('Findings (' + (d.b.model ? d.b.model.checks.reduce((s, c) => s + c.items.length, 0) : 0) + ')', 'findings', { kind: 'findings', b: d.b }, 'checklist', C.Expanded)];
    }
    if (d.kind === 'alarms' && d.b.model) {
      const m = d.b.model;
      if (!m.groups.length) return [new Item(m.checkpoint ? 'Nothing to recheck since ' + m.checkpoint.toUpperCase() : 'No checkpoint yet (use Set checkpoint)', 'message', { kind: 'info' }, 'pass')];
      return m.groups.map((g, gi) => new Item(g.display + ' · ' + [g.short, g.subject].filter(Boolean).join(' '), 'group', { kind: 'group', b: d.b, gi }, 'git-commit', C.Expanded));
    }
    if (d.kind === 'group' && d.b.model) {
      const g = d.b.model.groups[d.gi];
      return g.nodes.map(n => {
        const uri = CTRL.mapped(d.b, n.loc);
        const it = new Item(n.name, 'node' + (n.role === 'removed' ? '' : '-triageable-why') + (uri ? '-mapped' : ''), { kind: 'node', b: d.b, n, groupId: g.id, uri }, n.role === 'changed' ? 'edit' : n.role === 'removed' ? 'trash' : 'arrow-down');
        it.description = [n.relation, STATE_LABEL[n.triage] ? '[' + STATE_LABEL[n.triage] + ']' : '', n.loc && !uri ? '(' + hubPath(n.loc.repo, n.loc.path) + ': repo not open here)' : ''].filter(Boolean).join(' ');
        it.tooltip = n.name + '\n' + (n.loc ? hubPath(n.loc.repo, n.loc.path) + (n.loc.line ? ':' + n.loc.line : '') : '') + (n.outdated ? '\nTriage is outdated: the item changed after you triaged it.' : '');
        if (uri && n.loc) it.command = { command: 'lemmata.openItem', title: 'Open', arguments: [uri, (n.loc.line || 1) - 1] };
        return it;
      });
    }
    if (d.kind === 'findings' && d.b.model) {
      const m = d.b.model;
      if (!m.checks.length) return [new Item('No findings', 'message', { kind: 'info' }, 'pass')];
      return m.checks.map((c, ci) => new Item(c.title + ' (' + c.items.length + ')', 'check', { kind: 'check', b: d.b, ci }, 'symbol-event', C.Collapsed));
    }
    if (d.kind === 'check' && d.b.model) {
      return d.b.model.checks[d.ci].items.map(f => {
        const first = f.locs[0] || null;
        const uri = CTRL.mapped(d.b, first);
        const it = new Item(f.message, 'finding-triageable' + (uri ? '-mapped' : ''), { kind: 'finding', b: d.b, f, uri }, f.severity === 'info' ? 'info' : 'warning');
        it.description = [first ? hubPath(first.repo, first.path) + (first.line ? ':' + first.line : '') : '', STATE_LABEL[f.triage] ? '[' + STATE_LABEL[f.triage] + ']' : '', first && !uri ? '(repo not open here)' : ''].filter(Boolean).join(' ');
        it.tooltip = f.message + (f.locs.length > 1 ? '\n' + f.locs.map(l => hubPath(l.repo, l.path) + (l.line ? ':' + l.line : '')).join('\n') : '');
        if (uri && first) it.command = { command: 'lemmata.openItem', title: 'Open', arguments: [uri, (first.line || 1) - 1] };
        return it;
      });
    }
    return [];
  }
  private mk(label: string, ctx: string, data: Data, icon: string, c: vscode.TreeItemCollapsibleState) { return new Item(label, ctx, data, icon, c); }
}

/* ---------- git remotes ---------- */
function gitRemotes(cwd: string): Promise<string[]> {
  return new Promise(resolve => {
    execFile('git', ['config', '--get-regexp', '^remote\\..*\\.url$'], { cwd, timeout: 5000, windowsHide: true }, (err, stdout) => {
      resolve(err ? [] : parseGitConfigRemotes(String(stdout)));
    });
  });
}

/* ---------- commands ---------- */
function projectTarget(arg?: Item): { client: HubClient; pid: string } | null {
  const client = CTRL.clientOrNull();
  if (!client) { void vscode.window.showWarningMessage('Lemmata: connect to a server first.', 'Connect').then(a => a && vscode.commands.executeCommand('lemmata.connect')); return null; }
  const d = arg && arg.data;
  if (d && 'b' in d) return { client, pid: d.b.binding.project.id };
  return null;
}
async function pickProject(arg?: Item): Promise<{ client: HubClient; pid: string; name: string } | null> {
  const client = CTRL.clientOrNull();
  if (!client) { void vscode.window.showWarningMessage('Lemmata: connect to a server first.', 'Connect').then(a => a && vscode.commands.executeCommand('lemmata.connect')); return null; }
  const t = projectTarget(arg);
  if (t) return { ...t, name: '' };
  if (!CTRL.bound.length) { void vscode.window.showInformationMessage('Lemmata: no hub project matches this workspace. Open the project\'s GitHub clone or set "lemmata.project".'); return null; }
  if (CTRL.bound.length === 1) return { client, pid: CTRL.bound[0].binding.project.id, name: CTRL.bound[0].binding.project.name };
  const pick = await vscode.window.showQuickPick(CTRL.bound.map(b => ({ label: oneLine(b.binding.project.name, 60), pid: b.binding.project.id })), { placeHolder: 'Which Lemmata project?' });
  return pick ? { client, pid: pick.pid, name: pick.label } : null;
}
const fail = (what: string, e: unknown) => vscode.window.showErrorMessage('Lemmata: ' + what + ': ' + (e instanceof Error ? e.message : String(e)));

async function connect() {
  const cur = String(CTRL.cfg().get('serverUrl', DEFAULT_URL));
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
    await CTRL.ctx_secrets().store(TOKEN_KEY, token.trim());
    await CTRL.cfg().update('serverUrl', norm.url, vscode.ConfigurationTarget.Global);
    CTRL.resetClient();
    void vscode.window.showInformationMessage('Lemmata: connected. ' + projects.length + ' project' + (projects.length === 1 ? '' : 's') + ' on the server.');
    await CTRL.refresh();
  } catch (e) {
    if (e instanceof HubError && e.unauthorized) void vscode.window.showErrorMessage('Lemmata: the server did not accept that token. Create a new one with lemmata hub token.');
    else void fail('could not connect', e);
  }
}

function setTriage(state: TriageState) {
  return async (it?: Item) => {
    const d = it && it.data;
    if (!d || (d.kind !== 'node' && d.kind !== 'finding')) return;
    const client = CTRL.clientOrNull(); if (!client) return;
    const note = await vscode.window.showInputBox({ title: 'Lemmata: ' + STATE_LABEL[state], prompt: 'Optional note (kept in the project\'s triage file on the server)', ignoreFocusOut: true });
    if (note === undefined) return;   // Escape cancels
    try {
      if (d.kind === 'node') await client.setTriage(d.b.binding.project.id, 'node', d.n.nodeId, state, note);
      else await client.setTriage(d.b.binding.project.id, 'finding', d.f.id, state, note);
      await CTRL.refresh();
    } catch (e) { void fail('could not save triage', e); }
  };
}

export async function activate(ctx: vscode.ExtensionContext) {
  CTRL = new Controller(ctx);
  const c = vscode.commands.registerCommand;
  ctx.subscriptions.push(
    vscode.window.createTreeView('lemmata.panel', { treeDataProvider: CTRL, showCollapseAll: true }),
    vscode.workspace.registerTextDocumentContentProvider(WHY_SCHEME, CTRL),
    c('lemmata.connect', connect),
    c('lemmata.disconnect', async () => { await ctx.secrets.delete(TOKEN_KEY); CTRL.resetClient(); await CTRL.refresh(); void vscode.window.showInformationMessage('Lemmata: token removed from this computer.'); }),
    c('lemmata.refresh', () => CTRL.refresh()),
    c('lemmata.showPanel', async () => { await vscode.commands.executeCommand('workbench.view.extension.lemmata'); void CTRL.refresh(); }),
    c('lemmata.openItem', async (uri: vscode.Uri, line0: number) => {
      try { await vscode.window.showTextDocument(uri, { selection: new vscode.Range(line0, 0, line0, 0), preview: true }); }
      catch { void vscode.window.showWarningMessage('Lemmata: ' + vscode.workspace.asRelativePath(uri) + ' is not in this checkout (try Sync now, then pull).'); }
    }),
    c('lemmata.markReviewed', setTriage('reviewed')),
    c('lemmata.markNeedsFixing', setTriage('needs_fixing')),
    c('lemmata.markIgnored', setTriage('ignored')),
    c('lemmata.why', async (it?: Item) => {
      const d = it && it.data; if (!d || d.kind !== 'node') return;
      const uri = vscode.Uri.from({ scheme: WHY_SCHEME, path: '/Why ' + d.n.name.replace(/[\\/]/g, ' ') + '.diff',
        query: new URLSearchParams({ pid: d.b.binding.project.id, group: d.groupId, node: d.n.nodeId }).toString() });
      const doc = await vscode.workspace.openTextDocument(uri);
      try { await vscode.languages.setTextDocumentLanguage(doc, 'diff'); } catch { /* plain text is fine */ }
      await vscode.window.showTextDocument(doc, { preview: true });
    }),
    c('lemmata.openInLemmata', async (it?: Item) => {
      const t = await pickProject(it); if (!t) return;
      await vscode.env.openExternal(vscode.Uri.parse(CTRL.serverBase() + '/p/' + encodeURIComponent(t.pid) + '/'));
    }),
    c('lemmata.sync', async (it?: Item) => {
      const t = await pickProject(it); if (!t) return;
      await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: 'Lemmata: syncing from GitHub and Overleaf…' }, async () => {
        try {
          const r = await t.client.sync(t.pid);
          const code = r.code ? r.code.changed : !!r.changed, paper = !!(r.paper && r.paper.changed);
          const perr = r.paper && r.paper.error;
          if (perr) void vscode.window.showWarningMessage('Lemmata: Overleaf: ' + oneLine(perr, 200) + (code ? ' (code was synced)' : ''));
          else void vscode.window.showInformationMessage(code || paper ? 'Lemmata: synced' + (code ? ' code' : '') + (paper ? ' paper' : '') + ' and rescanned.' : 'Lemmata: already up to date.');
          await CTRL.refresh();
        } catch (e) { void fail('sync failed', e); }
      });
    }),
    c('lemmata.checkpoint', async (it?: Item) => {
      const t = await pickProject(it); if (!t) return;
      const note = await vscode.window.showInputBox({ title: 'Lemmata: set checkpoint', prompt: 'A note for this checkpoint (optional)', ignoreFocusOut: true });
      if (note === undefined) return;
      const ok = await vscode.window.showWarningMessage('Set a new checkpoint? Code and paper as they are on the server now become your last known good state. Alarms restart from here; older checkpoints are kept.', { modal: true }, 'Set checkpoint');
      if (ok !== 'Set checkpoint') return;
      try { await t.client.checkpoint(t.pid, note); void vscode.window.showInformationMessage('Lemmata: checkpoint set.'); await CTRL.refresh(); }
      catch (e) { void fail('could not set the checkpoint', e); }
    }),
    vscode.window.onDidChangeWindowState(s => { if (s.focused) void CTRL.refresh(); }),
    vscode.workspace.onDidSaveTextDocument(() => CTRL.scheduleSaveRefresh()),
    vscode.workspace.onDidChangeWorkspaceFolders(() => void CTRL.refresh()),
    vscode.workspace.onDidChangeConfiguration(e => {
      if (e.affectsConfiguration('lemmata.refreshSeconds')) CTRL.restartTimer();
      if (e.affectsConfiguration('lemmata')) { CTRL.resetClient(); void CTRL.refresh(); }
    }),
    ctx.secrets.onDidChange(e => { if (e.key === TOKEN_KEY) { CTRL.resetClient(); void CTRL.refresh(); } }),
    { dispose: () => CTRL.dispose() },
  );
  await CTRL.start();
}

export function deactivate() { /* disposables are registered on the context */ }
