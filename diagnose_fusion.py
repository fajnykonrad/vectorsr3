#!/usr/bin/env python3
"""Diagnose which fusion policy actually helps, per problem group.

    python3 diagnose_fusion.py

Reads data/signals.jsonl, splits by problem id into fit and held-out parts
(the same split fit_model.py uses), and prints the accuracy of several
decision rules on both parts, per group (with / without OCR options):

    raw        argmax of the model's own probabilities
    votes      argmax of the neighbours' label shares (pure kNN)
    fused      raw + fitted offsets + knn weight, as data/model.json has it
    grid       raw + s*offset + v*votes for a grid of (s, v), fit part only

The point: pick per group the rule that wins on the fit part, then check it
on the held-out part before writing any policy into fit_model.py.
"""
import argparse
import json
import sys

import fit_model

GRID_S = [0.0, 0.25, 0.5, 0.75, 1.0]   # multiplier on the fitted offsets
GRID_V = [0.0, 1.0, 2.0, 4.0]          # multiplier on the fitted knn weight


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/signals.jsonl")
    p.add_argument("--holdout", type=float, default=0.2)
    p.add_argument("--epochs", type=int, default=300)
    return p.parse_args()


def predict(row, offsets=None, weight=0.0, s=0.0, v=0.0):
    """argmax of probs + s*offset + v*weight*votes (s=0, v=0 is the raw rule)."""
    best, best_score = "A", None
    for letter in fit_model.LETTERS:
        score = row["probs"].get(letter, fit_model.FLOOR)
        if offsets:
            score += s * offsets.get(letter, 0.0)
        if v and weight:
            score += v * weight * (row.get("votes") or {}).get(letter, 0.0)
        if best_score is None or score > best_score:
            best, best_score = letter, score
    return best


def accuracy(rows, **kwargs):
    return sum(predict(row, **kwargs) == row["label"] for row in rows) / max(len(rows), 1)


def line(name, rows, **kwargs):
    return f"  {name:26} {100 * accuracy(rows, **kwargs):5.1f}%  ({len(rows)} rows)"


def main():
    args = parse_args()
    rows = fit_model.load_signals(args.input)
    fit_rows, held_rows = fit_model.split(rows, args.holdout)
    try:
        with open("data/model.json", encoding="utf-8") as f:
            shipped = json.load(f)
    except (OSError, ValueError):
        sys.exit("data/model.json not found: run fit_model.py first")

    for group in ("with_options", "without_options"):
        part = [r for r in rows if fit_model.group_of(r) == group]
        fit_p = [r for r in fit_rows if fit_model.group_of(r) == group]
        held_p = [r for r in held_rows if fit_model.group_of(r) == group]
        offsets = (shipped["offsets"].get(group) or shipped["offsets"]["global"])
        weight = shipped.get(f"knn_weight_{group}", shipped.get("knn_weight", 0.0))
        print(f"\n=== {group} ({len(part)} rows: {len(fit_p)} fit / {len(held_p)} held) ===")
        print("fit part:")
        print(line("raw", fit_p))
        print(line("votes only (pure kNN)", fit_p, weight=1.0, v=1.0))
        print(line("fused as shipped", fit_p, offsets=offsets, weight=weight, s=1.0, v=1.0))
        best = None
        for s in GRID_S:
            for v in GRID_V:
                if s == 0 and v == 0:
                    continue
                acc = accuracy(fit_p, offsets=offsets, weight=weight, s=s, v=v)
                if best is None or acc > best[0]:
                    best = (acc, s, v)
        print(f"  best on fit: s={best[1]} v={best[2]}  {100 * best[0]:5.1f}%")
        print("held-out part:")
        print(line("raw", held_p))
        print(line("votes only (pure kNN)", held_p, weight=1.0, v=1.0))
        print(line(f"fused s={best[1]} v={best[2]}", held_p,
                   offsets=offsets, weight=weight, s=best[1], v=best[2]))


if __name__ == "__main__":
    main()
