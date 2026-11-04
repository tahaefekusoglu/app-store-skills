---
name: apptest-upgrade
description: "Tests that a new version opens with an old version's data: install over the old build in a simulator, schema upgrade tests, old backups. Upgrade test, upgrading from an old version, migration test."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-upgrade — upgrading from an old version

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.3 · group principles
`../apptest/shared/test-methods.md` · rules in data-integrity (DI-P1,
DI-P2) · report `../apptest/shared/report.md`. Shared tool:
`../apptest/shared/sim_session.py`.

**Default contract:** Runs in a temporary simulator; does not touch the user's device
or data. The old version is built from a git tag / archive, without touching the
main working tree (worktree).

## When

- Before every release that changes the data model / schema / persisted settings.
- "My data disappeared after updating" reports.
- On the first release: to keep the old schema and sample data needed later.

## Out of scope

- Schema upgrade RULES (version, onUpgrade, destructive migration) → data-integrity
  (the static scan lives there). This member RUNS the upgrade.

## Step 0

CONVENTIONS §5: the old version is built in a separate worktree; temporary simulator;
heavy work (builds take minutes): time estimate and approval (§6).

## Member principles

- **UP-P1** On the first release it says "Not applicable" but suggests once keeping
  the old schema snapshot and sample data needed later.
  *Why:* an old version's data cannot be obtained afterwards.
- **UP-P2** Tries upgrading to current not only from the previous version but from EVERY
  version in the store (at least the oldest and the previous one).
  *Why:* users skip versions; a migration step in the middle of the chain only
  runs on a long jump (e.g. in a budgeting app the v1 → current test caught the
  "duplicate column" trap, the test from the previous version did not).

## Profile

`python3 -I ~/.claude/skills/apptest/shared/profile.py <root>` →
database capability, technology (build command), `setting:version`.

## Setup (good to know from day one)

1. **Every released version is tagged** (git tag) or its archive is kept,
   so the old version can be rebuilt.
2. **A snapshot of every schema version** and FULL sample data written with that
   version (e.g. drift `drift_schemas/` + test data) are kept.
3. **Upgrade unit test:** from every old schema to current, with full data,
   comparing record counts and critical totals.

## Test

### 1. Unit level (fast; if the project has it)

drift `SchemaVerifier` / generated migration tests, a load test with Core Data model versions,
a GRDB `DatabaseMigrator` test, a Realm migration test: from every
old version to current with FULL data (DI-P2).

### 2. Install-over tour (simulator)

```sh
# old version: build from the tag in a separate worktree
git worktree add <temp>/wt-old <old-tag>
#   Flutter:  (cd <temp>/wt-old && flutter build ios --simulator --debug)
#   Native:   xcodebuild -scheme <scheme> -sdk iphonesimulator -configuration Debug -derivedDataPath <temp>/dd build
U=$(python3 -I ~/.claude/skills/apptest/shared/sim_session.py create --project <root>)
python3 -I ~/.claude/skills/apptest-upgrade/scripts/upgrade_tour.py --udid $U --bundle <bundle_id> \
    --old <old.app> --new <new.app> [--seed "<data entry command>"] [--verify "<verify command>"]
python3 -I ~/.claude/skills/apptest/shared/sim_session.py cleanup --project <root> --udid "$U"
```

The script: installs and launches the old version → data is entered (`--seed` command or
by hand, Enter) → lists the container → installs the new version OVER it (the container is kept) →
launches → is it running, are any files gone or shrunk by more than half
(excluding caches and snapshots iOS regenerates), did `--verify`
pass. `--seed` / `--verify` commands receive the environment variables `APPTEST_UDID`,
`APPTEST_BUNDLE`, `APPTEST_CONTAINER`. Exit
code: 0 no problem found · 1 a problem was found · 3 could not check (the data folder could not be
read, or it held no data before the upgrade, so the tour proves nothing).

Data entry: the most reliable way is the project's own device tour (the integration / UI test
at the old version's tag enters the demo data). When entering by hand, use
realistic and FULL data: many records, edge values, at least one
example of every feature.

### 3. Restoring from an old backup

If the app has a backup / export feature: back up in the old version →
restore in the new version → same comparison (data-integrity DI-17).

## Release (before submitting)

1. Did the schema / persisted settings change in this release? If so, unit upgrade
   tests + at least "last store version → new" and "oldest version →
   new" install-over tours.
2. Cleanup and report.

## Report

`shared/report.md`. Per tour: old → new version, data entered, did it
open, files gone / shrunk, verify result, manual comparison
(counts, totals, latest record).
