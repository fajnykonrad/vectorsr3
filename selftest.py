#!/usr/bin/env python3
"""End-to-end test of the fusion maths, without any model server.

It fakes signals for 800 training problems whose model behaves like the one
we measured on the board: weak accuracy, a strong bias towards D, a smaller
one towards A, and a real but modest kNN signal. Then it runs the same fit
fit_model.py runs, checks that it recovers the planted bias, and that the
fused answers beat the raw model on held-out problems. It also checks that
copilot.model.pick() and fit_model.pick() agree, so what the fit learns is
what predict.py applies.

    python3 selftest.py        # a few seconds, prints PASS/FAIL lines

Run it after any change to fit_model.py or copilot/model.py.
"""
import json
import math
import random
import sys
import tempfile

import fit_model
from copilot import model

N = 800
SKILL = 1.0      # how much better the true answer's logit is (raw accuracy lands ~40%)
D_BIAS = 1.3     # the model's systematic love of D
A_BIAS = 0.7     # and of A
VOTE_QUALITY = 0.32  # chance a neighbour's answer is the true one
LABEL_WEIGHTS = [19, 19, 19, 26, 17]  # M3Kang: D is the most common answer


def log_softmax(logits):
    top = max(logits.values())
    exps = {letter: math.exp(value - top) for letter, value in logits.items()}
    total = sum(exps.values())
    return {letter: math.log(value / total) for letter, value in exps.items()}


def make_signals(rng):
    rows = []
    for i in range(N):
        truth = rng.choices(list("ABCDE"), weights=LABEL_WEIGHTS)[0]
        logits = {letter: rng.gauss(0, 1) for letter in "ABCDE"}
        logits[truth] += SKILL
        logits["D"] += D_BIAS
        logits["A"] += A_BIAS
        probs = log_softmax(logits)
        votes = {}
        labels = []
        for _neighbour in range(8):
            labels.append(truth if rng.random() < VOTE_QUALITY
                          else rng.choice([l for l in "ABCDE" if l != truth]))
        for letter in "ABCDE":
            votes[letter] = labels.count(letter) / len(labels)
        rows.append({"id": f"fake_{i}", "language": "eng", "level": rng.randint(0, 7),
                     "has_options": rng.random() < 0.62, "label": truth,
                     "probs": probs, "votes": votes})
    return rows


def main():
    rng = random.Random(7)
    rows = make_signals(rng)
    fit_rows, held_rows = fit_model.split(rows, 0.2)

    params, _fit_acc = fit_model.fit(fit_rows)
    # fit() returns the fitted values under "global"; the shipped model.json
    # applies them per group (strict policy), so evaluate the same way
    params = {"offsets": {"with_options": params["offsets"]["global"],
                          "without_options": params["offsets"]["global"]},
              "knn_weight": params["knn_weight"],
              "knn_weight_with_options": params["knn_weight"],
              "knn_weight_without_options": params["knn_weight"]}
    raw = 100 * fit_model.accuracy(held_rows)
    fused = 100 * fit_model.accuracy(held_rows, params)
    offsets = params["offsets"]["with_options"]
    floor_letter, floor_count = max(
        ((letter, sum(row["label"] == letter for row in held_rows)) for letter in "ABCDE"),
        key=lambda pair: pair[1])
    floor = 100 * floor_count / len(held_rows)
    print(f"Synthetic signals: {N} problems ({len(fit_rows)} fit / {len(held_rows)} held out)")
    print(f"raw   holdout accuracy {raw:.1f}%   (always-{floor_letter} floor {floor:.1f}%)")
    print(f"fused holdout accuracy {fused:.1f}%")
    print("fitted offsets: " + "  ".join(f"{l} {offsets[l]:+.2f}" for l in "ABCDE")
          + f"   kNN weight {params['knn_weight']:+.2f}")

    checks = [
        ("fused beats raw on held-out problems", fused > raw),
        ("fused beats the always-D floor", fused > floor),
        ("the D bias is corrected (offset D < 0)", offsets["D"] < 0),
        ("the A bias is corrected (offset A < 0)", offsets["A"] < 0),
        ("the kNN votes are used (weight > 0.05)", params["knn_weight"] > 0.05),
    ]

    # copilot.model.pick must agree with the fit's own pick on held-out rows
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"enabled": True, **params}, f)
        path = f.name
    model.load(path=path, force=True)
    mismatched = 0
    for row in held_rows:
        ours = model.pick(row["probs"], row["votes"], has_options=row["has_options"])
        theirs = fit_model.pick(row, params, fit_model.group_of(row))
        mismatched += ours != theirs
    checks.append(("copilot.model.pick agrees with fit_model.pick", mismatched == 0))
    print(f"pick agreement: {len(held_rows) - mismatched}/{len(held_rows)} rows")
    model.load(force=True)  # back to the real data/model.json, if there is one

    failed = 0
    for name, ok in checks:
        print(("PASS  " if ok else "FAIL  ") + name)
        failed += not ok
    if failed:
        sys.exit(f"\nselftest: {failed} check(s) failed")
    print(f"\nselftest: all {len(checks)} checks passed")


if __name__ == "__main__":
    main()
