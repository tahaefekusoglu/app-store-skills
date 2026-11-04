#!/usr/bin/env python3
"""apptest-data-integrity — static scan (local data, schema upgrades, destructive
migrations, sensitive data, backup / copy, cache in backups, migration tests).

Standard library only; does NOT WRITE to the project. Output is a CANDIDATE (verify
against the DI-xx ids in SKILL.md).

    python3 -I data_scan.py <project_root> [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys

_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "apptest", "shared", "scanlib.py")
_s = importlib.util.spec_from_file_location("apptest_scanlib", _p)
scan = importlib.util.module_from_spec(_s)
_s.loader.exec_module(scan)

DESTRUCTIVE = [
    ("Room destructive migration", r"fallbackToDestructiveMigration"),
    ("Realm: delete the database if migration is needed", r"deleteRealmIfMigrationNeeded\s*[:=]\s*true|deleteRealmIfMigrationNeeded\(\)"),
    ("Table dropped during upgrade", r"(?i)on_?upgrade[^\n]{0,200}DROP TABLE|DROP TABLE[^\n]{0,80}IF EXISTS"),
    ("Data store deleted on load failure",
     r"destroyPersistentStore|removeItem\(\s*at\s*:\s*\w*(store|sqlite|db|database)\w*|"
     r"deleteDatabase\(|deleteFromDisk\(\)|\.delete\(\)\s*;?\s*//?\s*(reset|corrupt)"),
]
SENSITIVE_PLAIN = r"(?i)(UserDefaults[^\n]{0,60}\.set\([^\n]{0,80}|setString\(\s*['\"]|AsyncStorage\.setItem\(\s*['\"]|" \
                  r"MMKV[^\n]{0,40}\.set\w*\(\s*['\"]|prefs\.set\w*\(\s*['\"]|Preferences\.set\(\s*\{?\s*key\s*:\s*['\"]|" \
                  r"localStorage\.setItem\(\s*['\"])[^\n]{0,40}(access_?token|refresh_?token|auth_?token|password|passwd|" \
                  r"secret|api_?key|private_?key|session_?token|\bpin\b|jwt)"
SECURE_STORE = r"Keychain|KeychainAccess|SecItemAdd|flutter_secure_storage|expo-secure-store|react-native-keychain|" \
               r"SecureStorage|EncryptedSharedPreferences"
_COPY = r"(copyItem\(\s*at|FileManager[^\n]{0,40}copy|\.copy\(|\.copySync\(|copyFile|RNFS\.copyFile|FileSystem\.copyAsync)"
_DBF = r"(\.sqlite|\.db\b|\.realm|database|Database|dbPath|dbFile|dbURL|storeURL)"
DB_COPY = _COPY + r"[^\n]{0,120}" + _DBF + r"|" + _DBF + r"[^\n]{0,80}" + _COPY
SAFE_BACKUP = r"wal_checkpoint|VACUUM INTO|sqlite3_backup|\.backup\(|NSPersistentStoreCoordinator[^\n]{0,40}migratePersistentStore|" \
              r"replacePersistentStore|realm\.writeCopy|writeCopy\(toFile|exportDatabase|checkpoint"
DOCS_CACHE = r"(documentDirectory|getApplicationDocumentsDirectory|DocumentDirectoryPath|documentsDirectory|" \
             r"FileSystem\.documentDirectory)[^\n]{0,120}(?i:cache|download|tmp|temp|thumbnail|thumb|image_?cache|media)"
EXCLUDE_BACKUP = r"isExcludedFromBackup|NSURLIsExcludedFromBackupKey|excludeFromBackup|setExcludedFromBackup"


def detect_stores(p, files, deps):
    """[(name, evidence)] — persistent data technologies in use."""
    out = []
    checks = [
        ("drift (SQLite)", r"\bdrift\b|moor:", r"@DriftDatabase|GeneratedDatabase"),
        ("sqflite (SQLite)", r"\bsqflite\b", r"openDatabase\("),
        ("Core Data", None, r"NSPersistentContainer|NSManagedObjectContext|NSPersistentCloudKitContainer"),
        ("SwiftData", None, r"@Model\b|ModelContainer\("),
        ("Realm", r"realm", r"Realm\.Configuration|RealmConfiguration|Realm\("),
        ("GRDB", r"GRDB", r"DatabaseQueue|DatabasePool|DatabaseMigrator"),
        ("Hive", r"\bhive\b|hive_flutter", r"@HiveType|Hive\.openBox"),
        ("Isar", r"\bisar\b", r"Isar\.open|@collection"),
        ("ObjectBox", r"objectbox", r"openStore\(|@Entity"),
        ("WatermelonDB", r"@nozbe/watermelondb", r"appSchema\("),
        ("expo-sqlite / react-native-sqlite", r"expo-sqlite|react-native-sqlite|op-sqlite", r"openDatabase|SQLite\."),
        ("MMKV / AsyncStorage", r"react-native-mmkv|async-storage", r"MMKV|AsyncStorage"),
        ("Room / SQLDelight (KMP)", r"sqldelight|androidx\.room", r"@Database|SqlDriver"),
        ("SQLite (C# / MAUI)", r"sqlite-net|SQLitePCL|LiteDB|Microsoft\.Data\.Sqlite", r"SQLiteAsyncConnection|LiteDatabase"),
    ]
    for name, dep_rx, code_rx in checks:
        dm = re.search(dep_rx, deps) if dep_rx else None
        if dep_rx and not dm:
            continue  # technology needing a package: without the dependency a generic function name (openDatabase) misleads
        c, first = scan.count(p, code_rx, files=files)
        if dm or c:
            out.append((name, f"{p.rel(first[0])}:{first[1]}" if first else f"dependency: {dm.group(0)}"))
    if any(f.endswith(".xcdatamodeld") or ".xcdatamodeld/" in f for f in p.files) and \
            not any(n == "Core Data" for n, _ in out):
        out.append(("Core Data", "xcdatamodeld"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    p = scan.load_profile(a.root)
    if scan.guard_unknown(p):
        return 0
    rep = scan.Report("DI", p, "data-integrity scan")
    files = scan.code_files(p)
    test_files = [f for f in scan.code_files(p, include_tests=True) if scan.TEST_PATH.search("/" + p.rel(f))]
    deps = "\n".join(scan.p_read(f) for f in p.files if os.path.basename(f) in
                     ("pubspec.yaml", "package.json", "Podfile", "Package.swift", "build.gradle.kts", "build.gradle")
                     or f.endswith(".csproj"))
    deps += "\n".join(re.findall(r'repositoryURL = "([^"]+)"', "\n".join(
        scan.p_read(f, 5_000_000) for f in p.files if f.endswith("project.pbxproj"))))

    stores = detect_stores(p, files, deps)
    if not stores:
        rep.skip("DI-10…", "no persistent data store found (server only, or no data)")
    else:
        rep.add("DI-10", "INFO", "Persistent data", "; ".join(f"{n} ({e})" for n, e in stores),
                "On every update, old data MUST OPEN in the new version (DI-P2: verify with full data).")
    names = {n for n, _ in stores}
    migr_tests = scan.count(p, r"(?i)migrat|onUpgrade|schemaVersion|SchemaVerifier|upgrade", files=test_files)[0]

    # DI-11: schema version ↔ upgrade path
    if "drift (SQLite)" in names:
        sv = [int(m.group(1)) for f, n, l, m in scan.grep(p, r"schemaVersion\s*(?:=>|=|get\s*=>)\s*(\d+)", files=files)]
        has_up = scan.count(p, r"onUpgrade|MigrationStrategy|stepByStep", files=files)[0]
        snaps = any("/drift_schemas/" in f for f in p.files)
        if sv and max(sv) > 1 and not has_up:
            rep.add("DI-11", "USER BUG", f"drift schemaVersion {max(sv)} but no upgrade (onUpgrade)", "—",
                    "A user updating from an old version gets a database that will not open, or data is lost.")
        if sv and max(sv) > 1 and not snaps:
            rep.add("DI-15", "SUGGESTION", "no drift schema snapshots (drift_schemas/)", "—",
                    "`drift_dev schema dump` + generated migration tests verify upgrades from old schemas.")
    for f, n, line, m in scan.grep(p, r"openDatabase\([^)]*version\s*:\s*(\d+)", files=files):
        body = scan.p_read(f)
        if int(m.group(1)) > 1 and "onUpgrade" not in body:
            rep.add("DI-11", "USER BUG", f"sqflite version {m.group(1)} but no onUpgrade", f"{p.rel(f)}:{n}",
                    "An updating user's database cannot be upgraded.")
    if "Core Data" in names:
        for d in sorted({f.split(".xcdatamodeld")[0] + ".xcdatamodeld" for f in p.files if ".xcdatamodeld/" in f}):
            vers = sorted({x.split(".xcdatamodeld/")[1].split("/")[0] for x in p.files
                           if x.startswith(d + "/") and ".xcdatamodel/" in x})
            if len(vers) > 1:
                rep.add("DI-12", "INFO", f"Core Data model has {len(vers)} versions", p.rel(d),
                        "Lightweight migration is on by default; a mapping model for heavy changes. Try upgrading from every old version.")
        off = scan.count(p, r"shouldMigrateStoreAutomatically\s*=\s*false|shouldInferMappingModelAutomatically\s*=\s*false",
                         files=files)
        if off[0]:
            rep.add("DI-12", "SUGGESTION", "Core Data automatic migration turned off", f"{p.rel(off[1][0])}:{off[1][1]}",
                    "If intentional, is there a manual migration path for every old version?")
    if "SwiftData" in names and not scan.count(p, r"VersionedSchema|SchemaMigrationPlan", files=files)[0]:
        rep.add("DI-13", "SUGGESTION", "SwiftData models not versioned (no VersionedSchema / SchemaMigrationPlan)", "—",
                "A simple change migrates by itself; on a field name / type change without a plan, data can be lost.")
    if "Hive" in names:
        for f in files:
            if scan.lang_of(f) != "dart":
                continue
            t = scan.p_read(f)
            for cls in re.split(r"@HiveType\(", t)[1:]:
                idx = re.findall(r"@HiveField\(\s*(\d+)", cls.split("@HiveType(")[0][:8000])
                dup = {i for i in idx if idx.count(i) > 1}
                if dup:
                    rep.add("DI-11", "USER BUG", f"Duplicate field number in a Hive class: {', '.join(sorted(dup))}",
                            p.rel(f), "Saved data is read into the wrong field.")

    # DI-14: destructive migration / deleting the store
    for label, rx in DESTRUCTIVE:
        for f, n, line, m in scan.grep(p, rx, files=files):
            # Deleting a cache store and dropping an old table in a migration are often legitimate (e.g. Wikipedia
            # CacheController cache database; NetNewsWire unused "tags" table) → SUGGESTION, verify.
            cache = re.search(r"(?i)cache|tmp|temp", p.rel(f) + " " + line)
            before = "\n".join(x for k, x in scan.lines(f) if n - 12 <= k <= n)
            # If not on an error path, it may be a deletion the user asked for, like "Delete all data" (e.g. Apidash).
            manual = label.startswith("Data store deleted on load failure") and not re.search(r"(?i)catch|corrupt|on\w*error|\berror\b|rescue|fail|\bexcept", before)
            soft = cache or manual or label == "Table dropped during upgrade"
            rep.add("DI-14", "SUGGESTION" if soft else "USER BUG",
                    ("Code that deletes the data store" if manual else f"{label}") + (" (cache)" if cache else ""),
                    f"{p.rel(f)}:{n} `{m.group(0)[:50]}`",
                    ("Intentional if a cache; if it holds user data, silent loss." if cache else
                     "Does not look like an error path: verify it runs only when the user asks." if manual else
                     "Verify whether the dropped table holds user data and whether data was moved first." if soft else
                     "The user's data is silently deleted. Otherwise an upgrade path or recovery + telling the user."))

    # DI-15: migration test
    if stores and not migr_tests and (names & {"drift (SQLite)", "sqflite (SQLite)", "Core Data", "SwiftData", "Realm",
                                               "GRDB", "WatermelonDB", "Room / SQLDelight (KMP)"}):
        rep.add("DI-15", "SUGGESTION", "Database present, no upgrade / migration test found", "test files",
                "An upgrade is safe only when verified with FULL old data (DI-P2; e.g. in a budgeting app the 'duplicate column' "
                "trap only appeared in the v1 → current test).")

    # DI-16: sensitive data in plain storage
    for f, n, line, m in scan.grep(p, SENSITIVE_PLAIN, files=files):
        if re.search(r"\.set\w*\(\s*(true|false|\d+)\s*,|(?i:shown|enabled|seen|dismissed|count)\b", line):
            continue  # a flag, not the value itself (e.g. Firefox PasswordGeneratorShown = true)
        rep.add("DI-16", "USER BUG", "Sensitive data may be written to plain storage",
                f"{p.rel(f)}:{n} `{m.group(0)[:60]}`",
                "Tokens / passwords belong in the Keychain (flutter_secure_storage, expo-secure-store, react-native-keychain); "
                "UserDefaults / SharedPreferences / AsyncStorage sit in the open in backups and on the device.")

    # DI-17: copying the database file without flushing the WAL
    copies = list(scan.grep(p, DB_COPY, files=files))
    if copies and not scan.count(p, SAFE_BACKUP, files=files)[0]:
        f, n, line, m = copies[0]
        rep.add("DI-17", "USER BUG", "Database file copied directly (backup / export)",
                f"{p.rel(f)}:{n}", "In SQLite WAL mode the latest writes are in the -wal file; checkpoint before copying, or use "
                "VACUUM INTO / a backup API. Otherwise the backup misses the latest records or the file is corrupt.")

    # DI-18: cache included in backups
    dc = list(scan.grep(p, DOCS_CACHE, files=files, max_hits=5))
    if dc and not scan.count(p, EXCLUDE_BACKUP, files=files)[0]:
        f, n, line, m = dc[0]
        rep.add("DI-18", "SUGGESTION", "Cache / downloads in the Documents folder and not excluded from backup",
                f"{p.rel(f)}:{n}", "Bloats the iCloud backup; regenerable data should go in Caches or be "
                "marked with isExcludedFromBackup (iOS Data Storage Guidelines).")

    rep.emit(a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
