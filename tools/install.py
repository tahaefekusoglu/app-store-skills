#!/usr/bin/env python3
"""Copies the skills into a Claude Code skills folder. Standard library only.

    python3 tools/install.py                      # to ~/.claude/skills
    python3 tools/install.py --target <folder>    # try it elsewhere first
    python3 tools/install.py --overlay <folder>   # optional personal layer, see below

Replaces only the skill folders this repo ships; other skills in the target stay untouched. An overlay folder may hold
`app-SKILL.md` (your own short names) and `descriptions-<lang>.json` ({"skill-name": "\\"description\\""}), so you can
keep commands and descriptions in your language without changing the repo.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=os.path.join(os.path.expanduser("~"), ".claude", "skills"))
    ap.add_argument("--overlay")
    a = ap.parse_args()
    os.makedirs(a.target, exist_ok=True)
    src = os.path.join(ROOT, "skills")
    names = sorted(n for n in os.listdir(src) if os.path.isfile(os.path.join(src, n, "SKILL.md")))
    for n in names:
        dst = os.path.join(a.target, n)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(os.path.join(src, n), dst, ignore=shutil.ignore_patterns("__pycache__"))
    if a.overlay:
        app = os.path.join(a.overlay, "app-SKILL.md")
        if os.path.isfile(app):
            with open(app, encoding="utf-8") as fh:
                if "~/.claude/skills" in fh.read():
                    print("warning: the overlay's app-SKILL.md names ~/.claude/skills; use ${CLAUDE_SKILL_DIR}/.. so it "
                          "works wherever the skills are installed", file=sys.stderr)
            shutil.copy(app, os.path.join(a.target, "app", "SKILL.md"))
        for f in glob.glob(os.path.join(a.overlay, "descriptions-*.json")):
            with open(f, encoding="utf-8") as fh:
                table = json.load(fh)
            for n, d in table.items():
                p = os.path.join(a.target, n, "SKILL.md")
                if n == "app" or not os.path.isfile(p):
                    continue
                with open(p, encoding="utf-8") as fh:
                    s = fh.read()
                s = re.sub(r"^description: .*$", lambda _: "description: " + d, s, count=1, flags=re.M)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(s)
    print(f"installed {len(names)} skills to {a.target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
