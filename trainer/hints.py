"""The hint ladder: four rungs, deterministic first, the model last.

Rung 1: a similar solved problem, from the embedding index when it is up,
        otherwise the nearest problem of the same topic at a lower level.
Rung 2: the strategy cue for the topic, written by hand, no model involved.
Rung 3: one short sentence from the language model, checked in code so it
        cannot leak the answer; on any failure we serve rung 2 instead.
Rung 4: the reveal, on purpose: the correct letter and the worked neighbour.
"""
import re

from .topics import TOPICS

MAX_HINT_WORDS = 35


def similar_problem(problem, index=None, problems=(), exclude_id=None):
    """Rung 1: (source, problem). The caller decides what to show."""
    if index is not None:
        try:
            hits = index.search(problem, k=1, exclude_id=exclude_id or problem["id"])
            if hits:
                return "embedding", hits[0][1]
        except Exception:
            pass  # the embedding server may be down; fall through
    topic = problem.get("topic", "other")
    level = problem.get("level", 0)
    candidates = [p for p in problems
                  if p["topic"] == topic and p["id"] != (exclude_id or problem["id"])
                  and p.get("options")]
    if not candidates:
        candidates = [p for p in problems if p["id"] != (exclude_id or problem["id"])]
    if not candidates:
        return None
    easier = [p for p in candidates if (p.get("level") or 0) <= level]
    pool = easier or candidates
    return "topic", sorted(pool, key=lambda p: abs((p.get("level") or 0) - level))[0]


def strategy_cue(problem):
    """Rung 2: the canned sentence for the topic."""
    return TOPICS.get(problem.get("topic", "other"), TOPICS["other"])["strategy"]


def leaks(hint, problem, label):
    """True when the hint would give the answer away."""
    low = hint.lower()
    options = problem.get("options") or {}
    for value in options.values():
        text = str(value).strip()
        if text and re.search(r"(?<![\w.])" + re.escape(text.lower()) + r"(?![\w.])", low):
            return True
    # the letter, spoken or written as the answer
    if label and re.search(r"\b(?:answer|option|correct)\s+(?:is|:)?\s*"
                           r"(?:letter\s+)?[" + label.lower() + r"]\b", low):
        return True
    return False


def model_hint(problem, label, llm, timeout=20.0):
    """Rung 3: one sentence from the model, leak-checked. (llm = callable)

    `llm(messages, timeout)` returns the model text; the server wires this to
    the llama.cpp endpoint. Returns (text, status): status is "ok", "leaked"
    (rejected) or "error".
    """
    messages = [
        {"role": "system",
         "content": "You give ONE sentence of help with a math problem. "
                    "Never say or compute the final answer, never name any "
                    "option value, never say which letter is correct. "
                    "At most 35 words. Start with 'Hint: '."},
        {"role": "user", "content": problem["text"] + "\n\nGive one hint."},
    ]
    try:
        text = llm(messages, timeout=timeout)
    except Exception:
        return None, "error"
    text = text.strip().strip('"')
    words = text.split()
    if len(words) > MAX_HINT_WORDS + 8:  # a little slack around the limit
        text = " ".join(words[:MAX_HINT_WORDS]) + "..."
    if leaks(text, problem, label):
        return None, "leaked"
    return text, "ok"


def hint_rung(rung, problem, label, index=None, problems=(), llm=None):
    """The ladder entry point. Returns a dict for the API."""
    if rung <= 1:
        found = similar_problem(problem, index=index, problems=problems,
                                exclude_id=problem["id"])
        if found:
            source, neighbour = found
            return {"rung": 1, "source": source, "neighbour": {
                        "id": neighbour["id"], "language": neighbour["language"],
                        "text": neighbour["text"], "topic": neighbour.get("topic"),
                        "level": neighbour.get("level"), "label": neighbour.get("label"),
                        "options": neighbour.get("options") or {}}}
        rung = 2  # nothing similar: fall through to the strategy
    if rung <= 2:
        return {"rung": 2, "text": strategy_cue(problem)}
    if rung <= 3 and llm is not None:
        text, status = model_hint(problem, label, llm)
        if text:
            return {"rung": 3, "text": text, "status": status}
        return {"rung": 2, "text": strategy_cue(problem),
                "status": status or "fallback"}
    # rung 4, the reveal
    options = problem.get("options") or {}
    return {"rung": 4, "label": label, "options": options,
            "note": "The correct answer. The ladder stops here."}
