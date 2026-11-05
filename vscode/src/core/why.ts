import { Analysis } from './types';
import { clean, oneLine } from './text';

/** Plain-text body of the read-only "Why?" document: explanation, chain, diffs. All repo text is cleaned. */
export function formatWhy(a: Analysis, nameOf: (id: string) => string): string {
  const L: string[] = [];
  L.push('Lemmata: why is this flagged?');
  L.push('Quoted text below is data from your repository, shown as plain text.');
  L.push('');
  L.push(clean(a.explanation, 2000));
  L.push('');
  L.push('Chain (from the changed item to this one):');
  const nodes = (a.chain && a.chain.nodes) || [];
  nodes.forEach((n, i) => L.push('  ' + (i + 1) + '. ' + oneLine(nameOf(n), 120)));
  for (const d of a.diffs || []) {
    L.push('');
    L.push('Diff: ' + oneLine(d.repo + '/' + d.path, 200) + '  (' + oneLine(d.from_label || 'checkpoint', 40) + ' -> ' + oneLine(d.to_label || 'now', 40) + ')');
    if (d.binary) L.push('(binary file)');
    else L.push(clean(d.unified, 60000).replace(/\n$/, ''));
    if (d.truncated) L.push('(diff cut at 400 lines)');
  }
  return L.join('\n') + '\n';
}
