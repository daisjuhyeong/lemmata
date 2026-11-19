import * as vscode from 'vscode';
import * as assert from 'assert';

export async function run(): Promise<void> {
  const ext = vscode.extensions.getExtension('lemmata-local.lemmata');
  assert.ok(ext, 'extension is installed');
  await ext!.activate();
  const cmds = await vscode.commands.getCommands(true);
  for (const c of ['lemmata.connect', 'lemmata.goto', 'lemmata.refresh', 'lemmata.runs.sync', 'lemmata.setupAgent', 'lemmata.addProject', 'lemmata.openMap', 'lemmata.disconnect', 'lemmata.showPanel', 'lemmata.openSetup', 'lemmata.openWebsite', 'lemmata.row.record', 'lemmata.row.open', 'lemmata.row.tab', 'lemmata.row.site', 'lemmata.row.copy', 'lemmata.row.snooze', 'lemmata.run.attach']) assert.ok(cmds.includes(c), 'command ' + c);
  for (const gone of ['lemmata.checkpoint', 'lemmata.why', 'lemmata.markReviewed', 'lemmata.openTab.review']) assert.ok(!cmds.includes(gone), 'command ' + gone + ' left VS Code in S35');
  for (const v of ['lemmata.now', 'lemmata.experiments', 'lemmata.torun']) await vscode.commands.executeCommand(v + '.focus');
  assert.equal(vscode.workspace.getConfiguration('lemmata').get('serverUrl'), 'http://100.111.135.94:8765');
  console.log('host smoke test ok');
}
