"""Pick the next problem: weak topics first, with an anti-boredom mix.

The topic chance is 75% adaptive (softmax over how far each topic's rating
sits below the user's average) plus 25% uniform, so practice keeps varying.
Inside a topic, the problem whose rating is nearest to the user's rating plus
a small margin is chosen: a gentle stretch, never far above what they can do.
"""
import math
import random

from .elo import USER_SEED, difficulty_probabilities, problem_seed
from .topics import TOPIC_IDS

MIX_ADAPTIVE = 0.75   # the rest is uniform over topics, so practice varies
GAP_SCALE = 120.0     # elo points of gap that multiply a topic's weight by e
GAP_MIN, GAP_MAX = -200.0, 400.0
TARGET_MARGIN = 60.0  # aim a bit above the user's rating
RECENT = 20           # never repeat the last N problems shown
RANDOMNESS = 3        # pick among the 3 nearest problems, for variety


def pick_difficulty(rating, rng=random):
    """0, 1 or 2, drawn from the probabilities the rating implies."""
    probabilities = difficulty_probabilities(rating)
    return rng.choices((0, 1, 2), weights=probabilities)[0]


def topic_probabilities(ratings):
    """{topic: probability} from {topic: rating}; unseen topics count as average."""
    seen = [r for r in ratings.values() if r is not None]
    mean = sum(seen) / len(seen) if seen else USER_SEED
    weights = {}
    for topic in TOPIC_IDS:
        rating = ratings.get(topic)
        if rating is None:
            rating = mean  # an untried topic looks neither weak nor strong
        gap = max(GAP_MIN, min(GAP_MAX, mean - rating))
        weights[topic] = math.exp(gap / GAP_SCALE)
    total = sum(weights.values())
    uniform = (1.0 - MIX_ADAPTIVE) / len(TOPIC_IDS)
    return {t: MIX_ADAPTIVE * weights[t] / total + uniform for t in TOPIC_IDS}


def pick_topic(ratings, rng=random):
    probabilities = topic_probabilities(ratings)
    return rng.choices(list(probabilities), weights=list(probabilities.values()))[0]


def pick_problem(problems, topic, ratings, problem_ratings, recent, rng=random):
    """One problem from `topic`: the user's rating decides the difficulty,
    then the nearest rating to the target, with options, not seen recently.
    Falls back progressively so it always returns one."""
    user_rating = ratings.get(topic, USER_SEED)
    target = user_rating + TARGET_MARGIN
    wanted = pick_difficulty(user_rating, rng)
    rating_of = lambda p: problem_ratings.get(
        p["id"], problem_seed(p.get("level"), p.get("difficulty")))
    pool = [p for p in problems if p["topic"] == topic and p["id"] not in recent]
    if not pool:
        pool = [p for p in problems if p["id"] not in recent]
    if not pool:
        pool = list(problems)
    if not pool:
        return None
    ranked = sorted(pool, key=lambda p: (p.get("difficulty", 0) != wanted,
                                         abs(rating_of(p) - target),
                                         0 if p.get("options") else 1))
    top = ranked[:RANDOMNESS]
    return rng.choice(top)
