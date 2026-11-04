---
name: apptest-data-integrity
description: "Use when a schema or database change could lose user data on update: migrations (drift, Core Data, SwiftData, Realm, GRDB...), wiping the store on error, backup without WAL, delete and reinstall. Data loss."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-data-integrity — data integrity

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.2 · for dynamic tries
`../apptest/shared/test-methods.md` · report `../apptest/shared/report.md`.
Not directly an App Store rule, focused on USER BUG; only for account / data
deletion (5.1.1(v)) and the iOS data storage guideline is Apple's current page
read (principle 7):
https://developer.apple.com/documentation/foundation/optimizing-your-app-s-data-for-icloud-backup

**Default contract:** Reports only; does not touch code or data. Destructive
tries (deleting, corrupting, interrupting) happen only on COPIED data in a
temporary simulator (DI-P1).

## When

- A data model / table / field is changing; the new version must open old data.
- Backup, restore, export / import or "delete all data" is being written.
- Sensitive data such as tokens or passwords is stored.
- Before release, especially from the second version on.

## Out of scope

- Server-side data and sync conflicts (only client-side loss).
- The App Store rule on account deletion → network (NW-10).
- The systematic tour of upgrades from old versions → upgrade (this member
  gives the rules, that member tries every version).

## Step 0

CONVENTIONS §5 + test-methods T1/T2. The static scan only reads. Dynamic tries
run in its own temporary simulator, with demo data; the data on the user's own
device / simulator is not touched.

## Principles specific to this member

- **DI-P1** Does destructive tries (deleting, corrupt file, interrupting) only
  on a copy of the data.
  *Why:* the real data of the user or developer does not come back.
- **DI-P2** Does not pass an upgrade because "it worked on an empty database";
  verifies with FULL old data.
  *Why:* schema errors appear only on full data (e.g. in a budgeting app the
  "duplicate column" trap only showed up in the v1 → current test with data).

## Profile

`python3 -I ~/.claude/skills/apptest/shared/profile.py <root>` →
`capability:database` (the database capability), `account` (account), iCloud
capabilities; technology (the migration mechanism varies by technology).

## Setup (good to know from the start)

1. **Schema version from day one,** increased at every change; an upgrade path
   is written from every old version to the current one (drift / sqflite
   `onUpgrade`, Core Data model version, SwiftData `VersionedSchema` +
   `SchemaMigrationPlan`, Realm `schemaVersion` + migration, GRDB
   `DatabaseMigrator`).
2. **Keep a snapshot of every schema version** (e.g. drift `drift_schemas/`);
   the upgrade test is written with FULL data.
3. **Do not use "delete if migration fails" options** (Room
   `fallbackToDestructiveMigration`, Realm `deleteRealmIfMigrationNeeded`,
   `destroyPersistentStore` on load failure) — only on a cache that can be
   regenerated, on purpose.
4. **Atomic writes:** related changes go in one transaction; an interrupted
   operation does not leave half data.
5. **Sensitive data in the Keychain** (or a secure storage package), not in
   plain preferences.
6. **Backup / export:** if SQLite is in WAL mode, checkpoint before copying, or
   use `VACUUM INTO` / a backup API; on restore, check the version and copy the
   existing data before restoring.
7. **Regenerable data** (cache, downloads) goes in Caches or is excluded from
   backup; user data goes in Documents / Application Support.
8. **"Delete all data",** if present, needs thought about order: backup copies
   / side files first, main data last — so data stays consistent if it stops
   halfway (e.g. a budgeting app's `deleteLocalDataFiles`).

## Test (while developing)

### 1. Static scan (seconds)

```sh
python3 -I ~/.claude/skills/apptest-data-integrity/scripts/data_scan.py <root> [--json]
```

| ID | Topic | Severity |
|---|---|---|
| DI-10 | Persistent data technologies (inventory) | INFO |
| DI-11 | Schema version increased, no upgrade path · duplicate Hive field number | USER BUG |
| DI-12 | Core Data model versions / automatic migration off | INFO / SUGGESTION |
| DI-13 | SwiftData not versioned | SUGGESTION |
| DI-14 | Destructive migration, or deleting the store on load failure | USER BUG |
| DI-15 | Database present, no migration test / schema snapshot | SUGGESTION |
| DI-16 | Token / password in plain storage | USER BUG |
| DI-17 | Database file copied without flushing the WAL | USER BUG |
| DI-18 | Cache in Documents, not excluded from backup | SUGGESTION |

Output is a CANDIDATE (principle 6). When verifying: is DI-14 only on a cache
store (may be intentional); in DI-17 is the connection closed or a checkpoint
done before the copy; in DI-16 is the value actually sensitive.

### 2. Dynamic tours (temporary simulator; principle 13; T1)

App container: `xcrun simctl get_app_container <UDID> <bundle> data`.

| Tour | Steps | Expected |
|---|---|---|
| **Install over** | build of the previous version (git tag / archive) is installed → realistic FULL demo data is entered → `xcrun simctl install <UDID> <new.app>` (container kept) → opened | data intact, no upgrade error |
| **Delete and reinstall** | app is deleted → reinstalled | clean start; iCloud / account data comes back as expected |
| **Interrupt** | `xcrun simctl terminate <UDID> <bundle>` during a save | no half record on open, data consistent |
| **Backup / restore** | take backup → change data → restore; also an old version's backup | includes the last record in the backup; old backup is upgraded |
| **Low disk** | (on a device, by the user) storage full | clear error, data not corrupted |

If the project has unit-level migration test infrastructure (drift
`SchemaVerifier`, Core Data model versions, GRDB migrator tests), recommend a
test with full data from every old version to the current one (the upgrade
member does this systematically).

## Release (before submitting)

1. Did the schema change in this version? If so: was the version increased, is
   there an upgrade path and a test with full data, was installing over the
   previous STORE version tried (the most critical tour).
2. Static scan.
3. Report.

## Report

`shared/report.md`. For the upgrade tour: from which version, with which demo
data, the result. Environment: simulator, iOS, versions tried.
