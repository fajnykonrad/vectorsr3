"""Fuse the model's letter distribution with what the training set taught us.

fit_model.py learns two things from the signals collected with collect.py on
the training problems (data/signals.jsonl):

- letter offsets: a per-letter correction for the model's letter bias
  (on the board it answered D 21 times and A 14 times out of 40), fitted so
  that argmax(log p + offset) answers more training problems correctly;
- the kNN weight: how much the answers of the nearest training problems,
  taken from the retrieval index, should count in the fusion.

data/model.json holds both. Without the file, or with "enabled": false, this
module is transparent: pick() returns the model's own greedy letter.

    score(L) = log p(L) + offset_L + knn_weight * vote_L
"""
import json
import os

from .config import ROOT

PATH = os.path.join(ROOT, "data", "model.json")
FLOOR = -12.0  # must match copilot.llm.FLOOR

_params = None


def load(path=PATH, force=False):
    """Read data/model.json once. A missing file or "enabled": false means no fusion."""
    global _params
    if _params is None or force:
        try:
            with open(path) as f:
                params = json.load(f)
            if not params.get("enabled", True):
                params = {}
        except (OSError, ValueError):
            params = {}
        _params = params or {}
    return _params


def active():
    """True when there is a fitted model to fuse with."""
    return bool(load())


def weight_of(params, group):
    """The kNN weight for a group ("global", "with_options", "without_options")."""
    return params.get(f"knn_weight_{group}", params.get("knn_weight", 0.0))


def pick(probs, votes=None, has_options=None):
    """One letter A..E: argmax of the fused score. Ties keep the earlier letter.

    Strict group policy: the fitted offsets apply only to the group they were
    shipped for (fit_model.py decides by cross-validation). A group without
    its own entry answers with the model's raw distribution — no fallback, no
    votes — so a fit that does not generalize cannot hurt that group.
    """
    letters = "ABCDE"
    if not any(letter in probs for letter in letters):
        return None
    params = load()
    if not params:
        return raw_pick(probs)
    group = "with_options" if has_options else "without_options"
    chosen_group = (params.get("offsets") or {}).get(group)
    if chosen_group is None:
        return raw_pick(probs)
    weight = weight_of(params, group) if votes else 0.0
    best, best_score = None, None
    for letter in letters:
        score = probs.get(letter, FLOOR) + chosen_group.get(letter, 0.0)
        score += weight * votes.get(letter, 0.0)
        if best_score is None or score > best_score:
            best, best_score = letter, score
    return best


def raw_pick(probs):
    """The model's own greedy letter, without any fusion."""
    best, best_score = None, None
    for letter in "ABCDE":
        score = probs.get(letter, FLOOR)
        if best_score is None or score > best_score:
            best, best_score = letter, score
    return best
