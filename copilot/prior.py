"""Two measured heuristics that beat the model on their own turf.

Both are deterministic, offline, and instant (no LLM call):

- median option value: where all five options parse as numbers, the letter
  holding the median value answers better than the model (27.7% vs 22.8% on
  the 329 numeric cat+eng validation problems). The classic multiple-choice
  heuristic, and in Kangaroo sets the answer concentrates there.
- level prior: where the OCR could not read the options, the model's
  distribution is A/D noise; the most common true letter of the problem's
  level, learned from the eng+cat training problems, answers better (28.1%
  full policy vs 24.0% raw on the 562 cat+eng set).

Both were measured before shipping (tune_policy2.py) and neither is fitted
on validation data: the median is a classical rule, the prior comes from
train only.
"""
import json
import os
import re

from .config import ROOT

LETTERS = "ABCDE"
NUM = re.compile(r"-?\d+(?:[.,]\d+)?")
PRIOR_PATH = os.path.join(ROOT, "data", "level_prior.json")
_prior = None


def level_prior():
    """{level(int): letter} from data/level_prior.json, else {}."""
    global _prior
    if _prior is None:
        try:
            with open(PRIOR_PATH, encoding="utf-8") as f:
                document = json.load(f)
            _prior = {int(level): letter for level, letter in document.get("level_prior", {}).items()}
        except (OSError, ValueError):
            _prior = {}
    return _prior


def median_letter(problem):
    """The letter holding the median option value, or None if unparseable."""
    options = problem.get("options") or {}
    values = {}
    for letter in LETTERS:
        if letter not in options:
            return None
        match = NUM.search(str(options[letter]))
        if not match:
            return None
        try:
            values[letter] = float(match.group().replace(",", "."))
        except ValueError:
            return None
    ordered = sorted(values, key=values.get)
    return ordered[2]
