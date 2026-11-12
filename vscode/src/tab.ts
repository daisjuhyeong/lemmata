// The Lemmata tab: the hub's own pages (Review, Claims tree, Experiments, ...) inside VS Code.
// The page is built from the hub's files and runs with no network access. Its requests come here as messages, are
// checked (core/embed.ts) and sent to the hub with the stored token, so it also works over Remote-SSH, where only the
// extension can reach the hub. The token never enters the page.
import * as vscode from 'vscode';
import * as fs from 'fs/promises';
import * as os from 'os';
import * as path from 'path';
import { randomBytes } from 'crypto';
import { HubClient, HubError } from './core/client';
import { ASSETS, FONT_DIR, KATEX_FONT_DIR, TAB_FONTS, View, VIEWS, allowedRequest, buildPage, fontNames, inlineFonts, openKind, suggestedName } from './core/embed';

export interface TabHost {
  log(msg: string): void;
  /** Open a hub file location (repo "code" or "paper", repo-relative path) in the editor; false when it is not in this workspace. */
  openLocation(pid: string, repo: string, rel: string, line: number): Promise<boolean>;
  /** Called after the page changed something on the hub, so the panel and warnings can refresh. */
  hubChanged(): void;
}

interface Open { panel: vscode.WebviewPanel; client: HubClient; pid: string; ready: boolean; want: View | null }

export class LemmataTab {
  private readonly tabs = new Map<string, Open>();      // project id -> its tab
  private assets: { base: string; parts: { katexJs: string; appJs: string; researchJs: string; katexCss: string; appCss: string; tokensCss: string } } | null = null;

  constructor(private readonly ctx: vscode.ExtensionContext, private readonly host: TabHost) { }

  async open(client: HubClient, base: string, pid: string, name: string, view?: View) {
    const cur = this.tabs.get(pid);
    if (cur) {
      cur.panel.reveal(undefined, false);
      if (view) { if (cur.ready) void cur.panel.webview.postMessage({ t: 'view', k: view }); else cur.want = view; }
      return;
    }
    const panel = vscode.window.createWebviewPanel('lemmata.tab', name ? 'Lemmata: ' + name : 'Lemmata', vscode.ViewColumn.Active,
      { enableScripts: true, retainContextWhenHidden: true, localResourceRoots: [] });
    const o: Open = { panel, client, pid, ready: false, want: view || null };
    this.tabs.set(pid, o);
    panel.onDidDispose(() => { if (this.tabs.get(pid) === o) this.tabs.delete(pid); }, null, this.ctx.subscriptions);
    panel.webview.onDidReceiveMessage(m => { void this.onMessage(o, m); }, null, this.ctx.subscriptions);
    panel.webview.html = this.note('Loading Lemmata…');
    try {
      const parts = await this.load(client, base);
      const embedJs = await fs.readFile(path.join(this.ctx.extensionPath, 'media', 'embed.js'), 'utf8');
      const vscodeCss = await fs.readFile(path.join(this.ctx.extensionPath, 'media', 'vscode.css'), 'utf8');
      panel.webview.html = buildPage({ nonce: randomBytes(16).toString('hex'), pid, embedJs, vscodeCss, site: base.replace(/\/+$/, '') + '/p/' + encodeURIComponent(pid) + '/', ...parts });
    } catch (e) {
      const offline = e instanceof HubError && e.offline;
      panel.webview.html = this.note(offline ? 'Your Lemmata hub cannot be reached from this machine. Check the connection, then close this tab and open it again.'
        : e instanceof HubError && e.code === 'old_hub' ? 'Your Lemmata hub is older than this extension and cannot be shown here yet. Update the hub (on the Mac mini: lemmata hub update), then open this tab again.'
        : 'The Lemmata pages could not be loaded from the hub (' + (e instanceof HubError ? 'HTTP ' + e.status : 'error') + ').');
      if (!(e instanceof HubError && e.offline)) this.assets = null;
      this.host.log('tab: loading the pages failed: ' + (e instanceof HubError ? e.status + ' ' + e.code : String(e)));
    }
  }

  /** Forget the pages fetched from the hub (after reconnecting, or a hub update). */
  reset() { this.assets = null; }
  closeAll() { for (const o of [...this.tabs.values()]) o.panel.dispose(); }

