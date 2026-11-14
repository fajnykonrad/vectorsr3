"""Demo of the trained fusion, without any server or real data.

Uses the synthetic signals of selftest.py and the model fitted by
fit_model.py, and shows the raw model's letter against the fused one for a
few problems. A stand-in for what predict.py does on the board.

    python3 .venv/Scripts/python.exe demo_fusion.py   # from the repo folder
"""
import json
import os
import sys

from copilot import model

SIGNALS = "data/signals-demo.jsonl"
MODEL = "data/model-demo.json"

if not os.path.exists(SIGNALS):
    sys.exit(f"{SIGNALS} not found: python3 selftest.py first generates it")
if not os.path.exists(MODEL):
    sys.exit(f"{MODEL} not found: run python3 fit_model.py --input {SIGNALS} --out {MODEL}")

model.load(MODEL, force=True)
print("fusion activa:", model.active(), "\n")

rows = [json.loads(line) for line in open(SIGNALS) if line.strip()]
right = {"raw": 0, "fused": 0}
for row in rows:
    raw = model.raw_pick(row["probs"])
    fused = model.pick(row["probs"], row["votes"], has_options=row["has_options"])
    right["raw"] += raw == row["label"]
    right["fused"] += fused == row["label"]
for row in rows[:6]:
    raw = model.raw_pick(row["probs"])
    fused = model.pick(row["probs"], row["votes"], has_options=row["has_options"])
    mark = lambda x: "OK " if x == row["label"] else "mal"
    print(f"{row['id']:8} raw {raw} [{mark(raw)}]  fused {fused} [{mark(fused)}]  "
          f"verdad {row['label']}")

n = len(rows)
print(f"\nEn las {n} senales: raw {right['raw'] / n:.1%}, "
      f"fused {right['fused'] / n:.1%} (las senales de fit; lo honesto es el "
      f"held-out de fit_model.py)")
