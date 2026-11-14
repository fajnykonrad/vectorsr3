"""The rating model: one score from an attempt, one update for each rating.

Pure functions, no I/O, so the simulated student can test them and the server
only applies them. Both sides follow Elo: the expected score is
E = 1 / (1 + 10**((Rp - Ru) / 400)), and after an attempt each side moves
toward what happened. Problems start at 800 + 150 per level, users at 800.
"""
import math

USER_SEED = 700.0    # everyone starts the climb here
K_USER_NEW = 56.0    # first attempts in a topic: learn fast
K_USER = 40.0
K_PROBLEM = 8.0      # problems move less: their difficulty is mostly the level
NEW_TOPICS = 10      # attempts before a topic counts as known
CORRECT_BOOST = 1.3  # correct answers earn more: the ladder is climbable

# Certainty is the slider, 1 (a guess) to 5 (sure). Correct answers score
# above 0.5, wrong ones below, and certainty sets how far from the middle:
# a sure correct answer is a perfect 1.0, a sure wrong answer is 0.0. A lucky
# guess counts, but far less than knowing: the break-even is roughly 40%
# correct. Right answers also gain a small time bonus near the par time.
SCORE_CORRECT = (0.76, 0.82, 0.88, 0.94, 1.00)   # index = certainty - 1
SCORE_WRONG = (0.24, 0.18, 0.12, 0.06, 0.00)

TIME_FAST = 0.5      # correct in under half the par time: a small bonus
TIME_SLOW = 2.0      # correct after twice the par time: a small penalty
TIME_BONUS = 0.10
HINT_COST = 0.85     # each hint rung used scales the score down


def problem_seed(level, difficulty=0):
    """A problem's starting rating: the grade band plus the within-band
    difficulty. Levels 0..7, difficulties 0 easy / 1 medium / 2 hard."""
    return 800.0 + 100.0 * (level or 0) + 120.0 * (difficulty or 0)


def par_seconds(level):
    return 40.0 + 20.0 * (level or 0)


def difficulty_probabilities(rating):
    """Which difficulty to serve, from the user's rating in the topic.

    Around the seed (800) problems stay easy; at ~1160 they are hard, with
    a smooth spread in between and a little variety either side.
    """
    target = max(0.0, min(2.0, (rating - USER_SEED) / 250.0))
    spread = 0.7
    weights = [math.exp(-0.5 * ((d - target) / spread) ** 2) for d in (0, 1, 2)]
    total = sum(weights)
    return [0.95 * w / total + 0.05 / 3 for w in weights]


def attempt_score(correct, certainty, seconds, level, hint_rung=0):
    """The observed result S in [0, 1], adjusted for time and hints."""
    certainty = min(5, max(1, int(certainty)))
    s = (SCORE_CORRECT if correct else SCORE_WRONG)[certainty - 1]
    par = par_seconds(level)
    if correct:
        if seconds < TIME_FAST * par:
            s += TIME_BONUS
        elif seconds > TIME_SLOW * par:
            s -= TIME_BONUS
    if hint_rung:
        s *= HINT_COST ** hint_rung
    return max(0.0, min(1.0, s))


def expected(user_rating, problem_rating):
    return 1.0 / (1.0 + 10.0 ** ((problem_rating - user_rating) / 400.0))


def update(user_rating, problem_rating, score, attempts_in_topic=NEW_TOPICS):
    """Return the new (user_rating, problem_rating) after one attempt.

    Correct answers earn more (the climb is meant to be rewarding); wrong
    ones cost, scaled by certainty through the score. No cap: the sea and
    the castle are far apart for a reason.
    """
    e = expected(user_rating, problem_rating)
    k = K_USER_NEW if attempts_in_topic < NEW_TOPICS else K_USER
    delta = k * (score - e)
    if score > e:
        delta *= CORRECT_BOOST
    return (user_rating + delta,
            problem_rating + K_PROBLEM * (e - score))
