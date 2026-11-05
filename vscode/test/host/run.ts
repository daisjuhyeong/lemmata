// Extension-host smoke test (optional): downloads VS Code, loads the extension, checks activation + commands.
import * as path from 'path';
import { runTests } from '@vscode/test-electron';

async function main() {
  const root = path.resolve(__dirname, '../../..');
  await runTests({ extensionDevelopmentPath: root, extensionTestsPath: path.resolve(__dirname, 'suite.js'),
    launchArgs: ['--disable-extensions', '--disable-gpu', '--no-sandbox'] });
}
main().catch(e => { console.error(String(e)); process.exit(1); });
