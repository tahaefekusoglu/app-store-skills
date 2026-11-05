#!/usr/bin/env python3
"""apptest-input-actions — static scan (double submit, destructive action without
confirmation, comma decimals, money in floating point, length limit measured in
UTF-16, keyboard type on number fields).

Standard library only; does NOT WRITE to the project. Output is a CANDIDATE (verify
against the IA-xx ids in SKILL.md). Does not interfere with input format / design (IA-P2).

    python3 -I input_scan.py <project_root> [--json]
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

WRITE_VERB = r"(save|create|add|insert|submit|post|send|pay|purchase|buy|checkout|upload|register|signUp|book|order|" \
             r"transfer|kaydet|ekle|gönder|öde)\w*\s*\("
ASYNC_HANDLER = {
    "dart": r"on(Pressed|Tap|Submitted)\s*:\s*\(\)\s*async\s*\{",
    "swift": r"Button\s*(\([^)]*\))?\s*\{\s*Task\s*\{|Button\s*\(action\s*:\s*\{\s*Task",
    "js": r"onPress\s*=\s*\{\s*async\s*\(|onSubmit\s*=\s*\{\s*async\s*\(|onClick\s*=\s*\{\s*async\s*\(",
}
GUARD = r"_?is(Saving|Loading|Submitting|Busy|Processing)\b|_saving|_busy|_submitting|_loading|inFlight|in_flight|" \
        r"singleFlight|SingleFlight|isPending|isMutating|\.disabled\(|disabled\s*=\s*\{|onPressed\s*:\s*\w+\s*\?\s*null|" \
        r"AbsorbPointer|IgnorePointer|debounce|throttle|guard\s+!is|if\s*\(\s*_?\w*(saving|busy|loading|submitting)\w*\s*\)\s*return"
DELETE_CALL = r"\b(delete|remove|erase|destroy|clear(All)?|wipe|reset|cancelSubscription|sil)\w*\s*\("
CONFIRM = r"showDialog|showCupertinoDialog|AlertDialog|CupertinoAlertDialog|confirm\w*\(|\.confirmationDialog\(|\.alert\(|" \
          r"UIAlertController|Alert\.alert\(|ActionSheet|showModalActionSheet|undo|Undo|SnackBarAction|onDismissed"
DESTRUCTIVE_UI = {
    "dart": r"(Icons\.delete\w*|Icons\.remove_circle\w*|['\"](Delete|Remove|Sil|Kaldır|Löschen|Entfernen|Elimina|Cancella|Rimuovi|Eliminar|Borrar|Quitar|Supprimer|Excluir|Remover)['\"])",
    "swift": r"role\s*:\s*\.destructive|systemName\s*:\s*\"trash",
    "js": r"(trash|delete)[-_]?(icon|outline)?['\"]|title\s*=\s*['\"](Delete|Remove|Sil|Löschen|Elimina|Eliminar|Supprimer|Excluir)",
}
# Only USER TEXT converted to a number: not number-to-number conversion like Double(fundedPercent).
_TXT = r"[^)\n]{0,40}(\.text\b|[a-z]Text\b|\btext\b|input|Input|controller|Controller|[a-z]Field\b|\bfield\b)"
UI_INPUT = r"TextField|UITextField|TextFormField|TextInput|onChangeText|onChanged|textFieldDidChange|editingChanged|" \
           r"UITextView|SecureField|EditText|<input"
NUM_PARSE = {
    "dart": r"\b(double|num)\.(parse|tryParse)\(" + _TXT,
    "swift": r"\b(Double|Float)\(" + _TXT + r"|Decimal\(\s*string\s*:",
    "js": r"\bparseFloat\(" + _TXT + r"|\bNumber\(" + _TXT,
    "kotlin": r"(text|input|value)\w*(\.toString\(\))?\.toDouble\(\)",
}
LOCALE_NUM = r"NumberFormat|NumberFormatter|replaceAll\(\s*['\"],['\"]|replace\(\s*['\"],['\"]|decimalSeparator|" \
             r"Locale|locale|toLocaleString|Intl\.NumberFormat|parseKurus|FormatStyle|\.number\b"
# At the START of a word ("currency" inside "@preconcurrency" is not money — e.g. Pocket Casts).
MONEY_FILE = re.compile(r"(?i)(?<![a-z])(currency|price|pricing|payment|invoice|wallet|money|cents\b|kuruş|tutar|"
                        r"fiyat|bakiye|pledge|checkout|subtotal)|NumberFormat\.simpleCurrency|[€£₺¥]")
MONEY_FLOAT = {
    "dart": r"\b(double|num)\s+(price|amount|total|balance|cost|fee|subtotal|tax|tutar|fiyat|bakiye)\w*\b",
    "swift": r"\b(var|let)\s+(price|amount|total|balance|cost|fee|subtotal|tutar|fiyat|bakiye)\w*\s*:\s*(Double|Float)\b",
    "js": r"\b(price|amount|total|balance|cost|fee)\w*\s*[:=]\s*parseFloat\(",
    "kotlin": r"\b(val|var)\s+(price|amount|total|balance|cost|fee)\w*\s*:\s*(Double|Float)\b",
}
UTF16_LEN = {
    "dart": r"\b(name|title|text|value|input|nick\w*|display\w*)\w*\.(trim\(\)\.)?length\s*(<|>|<=|>=|==)\s*\d+",
    "js": r"\b(name|title|text|value|input|nick\w*|display\w*)\w*\.(trim\(\)\.)?length\s*(<|>|<=|>=|===?)\s*\d+",
}
NUMERIC_FIELD = {
    "dart": (r"TextField\(|TextFormField\(", r"(?i)(amount|price|tutar|fiyat|phone|telefon|quantity|adet|age|yaş)",
             r"keyboardType\s*:"),
    "swift": (r"TextField\(", r"(?i)(amount|price|tutar|fiyat|phone|quantity|age)", r"\.keyboardType\("),
    "js": (r"<TextInput\b", r"(?i)(amount|price|phone|quantity|age)", r"keyboardType\s*="),
}
DEV_SCREEN = re.compile(r"(?i)(debug|developer|betatools|designsystem|internal|playground|sample|example|preview|mock|fixture)")


def call_body(text: str, start: int, max_len: int = 2500) -> str:
    depth, i = 0, start
    while i < min(len(text), start + max_len):
        c = text[i]
        if c in "({":
            depth += 1
        elif c in ")}":
            depth -= 1
            if depth <= 0 and i > start:
                return text[start:i + 1]
        i += 1
    return text[start:start + max_len]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    p = scan.load_profile(a.root)
    if scan.guard_unknown(p):
        return 0
    rep = scan.Report("IA", p, "input-actions scan")
    files = [f for f in scan.code_files(p) if not DEV_SCREEN.search(p.rel(f))]
    by_lang: dict[str, list[str]] = {}
    for f in files:
        by_lang.setdefault(scan.lang_of(f), []).append(f)

    # IA-10: double submit
    for lg, pat in ASYNC_HANDLER.items():
        for f in by_lang.get(lg, []):
            text = scan.p_read(f)
            if re.search(GUARD, text):
                continue
            for m in re.finditer(pat, text):
                body = call_body(text, m.end() - 1)
                w = re.search(r"await[^\n;]{0,80}" + WRITE_VERB, body)
                if w:
                    n = text.count("\n", 0, m.start()) + 1
                    rep.add("IA-10", "SUGGESTION", "Saving button may be open to a second tap while working",
                            f"{p.rel(f)}:{n} `{w.group(0)[:50]}`",
                            "Two quick taps can create two saves / two payments. Disabling the button while working, or "
                            "single-flight, is one way. Verify with rapid-input.")
                    break

    # IA-11: destructive action without confirmation
    for lg, pat in DESTRUCTIVE_UI.items():
        for f in by_lang.get(lg, []):
            text = scan.p_read(f)
            # Near each button, not the whole file: one dialog elsewhere in a big file says nothing about this button.
            m = next((x for x in re.finditer(pat, text)
                      if re.search(DELETE_CALL, text[max(0, x.start() - 300):x.end() + 500])
                      and not re.search(CONFIRM, text[max(0, x.start() - 300):x.end() + 500])), None)
            if not m:
                continue
            n = text.count("\n", 0, m.start()) + 1
            rep.add("IA-11", "SUGGESTION", "Destructive action (delete / remove) may have no confirmation or undo",
                    f"{p.rel(f)}:{n}", "An accidental tap loses data: a confirmation dialog or 'Undo' is one way "
                    "(the confirmation may be in another file — not verified).")

    # IA-12: comma decimal
    for lg, pat in NUM_PARSE.items():
        for f in by_lang.get(lg, []):
            text = scan.p_read(f)
            if re.search(LOCALE_NUM, text) or not re.search(UI_INPUT, text) or \
                    re.search(r"(?i)/(api|models?|network|dto|decod)", "/" + p.rel(f)):
                continue  # only screens with a text field; server data has a fixed format
            m = re.search(pat, text)
            if m:
                n = text.count("\n", 0, m.start()) + 1
                rep.add("IA-12", "USER BUG", "User input may be converted to a number without regard to the decimal separator",
                        f"{p.rel(f)}:{n} `{m.group(0)}`",
                        "On Turkish, German, French … keyboards the decimal separator is a comma: '12,5' fails to parse or is "
                        "misread. Parsing by locale is one way.")

    # IA-13: keeping money in floating point
    for lg, pat in MONEY_FLOAT.items():
        # Constants (const / static let) and theme / style files: "amount" there may be a font size.
        cand = [f for f in by_lang.get(lg, []) if not re.search(r"(?i)/(theme|style|design|tokens?|fonts?)[/_.]", "/" + p.rel(f))]
        # With no MONEY context in the file, "total / amount" is a duration, scale or position (e.g. Pocket Casts
        # playback time, Immich zoom, AppFlowy list position — false alarms).
        cand = [f for f in cand if MONEY_FILE.search(scan.p_read(f, 300_000))]
        hits = [(f, n) for f, n, line, m in scan.grep(p, pat, files=cand)
                if not re.search(r"\bconst\b|static\s+(let|const)|static\s+final", line)]
        c, first = len(hits), (hits[0] if hits else None)
        if c:
            rep.add("IA-13", "USER BUG", f"Money amount kept in floating point (double/Float) ({c} places)",
                    f"{p.rel(first[0])}:{first[1]}",
                    "0.1 + 0.2 ≠ 0.3: totals drift by cents. An integer in the smallest unit (cents) or Decimal is one way "
                    "(e.g. a budgeting app keeps all money as integer minor units).")

    # IA-14: measuring a length limit in UTF-16 units
    for lg, pat in UTF16_LEN.items():
        for f, n, line, m in scan.grep(p, pat, files=by_lang.get(lg, []), max_hits=6):
            if "characters" in line or "graphemes" in line or "Intl.Segmenter" in line:
                continue
            if re.search(r"\b(length|count)\s*(?:===?|!==?|>|<=)\s*0\b", line):
                continue  # asking "is it empty?": the unit does not change the answer
            rep.add("IA-14", "SUGGESTION", "Text length measured in UTF-16 units (emoji / combining letters count as 2+)",
                    f"{p.rel(f)}:{n} `{m.group(0)[:50]}`",
                    "The limit does not match the character count the user sees (👍🏽 = 4 units). Dart: characters.length; "
                    "JS: Intl.Segmenter. Swift .count is already correct.")

    # IA-15: keyboard type on a numeric field
    for lg, (field_rx, name_rx, kb_rx) in NUMERIC_FIELD.items():
        for f in by_lang.get(lg, []):
            text = scan.p_read(f)
            for m in re.finditer(field_rx, text):
                body = call_body(text, m.end() - 1, 1200)
                if re.search(name_rx, body) and not re.search(kb_rx, body):
                    n = text.count("\n", 0, m.start()) + 1
                    rep.add("IA-15", "SUGGESTION", "No keyboard type set on a number / phone field",
                            f"{p.rel(f)}:{n}", "A letter keyboard opens; the right keyboard (number, decimal, phone) makes input easier.")
                    break

    rep.emit(a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
