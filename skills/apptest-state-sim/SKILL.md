---
name: apptest-state-sim
description: "Tests business rules with a seeded random simulation: hundreds of actions, invariants at every step, rejected actions leave state unchanged, shrinks a failing seed. Dart, Swift, TS. Property-based test, invariants."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-state-sim: seeded random use + invariants

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.10 · group principles
`../apptest/shared/test-methods.md` (T1–T10) · rules in data-integrity,
input-actions · report `../apptest/shared/report.md`.
Talking with the user: `../apptest/shared/CONVENTIONS.md` §11 (when to ask, status lines, one next step).

**Default contract:** Suggests invariants from the code and the user approves;
adapts the test template and writes it to the project's test folder with
approval. Does not add hooks to app code (T3); runs with an in-memory database
and a fake clock.

## When

- The app has interdependent state: balance, stock, cart, counter, period /
  cycle, sync queue, linked records.
- Bugs of the "totals sometimes do not add up" or "it stays somewhere after
  deleting" kind, which cannot be reproduced by steps.
- A business rule changed: hand-written example tests do not cover every path.

## Out of scope

- UI taps → crawl. Flows on a real simulator → device-tour.
  This member calls the business rule layer (service / engine / repository)
  directly.

## Step 0

CONVENTIONS §5. The normal tour is fast (seconds); a long stress tour (thousands
of steps) runs under a separate tag and with approval (§6).

## Member-specific principles

- **SS-P1** Invariants come from the app's DOMAIN: candidates are drawn from the
  rules in the code (validation, triggers, constraints, documents) and the user
  approves; they are not invented.
  *Why:* a wrong invariant either treats correct behaviour as a bug or misses a
  real bug (e.g. a budgeting app's invariants came from its brief and ledger
  rules: single active cycle, gapless chain, transaction = ledger, closed-cycle
  carryover).
- **SS-P2** All randomness is seeded; a failure is reported with the seed + step
  number + a log of the last steps, then shrunk to the shortest sequence and
  kept as a regression test.
  *Why:* an unseeded random failure is never seen again (T5, T8).
- **SS-P3** A rejected action must NOT have changed state: a snapshot before each
  action, equality after a rejection.
  *Why:* a half-finished write (one table first, then an error) is the most
  common and the quietest data corruption.
- **SS-P4** A coverage check at the end: every action type must SUCCEED at least
  once; if not, the test fails even if everything else is green.
  *Why:* when a rule changes, an action can start being rejected every time and
  the simulation silently stops testing that path (e.g. a budgeting app's
  `succeeded` coverage test).

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
technology (template language), database capability, `has_tests`.

## Setup (good to know from the start)

1. Business rules live in a layer separate from the UI and can be called without
   it.
2. The database can open in memory; the clock can be injected (time-travel).
3. A rejection returns a distinguishable error type (not a generic exception).
4. A comparable snapshot of the state can be taken.

## Test

Templates: `references/templates.md` (Dart, Swift, TypeScript; seeded generators
included). Adaptation steps:

1. Action list: every state-changing operation the user can do + clock forward /
   BACK (if any) + settings changes; weights close to real use.
2. Invariant list (SS-P1), approved.
3. Seeds (e.g. 8 × 400 steps) in the normal tour; concurrent write bursts (several
   actions at once) with separate seeds; a long stress tour tagged and driven by
   an environment variable (steps / seed range).
4. Also runs in a zone with DST (`TZ=Europe/Berlin`, time-travel TT-P3).
5. On failure: shrink to the shortest sequence (last section of the template) →
   regression test.

## Release (before submitting)

1. Normal tour + one stress tour are clean.
2. If a business rule changed: is the invariant list current, is the coverage
   test green?

## Report

`shared/report.md`. For each failure: seed, step, last 20 steps, the violated
invariant, expected / observed; the shrunk sequence and the suggested regression
test.
