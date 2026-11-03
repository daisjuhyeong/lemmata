#!/usr/bin/env python3
"""Post agent reports to Slack through an incoming webhook.

  python3 tools/report/slack.py flush    # post wiki/reports/outbox/*.md, move them to wiki/reports/sent/YYYY-MM/
  python3 tools/report/slack.py digest   # daily summary from wiki/log.md + reports sent today + open questions
  python3 tools/report/slack.py test     # one test message

Webhook URL: $LEMMATA_SLACK_WEBHOOK, else ~/.config/lemmata/slack_webhook. With neither, messages are printed only.
Run as a Claude Code hook it must never fail the session, so every error is printed and the exit code is 0.
Standard library only.
"""
import datetime as dt, json, os, pathlib, re, shutil, subprocess, sys, urllib.request

ROOT = pathlib.Path(os.environ.get('CLAUDE_PROJECT_DIR') or pathlib.Path(__file__).resolve().parents[2])
OUTBOX, SENT, LOG = ROOT / 'wiki/reports/outbox', ROOT / 'wiki/reports/sent', ROOT / 'wiki/log.md'
TAGS = {'approval': '[승인 필요]', 'blocked': '[막힘]', 'done': '[완료]', 'weekly': '[주간]', 'daily': '[일일 요약]'}
REPO = 'https://github.com/daisjuhyeong/lemmata'


def branch():
    try:
        return subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True, text=True, timeout=5).stdout.strip() or 'main'
    except Exception:
        return 'main'


def webhook():
    url = os.environ.get('LEMMATA_SLACK_WEBHOOK')
    f = pathlib.Path.home() / '.config/lemmata/slack_webhook'
    if not url and f.exists():
        url = f.read_text().strip()
    return url or None


def post(text):
    url = webhook()
    if not url:
        print('[slack dry-run]\n' + text + '\n'); return True
    req = urllib.request.Request(url, data=json.dumps({'text': text}).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception as e:
        print(f'[slack] post failed: {e}', file=sys.stderr); return False


def parse(path):
    raw = path.read_text()
    meta, body = {}, raw
    m = re.match(r'^---\n(.*?)\n---\n?(.*)$', raw, re.S)
    if m:
        body = m.group(2)
        for line in m.group(1).splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                meta[k.strip()] = re.sub(r'\s+#.*$', '', v).strip()
    return meta, body.strip()


def render(path):
    meta, body = parse(path)
    kind = meta.get('report_type', 'done')
    title, lines, question, in_q = path.stem, [], [], False
    for line in body.splitlines():
        if line.startswith('# ') and title == path.stem:
            title = line[2:].strip(); continue
        if line.startswith('## '):
            in_q = '결정' in line or '질문' in line; continue
        if line.strip():
            (question if in_q else lines).append(line.rstrip())
    out = [f"*{TAGS.get(kind, '[보고]')} {meta.get('owner_agent', '?')} · {title}*"]
    out += [re.sub(r'^\s*[-*]\s+', '• ', l) for l in lines[:8]]
    q = ' '.join(x.lstrip('-* ').strip() for x in question)
    if q and q != '없음':
        out.append(f'*결정 필요:* {q}')
    links = [x.strip() for x in meta.get('links', '').strip('[]').split(',') if x.strip()]
    if meta.get('task'):
        links.insert(0, f"{REPO}/blob/{branch()}/{meta['task']}")
    if links:
        out.append('링크: ' + ' | '.join(links[:3]))
    return '\n'.join(out)


def flush():
    if not OUTBOX.exists():
        return
    for f in sorted(OUTBOX.glob('*.md')):
        if f.name == 'README.md':
            continue
        if post(render(f)) and webhook():
            dest = SENT / dt.date.today().strftime('%Y-%m'); dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), dest / f.name)


def digest():
    today = dt.date.today().isoformat()
    log = [l for l in LOG.read_text().splitlines() if l.startswith(today)] if LOG.exists() else []
    sent = sorted((SENT / today[:7]).glob(f'{today}*.md')) if (SENT / today[:7]).exists() else []
    waiting = [f for f in sorted(OUTBOX.glob('*.md')) if f.name != 'README.md'] if OUTBOX.exists() else []
    opened = []
    for f in sorted(SENT.glob('*/*.md')) if SENT.exists() else []:
        meta, _ = parse(f)
        if meta.get('report_type') in ('approval', 'blocked') and meta.get('status') != 'resolved':
            opened.append(f)
    out = [f'*[일일 요약] {today}*', f'• 작업 기록 {len(log)}건, 보고 {len(sent)}건 전송, 미전송 {len(waiting)}건']
    for l in log[:8]:
        parts = [p.strip() for p in l.split('|')]
        if len(parts) >= 5:
            out.append(f'• {parts[1]}: {parts[4][:90]}')
    if opened:
        out.append(f'*답을 기다리는 것 {len(opened)}건:* ' + ', '.join(f.stem[16:] for f in opened[:5]))
    post('\n'.join(out))


if __name__ == '__main__':
    try:
        cmd = sys.argv[1] if len(sys.argv) > 1 else 'flush'
        {'flush': flush, 'digest': digest, 'test': lambda: post('*[테스트]* Lemmata 보고 채널 연결 확인')}[cmd]()
    except Exception as e:
        print(f'[slack] {e}', file=sys.stderr)
    sys.exit(0)
