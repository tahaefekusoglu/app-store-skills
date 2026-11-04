#!/usr/bin/env python3
"""apptest-store-assets: checks a folder of store screenshots, preview videos or
in-app purchase review screenshots: format, accepted pixel size, alpha channel,
count per device class (1–10), required classes covered.

Standard library only; does NOT write to the images. The size table below is
DATED and Apple may change it: read the official page before use (CONVENTIONS principle 7):
https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/

    python3 -I assets_check.py <folder> [--ipad] [--json]
      --ipad : the app also runs on iPad (a 13" iPad set becomes required)
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import subprocess
import sys
import zlib

# Non-ASCII characters must not crash output on a non-UTF-8 console such as Windows (every OS).
for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SPEC_DATE = "2026-10-29"
# (class, requirement, portrait sizes); landscape swaps width and height.
CLASSES = [
    # Page as of 2026-10-29: a large screen is REQUIRED: 6.5" (Face ID large) if 6.9" is not provided; a missing
    # medium set is scaled from the large one (on 2026-10-28 medium read "required": the page can change, principle 7).
    ("iPhone · Dynamic Island (large, 6.9\")", "6.9\" or 6.5\" REQUIRED", [(1260, 2736), (1290, 2796), (1320, 2868)]),
    ("iPhone · Dynamic Island (medium, 6.1\"/6.3\")", "optional (otherwise from the large set)", [(1179, 2556), (1206, 2622)]),
    ("iPhone · Face ID (large, 6.5\")", "REQUIRED if no 6.9\"", [(1284, 2778), (1242, 2688)]),
    ("iPhone · Face ID (medium)", "optional", [(1170, 2532), (1125, 2436), (1080, 2340)]),
    ("iPhone · Home button (5.5\")", "optional", [(1242, 2208)]),
    ("iPhone · Home button (4.7\")", "optional", [(750, 1334)]),
    ("iPhone · 4\"", "optional", [(640, 1096), (640, 1136)]),
    ("iPhone · Duo (outer)", "optional (required with the iOS 27.1 SDK from April 2027)", [(1398, 2034)]),
    ("iPhone · Duo (inner)", "optional (required with the iOS 27.1 SDK from April 2027)", [(2007, 2853)]),
    ("iPad · 13\"", "REQUIRED if iPad is supported", [(2064, 2752), (2048, 2732)]),
    ("iPad · 11\"", "optional", [(1488, 2266), (1668, 2420), (1668, 2388), (1640, 2360)]),
    ("iPad · 10.5\"", "optional", [(1668, 2224)]),
]
IMG_EXT = (".png", ".jpg", ".jpeg")
VID_EXT = (".mov", ".mp4", ".m4v")


def png_alpha(data: bytes) -> tuple[bool, bool | None]:
    """(has alpha channel, has transparent pixel); pixels are measured for 8-bit, non-interlaced PNG."""
    ctype, bit, interlace = data[25], data[24], data[28]
    trns = b"tRNS" in data[:300000]
    if ctype not in (4, 6) and not trns:
        return False, False
    if ctype not in (4, 6) or bit != 8 or interlace:
        return True, None
    pos, idat = 8, b""
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        if data[pos + 4:pos + 8] == b"IDAT":
            idat += data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
    try:
        raw = zlib.decompress(idat)
    except zlib.error:
        return True, None
    w, h = struct.unpack(">II", data[16:24])
    bpp = 4 if ctype == 6 else 2
    stride, prev, o = w * bpp, bytearray(w * bpp), 0
    for _ in range(h):
        ft, line = raw[o], bytearray(raw[o + 1:o + 1 + stride])
        o += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if ft == 1:
                line[x] = (line[x] + a) & 255
            elif ft == 2:
                line[x] = (line[x] + b) & 255
            elif ft == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif ft == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
        if any(line[i] != 255 for i in range(bpp - 1, stride, bpp)):
            return True, True
        prev = line
    return True, False


def jpeg_size(data: bytes):
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def image_info(path: str):
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        alpha, transparent = png_alpha(data)
        return "png", w, h, alpha, transparent
    if data[:2] == b"\xff\xd8":
        sz = jpeg_size(data)
        return ("jpeg", *sz, False, False) if sz else ("jpeg", None, None, False, False)
    return None


def classify(w, h):
    for name, need, sizes in CLASSES:
        for pw, ph in sizes:
            if (w, h) in ((pw, ph), (ph, pw)):
                return name, need, "portrait" if h > w else "landscape"
    return None, None, None


def video_duration(path: str):
    try:
        out = subprocess.run(["mdls", "-raw", "-name", "kMDItemDurationSeconds", path],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return float(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--ipad", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.folder):
        print(f"folder missing or not accessible: {a.folder}", file=sys.stderr)
        return 2
    findings, per_class, images, videos = [], {}, 0, {}

    def add(fid, sev, title, ev, note=""):
        findings.append({"id": fid, "severity": sev, "title": title, "evidence": ev, "note": note})

    for dirpath, _dirs, files in os.walk(a.folder):
        for fn in sorted(files):
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, a.folder)
            low = fn.lower()
            if low.endswith(VID_EXT):
                videos.setdefault(os.path.dirname(rel) or ".", []).append(rel)
                mb = os.path.getsize(path) / 1_000_000
                dur = video_duration(path)
                if mb > 500:
                    add("SA-20", "REJECTION RISK", f"Preview video is {mb:.0f} MB (500 MB at most)", rel)
                if dur is not None and not (15 <= dur <= 30):
                    add("SA-20", "REJECTION RISK", f"Preview video is {dur:.1f} s (must be 15–30 s)", rel)
                if dur is None:
                    add("SA-20", "INFO", "Could not measure video length (verify 15–30 s, ≤500 MB by hand)", rel)
                continue
            if not low.endswith(IMG_EXT):
                continue
            info = image_info(path)
            if not info or info[1] is None:
                add("SA-10", "REJECTION RISK", "Image unreadable or unsupported format", rel, ".png / .jpg / .jpeg only.")
                continue
            images += 1
            kind, w, h, alpha, transparent = info
            if alpha:
                add("SA-11", "REJECTION RISK", "Has an alpha channel" + (" (and transparent pixels)" if transparent else ""), rel,
                    "App Store Connect does not accept images with an alpha channel: export as RGB PNG or JPEG "
                    "(e.g. a budgeting app's in-app purchase review screenshot was rejected for this).")
            name, need, orient = classify(w, h)
            if not name:
                add("SA-12", "REJECTION RISK", f"Size not accepted: {w}×{h}", rel,
                    "If this is not a store screenshot (in-app purchase review screenshot) only the alpha rule applies.")
                continue
            group = os.path.dirname(rel) or "."
            per_class.setdefault((group, name), []).append((rel, orient, need))
    for (group, name), items in sorted(per_class.items()):
        orients = {o for _r, o, _n in items}
        if len(items) > 10:
            add("SA-13", "REJECTION RISK", f"{name}: {len(items)} images (10 at most)", group)
        if len(orients) > 1:
            add("SA-14", "SUGGESTION", f"{name}: mixed portrait and landscape", group, "A single orientation looks tidier in the store.")
    for g, vids in videos.items():
        if len(vids) > 3:
            add("SA-21", "REJECTION RISK", f"{len(vids)} preview videos (3 at most per device and language)", g,
                "H.264 / ProRes 422 HQ, 30 fps at most (not verified: fps is not measured).")
    groups = sorted({g for g, _ in per_class})
    all_names = {n for _g, n in per_class}
    iphone = any(n.startswith("iPhone") for n in all_names)
    has_large = any("large, 6.9" in n or "Face ID (large" in n for n in all_names)
    if images and not has_large:
        add("SA-15", "REJECTION RISK",
            "No large-screen iPhone set: 6.9\" (1320×2868 / 1290×2796 / 1260×2736) or 6.5\" (1284×2778 / 1242×2688)",
            a.folder,
            "Apple: the 6.5\" set is required if 6.9\" is not provided; medium (1206×2622) alone is not enough. "
            "If they are in separate folders, pass their common parent folder. Verify the rule on the page every time.")
    elif iphone and has_large and not any("medium, 6.1" in n for n in all_names):
        add("SA-15", "INFO", "No medium (1206×2622) set: it is scaled from the large set", a.folder)
    for g in groups:
        names = {n for gg, n in per_class if gg == g}
        if a.ipad and not any("13\"" in n for n in names):
            add("SA-16", "REJECTION RISK", "The app runs on iPad but there is no 13\" iPad set", g)
    if not images:
        add("SA-10", "INFO", "No images in the folder", a.folder)
    order = {"REJECTION RISK": 0, "USER BUG": 1, "SUGGESTION": 2, "INFO": 3}
    findings.sort(key=lambda f: (order[f["severity"]], f["id"]))
    summary = {f"{g} · {n}": len(v) for (g, n), v in sorted(per_class.items())}
    if a.json:
        json.dump({"member": "SA", "folder": os.path.abspath(a.folder), "spec_date": SPEC_DATE, "images": images,
                   "classes": summary, "findings": findings}, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0
    print(f"# store-assets check — `{os.path.abspath(a.folder)}`\n")
    print(f"Size table dated {SPEC_DATE}: compare with Apple's page before submitting (principle 7).\n")
    print(f"Images: {images}\n\n| Folder · class | Count |\n|---|---|")
    for k, v in summary.items():
        print(f"| {k} | {v} |")
    cur = None
    for f in findings:
        if f["severity"] != cur:
            cur = f["severity"]
            print(f"\n## {cur}")
        note = f" — {f['note']}" if f["note"] else ""
        print(f"- [{f['id']}] {f['title']} — `{f['evidence']}`{note}")
    if not findings:
        print("\nNo candidates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
