import { Alarms, Analysis, Findings, Graph, HubProject, Triage } from './types';

export class HubError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); this.name = 'HubError'; }
  get offline(): boolean { return this.status === 0; }
  get unauthorized(): boolean { return this.status === 401 || this.status === 403; }
}

/** Minimal Bearer client. The token is only ever placed in the Authorization header: it is not in URLs, messages or logs. */
export class HubClient {
  constructor(private readonly base: string, private readonly token: string, private readonly timeoutMs = 15000) {
    const u = new URL(base);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') throw new Error('server URL must be http(s)');
    this.base = u.origin;
  }

  private async req<T>(method: 'GET' | 'POST', path: string, body?: unknown, timeoutMs = this.timeoutMs): Promise<T> {
    if (!path.startsWith('/')) throw new Error('bad path');
    const headers: Record<string, string> = { Authorization: 'Bearer ' + this.token, Accept: 'application/json' };
    let data: string | undefined;
    if (body !== undefined) { headers['Content-Type'] = 'application/json'; data = JSON.stringify(body); }
    let r: Response;
    try {
      r = await fetch(this.base + path, { method, headers, body: data, redirect: 'error', signal: AbortSignal.timeout(timeoutMs) });
    } catch (e) {
      throw new HubError(0, 'offline', 'Cannot reach the Lemmata server at ' + this.base + '.');
    }
    let j: any = null;
    try { j = await r.json(); } catch { /* no JSON body */ }
    if (!r.ok) {
      const msg = j && j.error && typeof j.error.message === 'string' ? j.error.message.slice(0, 300) : 'HTTP ' + r.status;
      throw new HubError(r.status, (j && j.error && j.error.code) || 'http_' + r.status, msg);
    }
    return j as T;
  }

  /**
   * One request whose body is returned as bytes, whatever the status (for the Lemmata tab, which shows the hub's own pages).
   * `path` must already be checked by the caller (core/embed.ts). Bodies larger than `maxBytes` are refused.
   */
  async raw(method: 'GET' | 'POST' | 'PUT' | 'DELETE', path: string, body?: { contentType: string; data: string | Uint8Array }, maxBytes = 25 * 1024 * 1024,
    timeoutMs = 120000): Promise<{ status: number; contentType: string; data: Buffer }> {
    if (!path.startsWith('/') || path.startsWith('//')) throw new Error('bad path');
    const headers: Record<string, string> = { Authorization: 'Bearer ' + this.token };
    if (body) headers['Content-Type'] = body.contentType;
    let r: Response;
    try {
      r = await fetch(this.base + path, { method, headers, body: body ? body.data : undefined, redirect: 'error', signal: AbortSignal.timeout(timeoutMs) });
    } catch (e) {
      throw new HubError(0, 'offline', 'Cannot reach the Lemmata server at ' + this.base + '.');
    }
    const len = Number(r.headers.get('content-length') || 0);
    if (len > maxBytes) throw new HubError(r.status, 'too_large', 'The answer is too large to show here.');
    const data = Buffer.from(await r.arrayBuffer());
    if (data.length > maxBytes) throw new HubError(r.status, 'too_large', 'The answer is too large to show here.');
    return { status: r.status, contentType: r.headers.get('content-type') || '', data };
  }

  /** Add a project from a GitHub repository (the hub clones it, which can take a few minutes). */
  createProject = async (repo: string, branch: string | null, name: string): Promise<HubProject> => {
    const r = await this.req<any>('POST', '/api/hub/projects', { code_repo: repo, branch: branch || undefined, name }, 600000);
    return (r && r.project) || r;
  };
  projects = async (): Promise<HubProject[]> => (await this.req<{ projects: HubProject[] }>('GET', '/api/hub/projects')).projects || [];
  private p(pid: string, rest: string) { return '/p/' + encodeURIComponent(pid) + '/api/' + rest; }
  alarms = (pid: string) => this.req<Alarms>('GET', this.p(pid, 'alarms'));
  findings = (pid: string) => this.req<Findings>('GET', this.p(pid, 'findings'));
  graph = (pid: string) => this.req<Graph>('GET', this.p(pid, 'graph'));
  triage = (pid: string) => this.req<Triage>('GET', this.p(pid, 'triage'));
  analyze = (pid: string, group: string, node: string) =>
    this.req<Analysis>('GET', this.p(pid, 'analyze?group=' + encodeURIComponent(group) + '&node=' + encodeURIComponent(node)));
  setTriage = (pid: string, type: 'node' | 'finding', id: string, state: string, note: string) =>
    this.req<unknown>('POST', this.p(pid, 'triage'), { target_type: type, target_id: id, state, note });
  runs = (pid: string) => this.req<{ runs: unknown[]; counts: Record<string, number> }>('GET', this.p(pid, 'runs'));
  postRuns = (pid: string, runs: unknown[]) => this.req<{ added: number; updated: number; total: number }>('POST', this.p(pid, 'runs'), { runs });
  checkpoint = (pid: string, note: string) => this.req<unknown>('POST', this.p(pid, 'checkpoints'), { note, at: null });
  sync = (pid: string) => this.req<{ changed?: boolean; code?: { changed: boolean }; paper?: { changed: boolean; error?: string } }>('POST', '/api/hub/projects/' + encodeURIComponent(pid) + '/sync', {});
}
