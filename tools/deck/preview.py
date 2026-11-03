#!/usr/bin/env python3
"""Render a deck (deck.json + slides/*.html) to PNGs and one contact sheet, and flag overflow.

usage: python3 tools/deck/preview.py <deck>/project [--out <dir>]
needs: pip install playwright pillow && python3 -m playwright install chromium
Images referenced as /_blob/<hash> are drawn as grey placeholders (they live in the published artifact).
"""
import argparse, json, pathlib, re
from playwright.sync_api import sync_playwright
from PIL import Image

CSS = ("*{margin:0;box-sizing:border-box}section{width:1920px;height:1080px;position:relative;overflow:hidden}"
       "table{border-collapse:collapse;width:100%}td,th{padding:12px 16px;text-align:left;border-bottom:1px solid #ccc;"
       "vertical-align:top}th{font-weight:600}img[src^='/_blob']{background:#ddd}")
CHECK = """() => { const s = document.querySelector('section'); let bottom = 0, small = 0;
  for (const e of s.querySelectorAll('*')) { if (e.closest('[style*="position:absolute"]')) continue;
    const b = e.getBoundingClientRect(); bottom = Math.max(bottom, b.bottom);
    const fs = parseFloat(getComputedStyle(e).fontSize); const own = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()); if (own && fs < 24) small++; }
  let clipped = 0; for (const e of s.querySelectorAll('*')) { const b = e.getBoundingClientRect();
    if (b.width && (b.right > 1920 || b.bottom > 1080 || b.left < 0)) clipped++;
    if (e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflow !== 'visible') clipped++; }
  const font = document.fonts.check('24px "IBM Plex Sans KR"');
  return {clipped, font, bottom: Math.round(bottom), small, footer: !!s.querySelector('[style*="position:absolute"][style*="bottom"]')}; }"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    proj = pathlib.Path(a.project)
    out = pathlib.Path(a.out or proj.parent / 'preview')  # gitignored; out.mkdir(parents=True, exist_ok=True)
    deck = json.loads((proj / 'deck.json').read_text())
    order = deck['order']
    fonts = ''.join(f'<link rel="stylesheet" href="{f["href"]}">' for f in deck.get('faces', {}).values())
    pngs, problems = [], []
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={'width': 1920, 'height': 1080})
        for i, sid in enumerate(order, 1):
            f = proj / 'slides' / f'{sid}.html'
            if not f.exists():
                problems.append(f'{i:02d} {sid}: file missing'); continue
            html = re.sub(r'<aside>[\s\S]*?</aside>', '', f.read_text())
            pg.set_content(f'{fonts}<style>{CSS}</style>{html}', wait_until='load')
            pg.wait_for_timeout(300)
            r = pg.evaluate(CHECK)
            if r['bottom'] > (945 if r['footer'] else 1010): problems.append(f'{i:02d} {sid}: content reaches y={r["bottom"]} (footer zone starts ~945)')
            if r['clipped']: problems.append(f'{i:02d} {sid}: {r["clipped"]} elements cut off at the frame or their box')
            if not r['font'] and not any('font' in x for x in problems): problems.append('webfont IBM Plex Sans KR not loaded (offline?): line breaks are approximate')
            if r['small']: problems.append(f'{i:02d} {sid}: {r["small"]} text elements under 24px')
            p = out / f'{i:02d}_{sid}.png'; pg.screenshot(path=str(p)); pngs.append(p)
        b.close()
    cols, w, h = 3, 640, 360
    sheet = Image.new('RGB', (cols * w, ((len(pngs) + cols - 1) // cols) * h), '#888888')
    for k, p in enumerate(pngs):
        sheet.paste(Image.open(p).resize((w, h)), ((k % cols) * w, (k // cols) * h))
    sheet.save(out / 'contact_sheet.png')
    print(f'{len(pngs)} slides -> {out}/contact_sheet.png')
    print('\n'.join(problems) if problems else 'no overflow or small-text problems found')


if __name__ == '__main__':
    main()
