"""The copilot: one problem in, one letter out.

This is the file to change first. predict.py and eval.py both call solve(),
so whatever you build here is exactly what the official run measures.

What the training problems contribute at answer time:
- data/index.db: every training problem embedded. Its nearest neighbours
  vote with their labels (the kNN prior), and the top ones can be shown to
  the model as solved examples (--rag K).
- data/model.json: letter offsets and the kNN weight, fitted by fit_model.py
  on signals collected with collect.py. They correct the model's letter bias
  and balance the vote against the model's own distribution.

score(L) = log p(L) + offset_L + knn_weight * vote_L, then argmax.
Without index.db or model.json the copilot degrades to the raw model, and
to FALLBACK when the language model is down or too slow.
"""
import os
import socket
import time
import urllib.error

from . import model
from .config import CONFIG
from .llm import URL, answer_distribution
from .prior import level_prior, median_letter

TIME_LIMIT = float(CONFIG["TIME_LIMIT_SECONDS"])
FALLBACK = CONFIG["FALLBACK_ANSWER"]
MARGIN = 3.0  # seconds kept free for Python and for writing the answer
VOTES = 8     # neighbours whose answers form the kNN prior
FUSION = os.environ.get("FUSION", "1").lower() not in ("0", "false", "off")


def label_votes(hits):
    """The share of the neighbours whose answer is each letter."""
    counts = {}
    for _score, hit in hits:
        counts[hit["label"]] = counts.get(hit["label"], 0) + 1
    total = sum(counts.values()) or 1
    return {letter: n / total for letter, n in counts.items()}


def solve(problem, index=None, k=0, exclude_id=None, image_b64=None, llm_url=URL,
          time_limit=TIME_LIMIT, fusion=None):
    """Return {"answer", "seconds", "status", ...} for one problem.

    index and k turn on retrieval: the k most similar solved problems are
    added to the prompt as examples, and their neighbours' labels vote in the
    fusion (VOTES of them, whether or not k > 0). fusion=False answers with
    the model's own greedy letter and is how you ablate the fitted model.
    image_b64 and llm_url send the problem image to a vision server.
    """
    if fusion is None:
        fusion = FUSION and model.active()
    start = time.perf_counter()
    result = {"answer": FALLBACK, "status": "ok", "prompt_tokens": 0, "retrieved": "",
              "examples": [], "probs": {}, "votes": {}}
    # The two measured heuristics (copilot/prior.py) answer where they beat
    # the model, instantly and deterministically:
    if not problem.get("options"):
        prior = level_prior().get(problem.get("level"), FALLBACK)
        result["answer"] = prior
        result["status"] = "ok-level-prior"
        result["seconds"] = round(time.perf_counter() - start, 3)
        return result
    median = median_letter(problem)
    if median:
        result["answer"] = median
        result["status"] = "ok-median"
        result["seconds"] = round(time.perf_counter() - start, 3)
        return result
    # everything else goes to the model, fused when a fit shipped
    try:
        examples, votes = [], {}
        if index is not None:
            try:
                hits = index.search(problem, k=max(k, VOTES), exclude_id=exclude_id)
            except (socket.timeout, TimeoutError, urllib.error.URLError, OSError):
                hits = []  # embeddings down: still answer with the language model
            if hits:
                votes = label_votes(hits)
                result["votes"] = {l: round(v, 3) for l, v in votes.items()}
                with_options = [p for _score, p in hits if p.get("options")]
                examples = (with_options or [p for _score, p in hits])[:k]
                result["examples"] = hits[:k]
                result["retrieved"] = ";".join(f"{p['id']}:{score:.2f}" for score, p in hits[:k])
        remaining = time_limit - (time.perf_counter() - start) - MARGIN
        letter, probs, timings = answer_distribution(problem, examples, timeout=max(remaining, 1.0),
                                                     image_b64=image_b64, url=llm_url)
        result["probs"] = {l: round(v, 4) for l, v in probs.items()}
        result["prompt_tokens"] = timings.get("prompt_n", 0)
        chosen = model.pick(probs, votes, has_options=bool(problem.get("options"))) \
            if fusion else letter
        result["answer"] = chosen or letter or FALLBACK
    except (socket.timeout, TimeoutError):
        result["status"] = "timeout"
    except urllib.error.URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            result["status"] = "timeout"
        else:
            result["status"] = f"error: {error.reason}"
    result["seconds"] = round(time.perf_counter() - start, 2)
    return result
