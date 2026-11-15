"""Post-mortem of the demo run's level-0 anomaly (0/16)."""
import csv
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
rows = list(csv.DictReader(open("results/demo-raw-v2.csv", encoding="utf-8")))
print("total filas:", len(rows))
l0 = [r for r in rows if r["level"] == "0"]
print(f"\n=== NIVEL 0: {len(l0)} filas ===")
print("verdades:", dict(Counter(r["label"] for r in l0)))
print("respuestas:", dict(Counter(r["answer"] for r in l0)))
for r in l0:
    mark = "OK " if r["correct"] == "1" else "mal"
    print(f"  {r['id']:15} {r['language']}: modelo {r['answer']} verdad {r['label']} [{mark}]")

# truth distribution per level across the whole set
print("\n=== verdades por nivel ===")
by_level = {}
for r in rows:
    by_level.setdefault(r["level"], Counter())[r["label"]] += 1
for level in sorted(by_level, key=int):
    counts = by_level[level]
    print(f"  nivel {level}: {dict(sorted(counts.items()))}")
