#!/usr/bin/env python3
"""Crop the options out of problem images whose options are pictures.

For every problem whose OCR found no text options, this re-reads the bottom
strip of its image, finds the A..E markers, and saves one small PNG per
option: the letter and its picture. The trainer shows them on the answer
buttons, so the student can still choose.

    .venv/bin/python -m trainer.make_option_crops            # all languages
    .venv/bin/python -m trainer.make_option_crops --languages eng

Writes data/images/<id>_<lang>-opt<A..E>.png and data/option_crops.json
({ "<id>|<lang>": {"A": filename, ...} }). Cached like the OCR cache, so
re-runs are cheap.
"""
import argparse
import json
import multiprocessing
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "laptop"))
from prepare_m3kang import LETTERS, MARKER, reading_order  # noqa: E402

STRIP = 0.5        # the options live in the bottom half of the image
PAD = 6            # pixels kept left of each marker
WORKERS = 6


def marker_positions(items):
    """The (letter, x, y) of the last in-order A..E run, or None."""
    seq = []
    for it in items:
        m = MARKER.match(it["text"])
        if not m:
            continue
        letter, paren, rest = m.group(1), m.group(2), m.group(3) or ""
        # a marker is "A", "A)", "A)12" or "A12": a letter with nothing but a
        # value after it. Words like "ADA" do not count.
        if paren or rest == "" or re.match(r"^[-+−\d]", rest):
            seq.append((letter, int(it["x"]), it["y"]))
    for start in range(len(seq) - 1, -1, -1):
        if seq[start][0] != "A":
            continue
        found, marks = {}, []
        for letter, x, y in seq[start:]:
            if letter not in found:
                found[letter] = (x, y)
                marks.append((letter, x, y))
            if len(found) == 5:
                return marks
            if len(found) < len(marks):  # a repeated letter: this run is broken
                break
    return None


