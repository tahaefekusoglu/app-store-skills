#!/usr/bin/env python3
"""apptest-rapid-input — test plan and defence inventory against rapid / concurrent input:
(1) where actions write records or spend money (the try list), (2) data-layer defences against
duplicate records (unique constraint, idempotency key), (3) existing rapid-input tests,
(4) code that crashes when leaving a screen mid-operation (is the Flutter lint off), (5) database
code that makes several writes without a transaction.

A button open to a second tap mid-operation → input-actions IA-10 (not repeated here).
Standard library only (Python 3.9+); does NOT write to the project.

    python3 -I ri_scan.py <project_root> [--json]
"""
from __future__ import annotations

import argparse
import os
import importlib.util
import re
import sys

_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "apptest", "shared", "scanlib.py")
_s = importlib.util.spec_from_file_location("apptest_scanlib", _p)
scan = importlib.util.module_from_spec(_s)
_s.loader.exec_module(scan)

# Action site: a call that writes / spends inside or right next to a tap handler.
HANDLER = {
    "dart": r"on(Pressed|Tap|Submitted|LongPress|Dismissed)\s*:",
    "swift": r"\bButton\s*[\({]|\.onTapGesture\b|\.swipeActions\b|\.onSubmit\b|addTarget\(|@IBAction\b",
    "objc": r"addTarget:|-\s*\(IBAction\)",
    "js": r"\bon(Press|Submit|Click|LongPress)\s*=\s*\{",
    "kotlin": r"\bonClick\s*=\s*\{|setOnClickListener",
    "csharp": r"Command\s*=|\bClicked\s*\+=|ICommand\b|RelayCommand|AsyncRelayCommand",
    "xaml": r"Command=\"\{Binding|Clicked=\"",
}
VERBS = (r"(save|create|add|insert|submit|post|send|pay|purchase|buy|checkout|upload|register|signUp|"
                   r"book|order|transfer|delete|remove|archive|restore|import|kaydet|ekle|gönder|öde|sil)")
# A call (save(...)) or a function name passed to a handler (onPressed: _save, action: save, Command="{Binding Save…").
WRITE = re.compile(r"\b_?" + VERBS + r"\w*\s*\(|(on(Pressed|Tap|Submitted|Press|Click|Submit)|action|Command)\s*[:=]\s*"
                   r"[\"{]?\s*(\w+\s*\?\s*null\s*:\s*)?(\{?\s*Binding\s+)?(self\.|this\.)?_?" + VERBS + r"\w*\b",
                   re.IGNORECASE)
# A call or a name passed to a handler (onPressed: _pay). Excluded: sorting (orderBy, ordered), message
# recipient (subscriber), Turkish "pay" = share and its inflected forms.
MONEY = re.compile(r"(?i)\b_?(pay(?!ı|lar|laş|da|ın|ını)|purchase|buy|checkout|order(?!By|ing|ed)|transfer|subscribe(?!r)|öde|satın)\w*\b"
                   r"(?=\s*\(|\s*[,)}\]])")

# Data-layer defence against duplicate records.
UNIQUE = r"\bUNIQUE\b|\.unique\(\)|unique\s*:\s*true|@Attribute\(\s*\.unique|uniquenessConstraints|" \
         r"\bunique\s*=\s*True|@Index\([^)]*unique|INSERT\s+OR\s+(IGNORE|REPLACE)|ON\s+CONFLICT|" \
         r"insertOnConflictUpdate|InsertMode\.insertOr|onConflict\s*:|upsert\w*\("
# Only names that dedupe WRITES ("dedupe" is also used for display; an empty clientMutationId is no defence).
IDEMPOTENCY = r"(?i)idempoten\w*|alreadyProcessed|already_processed|processedIds|processed_ids"

