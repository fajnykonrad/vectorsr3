"""The hint ladder: three rungs, deterministic first, the model second.

Rung 1: the topic's strategy cue, written by hand, no model involved.
Rung 2: one short sentence from the language model, checked in code so it
        cannot leak the answer; on any failure we serve rung 1 instead.
Rung 3: the reveal, on purpose: the correct letter with its value.
"""
import re

from .topics import TOPICS

MAX_HINT_WORDS = 35

HINT_SYSTEM = (
    "You give ONE short hint for a math problem. You are given the problem "
    "and its worked solution. Write ONE sentence of at most 30 words that "
    "guides the student to take only the FIRST step of the solution. Never "
    "state the final answer, never name any option's value, never say which "
    "letter is correct, and never mention that a solution was shown to you. "
    "Start with 'Hint: '. Write in the same language as the problem.")


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


def model_hint(problem, label, llm, index=None, problems=(), bank=None,
               timeout=25.0):
    """Rung 2: one sentence from the model, grounded, leak-checked.

    A small model given only the bare problem writes generic advice ("place
    the largest numbers..."), useless for the problem at hand. So it gets
    the worked solution - from the bank when the problem has one, else the
    similar solved problem from retrieval - and only has to compress it
    into a first-step nudge. The leak check still rejects anything that
    names an option value or the correct letter; two attempts, then the
    caller falls back to the method cue.
    """
    solution = None
    if bank and problem["id"] in bank:
        solution = bank[problem["id"]]["text"]
    else:
        found = similar_problem(problem, index=index, problems=problems,
                                exclude_id=problem["id"])
        if found:
            _, neighbour = found
            n_opts = neighbour.get("options") or {}
            n_ans = str(neighbour.get("label") or "")
            if n_ans in n_opts:
                n_ans += f") {n_opts[n_ans]}"
            n_text = neighbour["text"].strip()
            if len(n_text) > 200:
                n_text = n_text[:200] + "..."
            solution = (f'A similar worked problem: "{n_text}" Its answer '
                        f'is {n_ans}. Use the same idea for the problem '
                        f'below.')
    user_text = f"Problem:\n{problem['text'].strip()}"
    if solution:
        if len(solution) > 320:
            solution = solution[:320] + "..."
        user_text += f"\n\nWorked solution:\n{solution}"
    user_text += "\n\nGive one hint about the first step, for the problem above."
    messages = [{"role": "system", "content": HINT_SYSTEM},
                {"role": "user", "content": user_text}]
    last = ("error", None)
    for temperature in (0.7, 0.3):
        try:
            raw = llm(messages, timeout=timeout, temperature=temperature,
                      max_tokens=90)
        except Exception as error:
            return None, f"error: {error}"
        text = clean_math_text(raw.strip().strip('"'))
        words = text.split()
        if len(words) > MAX_HINT_WORDS + 8:  # a little slack around the limit
            text = " ".join(words[:MAX_HINT_WORDS]) + "..."
        if leaks(text, problem, label):
            last = ("leaked", text)
            continue
        return text, "ok"
    return last[1], last[0]


WRONG_LETTER = re.compile(
    r"\b(?:correct|right)\s+(?:option|answer|choice)\s+(?:is|:)\s*"
    r"(?:letter\s+)?([a-e])\b")


def consistent(explanation, problem, label):
    """True when the explanation could plausibly walk to the right answer.

    The model must land on the correct option's value: if the explanation
    never mentions 20 while explaining why D) 20 is right, it is inventing
    its own (wrong) path. It must also never name a DIFFERENT letter as the
    correct one (a small model given a second solved problem will sometimes
    conclude with that one's answer instead). Without options there is
    nothing to anchor on, so any reasonably long text passes.
    """
    if not explanation or len(explanation.split()) < 8:
        return False
    low = explanation.lower()
    for match in WRONG_LETTER.finditer(low):
        if match.group(1) != label.lower():
            return False  # asserts another option is the correct one
    value = str((problem.get("options") or {}).get(label, "")).strip()
    if not value:
        return True
    pattern = r"(?<![\w.])" + re.escape(value.lower()) + r"(?![\w.])"
    # The landing: the value must be in the FINAL sentence. "6" appears
    # incidentally in a problem about 6 apples even when the explanation
    # concludes with the wrong number; naming the correct letter also counts.
    sentences = re.split(r"(?<=[.!?])\s+", low.strip())
    last = sentences[-1] if sentences else low
    if re.search(pattern, last):
        return True
    return re.search(r"\b(?:correct|right)\s+(?:option|answer|choice)\s+"
                     r"(?:is|:)\s*(?:letter\s+)?" + label.lower() + r"\b",
                     low) is not None


EXPLAIN_SYSTEM = (
    "You explain math to school students. You get a problem with options, "
    "its correct option, and the method for this kind of problem. Explain "
    "how to reach the correct answer in exactly 3 short numbered steps: "
    "1) what the problem asks and what we know, 2) the reasoning or "
    "calculation using the numbers, 3) why the correct option is the right "
    "one, ending with its letter and value (for example: 'so the answer is "
    "B) 14'). Use only numbers that appear in the problem or its options. "
    "Plain text: no markdown, no asterisks, no LaTeX. At most 80 words. "
    "Write in the same language as the problem."
)


