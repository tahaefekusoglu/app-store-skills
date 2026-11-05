#!/usr/bin/env python3
"""Text inventory and automatic pre-checks (apptest-copy-audit, Step 2 + 4-C/4-F).

Standard library only. Does NOT WRITE to the project; puts output in the --out folder
(default: a temporary folder) and prints a markdown summary to stdout.

What it does:
  1. Finds and reads translation files: Flutter .arb, web/RN locale .json
     (nested keys are flattened), iOS .strings, Android strings.xml,
     gettext .po, YAML (if PyYAML is present).
  2. Writes a `key<TAB>length<TAB>category<TAB>text` dump for each language
     (length: words in spaced languages, characters/2 in JA/ZH/TH/KO).
  3. Pre-checks (not a FINAL verdict, a candidate list to READ):
     - missing key / text identical to the source language (untranslated)
     - placeholder mismatch between languages
     - no plural form on a number placeholder (in languages with plurals)
     - long text over the category threshold (Step 4-F)
     - the same sentence repeated in several keys (F4/F5)
     - the same idea written in different keys: shared 3-word sequence (F4)
     - the same stem repeated within a text (F1)

Usage:
  python3 copy_inventory.py <project_root> [--out FOLDER] [--source en]
         [--files a.arb b.arb ...] [--max 40]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import plistlib
import re
import sys
import tempfile
import xml.etree.ElementTree as ET

# If the Windows console is not UTF-8, non-ASCII letters must not crash the output (every OS).
for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SKIP_DIRS = {
    ".claude", ".cursor", ".codex", ".agents",
    ".git", "node_modules", "build", "dist", ".dart_tool", "Pods", ".next",
    ".nuxt", "vendor", "DerivedData", ".gradle", "coverage", "out", ".venv",
    "venv", "__pycache__", "generated", ".idea", ".vscode",
}
NO_SPACE_LANGS = {"ja", "zh", "th", "ko", "lo", "km", "my"}
# Languages WITHOUT a plural distinction: number + noun has one form.
NO_PLURAL_LANGS = {"tr", "ja", "zh", "ko", "th", "vi", "id", "ms", "lo", "km", "my"}

# Category thresholds (words) — same as SKILL.md Step 4-F.
THRESHOLDS = {
    "button": 4, "error": 12, "hint": 15, "confirm": 15,
    "notification": 12, "onboarding": 15, "a11y": 12, "other": 15,
}

PLACEHOLDER_RE = re.compile(
    r"\{\{\s*[\w.]+\s*\}\}"           # {{name}} (i18next, Vue, Angular)
    r"|\{[A-Za-z_]\w*\}"               # {name} (ICU, arb)
    # %s %1$d %@ %.2f (printf, iOS, Android). No space flag and not before a
    # letter: "%0 to %100", "0% for" are percentages, not placeholders.
    r"|(?<![\w%])%(?:\d+\$)?[-+#]?(?:\.\d+)?(?:[@sdifuxXeEgGc]|ld|lld|lu)(?![A-Za-z])"
)
ICU_PLURAL_RE = re.compile(r"\{\s*\w+\s*,\s*(plural|select|selectordinal)\s*,")
# Filler patterns (F3) — a starter list per language; extend it if the
# project's language is missing. A match is a CANDIDATE.
FILLERS = {
    "en": [r"\bin order to\b", r"\bbe able to\b", r"\bsimply\b", r"\bjust\b",
           r"\bat this time\b", r"\bplease note\b", r"\bkindly\b", r"\byou will need to\b",
           r"\bit is possible to\b", r"\bin the event that\b"],
    "tr": [r"\bisterseniz\b", r"\buygulama içinden\b", r"\bdaha sonra\b.*\bdaha sonra\b",
           r"ebilirsiniz\b.*\bebilirsiniz\b", r"\bmevcut olan\b", r"\bsöz konusu\b",
           r"\bgerçekleştir", r"\bişlemini yap"],
    "de": [r"\bum\b.*\bzu können\b", r"\bgerne\b", r"\beinfach\b", r"\bbitte beachten\b"],
    "fr": [r"\bafin de pouvoir\b", r"\bsimplement\b", r"\bveuillez noter\b"],
    "es": [r"\bcon el fin de\b", r"\bsimplemente\b", r"\btenga en cuenta\b"],
    "it": [r"\bal fine di\b", r"\bsemplicemente\b", r"\bsi prega di\b", r"\bè possibile\b", r"\bin modo da poter\b"],
    "pt": [r"\ba fim de\b", r"\bsimplesmente\b", r"\btenha em conta\b"],
}
PLURAL_KEY_RE = re.compile(r"[._](zero|one|two|few|many|other)$")

COUNT_NAME_RE = re.compile(
    r"^(count|n|num|number|days?|hours?|minutes?|items?|qty|quantity|total|cycles?|months?|weeks?|years?)$",
    re.I,
)


# ---------------------------------------------------------------- reading

def guess_locale(path: str) -> str:
    base = os.path.basename(path)
    if base.endswith(".properties"):  # journal.properties (default), journal_fr.properties, x_pt_BR.properties
        m = re.match(r"^.*?_([a-z]{2,3})(?:[_-]([A-Za-z]{2,4}))?\.properties$", base)
        return (m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")) if m else "default"
    parts = re.split(r"[\\/]", path)
    for p in reversed(parts[:-1]):
        m = re.match(r"^([a-z]{2,3}(?:[_-][A-Za-z]{2,4})?)\.lproj$", p)
        if m:
            return m.group(1).replace("_", "-")
        if p == "Base.lproj":
            return "base"
        m = re.match(r"^values-([a-z]{2,3})(?:-r([A-Z]{2}))?$", p)
        if m:
            return m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")
        if p == "values":
            return "default"
    m = re.match(r"^(.*)\.(arb|json|ya?ml|po)$", base)
    if m:
        # app_en.arb, intl_pt_BR.arb, messages.de.json, en-US.json, fr.po
        m2 = re.search(r"(?:^|[_\-.])([a-z]{2,3})(?:[_-]([A-Z]{2}|[A-Z][a-z]{3}))?$", m.group(1))
        if m2 and m2.group(1) not in {"app", "intl", "res", "src", "lib"}:
            return m2.group(1) + (f"-{m2.group(2)}" if m2.group(2) else "")
    for p in reversed(parts[:-1]):
        if re.fullmatch(r"[a-z]{2,3}(?:[_-][A-Za-z]{2,4})?", p) and p not in {"src", "lib", "app", "res", "ios", "web"}:
            return p.replace("_", "-")
    return os.path.splitext(base)[0]


def family_of(path: str, root: str, lang: str) -> str:
    """Family name keeping language versions of the same text set together:
    language parts are dropped from the relative path (values-tr → values, en.lproj → lproj,
    app_en.arb → app_.arb, locales/de/common.json → locales/*/common.json)."""
    rel = os.path.relpath(path, root).replace("\\", "/")
    segs = rel.split("/")
    out = []
    for i, seg in enumerate(segs):
        last = i == len(segs) - 1
        seg = re.sub(r"^values(-[a-z]{2,3}(-r[A-Z]{2})?)?$", "values", seg)
        seg = re.sub(r"^[A-Za-z_-]+\.lproj$", "*.lproj", seg)
        if not last and lang != "default" and seg.replace("_", "-") == lang:
            seg = "*"
        if last and seg.endswith(".properties") and lang == "default":
            seg = seg[:-len(".properties")] + "_*.properties"
        elif last:
            seg = re.sub(r"([_\-.])" + re.escape(lang.split("-")[0]) + r"([_-][A-Za-z]{2,4})?(?=\.)", r"\1*", seg)
            if os.path.splitext(seg)[0].replace("_", "-") == lang:
                seg = "*" + os.path.splitext(seg)[1]
        out.append(seg)
    return "/".join(out)


def flatten(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from flatten(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from flatten(v, f"{prefix}[{i}]")
    elif isinstance(obj, str):
        yield prefix, obj


def read_arb(path):
    data = json.load(open(path, encoding="utf-8"))
    texts = {k: v for k, v in data.items() if not k.startswith("@") and isinstance(v, str)}
    meta = {k[1:]: v for k, v in data.items() if k.startswith("@") and not k.startswith("@@") and isinstance(v, dict)}
    return texts, meta


def read_json(path):
    data = json.load(open(path, encoding="utf-8"))
    return dict(flatten(data)), {}


STRINGS_RE = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;', re.M)


_ESCAPE_RE = re.compile(r"\\(U[0-9A-Fa-f]{1,8}|u[0-9A-Fa-f]{1,4}|.)", re.S)


def unescape(s):
    """.strings / .properties escapes. Does not touch non-ASCII letters (unicode_escape corrupted UTF-8:
    "können" → "kÃ¶nnen", e.g. Kickstarter; word counts came out wrong too)."""
    def sub(m):
        c = m.group(1)
        if c[0] in "Uu" and len(c) > 1:
            return chr(int(c[1:], 16))
        return {"n": "\n", "t": "\t", "r": "\r"}.get(c, c)
    return _ESCAPE_RE.sub(sub, s)


def read_strings(path):
    raw = open(path, "rb").read()
    text = None
    for enc in ("utf-8", "utf-16"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", "replace")
    return {unescape(m.group(1)): unescape(m.group(2)) for m in STRINGS_RE.finditer(text)}, {}


def read_stringsdict(path):
    """Old plural format: each key's plural branches become one ICU-like text."""
    out = {}
    with open(path, "rb") as fh:
        data = plistlib.load(fh)
    for key, body in data.items():
        if not isinstance(body, dict):
            continue
        for sub in body.values():
            if isinstance(sub, dict) and "NSStringFormatSpecTypeKey" in sub:
                items = {q: t for q, t in sub.items() if q in ("zero", "one", "two", "few", "many", "other")
                         and isinstance(t, str)}
                if items:
                    out[key] = "{n, plural, " + " ".join(f"{q}{{{t}}}" for q, t in items.items()) + "}"
                    break
    return out, {}


def _xc_value(loc):
    """stringUnit value or plural / device branches (ICU-like)."""
    if "stringUnit" in loc:
        return loc["stringUnit"].get("value")
    var = loc.get("variations") or {}
    plural = var.get("plural")
    if isinstance(plural, dict):
        items = {q: (b.get("stringUnit") or {}).get("value") for q, b in plural.items() if isinstance(b, dict)}
        items = {q: t for q, t in items.items() if t is not None}
        if items:
            return "{n, plural, " + " ".join(f"{q}{{{t}}}" for q, t in items.items()) + "}"
    device = var.get("device")
    if isinstance(device, dict):
        for b in device.values():
            if isinstance(b, dict):
                v = _xc_value(b)
                if v is not None:
                    return v
    return None


def read_xcstrings(path):
    """String Catalog (Apple's current default): all languages in ONE file. {language: {key: text}}, source language.
    With no translation entry in the source language, the text is the key itself."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    source = data.get("sourceLanguage", "en")
    by_lang = collections.defaultdict(dict)
    for key, entry in (data.get("strings") or {}).items():
        if not key.strip() or entry.get("shouldTranslate") is False:
            continue
        locs = entry.get("localizations") or {}
        for lang, loc in locs.items():
            value = _xc_value(loc) if isinstance(loc, dict) else None
            if value is not None:
                by_lang[lang][key] = value
        if source not in locs:
            by_lang[source][key] = key
    return dict(by_lang), source


def read_properties(path):
    """Java .properties (libGDX, non-Android Java). key=value, # ! comment, trailing \\ continuation."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    out, buf = {}, ""
    for line in lines:
        line = buf + line.lstrip()
        buf = ""
        if not line or line[0] in "#!":
            continue
        if line.endswith("\\") and not line.endswith("\\\\"):
            buf = line[:-1]
            continue
        m = re.match(r"((?:[^=:\s\\]|\\.)+)\s*[=:\s]\s*(.*)$", line, re.S)
        if m:
            out[unescape(m.group(1))] = unescape(m.group(2))
    return out, {}


def read_android(path):
    out = {}
    root = ET.parse(path).getroot()
    for el in root:
        name = el.get("name")
        if not name or el.get("translatable") == "false":
            continue
        if el.tag == "string":
            out[name] = "".join(el.itertext()).replace("\\'", "'").replace('\\"', '"')
        elif el.tag == "plurals":
            items = {i.get("quantity"): "".join(i.itertext()) for i in el}
            out[name] = "{n, plural, " + " ".join(f"{q}{{{t}}}" for q, t in items.items()) + "}"
    return out, {}


def read_po(path):
    out, msgid, cur = {}, None, None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line.startswith("msgid "):
            msgid, cur = json.loads(line[6:]), "id"
        elif line.startswith("msgstr "):
            out[msgid] = json.loads(line[7:])
            cur = "str"
        elif line.startswith('"') and msgid is not None:
            if cur == "id":
                msgid += json.loads(line)
            elif cur == "str":
                out[msgid] += json.loads(line)
    out.pop("", None)
    return out, {}


def read_yaml(path):
    try:
        import yaml  # type: ignore
    except ImportError:
        print(f"<!-- no PyYAML, skipped: {path} -->", file=sys.stderr)
        return {}, {}
    data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    # Rails: the single root key is the language code.
    if isinstance(data, dict) and len(data) == 1:
        data = next(iter(data.values()))
    return dict(flatten(data)), {}


def looks_like_locale_json(path):
    p = path.replace("\\", "/").lower()
    return any(s in p for s in ("/locales/", "/locale/", "/i18n/", "/lang/", "/translations/", "/messages/", "/l10n/"))


def code_language_modules(root):
    """If translations are kept as a CODE module (languages/en.ts, locales/de.js), this script cannot read them: do not stay silent."""
    hits = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if os.path.basename(dirpath).lower() in ("languages", "locales", "lang", "i18n", "translations"):
            mods = [f for f in filenames if re.fullmatch(r"[a-z]{2}(-[A-Za-z]{2,4})?\.(ts|js|tsx|jsx|mjs)", f)]
            if len(mods) >= 2:
                hits[os.path.relpath(dirpath, root).replace("\\", "/")] = len(mods)
    if not hits:
        return ""
    where = ", ".join(f"`{d}` ({n} languages)" for d, n in sorted(hits.items())[:4])
    return f"> NOT READ: translations kept as a code module: {where}. This text is NOT in the dump; read it by hand (SKILL.md Step 1)."


def discover(root):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            p = os.path.join(dirpath, f)
            low = f.lower()
            if low.endswith(".arb"):
                found.append((p, read_arb))
            elif low.endswith(".strings") and ".lproj" in dirpath:
                found.append((p, read_strings))
            elif low.endswith(".stringsdict") and ".lproj" in dirpath:
                found.append((p, read_stringsdict))
            elif low.endswith(".xcstrings"):
                found.append((p, read_xcstrings))
            elif low.endswith(".properties") and looks_like_locale_json("/" + os.path.relpath(p, root)):
                found.append((p, read_properties))
            elif low == "strings.xml" and os.path.basename(dirpath).startswith("values"):
                found.append((p, read_android))
            elif low.endswith(".po"):
                found.append((p, read_po))
            elif low.endswith(".json") and looks_like_locale_json("/" + os.path.relpath(p, root)) and "package" not in low:
                found.append((p, read_json))
            elif low.endswith((".yml", ".yaml")) and looks_like_locale_json("/" + os.path.relpath(p, root)):
                found.append((p, read_yaml))
    return found


# ---------------------------------------------------------------- measuring

def strip_markup(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return s


def icu_branches(s):
    """Returns the branches of ICU plural/select bodies ([s] if none)."""
    if not ICU_PLURAL_RE.search(s):
        return [s]
    branches, depth, buf, inside = [], 0, "", False
    for ch in s:
        if ch == "{":
            depth += 1
            if depth == 2:
                buf, inside = "", True
                continue
        elif ch == "}":
            if depth == 2 and inside:
                branches.append(buf)
                inside = False
            depth -= 1
            continue
        if inside:
            buf += ch
    return branches or [s]


def length(s, lang):
    best = 0
    for b in icu_branches(strip_markup(s)):
        b = PLACEHOLDER_RE.sub(" X ", b)
        if lang.split("-")[0] in NO_SPACE_LANGS:
            n = len(re.sub(r"\s", "", b)) / 2
        else:
            n = len(b.split())
        best = max(best, n)
    return round(best, 1)


def category(key, text):
    k = key.lower()
    if re.search(r"semantic|a11y|accessib|aria|contentdesc|voiceover", k):
        return "a11y"
    if re.search(r"error|invalid|failed|fail|required|toolarge|outofrange", k):
        return "error"
    if re.search(r"^notif|notification.*(body|title)|push", k):
        return "notification"
    if re.search(r"confirm|delete.*body|erase|archive.*body|body$", k):
        return "confirm"
    if re.search(r"onboard|welcome|intro|setup|paywall|benefit", k):
        return "onboarding"
    if re.search(r"hint|help|explain|description|note|detail|empty|caption|info", k):
        return "hint"
    if re.search(r"button|cta|action|label|title|tab|menu|upper$", k) or len(text.split()) <= 3:
        return "button"
    return "other"


def placeholders(s):
    names = set()
    for m in PLACEHOLDER_RE.finditer(s):
        t = m.group(0)
        if t.startswith("{{"):
            names.add(t.strip("{} "))
        elif t.startswith("{"):
            names.add(t.strip("{}"))
        else:
            names.add("%" + re.sub(r"^%(\d+\$)?.*?([@sdifuxXeEgGc])$", r"\1\2", t))
    for m in re.finditer(r"\{\s*(\w+)\s*,\s*(?:plural|select|selectordinal)\s*,", s):
        names.add(m.group(1))
    return names


WORD_RE = re.compile(r"[^\W\d_]+", re.U)


def words(s):
    return [w.lower() for w in WORD_RE.findall(PLACEHOLDER_RE.sub(" ", strip_markup(s)))]


# Short function words (not counted as repeats); not language-specific, the
# length threshold is the real filter (stem ≥ 5 letters).
STOP_PREFIX = {"which", "there", "their", "about", "would", "could", "should", "these", "those"}


def inner_repeats(s):
    """Words starting with the same 5-letter stem in ≥2 different positions in a text."""
    stems = collections.Counter()
    for w in words(s):
        if len(w) >= 6 and w[:5] not in STOP_PREFIX:
            stems[w[:5]] += 1
    return sorted(k for k, c in stems.items() if c >= 2)


def sentences(s):
    return [x.strip() for x in re.split(r"(?<=[.!?。！？])\s+", s) if len(x.split()) >= 4]


# ---------------------------------------------------------------- main flow

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", default=None)
    ap.add_argument("--source", default=None, help="source language (default: the one with the most keys)")
    ap.add_argument("--files", nargs="*", help="read these files instead of discovering")
    ap.add_argument("--max", type=int, default=40, help="maximum rows per section")
    a = ap.parse_args()

    if not a.files and not os.path.isdir(a.root):
        print(f"Folder does not exist or is not a folder: {a.root}", file=sys.stderr)
        sys.exit(2)
    out = a.out or tempfile.mkdtemp(prefix="copy-inventory-")
    problem = unsafe_out(out, a.root)
    if problem:
        print(problem, file=sys.stderr)
        sys.exit(2)
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, MARKER), "w").close()

    if a.files:
        readers = {".arb": read_arb, ".json": read_json, ".strings": read_strings,
                   ".xml": read_android, ".po": read_po, ".yml": read_yaml, ".yaml": read_yaml,
                   ".xcstrings": read_xcstrings, ".stringsdict": read_stringsdict, ".properties": read_properties}
        files = [(f, readers[os.path.splitext(f)[1].lower()]) for f in a.files]
    else:
        files = discover(a.root)
    code_langs = code_language_modules(a.root)
    if not files:
        print("No translation files found. Text may be hardcoded in components (SKILL.md Step 1).")
        if code_langs:
            print(code_langs)
        return

    families: dict[str, dict[str, dict[str, str]]] = collections.defaultdict(lambda: collections.defaultdict(dict))
    meta: dict[str, dict] = {}
    catalog_source: dict[str, str] = {}
    for path, reader in files:
        try:
            texts, m = reader(path)
        except Exception as e:  # a broken file must not stop the report
            print(f"<!-- could not read: {path}: {e} -->", file=sys.stderr)
            continue
        if reader is read_xcstrings:  # all languages in one file
            fam = os.path.relpath(path, a.root).replace("\\", "/")
            catalog_source[fam] = m
            for lang, values in texts.items():
                families[fam][lang].update(values)
            continue
        lang = guess_locale(path)
        families[family_of(path, a.root, lang)][lang].update(texts)
        meta.update(m)

    p = print
    p(f"# Text inventory\n\nRoot: `{a.root}` · files: {len(files)} · families: {len(families)} · dumps: `{out}`\n")
    summary_all = []
    for fam in sorted(families):
        by_lang = families[fam]
        langs = sorted(by_lang, key=lambda l: (l != "default", -len(by_lang[l]), l.split("-")[0] != "en", l))
        source = a.source if a.source in by_lang else (
            catalog_source[fam] if catalog_source.get(fam) in by_lang else langs[0])
        p(f"# Family `{fam}`\n\nLanguages: " + ", ".join(f"{l} ({len(by_lang[l])})" for l in langs)
          + f" · source: **{source}**\n")
        summary_all += audit_family(fam, by_lang, langs, source, meta, out, a.max)

    p("# Summary (only those with findings)\n")
    for title, n in summary_all:
        if n:
            p(f"- {title}: {n}")
    p("")
    if code_langs:
        p(code_langs + "\n")
    p("> This list is a CANDIDATE. Verify each item by reading the text; the meaning/behaviour (D) "
      "check is not this script's job.")


MARKER = ".copy-inventory"


def unsafe_out(out, root):
    """Why writing to `out` could harm the user's files, or None. Output never goes into the project, and an
    existing folder is reused only if this script made it."""
    real_out, real_root = os.path.realpath(out), os.path.realpath(root)
    if real_out == real_root or real_out.startswith(real_root.rstrip(os.sep) + os.sep):
        return f"--out is inside the project ({root}): give a folder outside it"
    if os.path.isdir(out) and os.listdir(out) and not os.path.exists(os.path.join(out, MARKER)):
        return f"--out ({out}) already holds other files: give an empty folder"
    return None


def audit_family(fam, by_lang, langs, source, meta, out, maxrows):
    p = print
    tag = re.sub(r"[^\w.-]+", "_", fam).strip("_")

    # 1) Dumps
    for l in langs:
        path = os.path.join(out, f"inventory_{tag}_{l}.tsv")
        with open(path, "w", encoding="utf-8") as f:
            for k, v in by_lang[l].items():
                f.write(f"{k}\t{length(v, l)}\t{category(k, v)}\t{v.replace(chr(10), ' ⏎ ')}\n")

    summary = []

    def section(title, rows, note=""):
        summary.append((title, len(rows)))
        if not rows:
            return
        p(f"## {title} ({len(rows)})\n")
        if note:
            p(note + "\n")
        for r in rows[:maxrows]:
            p(f"- {r}")
        if len(rows) > maxrows:
            p(f"- … +{len(rows) - maxrows} (all in the dump)")
        p("")

    src = by_lang[source]

    # 2) Missing / untranslated
    rows = []
    for l in langs:
        if l == source:
            continue
        missing = [k for k in src if k not in by_lang[l]]
        src_values = {v for v in src.values() if len(v.split()) >= 3}
        same = [k for k, v in by_lang[l].items() if len(v.split()) >= 3 and v in src_values]
        if missing:
            rows.append(f"**{l}** missing: {', '.join(missing[:15])}{' …' if len(missing) > 15 else ''}")
        if same:
            rows.append(f"**{l}** same as source (may be untranslated): {', '.join(same[:15])}{' …' if len(same) > 15 else ''}")
    section("Missing or untranslated keys", rows)

    # 3) Placeholder mismatch
    rows = []
    for k, v in src.items():
        ps = placeholders(v)
        for l in langs:
            if l == source or k not in by_lang[l]:
                continue
            pl = placeholders(by_lang[l][k])
            if ps != pl:
                rows.append(f"`{k}` {source}: {sorted(ps)} ≠ {l}: {sorted(pl)}")
    section("Placeholder mismatch (C)", rows, "Risk of an empty value or a raw `{x}` leak at runtime.")

    # 4) Missing plural form
    rows = []
    for l in langs:
        if l.split("-")[0] in NO_PLURAL_LANGS:
            continue
        for k, v in by_lang[l].items():
            if ICU_PLURAL_RE.search(v) or PLURAL_KEY_RE.search(k):
                continue
            numeric = set()
            for name, d in (meta.get(k, {}).get("placeholders") or {}).items():
                if isinstance(d, dict) and d.get("type") in ("int", "num", "double"):
                    numeric.add(name)
            for ph in placeholders(v):
                bare = ph.lstrip("%")
                if COUNT_NAME_RE.match(bare) or (ph.startswith("%") and ph.endswith("d")):
                    numeric.add(ph)
            # Noun-less use like "Day {day}/{total}", "{count} on": a candidate
            # if a noun follows the number.
            for ph in numeric:
                if ph.startswith("%"):
                    tok = r"%(?:\d+\$)?(?:l|ll)?[du]"
                else:
                    tok = r"(?:\{\{\s*" + re.escape(ph) + r"\s*\}\}|\{" + re.escape(ph) + r"\})"
                if re.search(tok + r"\s+[^\W\d_]{3,}", v):
                    rows.append(f"**{l}** `{k}`: {v}")
                    break
    section("Number + noun, no plural form (C)", rows,
            "READ with 0, 1, 2 and a large number: e.g. EN \"+1 more buckets\". If the number follows the noun (\"Day {day}\") it is usually fine.")

    # 5) Long text over threshold (F)
    for l in langs:
        rows = []
        for k, v in by_lang[l].items():
            c = category(k, v)
            n = length(v, l)
            if n > THRESHOLDS[c]:
                rows.append((n, f"`{k}` [{c}] **{n}** — {v}"))
        rows.sort(key=lambda r: -r[0])
        section(f"Over threshold long text · {l} (F)", [r[1] for r in rows],
                "Thresholds: " + ", ".join(f"{k} {v}" for k, v in THRESHOLDS.items()) + " words. READ them all; being long is not an error by itself.")

    # 6) Same sentence in several keys (F4/F5)
    for l in langs:
        idx = collections.defaultdict(list)
        for k, v in by_lang[l].items():
            for s in sentences(v):
                idx[s].append(k)
        rows = [f"×{len(ks)} \"{s}\" — {', '.join(ks[:8])}{' …' if len(ks) > 8 else ''}"
                for s, ks in sorted(idx.items(), key=lambda x: -len(x[1])) if len(ks) >= 3]
        section(f"Same sentence in ≥3 keys · {l} (F4/F5)", rows, "Can it become one pattern, can it be shorter?")

    # 7) Same idea: shared 3-word sequence (F4)
    for l in langs:
        idx = collections.defaultdict(set)
        for k, v in by_lang[l].items():
            w = words(v)
            for i in range(len(w) - 2):
                tri = tuple(w[i:i + 3])
                if all(len(x) >= 3 for x in tri):
                    idx[tri].add(k)
        groups = [(tri, ks) for tri, ks in idx.items() if 3 <= len(ks) <= 12]
        groups.sort(key=lambda g: -len(g[1]))
        seen, rows = set(), []
        for tri, ks in groups:
            key = frozenset(ks)
            if key in seen:
                continue
            seen.add(key)
            lens = sorted({int(length(by_lang[l][k], l)) for k in ks})
            if len(lens) >= 2 and lens[-1] >= 2 * max(lens[0], 1):
                rows.append(f"\"{' '.join(tri)}\" — {len(ks)} keys, length {lens[0]}–{lens[-1]}: {', '.join(sorted(ks)[:8])}")
        section(f"Same idea at different lengths · {l} (F4)", rows,
                "Shared 3-word sequence + the longest is ≥2× the shortest. If the same idea, suggest ONE pattern.")

    # 8) Stem repetition within a text (F1)
    for l in langs:
        rows = []
        for k, v in by_lang[l].items():
            reps = inner_repeats(v)
            if reps and length(v, l) >= 8:
                rows.append(f"`{k}` [{', '.join(reps)}…] — {v}")
        section(f"Stem repetition within a text · {l} (F1)", rows,
                "Same stem twice: a real repeat (\"can't be closed … close the gap\") or needed (product name)? READ.")

    # 9) Filler patterns (F3)
    for l in langs:
        pats = FILLERS.get(l.split("-")[0])
        if not pats:
            continue
        rows = []
        for k, v in by_lang[l].items():
            hit = [pt for pt in pats if re.search(pt, v, re.I)]
            if hit:
                rows.append(f"`{k}` — {v}")
        section(f"Filler patterns · {l} (F3)", rows,
                "Can it be shorter? If used deliberately for the brand voice (A), leave it.")

    return [(f"{fam} · {t}", n) for t, n in summary]


if __name__ == "__main__":
    main()
