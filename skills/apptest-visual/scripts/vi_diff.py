#!/usr/bin/env python3
"""apptest-visual — compares two screenshot folders (base / new) pixel by pixel.

Standard library only (Python 3.9+, zlib): reads all PNG color types (gray, RGB, palette, gray+alpha,
RGBA), 1/2/4/8/16 bit, including interlaced (Adam7). JPEG is not read (a lossy format does not suit pixel
diffs: capture PNG). Does NOT write to the project; diff images go to the --out folder (OUTSIDE the project, VI-P1).

    python3 -I vi_diff.py <base_folder> <new_folder> --out <diff_folder>
        [--tolerance 8] [--max-ratio 0] [--mask-top 0] [--mask x,y,w,h ...]
        [--mask-file masks.json] [--jobs N] [--json] [--allow-in-repo]
    python3 -I vi_diff.py --self-test

Exit code: 0 = no difference above threshold · 1 = difference / missing / size difference · 2 = usage or read error.
masks.json: {"<file pattern (fnmatch)>": [[x, y, w, h], ...]} — clock, cursor, random content.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import struct
import sys
import tempfile
import zlib

for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

PNG_SIG = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
ADAM7 = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))


class PngError(Exception):
    pass


def _chunks(data: bytes):
    if data[:8] != PNG_SIG:
        raise PngError("not a PNG (no signature) — if JPEG, capture as PNG")
    i = 8
    while i + 8 <= len(data):
        n, kind = struct.unpack(">I4s", data[i:i + 8])
        body = data[i + 8:i + 8 + n]
        if len(body) != n:
            raise PngError("truncated file")
        yield kind, body
        i += 12 + n
        if kind == b"IEND":
            return
    raise PngError("no IEND (truncated file)")


def _unfilter(raw, w, h, bpp, stride, pos):
    """Undoes row filters; (bytearray rows, new position)."""
    out = []
    prev = bytearray(stride)
    for _ in range(h):
        if pos >= len(raw):
            raise PngError("image data missing")
        ft = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        if len(line) != stride:
            raise PngError("image data missing")
        pos += 1 + stride
        if ft == 0:
            pass
        elif ft == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 0xFF
        elif ft == 2:
            line = bytearray((a + b) & 0xFF for a, b in zip(line, prev))
        elif ft == 3:
            for x in range(stride):
                left = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 0xFF
        elif ft == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 0xFF
        else:
            raise PngError(f"unknown filter {ft}")
        out.append(line)
        prev = line
    return out, pos


def _to_rgba(line, w, ct, depth, plte, trns):
    """Converts one row to RGBA bytes."""
    out = bytearray(w * 4)
    if depth < 8:
        vals = []
        per = 8 // depth
        mask = (1 << depth) - 1
        for byte in line:
            for k in range(per):
                vals.append((byte >> (8 - depth * (k + 1))) & mask)
        vals = vals[:w]
        if ct == 3:
            for x, v in enumerate(vals):
                if v * 3 + 2 >= len(plte):
                    raise PngError("color outside palette")
                out[x * 4:x * 4 + 3] = plte[v * 3:v * 3 + 3]
                out[x * 4 + 3] = trns[v] if v < len(trns) else 255
        else:  # gray
            scale = 255 // mask
            tgray = struct.unpack(">H", trns[:2])[0] if len(trns) >= 2 else None
            for x, v in enumerate(vals):
                g = v * scale
                out[x * 4:x * 4 + 4] = bytes((g, g, g, 0 if v == tgray else 255))
        return out
    step = CHANNELS[ct] * (2 if depth == 16 else 1)
    hi = 2 if depth == 16 else 1  # high byte at 16 bit
    for x in range(w):
        o = x * step
        if ct == 3:
            v = line[o]
            if v * 3 + 2 >= len(plte):
                raise PngError("color outside palette")
            out[x * 4:x * 4 + 3] = plte[v * 3:v * 3 + 3]
            out[x * 4 + 3] = trns[v] if v < len(trns) else 255
        elif ct == 0:
            g = line[o]
            raw = line[o:o + hi]
            a = 0 if (len(trns) >= 2 and raw == (trns[:2] if hi == 2 else trns[1:2])) else 255
            out[x * 4:x * 4 + 4] = bytes((g, g, g, a))
        elif ct == 4:
            g = line[o]
            out[x * 4:x * 4 + 4] = bytes((g, g, g, line[o + hi]))
        elif ct == 2:
            r, gg, b = line[o], line[o + hi], line[o + 2 * hi]
            a = 255
            if len(trns) >= 6:
                key = bytes(line[o:o + 3 * hi]) if hi == 2 else bytes((r, gg, b))
                tk = trns[:6] if hi == 2 else bytes((trns[1], trns[3], trns[5]))
                a = 0 if key == tk else 255
            out[x * 4:x * 4 + 4] = bytes((r, gg, b, a))
        else:  # 6
            out[x * 4:x * 4 + 4] = bytes((line[o], line[o + hi], line[o + 2 * hi], line[o + 3 * hi]))
    return out


def read_png(path: str):
    """(width, height, [RGBA rows], raw_signature). raw_signature: fast path for same file / same data."""
    with open(path, "rb") as fh:
        data = fh.read()
    ihdr = plte = None
    trns = b""
    idat = []
    for kind, body in _chunks(data):
        if kind == b"IHDR":
            ihdr = body
        elif kind == b"PLTE":
            plte = body
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            idat.append(body)
    if not ihdr or not idat:
        raise PngError("no IHDR / IDAT")
    w, h, depth, ct, comp, filt, inter = struct.unpack(">IIBBBBB", ihdr)
    if ct not in CHANNELS or comp != 0 or filt != 0 or inter not in (0, 1):
        raise PngError(f"unsupported PNG (color type {ct}, compression {comp}, filter {filt}, interlace {inter})")
    if ct == 3 and not plte:
        raise PngError("no PLTE in a palette PNG")
    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error as e:
        raise PngError(f"corrupt compression: {e}")
    sig = (ihdr, plte or b"", trns, raw)
    bits = CHANNELS[ct] * depth
    bpp = max(1, bits // 8)
    if inter == 0:
        stride = (w * bits + 7) // 8
        lines, _ = _unfilter(raw, w, h, bpp, stride, 0)
        rows = [_to_rgba(l, w, ct, depth, plte or b"", trns) for l in lines]
    else:
        rows = [bytearray(w * 4) for _ in range(h)]
        pos = 0
        for x0, y0, dx, dy in ADAM7:
            pw = (w - x0 + dx - 1) // dx if w > x0 else 0
            ph = (h - y0 + dy - 1) // dy if h > y0 else 0
            if not pw or not ph:
                continue
            stride = (pw * bits + 7) // 8
            lines, pos = _unfilter(raw, pw, ph, bpp, stride, pos)
            for j, l in enumerate(lines):
                px = _to_rgba(l, pw, ct, depth, plte or b"", trns)
                y = y0 + j * dy
                for i in range(pw):
                    x = x0 + i * dx
                    rows[y][x * 4:x * 4 + 4] = px[i * 4:i * 4 + 4]
    return w, h, rows, sig


def write_png(path: str, w: int, h: int, rows, ct: int = 6, depth: int = 8, plte=None, trns=None,
              interlace: bool = False, filters=(0,)):
    """Simple encoder: for the diff image (RGB) and the self-test (every type). rows: raw row bytes of the type."""
    def filt_line(line, prev, ft, bpp):
        out = bytearray(len(line))
        for x in range(len(line)):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x] if prev else 0
            c = prev[x - bpp] if (prev and x >= bpp) else 0
            if ft == 0:
                v = line[x]
            elif ft == 1:
                v = line[x] - a
            elif ft == 2:
                v = line[x] - b
            elif ft == 3:
                v = line[x] - ((a + b) >> 1)
            else:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                v = line[x] - (a if (pa <= pb and pa <= pc) else (b if pb <= pc else c))
            out[x] = v & 0xFF
        return bytes((ft,)) + bytes(out)

    bits = CHANNELS[ct] * depth
    bpp = max(1, bits // 8)
    payload = bytearray()
    k = 0
    if not interlace:
        prev = None
        for line in rows:
            ft = filters[k % len(filters)]
            k += 1
            payload += filt_line(line, prev, ft, bpp)
            prev = line
    else:
        raise ValueError("interlaced writing is set up separately in the self-test")
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    out = PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, depth, ct, 0, 0, 1 if interlace else 0))
    if plte:
        out += chunk(b"PLTE", bytes(plte))
    if trns:
        out += chunk(b"tRNS", bytes(trns))
    out += chunk(b"IDAT", zlib.compress(bytes(payload), 6)) + chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(out)


def _rect_masks(name, w, h, mask_top, masks, mask_file):
    rects = [(0, 0, w, mask_top)] if mask_top > 0 else []
    rects += masks
    for pat, rs in (mask_file or {}).items():
        if fnmatch.fnmatch(name, pat):
            rects += [tuple(r) for r in rs]
    # Both corners are kept inside the image, and empty or outside rectangles dropped: a mask off the image
    # must not shrink the area a difference is measured against.
    out = []
    for x, y, rw, rh in rects:
        x0, y0 = min(max(0, x), w), min(max(0, y), h)
        x1, y1 = min(max(0, x + rw), w), min(max(0, y + rh), h)
        if x1 > x0 and y1 > y0:
            out.append((x0, y0, x1, y1))
    return out


def _masked_area(rects, h):
    """Pixels covered by at least one rectangle, overlaps counted once."""
    total = 0
    for y in range(h):
        spans = sorted((x0, x1) for x0, y0, x1, y1 in rects if y0 <= y < y1)
        end = -1
        for x0, x1 in spans:
            if x1 <= end:
                continue
            total += x1 - max(x0, end)
            end = x1
    return total


def compare(job):
    """One pair; returns a dict (called from multiple processes)."""
    name, a_path, b_path, out_dir, tol, mask_top, masks, mask_file = job
    res = {"name": name}
    try:
        with open(a_path, "rb") as fa, open(b_path, "rb") as fb:
            identical = fa.read() == fb.read()
        # Decoded even when the bytes match: two identical broken captures are not a passing screen.
        aw, ah, ar, asig = read_png(a_path)
        if identical:
            res.update(status="same", changed=0, ratio=0.0)
            return res
        bw, bh, br, bsig = read_png(b_path)
    except (OSError, PngError) as e:
        res.update(status="unreadable", error=str(e))
        return res
    if (aw, ah) != (bw, bh):
        res.update(status="size difference", base=f"{aw}×{ah}", new=f"{bw}×{bh}")
        return res
    if asig == bsig:
        res.update(status="same", changed=0, ratio=0.0)
        return res
    rects = _rect_masks(name, aw, ah, mask_top, masks, mask_file)
    changed = 0
    box = [aw, ah, -1, -1]
    diff_rows = [] if out_dir else None
    for y in range(ah):
        ra, rb = ar[y], br[y]
        if ra == rb:
            if diff_rows is not None:
                diff_rows.append(_dim(ra))
            continue
        line_masks = [(x0, x1) for x0, y0, x1, y1 in rects if y0 <= y < y1]
        drow = _dim(ra) if diff_rows is not None else None
        for x in range(aw):
            o = x * 4
            if ra[o:o + 4] == rb[o:o + 4]:
                continue
            if any(x0 <= x < x1 for x0, x1 in line_masks):
                continue
            d = max(abs(ra[o] - rb[o]), abs(ra[o + 1] - rb[o + 1]), abs(ra[o + 2] - rb[o + 2]),
                    abs(ra[o + 3] - rb[o + 3]))
            if d <= tol:
                continue
            changed += 1
            box[0], box[1] = min(box[0], x), min(box[1], y)
            box[2], box[3] = max(box[2], x), max(box[3], y)
            if drow is not None:
                drow[x * 3:x * 3 + 3] = b"\xff\x00\x00"
        if diff_rows is not None:
            diff_rows.append(drow)
    masked = _masked_area(rects, ah)
    total = max(1, aw * ah - masked)
    res.update(status="changed" if changed else "same", changed=changed, ratio=changed / total)
    if changed:
        res["box"] = [box[0], box[1], box[2] - box[0] + 1, box[3] - box[1] + 1]
        if out_dir:
            dst = os.path.join(out_dir, name.replace("/", "__") + ".diff.png")
            write_png(dst, aw, ah, diff_rows, ct=2)
            res["diff_image"] = dst
    return res


def _dim(rgba):
    """Background of the diff image: the base faded to gray (RGB)."""
    out = bytearray(len(rgba) // 4 * 3)
    for i in range(0, len(rgba), 4):
        g = 140 + ((rgba[i] * 30 + rgba[i + 1] * 59 + rgba[i + 2] * 11) // 100) * 115 // 255
        out[i // 4 * 3:i // 4 * 3 + 3] = bytes((g, g, g))
    return out


def _pngs(root):
    out = {}
    for d, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith((".png", ".jpg", ".jpeg")) and not f.endswith(".diff.png"):
                full = os.path.join(d, f)
                out[os.path.relpath(full, root).replace("\\", "/")] = full
    return out


def _inside_repo(path):
    cur = os.path.abspath(path)
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        nxt = os.path.dirname(cur)
        if nxt == cur:
            return None
        cur = nxt


def self_test() -> int:
    """Write-read for each color type / bit depth / filter / interlace and measure a known difference."""
    import random
    rnd = random.Random(7)
    tmp = tempfile.mkdtemp(prefix="vi-selftest-")
    w, h = 13, 7
    ref = [[(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(w)] for _ in range(h)]
    fails = []

    def pack_bits(vals, depth):
        out, acc, n = bytearray(), 0, 0
        for v in vals:
            acc = (acc << depth) | v
            n += depth
            if n == 8:
                out.append(acc)
                acc, n = 0, 0
        if n:
            out.append(acc << (8 - n))
        return out

    cases = []
    for depth in (8, 16):
        for ct in (2, 6, 0, 4):
            cases.append((ct, depth))
    cases += [(3, 8), (3, 4), (3, 2), (3, 1), (0, 1), (0, 2), (0, 4)]
    for ct, depth in cases:
        rows, expect, plte, trns = [], [], None, None
        if ct == 3:
            ncol = min(256, 1 << depth)
            plte = bytearray()
            for i in range(ncol):
                plte += bytes(((i * 37) & 255, (i * 91) & 255, (i * 13) & 255))
            trns = bytes([255] * (ncol - 1) + [0])
        for y in range(h):
            line, ex = bytearray(), bytearray()
            vals = []
            for x in range(w):
                r, g, b = ref[y][x]
                a = (x * 20) & 255
                if ct == 2:
                    line += bytes((r, r, g, g, b, b)) if depth == 16 else bytes((r, g, b))
                    ex += bytes((r, g, b, 255))
                elif ct == 6:
                    line += bytes((r, r, g, g, b, b, a, a)) if depth == 16 else bytes((r, g, b, a))
                    ex += bytes((r, g, b, a))
                elif ct in (0, 4) and depth >= 8:
                    line += (bytes((r, r)) if depth == 16 else bytes((r,)))
                    if ct == 4:
                        line += (bytes((a, a)) if depth == 16 else bytes((a,)))
                    ex += bytes((r, r, r, a if ct == 4 else 255))
                elif ct == 0:
                    v = r & ((1 << depth) - 1)
                    vals.append(v)
                    g8 = v * (255 // ((1 << depth) - 1))
                    ex += bytes((g8, g8, g8, 255))
                else:  # palette
                    v = (r + x) % (1 << depth) if depth < 8 else r
                    vals.append(v)
                    ex += bytes(plte[v * 3:v * 3 + 3]) + bytes((trns[v] if v < len(trns) else 255,))
            if vals:
                line = pack_bits(vals, depth) if depth < 8 else bytearray(vals)
            rows.append(bytes(line))
            expect.append(ex)
        for filters in ((0,), (1,), (2,), (3,), (4,), (0, 1, 2, 3, 4)):
            path = os.path.join(tmp, f"c{ct}-d{depth}-f{''.join(map(str, filters))}.png")
            write_png(path, w, h, rows, ct=ct, depth=depth, plte=plte, trns=trns, filters=filters)
            rw, rh, got, _ = read_png(path)
            if (rw, rh) != (w, h) or [bytes(r) for r in got] != [bytes(r) for r in expect]:
                fails.append(f"color type {ct}, {depth} bit, filter {filters}")
    # Adam7: RGBA 8 bit, sub-images encoded by hand.
    rgba = [bytearray().join(bytes((ref[y][x][0], ref[y][x][1], ref[y][x][2], 255)) for x in range(w))
            for y in range(h)]
    payload = bytearray()
    for x0, y0, dx, dy in ADAM7:
        for y in range(y0, h, dy):
            sub = bytearray()
            for x in range(x0, w, dx):
                sub += rgba[y][x * 4:x * 4 + 4]
            if sub:
                payload += b"\x00" + sub

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    path = os.path.join(tmp, "adam7.png")
    with open(path, "wb") as fh:
        fh.write(PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 1)) +
                 chunk(b"IDAT", zlib.compress(bytes(payload))) + chunk(b"IEND", b""))
    _, _, got, _ = read_png(path)
    if [bytes(r) for r in got] != [bytes(r) for r in rgba]:
        fails.append("interlaced (Adam7)")
    # Known difference: 3 pixels change, one in the mask, one within tolerance.
    a_dir, b_dir, out = (os.path.join(tmp, d) for d in ("a", "b", "out"))
    for d in (a_dir, b_dir, out):
        os.makedirs(d)
    base = [bytearray(rgba[y]) for y in range(h)]
    new = [bytearray(r) for r in base]
    new[2][4 * 4] ^= 0xFF                 # changed
    new[5][9 * 4 + 1] ^= 0xFF             # changed
    new[0][0] ^= 0xFF                     # in the mask (mask-top 1)
    new[3][3 * 4 + 2] = (new[3][3 * 4 + 2] + 3) & 0xFF  # within tolerance
    write_png(os.path.join(a_dir, "s.png"), w, h, [bytes(r) for r in base], ct=6)
    write_png(os.path.join(b_dir, "s.png"), w, h, [bytes(r) for r in new], ct=6, filters=(4,))
    r = compare(("s.png", os.path.join(a_dir, "s.png"), os.path.join(b_dir, "s.png"), out, 8, 1, [], {}))
    if r.get("changed") != 2 or r.get("box") != [4, 2, 6, 4] or not os.path.exists(r.get("diff_image", "")):
        fails.append(f"known difference: {r}")
    else:
        dw, dh, drows, _ = read_png(r["diff_image"])
        if drows[2][4 * 4:4 * 4 + 3] != b"\xff\x00\x00":
            fails.append("no red mark in the diff image")
    # A corrupt file and a JPEG must give a clear error.
    bad = os.path.join(tmp, "bad.png")
    with open(bad, "wb") as fh:
        fh.write(PNG_SIG + b"\x00\x00")
    for p_, why in ((bad, "truncated"), (os.path.join(tmp, "x.jpg"), "JPEG")):
        if why == "JPEG":
            with open(p_, "wb") as fh:
                fh.write(b"\xff\xd8\xff\xe0JFIF")
        try:
            read_png(p_)
            fails.append(f"{why} file gave no error")
        except PngError:
            pass
    if fails:
        print("SELF-TEST FAILED (temporary folder kept for inspection: " + tmp + "):\n- " + "\n- ".join(fails))
        return 1
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Self-test passed: {len(cases) * 6} write-reads (color type × bit × filter), interlaced, known difference, "
          f"corrupt / JPEG file.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compares two screenshot folders pixel by pixel.")
    ap.add_argument("base", nargs="?")
    ap.add_argument("new", nargs="?")
    ap.add_argument("--out", help="diff images (OUTSIDE the project)")
    ap.add_argument("--tolerance", type=int, default=8, help="per-channel difference ignored (0–255; text antialiasing)")
    ap.add_argument("--max-ratio", type=float, default=0.0,
                    help="allowed changed pixel ratio per image (default 0: every pixel outside tolerance "
                         "is reported; a small button label is 0.02%%)")
    ap.add_argument("--mask-top", type=int, default=0, help="pixels ignored from the top (status bar)")
    ap.add_argument("--mask", action="append", default=[], help="x,y,w,h (pixels); can repeat")
    ap.add_argument("--mask-file", help='{"pattern*.png": [[x,y,w,h], ...]}')
    ap.add_argument("--jobs", type=int, default=0, help="parallel processes (default: core count)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--allow-in-repo", action="store_true", help="write even if --out is inside a git repo")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.base or not a.new:
        ap.error("base and new folders required (or --self-test)")
    for d in (a.base, a.new):
        if not os.path.isdir(d):
            print(f"No such folder: {d}", file=sys.stderr)
            return 2
    if a.out:
        repo = _inside_repo(a.out)
        if repo and not a.allow_in_repo:
            print(f"--out is inside a git repo ({repo}): diff images bloat the repo (VI-P1). "
                  f"Give a folder outside the project or use --allow-in-repo.", file=sys.stderr)
            return 2
        if os.path.isdir(a.out) and os.listdir(a.out) and not os.path.exists(os.path.join(a.out, ".vi-diff")):
            print(f"--out ({a.out}) already holds other files: give an empty folder. Diff images could overwrite them.",
                  file=sys.stderr)
            return 2
        os.makedirs(a.out, exist_ok=True)
        open(os.path.join(a.out, ".vi-diff"), "w").close()
    try:
        masks = [tuple(int(v) for v in m.split(",")) for m in a.mask]
        if any(len(m) != 4 for m in masks):
            raise ValueError
    except ValueError:
        print("--mask format: x,y,w,h", file=sys.stderr)
        return 2
    mask_file = {}
    if a.mask_file:
        with open(a.mask_file, encoding="utf-8") as fh:
            mask_file = json.load(fh)
    base, new = _pngs(a.base), _pngs(a.new)
    jobs = [(n, base[n], new[n], a.out, a.tolerance, a.mask_top, masks, mask_file) for n in sorted(base) if n in new]
    results = []
    if jobs:
        n = a.jobs or (os.cpu_count() or 1)
        if n > 1 and len(jobs) > 1:
            import multiprocessing
            with multiprocessing.Pool(min(n, len(jobs))) as pool:
                results = pool.map(compare, jobs)
        else:
            results = [compare(j) for j in jobs]
    results += [{"name": n, "status": "missing from new set"} for n in sorted(base) if n not in new]
    results += [{"name": n, "status": "only in new set"} for n in sorted(new) if n not in base]
    if not results:  # saying "all same" would be a false pass
        print("No images to compare: both folders are empty. Were captures taken?", file=sys.stderr)
        return 2
    bad = [r for r in results if r["status"] in ("size difference", "unreadable", "missing from new set", "only in new set")
           or (r["status"] == "changed" and r["ratio"] > a.max_ratio)]
    if a.json:
        json.dump({"threshold": a.max_ratio, "tolerance": a.tolerance, "results": results, "problems": len(bad)},
                  sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        same = sum(1 for r in results if r["status"] == "same")
        print(f"# Visual diff — {len(results)} images · same {same} · above threshold / problems {len(bad)}\n")
        print(f"Tolerance {a.tolerance}, threshold ratio {a.max_ratio}, top mask {a.mask_top} px.\n")
        for r in sorted(results, key=lambda r: (r["status"] == "same", -r.get("ratio", 1), r["name"])):
            if r["status"] == "same":
                continue
            extra = ""
            if r["status"] == "changed":
                over = "ABOVE THRESHOLD" if r["ratio"] > a.max_ratio else "below threshold"
                extra = f" — {r['changed']} pixels ({r['ratio']:.4%}, {over}), box x,y,w,h={r['box']}"
                if r.get("diff_image"):
                    extra += f", diff: {r['diff_image']}"
            elif r["status"] == "size difference":
                extra = f" — {r['base']} → {r['new']}"
            elif r["status"] == "unreadable":
                extra = f" — {r['error']}"
            print(f"- {r['name']}: {r['status']}{extra}")
        if not bad and same == len(results):
            print("All images are the same.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
