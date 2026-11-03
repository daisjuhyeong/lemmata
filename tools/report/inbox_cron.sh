#!/bin/zsh
# Optional: check Slack replies automatically. Runs Claude Code headless with /inbox, only when an open report exists,
# so idle runs cost nothing. Add to crontab (every 30 min, 9-23h):
#   */30 9-23 * * * ~/work/lemmata/tools/report/inbox_cron.sh >> /tmp/lemmata-inbox.log 2>&1
cd "${0:A:h}/../.." || exit 0
open=$(python3 tools/report/slack.py open 2>/dev/null | tail -1)
[ -z "$open" ] || [ "$open" = "0" ] && exit 0
echo "$(date '+%F %T') open=$open"
claude -p "/inbox" --permission-mode acceptEdits
python3 tools/report/slack.py flush
