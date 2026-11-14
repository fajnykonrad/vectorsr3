#!/usr/bin/env python3
"""Where did the fusion change answers, and did it help or hurt?

    python3 analyze_flips.py results/eval-<stamp>-raw-laptop.csv results/eval-<stamp>-fused-laptop-v2.csv

Joins two eval CSVs by problem id and prints, per options group:
how many answers changed, how many flips were correct->wrong and
wrong->correct, and the letter distribution before and after.
"""
import csv
import sys
from collections import Counter

raw_path, fused_path = sys.argv[1], sys.argv[2]


def load(path):
    rows = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["id"]] = row
    return rows


raw, fused = load(raw_path), load(fused_path)
common = sorted(set(raw) & set(fused))
print(f"{len(common)} problemas en comun")

for group, key in (("sin opciones", "False"), ("con opciones", "True")):
    ids = [i for i in common if raw[i]["has_options"] == key]
    if not ids:
        continue
    fixed = sum(1 for i in ids if raw[i]["answer"] != raw[i]["label"] and fused[i]["answer"] == raw[i]["label"])
    broken = sum(1 for i in ids if raw[i]["answer"] == raw[i]["label"] and fused[i]["answer"] != raw[i]["label"])
    same = sum(1 for i in ids if raw[i]["answer"] == fused[i]["answer"])
    raw_ok = sum(1 for i in ids if raw[i]["answer"] == raw[i]["label"])
    fused_ok = sum(1 for i in ids if fused[i]["answer"] == fused[i]["label"])
    print(f"\n{group} ({len(ids)} problemas)")
    print(f"  raw   {raw_ok}/{len(ids)} = {100 * raw_ok / len(ids):.1f}%")
    print(f"  fused {fused_ok}/{len(ids)} = {100 * fused_ok / len(ids):.1f}%")
    print(f"  misma respuesta: {same}   arreglados: {fixed}   rotos: {broken}   neto: {fixed - broken:+d}")

print("\nletras raw   ", dict(sorted(Counter(raw[i]["answer"] for i in common).items())))
print("letras fused ", dict(sorted(Counter(fused[i]["answer"] for i in common).items())))
print("letras verdad", dict(sorted(Counter(raw[i]["label"] for i in common).items())))
