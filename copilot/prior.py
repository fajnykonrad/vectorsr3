"""Two measured heuristics that beat the model on their own turf, plus the
uniform-letter calibration for the jury's test distribution.

All are deterministic, offline, and instant (no LLM call):

- median option value: where all five options parse as numbers, the letter
  holding the median value answers better than the model (27.7% vs 22.8% on
  the 329 numeric cat+eng M3Kang validation problems). The classic
  multiple-choice heuristic: in M3Kang the answer concentrates at the median.
- level prior: where the OCR could not read the options, the model's
  distribution is A/D noise; the most common true letter of the problem's
  level, learned from the eng+cat training problems, answers better (28.1%
  full policy vs 24.0% raw on the 562 cat+eng set).
- uniform calibration: the jury's practice set states every letter is
  correct equally often, and the model's letter marginal is far from uniform
  (D 0.47 vs 0.20 expected). Dividing each letter's probability by its
  marginal share (lambda ~0.8) scored 25-26% vs raw 20% on the practice set
  and held up in a half-to-half split check. Only meaningful on a
  uniform-letter distribution: on M3Kang keep it off (UNIFORM=0), on the
  jury's test set set UNIFORM=1 (predict.py does when --uniform passes).

Measured before shipping in tune_policy2.py / calibrate_uniform.py.
"""
import json
import math
import os
import re

from .config import ROOT

LETTERS = "ABCDE"
NUM = re.compile(r"-?\d+(?:[.,]\d+)?")
PRIOR_PATH = os.path.join(ROOT, "data", "level_prior.json")
FLOOR = -12.0
_prior = None


def level_prior():
    """{level(int): letter} from data/level_prior.json, or {}."""
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


def uniform_pick(probs, lam=0.8):
    """argmax of log p(L) - lam * log q_L, with q a FIXED calibration marginal.

    The marginal must be a constant measured across a whole set
    (calibrate_uniform.py on the jury's practice set): computing it from the
    single problem's own probs would be a no-op (q = p normalised, argmax
    unchanged, everything stays the model's greedy D).
    """
    best, best_score = None, None
    for letter in LETTERS:
        score = probs.get(letter, FLOOR) - lam * math.log(JURY_MARGINALS[letter])
        if best_score is None or score > best_score:
            best, best_score = letter, score
    return best


# The model's letter marginal on the jury's practice set (100 problems,
# measured with calibrate_uniform.py): D 0.47, C 0.05 - far from the uniform
# 0.20 the jury announces. The final test comes from the same authors, so
# this vector is the system's calibration constant.
JURY_MARGINALS = {"A": 0.249, "B": 0.128, "C": 0.047, "D": 0.465, "E": 0.111}
