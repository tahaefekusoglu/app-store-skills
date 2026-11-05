---
name: apptest-network-chaos
description: "Tests behaviour on a bad network: slow, hanging or dropped connections, 5xx, bad responses, 401, 429; endless spinner, data loss, double records. Uses a mock or local proxy, never production. Use for network chaos and offline tests."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-network-chaos — behaviour on a bad network

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.3 · group principles
`../apptest/shared/test-methods.md` (T1–T10) · rule member network
(NW-12 connection monitoring, NW-13 plain http) · related rapid-input
(RI-S9 double record on retry) · report `../apptest/shared/report.md`.

**Default contract:** Scans, provides scenarios and templates, runs the proxy only
in front of a mock / staging server the user names; writes tests into the project
only with approval. Adds no hooks to app code (T3); if the base URL cannot be
changed, suggests that once.

## When to use

- The app connects to a server (profile: `network`).
- A report like "won't open without internet / spins forever / what I sent is gone".
- The network layer, authentication or offline queue changed.
- Before release: the review network may be restricted (2.1).

## Out of scope

- Whether connectivity is monitored, plain http, account deletion → network (rule
  member). This member INJECTS the error and sees the result.
- Double records from double taps → rapid-input; retry duplication in NC-S8 / S9 is
  the same finding in both members, written once.
- The server's own resilience (load testing): out of scope.

## Step 0

CONVENTIONS §5. Unit level takes seconds; a proxy tour takes minutes per scenario
(§6). The proxy runs in the background; it is tracked with a PID file and stopped by
PID. If a finding touches an App Store rule (crash on launch with no network → 2.1),
principle 7 applies: the rule's current text is read.

## Principles specific to this member

- **NC-P1** Faults are injected only into a mock or staging server / local proxy;
  never production.
  *Why:* it affects real users. `nc_proxy.py` does not run against a server whose
  name does not look like mock / staging without `--confirm-nonprod`; that
  confirmation is given only if the user says "not production".
- **NC-P2** Does not touch the Mac's network: Wi-Fi, Network Link Conditioner, DNS,
  and proxy settings are NOT CHANGED; the network is broken only in the app's client
  (mock) or at the address the app connects to (proxy).
  *Why:* T4; the simulator uses the Mac's network, breaking it breaks all the user's
  work and goes unnoticed if forgotten. Manual paths are suggested to the user, who
  does them.
- **NC-P3** "No network" and "server unreachable" are separate states and are named
  separately.
  *Why:* the proxy refusing a connection looks "connected" to a connectivity monitor
  (NWPathMonitor); the real offline UI (cache, offline banner) only appears with
  `notConnectedToInternet` in a mock or by hand with airplane mode.
- **NC-P4** Every finding carries which fault was given to which request (proxy log /
  mock setting) and quotes the text the user saw verbatim.
  *Why:* T5; "it sometimes keeps spinning" cannot be reproduced, "GET /v1/feed →
  hang:120 → loading for 120 s, no retry" can.
- **NC-P5** For a write request, looks at TWO places after the fault: local state
  (screen, local database) and server (the mock server's record).
  *Why:* the most expensive bugs appear where the two diverge: a record that never
  reached the server shows as "saved", or a retry creates a second record.

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` → `network`
(if absent the member does not apply), `account` (NC-S6), technology (template).

## Scan

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-network-chaos/scripts/nc_scan.py" <root> [--json]
```

| Id | What | Severity |
|---|---|---|
| NC-10 | Network clients (URLSession, Alamofire, http, dio, fetch, axios, HttpClient, GraphQL, WebSocket, Firebase / Supabase) | INFO |
| NC-11 | Whether the base URL can change in tests (environment / launch argument / build define), whether a network mock exists | INFO |
| NC-12 | No timeout setting on the client (http, dio, axios default to unlimited; fetch has no timeout of its own) | SUGGESTION |
| NC-13 | Accounts exist, no trace of handling session loss (401 / expired token) (info if present) | SUGGESTION / INFO |
| NC-14 | Raw error text shown to the user (`localizedDescription`, `e.toString()`, `error.message`) | SUGGESTION |
| NC-15 | Trace of retry / offline queue | INFO |

Results are CANDIDATES. Clients are searched only in their own languages (Core Data's
`fetch()` in Swift is not a client). NC-12 goes quiet if it sees a timeout anywhere in
the project: NC-S3 shows whether every request is covered.

## Proxy

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-network-chaos/scripts/nc_proxy.py" \
  --upstream <mock / staging server> [--port 8899] \
  [--rule '<regex "METHOD /path">' '<fault[@N]>' …] [--rate 1.0] [--seed 1] [--log <file>]
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-network-chaos/scripts/nc_proxy.py" --self-test
```

Faults: `pass`, `delay:MS`, `status:CODE`, `drop`, `reset`, `hang:SEC`,
`truncate:PERCENT`, `garbage`, `slow:BPS`; `@N` only on the first N matches.
The app connects to `http://localhost:<port>` (iOS 17+ blocks IP addresses —
`references/faults.md`). Response bodies are held in memory: not suitable for large
file downloads / streams (SSE, WebSocket); test those with a mock.

## Setup (good to know from the start)

1. The base URL can be changed from outside in the test build (environment variable,
   launch argument, build define).
2. The network client can be swapped in tests (passed as a dependency).
3. Every request has a timeout; the user gets an error and a retry path, not an
   endless spinner.
4. The user sees clear text in the app's language, not technical error text.
5. Repeating a record-creating request does not create a second record (idempotency
   key or server-side protection).

## Test

Details: `references/faults.md` (injection paths, iOS ATS details, NC-S1 … NC-S9,
finding ids, Flutter / Swift URLProtocol / msw / .NET templates, manual path).

1. `nc_scan.py` → clients, base URL / mock, candidates.
2. Pick a path: mock if there is one, at unit level; proxy if the base URL can change;
   if neither, by hand (the user does it) + the NC-11 suggestion.
3. Scenarios: NC-S1, S3, S4 first (most frequent and visible), then S8, S9 on write
   actions; S6 if there are accounts.
4. In each scenario: text the user saw (verbatim), spinner duration, local and server
   state (NC-P5), crash.
5. Findings: NC-20 … NC-27 (references), with request + fault + observation (NC-P4).

## Release (before submitting)

1. NC-S1 and NC-S3 on launch and the main screen: no crash / endless spinner (review
   may happen on a restricted network).
2. NC-S9 on the main write action: "saved" only once the server confirms; one record
   on retry.
3. If there are accounts, NC-S6: no loop / dead end when the session drops.
4. A regression test was suggested for every NC-2x found (T8).

## Report

`shared/report.md`. Per scenario: path (mock / proxy / manual), request pattern, fault
given, what the user saw (text + screen), local / server state, result; relevant lines
of the proxy log (T5). For an app with no network, a single line: "Not applicable: no
network use."
