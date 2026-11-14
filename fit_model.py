#!/usr/bin/env python3
"""Fit the fusion model (letter offsets + kNN weight) from collected signals.

    python3 fit_model.py                      # data/signals.jsonl -> data/model.json
    python3 fit_model.py --languages eng      # fit on one language only

Input: one line per training problem from collect.py, with the raw model's
letter distribution ("probs"), the neighbour label votes ("votes") and the
true "label". The fit is a small multinomial logistic model: it raises the
probability the fusion assigns to the true answers, learning 5 letter
offsets (the correction for the model's letter bias) and the weight of the
kNN votes. Problems are split by id (so a problem and its translations never
straddle the split) into a fit part and a held-out part, and both accuracies
are printed, so the held-out numbers say what the fusion is worth on problems
the fit never saw. A separate set is fitted for problems with and without
options when each group is big enough (the bias differs).
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections import Counter

LETTERS = "ABCDE"
FLOOR = -12.0


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/signals.jsonl")
    p.add_argument("--out", default="data/model.json")
    p.add_argument("--languages", default="", help="e.g. eng (default: every language in the file)")
    p.add_argument("--holdout", type=float, default=0.2, help="share of problem ids held out")
    p.add_argument("--epochs", type=int, default=300, help="gradient steps for the fit")
    p.add_argument("--learning-rate", type=float, default=0.5)
    p.add_argument("--l2", type=float, default=0.01, help="L2 penalty on offsets and weight")
    p.add_argument("--min-group", type=int, default=60,
                   help="fit a group separately only from this many fit problems")
    return p.parse_args()


def load_signals(path, languages=()):
    rows = []
    if not os.path.exists(path):
        sys.exit(f"{path} not found. Collect signals first: python3 collect.py")
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                if row.get("probs") and (not languages or row.get("language") in languages):
                    rows.append(row)
    return rows


def split(rows, holdout_fraction=0.2):
    """Split by problem id, so translations never straddle fit and holdout."""
    fit, held = [], []
    for row in rows:
        bucket = int(hashlib.sha256(row["id"].encode()).hexdigest(), 16) % 1000
        (held if bucket < holdout_fraction * 1000 else fit).append(row)
    return fit, held


def group_of(row):
    return "with_options" if row.get("has_options") else "without_options"


def score(row, params, group="global"):
    """Letter -> fused score for one row: log p + offset + weight * vote."""
    offsets = params["offsets"].get(group) or params["offsets"]["global"]
    weight = params["knn_weight"] if votes_present(row) else 0.0
    votes = row.get("votes") or {}
    return {letter: row["probs"].get(letter, FLOOR) + offsets.get(letter, 0.0)
            + weight * votes.get(letter, 0.0) for letter in LETTERS}


def votes_present(row):
    return bool(row.get("votes"))


def pick(row, params, group="global"):
    scores = score(row, params, group)
    best = LETTERS[0]
    for letter in LETTERS[1:]:
        if scores[letter] > scores[best]:
            best = letter
    return best


def raw_pick(row):
    best = LETTERS[0]
    for letter in LETTERS[1:]:
        if row["probs"].get(letter, FLOOR) > row["probs"].get(best, FLOOR):
            best = letter
    return best


def accuracy(rows, params=None, group=None):
    if not rows:
        return 0.0
    if params is None:
        return sum(raw_pick(row) == row["label"] for row in rows) / len(rows)
    return sum(pick(row, params, group or group_of(row)) == row["label"] for row in rows) / len(rows)


def fit(rows, epochs=300, learning_rate=0.5, l2=0.01):
    """Fit the fusion by maximum likelihood: a multinomial logistic model.

    The score of each letter is log p + offset + weight * vote; the fit
    raises the log-probability the model assigns to the true answers, with a
    small L2 penalty. Adding the same constant to every offset changes no
    decision, so starting all of them at zero keeps only the differences,
    which is what the letter bias is. Deterministic, and seconds on a few
    hundred rows.

    Returns (params, fused accuracy on the rows), with params in the
    canonical shape {"offsets": {"global": {...}}, "knn_weight": value}.
    """
    offsets = {letter: 0.0 for letter in LETTERS}
    weight = 0.0
    n = len(rows)
    for _epoch in range(epochs if n else 0):
        grad_offset = {letter: 0.0 for letter in LETTERS}
        grad_weight = 0.0
        for row in rows:
            votes = row.get("votes") or {}
            used_weight = weight if votes else 0.0
            scores = {letter: row["probs"].get(letter, FLOOR) + offsets[letter]
                      + used_weight * votes.get(letter, 0.0) for letter in LETTERS}
            top = max(scores.values())
            exps = {letter: math.exp(scores[letter] - top) for letter in LETTERS}
            total = sum(exps.values())
            for letter in LETTERS:
                error = (1.0 if row["label"] == letter else 0.0) - exps[letter] / total
                grad_offset[letter] += error
                if votes:
                    grad_weight += error * votes.get(letter, 0.0)
        for letter in LETTERS:
            offsets[letter] += learning_rate * (grad_offset[letter] / n - l2 * offsets[letter])
        weight += learning_rate * (grad_weight / n - l2 * weight)
    params = {"offsets": {"global": offsets}, "knn_weight": weight}
    return params, accuracy(rows, params)


def main():
    args = parse_args()
    languages = set(filter(None, args.languages.split(",")))
    rows = load_signals(args.input, languages)
    if len(rows) < 40:
        sys.exit(f"Only {len(rows)} usable signals; collect more before fitting (aim for 300+).")
    fit_rows, held_rows = split(rows, args.holdout)

    # One fit over everything, then one per group when the group is big enough.
    plain, _acc = fit(fit_rows, args.epochs, args.learning_rate, args.l2)
    offsets = {"global": plain["offsets"]["global"]}
    knn = {"global": plain["knn_weight"]}
    for name in ("with_options", "without_options"):
        group_rows = [row for row in fit_rows if group_of(row) == name]
        if len(group_rows) >= args.min_group:
            fitted, _acc = fit(group_rows, args.epochs, args.learning_rate, args.l2)
            offsets[name] = fitted["offsets"]["global"]
            knn[name] = fitted["knn_weight"]
    params = {"offsets": offsets, "knn_weight": knn["global"],
              **{f"knn_weight_{name}": value for name, value in knn.items() if name != "global"}}

    # Honest numbers: the fit never saw the held-out rows.
    floor_letter, floor_count = Counter(row["label"] for row in held_rows).most_common(1)[0] \
        if held_rows else ("D", 0)
    print(f"Signals: {len(rows)} rows ({len(fit_rows)} fit / {len(held_rows)} held out)"
          f"{', ' + ','.join(sorted(languages)) if languages else ''}")
    print(f"Raw model   fit {100 * accuracy(fit_rows):5.1f}%   held out {100 * accuracy(held_rows):5.1f}%")
    print(f"Fused       fit {100 * accuracy(fit_rows, params):5.1f}%   "
          f"held out {100 * accuracy(held_rows, params):5.1f}%")
    print(f"Floor, always {floor_letter}: {100 * floor_count / max(len(held_rows), 1):.1f}% (held out)")
    for name in ("with_options", "without_options"):
        group_held = [row for row in held_rows if group_of(row) == name]
        if group_held:
            print(f"  {name:16} held out: raw {100 * accuracy(group_held):5.1f}% -> "
                  f"fused {100 * accuracy(group_held, params):5.1f}% ({len(group_held)} rows)")
    shown = offsets.get("with_options") or offsets["global"]
    print("Offsets: " + "  ".join(f"{l} {shown[l]:+.2f}" for l in LETTERS)
          + f"   kNN weight {knn['global']:.2f}")
    def letter_counts(answer_of):
        return {letter: sum(answer_of(row) == letter for row in held_rows) for letter in LETTERS}
    fused_counts = letter_counts(lambda row: pick(row, params, group_of(row)))
    raw_counts = letter_counts(raw_pick)
    truth_counts = letter_counts(lambda row: row["label"])
    print("Letters held out  raw   " + "  ".join(f"{l}:{raw_counts[l]:>3}" for l in LETTERS))
    print("                  fused " + "  ".join(f"{l}:{fused_counts[l]:>3}" for l in LETTERS))
    print("                  truth " + "  ".join(f"{l}:{truth_counts[l]:>3}" for l in LETTERS))

    document = {
        "version": 1,
        "enabled": True,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "signals": f"{args.input} ({len(rows)} rows)",
        "neighbours": max((len(row.get("votes") or {}) for row in rows), default=0),
        "offsets": offsets,
        "knn_weight": knn["global"],
        **{f"knn_weight_{name}": value for name, value in knn.items() if name != "global"},
        "metrics": {
            "fit_raw": round(100 * accuracy(fit_rows), 1),
            "fit_fused": round(100 * accuracy(fit_rows, params), 1),
            "holdout_raw": round(100 * accuracy(held_rows), 1),
            "holdout_fused": round(100 * accuracy(held_rows, params), 1),
            "holdout_n": len(held_rows),
        },
    }
    with open(args.out, "w") as f:
        json.dump(document, f, indent=2)
        f.write("\n")
    held_out = document["metrics"]["holdout_fused"] - document["metrics"]["holdout_raw"]
    print(f"\nWrote {args.out} (held-out gain {held_out:+.1f} points)")
    if held_out <= 0:
        print("WARNING: no held-out gain. The fusion overfits; collect more signals "
              "or raise --holdout before shipping this model.")


if __name__ == "__main__":
    main()
