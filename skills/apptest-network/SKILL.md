---
name: apptest-network
description: "Network and account rules audit: in-app account deletion (5.1.1(v)), third-party sign-in (4.8), IPv6 and offline, plain http, feature flags, hardcoded secrets, demo account for App Review."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - WebFetch
metadata:
  version: "1.0.0"
---

# apptest-network — network, accounts, servers

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.10 · group principles
(for dynamic trials) `../apptest/shared/test-methods.md` · report
`../apptest/shared/report.md` · rejection index (R-07, R-16, R-35, R-40, R-55).
Rule text comes from the official site EVERY TIME (principle 7):
https://developer.apple.com/app-store/review/guidelines/ ·
https://developer.apple.com/support/offering-account-deletion-in-your-app/
Talking with the user: `../apptest/shared/CONVENTIONS.md` §11 (when to ask, status lines, one next step).

**Default contract:** Reports; does not touch code, servers or accounts.
The script stays off the network. Secret keys are masked in the report (principle 17).

## When

- Accounts, sign-in, servers, sync, remote config or OTA updates are being added.
- A rejection under 5.1.1(v), 4.8 or 2.1 (crash / blank screen / demo account) arrived.
- Before release (the family head's Release mode). In an offline app the member
  marks itself "Not applicable" (only NW-15/16 remain).

## Out of scope

- The server's own security and scaling.
- Systematic testing of network errors → network-chaos (this member gives the
  rules, that member injects the faults).
- Privacy label and third-party data sharing → privacy-permissions.

## Step 0

CONVENTIONS §5 + test-methods T1/T2 (for dynamic trials). The static scan only
reads. Production servers, real accounts and real user data are NOT used.

## Member-specific principles

- **NW-P1** Sends no write requests to a production server; even reads only with
  the user's permission. Creates / deletes no real accounts; the demo account
  comes from the user and Claude does not ask for passwords.
  *Why:* risk of corrupting real user data and using up accounts and quotas.
- **NW-P2** Treats remote config and feature flags as finding candidates and asks
  the user; does not call them a "violation" on its own.
  *Why:* a feature enabled after review is grounds for 2.3.1 rejection and removal;
  but gradual rollout and A/B testing are legitimate, and the user knows the difference.

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` → `network` (network),
`account` (account), `third_party_login` (third-party sign-in), `user_content`
(user content; content on a server → content-safety), `ai` (AI; remote
model → privacy-permissions PP-30).

## Setup (good to know from the start)

1. **Is an account really needed?** Features that do not need an account must be
   usable without sign-in (5.1.1(v)). If one is needed, from day one: in-app
   **account deletion** (not just deactivation), easy to find; if Sign in with Apple
   is used, tokens are revoked on deletion (Sign in with Apple REST API).
2. **If third-party sign-in** (Google, Facebook …) is added, an equivalent sign-in
   meeting 4.8 is added too (Sign in with Apple meets those conditions).
3. **Offline design:** what is shown, saved and queued with no connection; timeouts
   and retries. Review can happen on an IPv6-only network too: no hardcoded IPv4
   addresses.
4. **https only;** ATS exceptions only for the domain that needs one, with a reason.
5. **Secret keys do not live in the app:** the app bundle can be opened;
   secret work happens on a server (e.g. an AI API through a proxy server).
6. **Feature flags:** the state during review matches the store state; an unreviewed
   feature is not switched on later (2.3.1).
7. **OTA / code updates** (Expo Updates, CodePush, Shorebird): only bug fixes and
   small changes; changing the main purpose or slipping a feature past review
   violates 2.5.2 / 2.3.1.
8. **A permanent demo account for review** and a server that stays up throughout
   review (store-readiness SR-88).

## Test (during development)

### 1. Static scan (seconds)

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-network/scripts/network_scan.py" <root> [--json]
```

| ID | Topic | Severity |
|---|---|---|
| NW-10 | Accounts can be created, no in-app deletion. Sign in with Apple, Firebase or a hosted auth service counts as creating accounts; other sign-in only as a suggestion. Deletion exists: info | REJECTION RISK (5.1.1(v)) |
| NW-11 | Third-party sign-in present, no Sign in with Apple | REJECTION RISK (4.8) |
| NW-12 | Network used, connection state not monitored | SUGGESTION (2.1) |
| NW-13 | Unencrypted `http://` (excluding local / schema / sample / test addresses) | USER BUG (1.6) |
| NW-14 | Remote config / feature flag | INFO (2.3.1, NW-P2) |
| NW-15 | Code updates from outside the app (CodePush, Expo Updates, JSPatch …) | SUGGESTION / REJECTION RISK (2.5.2) |
| NW-16 | Secret key in code (masked) | USER BUG |
| NW-17 | Accounts exist: demo account reminder for review | INFO |

The output is CANDIDATES (principle 6). When verifying: NW-10, does deletion really
delete (not sign out), is it easy to find in Settings; NW-11, does an exception
apply; NW-13, is the address really one requests go to; NW-16, is the key a sample.

### 2. Dynamic trial (principle 13; T1/T2)

The simulator uses the Mac's network; the Mac's network settings are NOT CHANGED (T4).
Routes:
- **The project's own tests:** with the HTTP client mocked / stubbed, no-connection,
  timeout, 401 / 500 scenarios.
- **Real device (done by the user):** airplane mode; Settings › Developer ›
  Network Link Conditioner (slow / lossy network).
- **IPv6-only (done by the user, optional):** connect the device through Mac Internet
  Sharing with "Create NAT64 Network"; since this is a Mac setting, only the user
  turns it on and off.

Look at: no crash or endless loading; clear messages; no data loss; the user is told
when a session expires; account deletion end to end (with a test account the user
creates, not the demo account).

## Release (before submitting)

1. **Check Apple (principle 7):** current text of 5.1.1(v), 4.8, 2.3.1, 2.5.2
   + "Last Updated"; the account deletion support page.
2. Static scan.
3. Demo account and server (with the user): does the account work, will it stay open
   during review, are any special steps in the review note.
4. Are feature flags in their store state for review (NW-P2).
5. Report.

## Report

`shared/report.md`. Secret key findings only masked. Environment:
"Apple rules: Last Updated <date>, read <today>"; if a dynamic trial was done,
by which route (mock / device).