def crop_options(image_bytes, threads):
    """One image -> the five crops, or None when no A..E run is found."""
    import cv2
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    ocr = RapidOCR(intra_op_num_threads=threads)
    arr = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return None
    strip = arr[arr.shape[0] // 2:]  # bottom half
    boxes, _ = ocr(strip)
    if not boxes:
        return None
    marks = marker_positions(reading_order(boxes))
    if not marks or len(marks) != 5:
        return None
    height = strip.shape[0]
    width = strip.shape[1]
    xs = [x for _letter, x, _y in marks]
    ys = [y for _letter, _x, y in marks]
    # The layout is "A) <content> B) <content> ...", so option i's content
    # sits between its own marker and the next one. Slice there, then trim
    # the white margins off each piece.
    bounds = [max(0, xs[0] - PAD)] + [x - PAD for x in xs[1:]] + [width]
    crops = []
    for i in range(5):
        piece = strip[:, bounds[i]:bounds[i + 1]]
        if piece.shape[1] < 8:  # overlapping or out-of-order markers
            return None
        columns = np.where(np.any(piece < 245, axis=(0, 2)))[0]
        if len(columns) == 0:
            return None
        left = max(0, columns[0] - PAD)
        right = min(piece.shape[1], columns[-1] + 1 + PAD)
        piece = piece[:, left:right]
        # keep only the band of rows around this option's marker, so shapes
        # from the problem's figure, higher up in the strip, do not leak in
        rows = np.where(np.any(piece < 245, axis=(1, 2)))[0]
        marker_y = int(ys[i])
        bands, current = [], [rows[0]]
        for r in rows[1:]:
            if r - current[-1] > 12:
                bands.append(current)
                current = []
            current.append(r)
        bands.append(current)
        band = None
        for b in bands:
            if b[0] - 6 <= marker_y <= b[-1] + 6:
                band = b
                break
        if band is None:
            return None
        top = max(0, band[0] - PAD)
        bottom = min(piece.shape[0], band[-1] + 1 + PAD)
        piece = piece[top:bottom]
        columns = np.where(np.any(piece < 245, axis=(0, 2)))[0]
        if len(columns) == 0:
            return None
        piece = piece[:, max(0, columns[0] - PAD):min(piece.shape[1], columns[-1] + 1 + PAD)]
        if piece.shape[1] < 8 or piece.shape[0] < 8:
            return None
        crops.append(piece)
    return crops, height


_OCR = None


def worker_init():
    global _OCR
    from rapidocr_onnxruntime import RapidOCR
    _OCR = RapidOCR(intra_op_num_threads=2)


def worker(item):
    key, image_bytes = item
    try:
        result = crop_options(image_bytes, 2)
    except Exception:
        result = None
    if result is None:
        return None
    crops, _height = result
    return key, crops


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="data")
    parser.add_argument("--languages", default="")
    args = parser.parse_args()

    problems = []
    for split in ("train", "val"):
        path = os.path.join(args.data, f"{split}.jsonl")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            problems += [json.loads(line) for line in f if line.strip()]
    if args.languages:
        keep = set(args.languages.split(","))
        problems = [p for p in problems if p["language"] in keep]
    todo = [p for p in problems if not p.get("options")]
    print(f"{len(todo)} problems with picture (or unreadable) options")

    images_dir = os.path.join(args.data, "images")
    out_meta = os.path.join(args.data, "option_crops.json")
    meta = {}
    if os.path.exists(out_meta):
        with open(out_meta) as f:
            meta = json.load(f)

    # recover from previous runs: when all five crop files already exist,
    # the problem is done even if the metadata write was interrupted
    for p in todo:
        key = f"{p['id']}|{p['language']}"
        if key in meta:
            continue
        names = {l: key.replace("|", "_") + f"-opt{l}.png" for l in LETTERS}
        if all(os.path.exists(os.path.join(images_dir, n)) for n in names.values()):
            meta[key] = names
    if meta:
        with open(out_meta, "w") as f:
            json.dump(meta, f, ensure_ascii=False)

    # only the ones we have an image for, and not done already
    jobs, done = [], 0
    for p in todo:
        key = f"{p['id']}|{p['language']}"
        if key in meta:
            done += 1
            continue
        path = os.path.join(images_dir, key.replace("|", "_") + ".png")
        if os.path.exists(path):
            with open(path, "rb") as f:
                jobs.append((key, f.read()))
    print(f"{done} already cropped, {len(jobs)} to do")

    if jobs:
        started = time.time()
        ctx = multiprocessing.get_context("fork")

        def save():
            with open(out_meta, "w") as f:
                json.dump(meta, f, ensure_ascii=False)

        with ctx.Pool(WORKERS, initializer=worker_init) as pool:
            results = pool.imap_unordered(worker, jobs)
            for n, result in enumerate(results, 1):
                if result is not None:
                    key, crops = result
                    names = {}
                    for letter, arr in zip(LETTERS, crops):
                        ok, buf = cv2_imencode(arr)
                        if not ok:
                            continue
                        name = key.replace("|", "_") + f"-opt{letter}.png"
                        with open(os.path.join(images_dir, name), "wb") as f:
                            f.write(buf)
                        names[letter] = name
                    if len(names) == 5:
                        meta[key] = names
                if n % 20 == 0:
                    save()  # incremental: the server can pick crops up any time
                    rate = n / (time.time() - started)
                    left = (len(jobs) - n) / max(rate, 0.01)
                    print(f"  {n}/{len(jobs)} ({rate:.1f}/s, ~{left:.0f} s left)",
                          flush=True)
        save()

    with open(out_meta, "w") as f:
        json.dump(meta, f, ensure_ascii=False)
    print(f"Wrote {out_meta}: {len(meta)} problems with option crops")


def cv2_imencode(arr):
    import cv2
    return cv2.imencode(".png", arr)


if __name__ == "__main__":
    main()
