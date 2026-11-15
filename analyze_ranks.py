"""Where does the demo set's true answer sit among the option values?

    python3 analyze_ranks.py

If the organisers place the answer at a consistent rank (lowest value, median,
highest...), a rank policy beats the raw model on their uniform-letter set.
Measured on data/demo/train.jsonl (the official practice set).
"""
import json
import re
import sys
from collections import Counter

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")
from copilot.prior import median_letter

rows = [json.loads(l) for l in open("data/demo/train.jsonl", encoding="utf-8") if l.strip()]
ranks = Counter()
numeric = 0
for r in rows:
    if median_letter(r) is None:
        continue
    numeric += 1
    options = r["options"]
    values = {}
    for letter in "ABCDE":
        match = re.search(r"-?\d+(?:[.,]\d+)?", str(options[letter]))
        values[letter] = float(match.group().replace(",", "."))
    ordered = sorted(values, key=values.get)
    rank = ordered.index(r["label"])  # 0 = smallest value ... 4 = largest
    ranks[rank] += 1

print(f"problemas con las 5 opciones numericas: {numeric}/100")
names = ["el valor MAS BAJO", "el 2o mas bajo", "LA MEDIANA", "el 2o mas alto", "el valor MAS ALTO"]
for rank in range(5):
    share = 100 * ranks[rank] / numeric
    bar = "#" * int(share / 2)
    print(f"  rank {rank} = {names[rank]:18} {ranks[rank]:3} veces ({share:4.0f}%) {bar}")
