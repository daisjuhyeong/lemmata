---
type: handoff
owner_agent: lead
status: needs-qa
sources: ["founder chat 2026-11-13 14:18 KST"]
last_reviewed: 2026-11-13
---
# S22-01: add a project from anywhere, on any branch

Asked by Juhyeong (chat, 2026-11-13 14:18 KST): "I don't want to access the Mac mini every time a new project is
created." Trigger: temporal_dependency, whose work is on branch `short-exp`, while New project always followed the
default branch.

## What changed
- **Hub:** `GET /api/hub/github/branches?repo=owner/name` lists a repository's branches, newest commit first, with
  the default marked (`hub/github.py: branches`). Repo names are checked; a repository GitHub does not show gives 404.
- **New project form:** after picking the code repository, a "Branch to follow" select (default branch selected).
  When another branch has newer commits it says so, with a one-click "Follow <branch>". Create sends that branch.
- **VS Code 0.5.0:** command **Lemmata: Add This Repository to Lemmata**. The status bar's "Lemmata: no project" and
  the panel's new "Add this repository to Lemmata…" item run it. It finds GitHub remotes in the open folders that are
  not projects yet, asks which branch to follow (the one checked out here, or the default), warns if that branch is
  not pushed, and creates the project with the extension's own token (no Mac mini, no browser).
- Fixed: the S19 version bump had replaced "0.3.0" everywhere in `vscode/package-lock.json`, changing the recorded
  versions of `asynckit` and `unicorn-magic`. The lock file is restored from before S19, with only the extension's
  own version set (0.5.0). `npm ci` and all tests pass with it.

## Verified
Python 173 passed / 2 skipped (fake GitHub now serves branches; `test_github_flow_owner_and_repos` checks order,
default flag, bad names, unknown repo); extension unit 67 (new `unmatchedRepos` test); end-to-end 9/9. Browser on
the mock hub: the select lists short-exp, experiment-reference, main (default); "Follow short-exp" sends
`branch: "short-exp"`.

## Not verified
- The VS Code command against a real hub and a real private repository (clone time, unpushed-branch message).
- Per-branch commit dates on a repository with many branches (one GitHub request per branch, capped at 30).