  private note(text: string): string {
    const esc = text.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string));
    return '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"></head>' +
      '<body style="font: 14px sans-serif; padding: 24px;">' + esc + '</body></html>';
  }

  private async load(client: HubClient, base: string) {
    if (this.assets && this.assets.base === base) return this.assets.parts;
    const text = async (p: string) => {
      const r = await client.raw('GET', p, undefined, 8 * 1024 * 1024, 30000);
      if (r.status !== 200) throw new HubError(r.status, 'asset', 'could not load ' + p);
      return r.data.toString('utf8');
    };
    const [appJs, researchJs, appCss, katexJs, katexCssRaw] = await Promise.all([text(ASSETS.appJs), text(ASSETS.researchJs), text(ASSETS.appCss), text(ASSETS.katexJs), text(ASSETS.katexCss)]);
    if (!appJs.includes('LEMMATA_EMBED')) throw new HubError(426, 'old_hub', 'the hub is older than this extension');
    const fonts: { [name: string]: string } = {};
    await Promise.all(fontNames(katexCssRaw).map(async n => {
      try { const r = await client.raw('GET', KATEX_FONT_DIR + n, undefined, 2 * 1024 * 1024, 30000); if (r.status === 200) fonts[n] = r.data.toString('base64'); } catch { /* math falls back to a system font */ }
    }));
    // S18: the hub's tokens and headline font. An older hub has neither: the tab then keeps that hub's own look.
    let tokensCss = '';
    try {
      const [tokens, fontsRaw] = await Promise.all([text(ASSETS.tokensCss), text(ASSETS.fontsCss)]);
      const own: { [name: string]: string } = {};
      await Promise.all(fontNames(fontsRaw).filter(n => TAB_FONTS.test(n)).map(async n => {
        try { const r = await client.raw('GET', FONT_DIR + n, undefined, 2 * 1024 * 1024, 30000); if (r.status === 200) own[n] = r.data.toString('base64'); } catch { /* headings fall back to Georgia */ }
      }));
      tokensCss = tokens + '\n' + inlineFonts(fontsRaw, own);
    } catch { /* keep the hub's own stylesheet */ }
    const parts = { katexJs, appJs, researchJs, katexCss: inlineFonts(katexCssRaw, fonts), appCss, tokensCss };
    this.assets = { base, parts };
    return parts;
  }

  private async onMessage(o: Open, m: any) {
    if (!m || typeof m !== 'object') return;
    try {
      if (m.t === 'fetch') return await this.onFetch(o, m);
      if (m.t === 'ready') { o.ready = true; if (o.want) { void o.panel.webview.postMessage({ t: 'view', k: o.want }); o.want = null; } return; }
      if (m.t === 'external' && typeof m.url === 'string' && /^https?:\/\//i.test(m.url)) { await vscode.env.openExternal(vscode.Uri.parse(m.url, true)); return; }
      if (m.t === 'openFile') {
        const ok = await this.host.openLocation(o.pid, String(m.repo || ''), String(m.path || ''), Number(m.line) || 1);
        if (!ok) void vscode.window.showInformationMessage('Lemmata: that file is not in a folder open in this window.');
        return;
      }
      if (m.t === 'open' && typeof m.path === 'string') return await this.onOpen(o, m.path);
    } catch (e) { this.host.log('tab: ' + String(m.t) + ' failed: ' + (e instanceof HubError ? e.status + ' ' + e.code : e instanceof Error ? e.message : String(e))); }
  }

  private async onFetch(o: Open, m: any) {
    const id = m.id;
    const ok = allowedRequest(o.pid, m.method, m.path);
    if (!ok) { void o.panel.webview.postMessage({ t: 'reply', id, error: 'This page can only talk to its own project on your Lemmata hub.' }); return; }
    try {
      let body: { contentType: string; data: string | Uint8Array } | undefined;
      if (ok.method !== 'GET' && (typeof m.bodyText === 'string' || typeof m.bodyB64 === 'string')) {
        const ct = typeof m.contentType === 'string' && /^[\w.+-]+\/[\w.+-]+(;\s*charset=[\w-]+)?$/.test(m.contentType) ? m.contentType : 'application/json';
        body = { contentType: ct, data: typeof m.bodyB64 === 'string' ? Buffer.from(m.bodyB64, 'base64') : m.bodyText };
      }
      const r = await o.client.raw(ok.method, ok.path, body);
      void o.panel.webview.postMessage({ t: 'reply', id, status: r.status, contentType: r.contentType, b64: r.data.toString('base64') });
      if (ok.method !== 'GET' && r.status < 300 && !ok.path.startsWith('/api/hub/events')) this.host.hubChanged();
    } catch (e) {
      void o.panel.webview.postMessage({ t: 'reply', id, error: e instanceof HubError ? e.message : 'The request failed.' });
    }
  }

  /** A hub file the user clicked: pictures open in an editor tab, text opens as a new document, anything else is saved. */
  private async onOpen(o: Open, p: string) {
    const ok = allowedRequest(o.pid, 'GET', p);
    if (!ok) return;
    const r = await o.client.raw('GET', ok.path);
    if (r.status !== 200) { void vscode.window.showWarningMessage('Lemmata: the hub could not provide that file (HTTP ' + r.status + ').'); return; }
    const kind = openKind(ok.path, r.contentType);
    const name = suggestedName(ok.path, r.contentType);
    if (kind === 'text') {
      const lang = /\.md$|markdown/.test(name + r.contentType) ? 'markdown' : /json/.test(name + r.contentType) ? 'json' : 'plaintext';
      const doc = await vscode.workspace.openTextDocument({ content: r.data.toString('utf8'), language: lang });
      await vscode.window.showTextDocument(doc, { preview: true, viewColumn: vscode.ViewColumn.Beside });
      return;
    }
    if (kind === 'image') {
      const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'lemmata-'));
      const file = path.join(dir, name);
      await fs.writeFile(file, r.data);
      await vscode.commands.executeCommand('vscode.open', vscode.Uri.file(file), { preview: true, viewColumn: vscode.ViewColumn.Beside });
      return;
    }
    const target = await vscode.window.showSaveDialog({ defaultUri: vscode.Uri.file(path.join(os.homedir(), name)), title: 'Save from Lemmata' });
    if (!target) return;
    await vscode.workspace.fs.writeFile(target, r.data);
    void vscode.window.showInformationMessage('Lemmata: saved ' + path.basename(target.fsPath) + '.');
  }
}

export const isView = (v: unknown): v is View => typeof v === 'string' && (VIEWS as readonly string[]).includes(v);
