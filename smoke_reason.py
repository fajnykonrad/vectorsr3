#!/usr/bin/env python3
"""Smoke test of the real copilot route against live servers.

    python3 smoke_reason.py

Shows, for the first sample problems: the raw model's letter, the fused
letter (with data/model.json if it exists, else the raw letter), and the
full letter distribution. This is the same code path predict.py runs.
"""
import json
import sys

sys.path.insert(0, ".")
from copilot.llm import answer_distribution
from copilot import model

rows = [json.loads(l) for l in open("data/sample_problems.jsonl", encoding="utf-8")]
model.load()
print("fusion (data/model.json):", "activa" if model.active() else "no entrenada todavia (sin offsets)")
print()

ok_raw = ok_any = 0
for r in rows:
    letter, probs, timings = answer_distribution(r)
    p = {k: round(v, 2) for k, v in probs.items()}
    fused = model.pick(probs, has_options=bool(r.get("options"))) or letter
    mark = lambda x: "OK " if x == r["label"] else "mal"
    print(f"{r['id']:9} raw {letter} [{mark(letter)}]  fused {fused} [{mark(fused)}]  verdad {r['label']}")
    print(f"          probs {p}   {timings.get('prompt_n', '?')} tokens leidos en {timings.get('prompt_ms', '?')} ms")
    ok_raw += letter == r["label"]
    ok_any += (letter == r["label"]) or (fused == r["label"])
print(f"\nraw {ok_raw}/{len(rows)}, alguna de las dos rutas acierta {ok_any}/{len(rows)} "
      f"(5 problemas: statistical noise, es solo para ver que la maquinaria funciona)")
