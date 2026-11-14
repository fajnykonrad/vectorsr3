#!/usr/bin/env python3
"""Compare answer policies on the full validation signals, exactly.

    python3 compare_val.py data/signals-val.jsonl

No sampling: every row is one validation problem with the raw model's probs,
the neighbours' votes, and the truth. Prints accuracy per group and language
for: raw, always-D, votes-only, and the shipped group policy (data/model.json).
"""
import json
import sys

sys.path.insert(0, ".")
import fit_model
from copilot import model

path = sys.argv[1] if len(sys.argv) > 1 else "data/signals-val.jsonl"
rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
model.load()
shipped = model.load()


def answer_of(row, policy):
    if policy == "alwaysD":
        return "D"
    if policy == "raw":
        return model.raw_pick(row["probs"])
    if policy == "votes":
        votes = row.get("votes") or {}
        return max("ABCDE", key=lambda l: votes.get(l, 0.0))
    if policy == "shipped":
        return model.pick(row["probs"], row.get("votes"), has_options=row.get("has_options"))
    raise ValueError(policy)


def acc(subset, policy):
    hits = sum(answer_of(r, policy) == r["label"] for r in subset)
    return f"{100 * hits / len(subset):5.1f}% ({hits}/{len(subset)})" if subset else "  -"


POLICIES = ["alwaysD", "raw", "votes", "shipped"]
print(f"{len(rows)} problemas de validacion (senales completas)\n")
print(f"{'':22}" + "".join(f"{p:>16}" for p in POLICIES))
print(f"{'TODOS':22}" + "".join(f"{acc(rows, p):>16}" for p in POLICIES))
for group in ("with_options", "without_options"):
    part = [r for r in rows if r.get("has_options") == (group == "with_options")]
    print(f"{group:22}" + "".join(f"{acc(part, p):>16}" for p in POLICIES))
for lang in sorted({r["language"] for r in rows}):
    part = [r for r in rows if r["language"] == lang]
    print(f"lang {lang:17}" + "".join(f"{acc(part, p):>16}" for p in POLICIES))
# the shipped policy's flips against raw, net effect
fixed = broken = 0
for r in rows:
    a_raw, a_ship = answer_of(r, "raw"), answer_of(r, "shipped")
    if a_raw != a_ship:
        fixed += a_ship == r["label"] and a_raw != r["label"]
        broken += a_raw == r["label"] and a_ship != r["label"]
print(f"\nflips de la politica shipped contra raw: arreglados {fixed}, rotos {broken}, neto {fixed - broken:+d}")
