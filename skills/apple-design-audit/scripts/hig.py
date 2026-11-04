#!/usr/bin/env python3
"""apple-design — reads Apple's Human Interface Guidelines from the official site (rule text is not copied into the skill).

Standard library only (Python 3.9+); does NOT write to the project. Pages read are stored under ~/.cache/apptest/hig/:
with no internet, the old copy is given with a "read on this date" warning; with no copy at all it plainly says
"could not read" (exit 3); no rule is made up.

    python3 -I hig.py list                     # all topics (section › title › slug)
    python3 -I hig.py read tab-bars [--max 6000]
    python3 -I hig.py find "toast"             # searches titles and abstracts
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

BASE = "https://developer.apple.com/tutorials/data/design/human-interface-guidelines"
WEB = "https://developer.apple.com/design/human-interface-guidelines"
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "apptest", "hig")
SLUG = re.compile(r"^[a-z0-9-]+$")


def _cache_path(slug):
    return os.path.join(CACHE, slug + ".json")


def fetch(slug, max_age=None):
    """(json, source_note). The site first; failing that the cache; failing that None. If max_age (s) is given and the
    copy is that recent, the site is not read: for the topic list only; page reads (read) are always live."""
    if max_age is not None and os.path.exists(_cache_path(slug)) and \
            time.time() - os.path.getmtime(_cache_path(slug)) < max_age:
        with open(_cache_path(slug), encoding="utf-8") as fh:
            return json.load(fh), "Topic list from a copy read in the last 24 hours"
    url = f"{BASE}.json" if slug == "index" else f"{BASE}/{slug}.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "apple-design"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
        data = json.loads(raw.decode("utf-8"))
        os.makedirs(CACHE, exist_ok=True)
        with open(_cache_path(slug), "wb") as fh:
            fh.write(raw)
        return data, f"Read from Apple's site just now ({time.strftime('%Y-%m-%d')})"
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", None)
        if code == 404:
            return None, f"no such page: {slug}"
        path = _cache_path(slug)
        if os.path.exists(path):
            day = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(path)))
            with open(path, encoding="utf-8") as fh:
                return json.load(fh), f"WARNING: could not read the site; copy from {day}. Apple may have changed it."
        return None, f"could not read ({type(e).__name__}) and no copy: internet required"


def _inline(items, refs):
    out = []
    for x in items or []:
        t = x.get("type")
        if t == "text":
            out.append(x.get("text", ""))
        elif t == "codeVoice":
            out.append(x.get("code", ""))
        elif t == "reference":
            r = refs.get(x.get("identifier"), {})
            out.append(r.get("title", ""))
        elif "inlineContent" in x:
            out.append(_inline(x["inlineContent"], refs))
    return "".join(out)


def _blocks(items, refs, out):
    for b in items or []:
        t = b.get("type")
        if t == "heading":
            out.append("\n" + "#" * min(int(b.get("level", 2)) + 1, 4) + " " + b.get("text", ""))
        elif t == "paragraph":
            out.append(_inline(b.get("inlineContent"), refs))
        elif t in ("unorderedList", "orderedList"):
            for it in b.get("items", []):
                sub = []
                _blocks(it.get("content"), refs, sub)
                out.append("- " + " ".join(sub))
        elif t == "aside":
            sub = []
            _blocks(b.get("content"), refs, sub)
            out.append(f"[{b.get('style', 'note')}] " + " ".join(sub))
        elif t == "table":
            for row in b.get("rows", []):
                cells = []
                for c in row:
                    sub = []
                    _blocks(c, refs, sub)
                    cells.append(" ".join(sub))
                out.append(" | ".join(cells))
        elif "content" in b:
            _blocks(b["content"], refs, out)


def read_page(slug, limit):
    data, note = fetch(slug)
    if data is None:
        print(f"Could not read the HIG: {note}", file=sys.stderr)
        return 3
    refs = data.get("references", {})
    out = []
    for s in data.get("primaryContentSections", []):
        _blocks(s.get("content"), refs, out)
    title = data.get("metadata", {}).get("title", slug)
    abstract = _inline(data.get("abstract"), refs).strip()
    text = "\n".join(x for x in out if x.strip())
    print(f"# {title}\nSource: {WEB}/{slug}\n{note}\n\n{abstract}\n{text[:limit]}")
    if len(text) > limit:
        print(f"\n… (cut off: {len(text)} characters; increase with --max)")
    return 0


def _tree():
    """[(section, title, slug, abstract)] — topics under the six main sections and groups (e.g. Components › Navigation)."""
    root, note = fetch("index")
    if root is None:
        return None, note
    out, notes = [], {note}
    refs = root.get("references", {})
    ids = [i for s in root.get("topicSections", []) for i in s.get("identifiers", [])]
    level = [(refs[i].get("title", ""), i, refs[i].get("title", ""), "", 0) for i in ids if i in refs]

    def visit(item):
        section, ident, title, abstract, depth = item
        return item, fetch(ident.rsplit("/", 1)[-1], max_age=86400)

    with ThreadPoolExecutor(max_workers=12) as pool:
        while level:
            nxt = []
            for (section, ident, title, abstract, depth), (data, n) in pool.map(visit, level):
                notes.add(n)
                if data is None:
                    continue
                r = data.get("references", {})
                kids = [x for sec in data.get("topicSections", []) for x in sec.get("identifiers", []) if x in r]
                if depth < 3 and kids:
                    nxt += [(section, x, r[x].get("title", ""), _inline(r[x].get("abstract"), r), depth + 1) for x in kids]
                else:
                    out.append((section, title, ident.rsplit("/", 1)[-1], abstract))
            level = nxt
    uniq = {t[2]: t for t in out}
    return sorted(uniq.values()), sorted(notes)[-1]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reads Apple's HIG from the official site.")
    ap.add_argument("command", choices=["list", "read", "find"])
    ap.add_argument("target", nargs="?")
    ap.add_argument("--max", type=int, default=6000)
    a = ap.parse_args(argv)
    if a.command == "read":
        if not a.target or not SLUG.match(a.target):
            ap.error("read: slug required (e.g. tab-bars)")
        return read_page(a.target, a.max)
    tree, note = _tree()
    if tree is None:
        print(f"Could not read the HIG: {note}", file=sys.stderr)
        return 3
    if a.command == "find":
        if not a.target:
            ap.error("find: search word required")
        tree = [t for t in tree if a.target.lower() in (t[1] + " " + t[3]).lower()]
    print(f"{note}\n")
    for section, title, slug, abstract in tree:
        print(f"{section} › {title} · {slug}" + (f" — {abstract[:90]}" if a.command == "find" else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