# Existing rapid / concurrent input test.
# "Double tap to …" is a VoiceOver hint, not a test.
RAPID_UI_TEST = r"(?i)double[_ -]?tap(?!\s+to\b)|doubleTap\(|multiTap\(|tap\w*\s*twice|twice\w*\s*tap|rapid[_ ]?tap|" \
                r"çift dokun|art arda dokun|hızlı dokun"
CONCURRENT_TEST = r"Future\.wait\(\s*\[|\basync let\b|Promise\.all\(|DispatchQueue\.concurrentPerform|withTaskGroup|" \
                  r"Task\.WhenAll|(?i:concurrent\w*)|eşzamanlı"

# Flutter: is the lint on context use after await turned off?
LINT_OFF = re.compile(r"use_build_context_synchronously\s*:\s*(false|ignore)")

# Database writes and transaction blocks.
# Only through a database object (in Dart, List.insert / Map.update are not database calls; e.g. AppFlowy).
# Object name is EXACT (not a prefix): "transaction.insertNode" is a text editor, "databaseController.addListener" a listener.
DB_WRITE = r"\.into\([^)]*\)\.insert|\b(db|_db|database|dao|txn|batch|box|isar|realm)\.(insert|update|" \
           r"delete|put|add|insertAll|insertOnConflictUpdate)\w*\(|\b(update|delete)\(\s*(db\.|_db\.|\w+Table|" \
           r"\w+Tbl)|context\.(insert|delete)\(|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|realm\.write|" \
           r"executeUpdate|\.save\(\)\s*$|modelContext\.(insert|delete)\("
TRANSACTION = r"\.transaction\(|transaction\s*\{|withTransaction|BEGIN\s+(IMMEDIATE\s+|EXCLUSIVE\s+)?TRANSACTION|" \
              r"\bBEGIN\b;|performAndWait|\.perform\s*\{|realm\.write\s*\{|writeTransaction|runInTransaction|" \
              r"inTransaction|db\.write\s*\{|dbQueue\.write|dbPool\.write|\.atomic\("
DB_TECH = ("capability:database",)
SCHEMA_EXT = (".sql", ".drift", ".sq", ".sqm")


