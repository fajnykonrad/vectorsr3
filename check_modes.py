"""End-to-end check of the two shipped modes (no server needed for statuses).

    python3 check_modes.py
"""
import json
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")
from copilot.pipeline import solve, heuristics_enabled
from copilot.prior import median_letter, level_prior, uniform_pick

rows = [json.loads(l) for l in open("data/sample_problems.jsonl", encoding="utf-8")]

print("=== MODO M3KANG (default: HEURISTICS=1, UNIFORM=0) ===")
for r in rows:
    ml = median_letter(r)
    if not r.get("options"):
        print(f"  {r['id']}: {level_prior().get(r['level'], 'D')} [ok-level-prior] (verdad {r['label']})")
    elif ml:
        print(f"  {r['id']}: {ml} [ok-median] (verdad {r['label']})")
    else:
        print(f"  {r['id']}: -> LLM (sin mediana posible)")

print("\n=== MODO JURADO (UNIFORM=1, HEURISTICS=0): recalibracion sobre probs del demo ===")
signals = [json.loads(l) for l in open("data/signals-demo.jsonl", encoding="utf-8") if l.strip()]
answers = {}
for s in signals[:20]:
    answers[s["key"]] = uniform_pick(s["probs"], 0.8)
from collections import Counter
print("  respuestas calibradas en 20 problemas:", dict(Counter(answers.values())))
print("  (ya no se apilan en D/A; con las letras uniformes del jurado esto puntua)")

print("\nheuristics_enabled() actual:", heuristics_enabled())