def _explain_messages(problem, label, strategy):
    """The prompt. No second problem in it: a 0.8B given a similar solved
    problem will explain (or conclude with) THAT one instead. The topic's
    method cue gives it guidance without anything confusable."""
    lines = [problem["text"].strip()]
    options = problem.get("options") or {}
    for letter in "ABCDE":
        if letter in options:
            lines.append(f"{letter}) {options[letter]}")
    target = f"The correct answer is {label}"
    if label in options:
        target += f") {options[label]}"
    target += "."
    parts = ["Problem:", "\n".join(lines), "", target, "",
             f"Method for this kind of problem: {strategy}", "",
             "Explain only this problem, in the 3 steps."]
    return [{"role": "system", "content": EXPLAIN_SYSTEM},
            {"role": "user", "content": "\n".join(parts)}]


def _fallback_explanation(problem, label, neighbour, source=None):
    """No model or two failed attempts: assemble from retrieval, no tokens.

    Always decent, never wrong: the worked neighbour is a real problem from
    the dataset with its real answer, plus the topic's strategy cue. The
    neighbour IS the content here, so it stays inside the text.
    """
    parts = []
    if neighbour is not None:
        n_text = neighbour["text"].strip()
        if len(n_text) > 220:
            n_text = n_text[:220] + "..."
        n_options = neighbour.get("options") or {}
        n_answer = str(neighbour.get("label") or "")
        if n_answer in n_options:
            n_answer += f") {n_options[n_answer]}"
        parts.append(f'A similar solved problem: "{n_text}" Its answer is '
                     f'{n_answer}. Work through it once: this problem is '
                     f'solved the same way.')
    parts.append(strategy_cue(problem))
    return {"text": " ".join(parts),
            "source": "retrieval" if neighbour is not None else "strategy"}


def explain_answer(problem, label, llm=None, index=None, problems=(),
                   bank=None):
    """After a wrong answer: how to actually do this problem.

    Order of preference:
    1. The precomputed bank (data/solutions.jsonl, generated offline with a
       bigger model and validated): instant, best quality, no tokens.
    2. The 0.8B model, verify-backwards with a 3-step scaffold: usable, and
       refused by consistent() when it lands wrong.
    3. The deterministic fallback: the worked neighbour plus the topic's
       strategy cue. Always right, never brilliant.

    The answer is already revealed, so the model never has to FIND it (the
    one thing a 0.8B model cannot do); it only explains how one CHECKS that
    the correct option fits, guided by the topic's method. The similar
    solved problem from the retrieval index stays OUT of the model prompt
    (the model explained that one instead) and anchors the page and the
    fallback instead.
    """
    found = similar_problem(problem, index=index, problems=problems,
                            exclude_id=problem["id"])
    neighbour, neighbour_source = None, None
    if found:
        neighbour_source, neighbour = found

    if bank is not None and problem["id"] in bank:
        return {"text": bank[problem["id"]]["text"], "source": "bank"}

    if llm is None:
        return _fallback_explanation(problem, label, neighbour, neighbour_source)

    messages = _explain_messages(problem, label, strategy_cue(problem))
    last_text = None
    for temperature in (0.4, 0.0):
        try:
            text = llm(messages, timeout=45.0, temperature=temperature,
                       max_tokens=200).strip().strip('"')
        except Exception:
            break  # the model server is out; do not retry the same way
        text = clean_math_text(text)
        words = text.split()
        if len(words) > 100:
            text = " ".join(words[:100]) + "..."
        last_text = text
        if consistent(text, problem, label):
            return {"text": text, "source": "model"}
    # both attempts failed the check: the deterministic path wins
    fallback = _fallback_explanation(problem, label, neighbour, neighbour_source)
    if last_text:
        fallback["rejected"] = last_text
    return fallback


def clean_math_text(text):
    """Small models love markdown and LaTeX; the page wants plain prose."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)      # **bold** -> bold
    text = re.sub(r"\*([^*]+)\*", r"\1", text)          # *italic* -> italic
    text = text.replace("\\cdot", " times ").replace("\\times", " times ")
    text = re.sub(r"\$([^$]*)\$", r"\1", text)          # $x$ -> x
    text = text.replace("\\(", " ").replace("\\)", " ")
    text = re.sub(r"\\[a-zA-Z]+", " ", text)            # leftover \frac etc.
    text = text.replace("{", " ").replace("}", " ")
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def hint_rung(rung, problem, label, index=None, problems=(), llm=None,
              bank=None):
    """The ladder entry point. Returns a dict for the API."""
    if rung <= 1:
        return {"rung": 1, "text": strategy_cue(problem)}
    if rung <= 2 and llm is not None:
        text, status = model_hint(problem, label, llm, index=index,
                                  problems=problems, bank=bank)
        if text and status == "ok":
            return {"rung": 2, "text": text, "status": status}
        return {"rung": 1, "text": strategy_cue(problem),
                "status": status or "fallback"}
    # rung 3, the reveal
    options = problem.get("options") or {}
    return {"rung": 3, "label": label, "options": options,
            "note": "The correct answer. The ladder stops here."}
