"""A topic for every problem, for the error analysis by topic.

M3Kang has no topic field, and two parts of this project need topics: the
trainer's adaptive selection and the copilot's error analysis. One source of
truth: trainer/build_tags.py tags every problem with the topic of its
closest anchor sentence (trainer/topics.py) and writes data/tags.json as
{problem_id: topic}, shared by every language of the same problem.

topic_of() reads that file when it exists and covers the problem; otherwise
it falls back to keyword rules, so eval.py works before build_tags.py runs.
The keyword topics are a coarse net; the anchor tags are the good ones.
"""
import json
import os
import re

from .config import ROOT

TAGS_PATH = os.path.join(ROOT, "data", "tags.json")
_tags = None


def anchor_topics():
    """{problem_id: topic} from trainer/build_tags.py, or {} before it runs."""
    global _tags
    if _tags is None:
        try:
            with open(TAGS_PATH) as f:
                _tags = json.load(f)
        except (OSError, ValueError):
            _tags = {}
    return _tags


# Fallback: checked by hand against M3Kang English problems. Order only
# matters for printing; the topic with the most keyword hits wins.
TOPICS = {
    "geometry": ["triangle", "square", "circle", "angle", "cube", "rectangle", "polygon",
                 "hexagon", "octagon", "rhombus", "diagonal", "radius", "diameter", "side",
                 "vertex", "quadrat", "triangle"],
    "counting": ["how many ways", "in how many", "different ways", "possible ways",
                 "arrange", "order the", "list the", "combin", "permut", "quantes maneres"],
    "numbers": ["digit", "sum", "product", "remainder", "divide", "divisor", "multiply",
                "prime", "even", "odd", "integer", "multiple", "square number", "factor"],
    "time_speed": ["clock", "hour", "minute", "day", "week", "speed", "km", "metres per",
                   "faster", "slower", "hours ago", "later", "rellotge", "hora", "velocitat"],
    "logic": ["always", "never", "truth", "liar", "knight", "statement", "at least one",
              "must be", "cannot be", "which of the following"],
    "patterns": ["next", "sequence", "pattern", "continues", "series", "rule", "first terms",
                 "segent", "seguent", "seqncia", "seqlencia", "patr"],
    "fractions": ["fraction", "half", "quarter", "third", "percent", "probability",
                  "chance", "ratio", "meitat", "quart", "probabilitat", "percentatge"],
    "area_volume": ["area", "perimeter", "volume", "surface", "coverage", "rea",
                    "permetre", "perímetre", "volum"],
    "money": ["euro", "cost", "pays", "price", "coins", "money", "spends", "sold for",
              "euros", "costa", "monedes", "preu", "diners"],
    "games": ["game", "plays", "wins", "dice", "cards", "board", "players", "tournament",
              "match", "joc", "dau", "cartes", "guanya", "partit"],
    "measures": ["weighs", "weight", "kg", "litre", "litres", "grams", "metres long",
                 "tall", "cm", "mm", "degrees"],
}
WORD = re.compile(r"\w+", re.UNICODE)


def keyword_topic(problem):
    """The keyword fallback: one topic from the problem's text."""
    text = problem.get("text", "").lower()
    tokens = set(WORD.findall(text))
    best, best_hits = "other", 0
    for topic, keywords in TOPICS.items():
        hits = sum(1 for keyword in keywords
                   if keyword in tokens or (keyword in text and " " in keyword))
        if hits > best_hits:
            best, best_hits = topic, hits
    return best


def topic_of(problem):
    """One topic per problem: the anchor tag when it exists, else keywords."""
    return anchor_topics().get(problem.get("id")) or keyword_topic(problem)
