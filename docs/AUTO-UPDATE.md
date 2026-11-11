# The hub updates itself

After a one-time set-up, nobody runs terminal commands to deploy. A small background job on the Mac mini checks GitHub every 5 minutes. When the followed branch has new commits it:

1. fast-forwards its **own** checkout (`~/Lemmata/deploy/lemmata`, separate from `~/work/lemmata` where you and the agents work, so switching branches there no longer changes what the hub runs),
2. checks that the new code starts (imports everything, starts a throwaway hub, asks it for its status),
3. restarts the hub and waits for it to answer,
4. if it does not answer, goes back to the previous commit and restarts again,
5. writes the outcome to `~/Lemmata/hub/update.log` and, if you gave it a Slack webhook, posts it.

It never pushes, never touches `~/work/lemmata`, and only moves forward along the branch (a rewritten history is refused).

## Set up once (Mac mini)
```
cd ~/work/lemmata && git pull
cd app && uv run lemmata hub autoupdate install --branch s07-public-site --notify https://hooks.slack.com/services/XXX/YYY/ZZZ
```
`--notify` is optional. Leave `--branch` out to follow the branch that is checked out.

## Day to day
- Push (or have an agent push) to the followed branch. Within about 5 minutes the hub is running it, or you get a failure report.
- `uv run lemmata hub autoupdate status` shows what is followed and the last change. `uv run lemmata hub status` shows it too.
- `uv run lemmata hub update` runs one check now. `--force` restarts even with nothing new.
- Follow another branch: run the install command again with the new `--branch`.
- Switch it off: `uv run lemmata hub autoupdate uninstall`.

## Who does what
- **The updater** deploys. It is plain code, not an AI, so it costs nothing and does the same thing every time.
- **The CTO agent** owns failures (see `.claude/agents/cto.md`). To wake it automatically, give the updater a command to run when an update fails or is rolled back:
  ```
  uv run lemmata hub autoupdate install --on-failure '<command>'
  ```
  The command gets `LEMMATA_UPDATE_LOG` and `LEMMATA_UPDATE_RESULT` in its environment. Which command starts your CTO agent depends on how your agent team is launched on the Mac mini; that wiring was not tested here.
- **QA** still verifies before a merge. The start-up check only proves the hub starts; it does not run the test suite.

## Limits
- Only code that reaches GitHub is deployed. Uncommitted work on the Mac mini is not.
- Following a feature branch means every push to it goes live. Once S07 to S09 are approved and merged, follow `main`.
- The desktop app and the VS Code extension are not rebuilt by this.
