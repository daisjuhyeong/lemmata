import * as vscode from 'vscode';
import * as assert from 'assert';

export async function run(): Promise<void> {
  const ext = vscode.extensions.getExtension('lemmata-local.lemmata');
  assert.ok(ext, 'extension is installed');
  await ext!.activate();
  const cmds = await vscode.commands.getCommands(true);
  for (const c of ['lemmata.connect', 'lemmata.refresh', 'lemmata.sync', 'lemmata.checkpoint', 'lemmata.why', 'lemmata.markReviewed', 'lemmata.openInLemmata', 'lemmata.runs.sync', 'lemmata.runs.refresh', 'lemmata.setupAgent', 'lemmata.openTab', 'lemmata.openTab.review', 'lemmata.openTab.claims', 'lemmata.openTab.experiments', 'lemmata.openTab.setup']) assert.ok(cmds.includes(c), c);
  assert.equal(vscode.workspace.getConfiguration('lemmata').get('serverUrl'), 'http://100.111.135.94:8765');
  console.log('host smoke test ok');
}