def scan_project(root: str, as_json: bool):
    p = scan.load_profile(root)
    if scan.guard_unknown(p):
        return 0
    rep = scan.Report("RI", p, "rapid-input — rapid input plan and defences")
    app = scan.code_files(p)
    everything = scan.code_files(p, include_tests=True)
    tests = [f for f in everything if scan.TEST_PATH.search("/" + p.rel(f))]

    # RI-10: action sites (per file; handler line and write call within 6 lines).
    per_file, money_files = {}, set()
    for f in app:
        lg = scan.lang_of(f)
        hp = HANDLER.get(lg)
        if not hp:
            continue
        hrx = re.compile(hp)
        rows = list(scan.lines(f))
        hits = 0
        for i, (n, line) in enumerate(rows):
            if not hrx.search(line):
                continue
            window = " ".join(l for _, l in rows[i:i + 7])
            if WRITE.search(window):
                hits += 1
                if MONEY.search(window):
                    money_files.add(f)
        if hits:
            per_file[f] = hits
    if per_file:
        top = sorted(per_file.items(), key=lambda kv: -kv[1])[:8]
        ev = "; ".join(f"{p.rel(f)} ×{c}" for f, c in top)
        rep.add("RI-10", "INFO", f"Action sites that write / spend: {sum(per_file.values())} site(s), {len(per_file)} file(s)",
                ev, "Try list: for each, double tap, repeated submit, back / background mid-operation.")
    if money_files:
        rep.add("RI-10", "INFO", f"Actions named payment / purchase / order: {len(money_files)} file(s)",
                "; ".join(p.rel(f) for f in sorted(money_files)[:6]),
                "If they spend real money, these come first: a second request is a second payment (test with a faked counter, T2).")

    # RI-11: data-layer defence.
    has_db = any(k.startswith(DB_TECH) for k in p.items)
    if per_file:
        # Schema files do not count as code files, but the unique constraint often lives there.
        schema = [f for f in p.files if p.mod.ios_path(f) and not scan.TEST_PATH.search("/" + p.rel(f))
                  and (f.endswith(SCHEMA_EXT) or (f.endswith("/contents") and ".xcdatamodel/" in f))]
        uc, ufirst = scan.count(p, UNIQUE, files=app + schema)
        ic, ifirst = scan.count(p, IDEMPOTENCY, files=app)
        if uc or ic:
            where = ufirst or ifirst
            rep.add("RI-11", "INFO", f"Data-layer defence against duplicates exists (unique constraint {uc}, idempotency key {ic})",
                    f"{p.rel(where[0])}:{where[1]}", "Verify the defence covers the TABLE / request of the action under test.")
        elif has_db or scan.count(p, r"https?://|URLSession|fetch\(|axios|dio\.|http\.(post|put)", files=app)[0]:
            rep.add("RI-11", "SUGGESTION", "Only a UI lock seems to guard against duplicates (no unique constraint / idempotency key found)",
                    "—", "If the UI lock is missed (two fingers, retry, concurrent request) a second record is created. "
                         "Server-side defences are NOT VISIBLE to this scan: show it with a test first (RI-20); the form of "
                         "the defence is the app's decision.")

    # RI-12: existing rapid-input tests.
    rc, rfirst = scan.count(p, RAPID_UI_TEST, files=tests)
    cc, cfirst = scan.count(p, CONCURRENT_TEST, files=tests)
    if rc:
        rep.add("RI-12", "INFO", f"Existing rapid-tap test ({rc} place(s))", f"{p.rel(rfirst[0])}:{rfirst[1]}",
                "See which actions it covers; add the ones missing from the RI-10 list.")
    if cc:
        rep.add("RI-12", "INFO", f"Test with concurrent calls ({cc} place(s))", f"{p.rel(cfirst[0])}:{cfirst[1]}",
                "Check whether it tests writing actions (record counts) or only reads / the cache.")
    if per_file and not rc and not cc:
        rep.add("RI-12", "SUGGESTION", "No rapid / concurrent input test found", "—",
                "The unit-level concurrent call test in references/templates.md is the cheapest start.")

    # RI-13: Flutter lint on context use after await is off.
    if "Flutter" in scan.techs(p):
        for f in p.files:
            if os.path.basename(f) == "analysis_options.yaml" and "/." not in "/" + p.rel(f):
                for n, line in enumerate(scan.p_read(f).splitlines(), 1):
                    if LINT_OFF.search(line) and not line.strip().startswith("#"):
                        rep.add("RI-13", "SUGGESTION", "use_build_context_synchronously turned off", f"{p.rel(f)}:{n}",
                                "Leaving a screen mid-operation (back / background) makes context use after await "
                                "fail; the lint caught this at compile time.")

    # RI-14: database writes exist, no transaction block anywhere.
    if has_db:
        wc, wfirst = scan.count(p, DB_WRITE, files=app)
        tc, _ = scan.count(p, TRANSACTION, files=app)
        if wc >= 3 and not tc:
            rep.add("RI-14", "SUGGESTION", f"Database writes in {wc} place(s), no transaction block at all",
                    f"{p.rel(wfirst[0])}:{wfirst[1]}",
                    "An action writing several rows, arriving twice at once, can leave a partial / mixed state; "
                    "verify with a concurrent call test (RI-23).")
        elif wc and tc:
            rep.add("RI-14", "INFO", f"Database writes in {wc} place(s), transaction blocks in {tc} place(s)", "—",
                    "Verify with a concurrent test that multi-row actions are inside a transaction.")

    if not per_file:
        rep.skip("RI-10", "no writing action found")
    rep.emit(as_json)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    return scan_project(os.path.abspath(a.root), a.json)


if __name__ == "__main__":
    sys.exit(main())
