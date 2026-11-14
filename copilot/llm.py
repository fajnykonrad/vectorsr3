"""Ask the small language model for one letter, A to E."""
from .config import CONFIG
from .client import post

URL = f"http://127.0.0.1:{CONFIG['LLM_PORT']}/v1/chat/completions"

# Keep the system prompt stable: llama-server caches the start of the prompt,
# so text that never changes is only read once.
SYSTEM = ("You solve multiple-choice math competition problems for school students. "
          "Read the problem and the options, then reply with the letter of the correct option.")

FLOOR = -12.0  # log-probability for letters the server never reported


def format_problem(problem, sees_image=False):
    lines = [problem["text"].strip()]
    options = problem.get("options") or {}
    for letter in "ABCDE":
        if letter in options:
            lines.append(f"{letter}) {options[letter]}")
    if not options:
        lines.append("(The options are in the picture.)" if sees_image else
                     "(The options are in a picture that you can't see. Pick the most likely letter.)")
    return "\n".join(lines)


def build_messages(problem, examples=(), image_b64=None, system=SYSTEM):
    """image_b64 is a PNG as base64 text. Only a server started with --mmproj can see it."""
    messages = [{"role": "system", "content": system}]
    for ex in examples:  # solved problems retrieved with RAG, if any
        messages.append({"role": "user", "content": format_problem(ex) + "\nAnswer:"})
        messages.append({"role": "assistant", "content": ex["label"]})
    text = format_problem(problem, sees_image=bool(image_b64)) + "\nAnswer:"
    if image_b64:
        content = [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + image_b64}},
                   {"type": "text", "text": text}]
    else:
        content = text
    messages.append({"role": "user", "content": content})
    return messages


def answer_distribution(problem, examples=(), timeout=60, image_b64=None, url=URL, system=SYSTEM):
    """Return (letter, probs, timings).

    The grammar forces the first token to be one letter, so the whole answer
    is a choice among five. probs holds the model's log-probability for each
    letter at that position, read from the response's top log-probabilities;
    a letter the server doesn't report gets FLOOR, so all five are always
    there. Without log-probabilities, probs is one-hot on the chosen letter.
    """
    response = post(url, {
        "messages": build_messages(problem, examples, image_b64, system),
        "grammar": "root ::= [A-E]",
        "max_tokens": 1,
        "temperature": 0,
        "seed": int(CONFIG["SEED"]),
        "cache_prompt": True,
        "logprobs": True,
        "top_logprobs": 40,  # raw (pre-grammar) logprobs; 40 keeps all five letters inside
    }, timeout=timeout)
    choice = response["choices"][0]
    letter = choice["message"]["content"].strip()
    if letter and letter[0] in "ABCDE":
        letter = letter[0]
    probs = {}
    content = (choice.get("logprobs") or {}).get("content") or []
    if content:
        for item in content[0].get("top_logprobs") or []:
            token = item["token"].strip()
            if len(token) == 1 and token in "ABCDE":
                probs[token] = item["logprob"]
    if letter in "ABCDE" and letter not in probs:
        probs[letter] = content[0].get("logprob", -0.01) if content else -0.01
    return letter, {l: probs.get(l, FLOOR) for l in "ABCDE"}, response.get("timings", {})


def answer_letter(problem, examples=(), timeout=60, image_b64=None, url=URL):
    """Return (letter, timings). The grammar makes any other output impossible."""
    letter, _probs, timings = answer_distribution(problem, examples, timeout=timeout,
                                                  image_b64=image_b64, url=url)
    return letter, timings
