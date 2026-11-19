---
type: handoff
owner_agent: lead
status: needs-qa
sources:
  - "founder message in chat, 2026-11-20 00:24 KST: 'Why is it that I have to re-sign into github all the time?'"
  - "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps (fetched 2026-11-20): an OAuth app can be set to expiring tokens; the access token then lasts eight hours and comes with a refresh token that lasts six months without use; the device flow answers with refresh_token, expires_in and refresh_token_expires_in; a token from the device flow is refreshed with client_id, grant_type=refresh_token and the refresh token, no secret; a refresh token works once; at most ten tokens per user, app and scope"
  - "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/token-expiration-and-revocation (fetched 2026-11-20): other ways a token ends (revoked by the user, unused for a year, more than ten for one app and scope)"
  - "code on branch s30-baselines: app/src/lemmata/hub/{github,auth,routes,projects}.py, app/tests/{test_hub.py,fake_github.py}, app/src/lemmata/web/research.js"
last_reviewed: 2026-11-20
---
# S31-02: the hub renews a GitHub sign-in that GitHub ends after eight hours

## Question
Juhyeong has to sign in to GitHub in Lemmata again and again.

## What the code did
- Browser sessions are not the cause: they are kept on disk (`hub/tokens.json`), the cookie lasts a year, and no new
  sign-in revokes an older session.
- The hub keeps one GitHub token per account. At sign-in it read `access_token` from GitHub's answer and nothing else.
  If the GitHub app is set to **expiring tokens**, that answer also carries `expires_in` (eight hours) and a
  `refresh_token`. The hub dropped both, so eight hours later GitHub answered 401, the hub marked the account
  "needs a new sign-in", and the site asked again.
- Whether Lemmata's GitHub app has that setting cannot be read from here (it is in the app's settings on GitHub, and
  the hub's saved record is on the Mac mini). It is the one cause in the code that produces "all the time".

## What changed
- `poll` keeps the refresh token and the two expiry times with the saved sign-in.
- `token()` renews the pair when ten minutes or less are left. A 401 on a GitHub API call renews once and asks again.
  One renewal at a time (a refresh token works once); a renewal made a moment ago is not repeated.
- Only when GitHub refuses the refresh token itself is the account marked as needing a sign-in. When GitHub cannot be
  reached, nothing is marked and the next request tries again.
- A sign-in that does not expire is left exactly as before.
- `/api/hub/status` says, per account, whether the sign-in expires, whether the hub renews it and how often it has.
  Settings → About → "GitHub sign-in" puts that in a sentence, so the cause is confirmed after the next sign-in.

## Verified
- 226 tests pass (2 new in `test_hub`; the fake GitHub now issues expiring tokens and one-time refresh tokens):
  renewed before expiry; renewed after a 401; not spent twice; kept when GitHub is unreachable; marked only when the
  refresh token is refused; cleared by a new sign-in; a non-expiring sign-in untouched.

## Not verified
- Against GitHub itself, and on the Mac mini hub. The record saved there today has no refresh token (the old code
  dropped it), so **one more sign-in is needed after the hub updates**; from then on it renews.
- That expiring tokens is in fact the cause. If Settings then says "does not run out by itself" and the prompt still
  comes back, the cause is elsewhere: the wording of the prompt tells which (reconnect GitHub, public repositories
  only, or connect this device).

## Other things found, not changed
- A new sign-in replaces the account's saved token and its scope. Choosing "public repositories only" on any browser
  lowers the access of the whole account on the hub. The default is private, so this needs a deliberate click.
- A sign-in that is in progress when the hub restarts (an update) is lost and has to be started again.
