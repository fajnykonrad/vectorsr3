"""Prompt views for the ensemble: the same problem, asked in several ways.

A weak model's errors change with the prompt, so asking the same problem in
a few independent ways and voting recovers accuracy no single prompt has.
Every view keeps the [A-E] grammar: exactly one letter out, temperature 0.
The options-reversed view relabels letters (the model's letter bias is
positional); score_ensemble.py maps the letters back with letter_map.
"""

VALUE_FIRST = ("You compare the answer options of a multiple-choice math "
               "problem. Work out the value or idea each option stands for, "
               "judge which one the problem asks for, and reply with the "
               "letter of that option.")

ELIMINATE = ("You solve multiple-choice math competition problems. First rule "
             "out the two least likely options in your head, then compare the "
             "three that remain, and reply with the letter of the most likely "
             "one.")

CAREFUL = ("You are a careful math competition judge. Read the problem twice, "
           "check what is really being asked, and reply with the letter of "
           "the correct option. Options that look similar usually hide a "
           "small detail, so prefer the one that survives a sanity check.")

LETTERS = "ABCDE"
REVERSED_MAP = {new: old for new, old in zip(LETTERS, reversed(LETTERS))}


def reverse_options(problem):
    """A copy of the problem whose options read E..A as A..E."""
    options = problem.get("options") or {}
    return {**problem, "options": {new: options[old]
                                   for new, old in REVERSED_MAP.items() if old in options}}


# name -> how the question is asked. "reverse": the options are presented in
# the reversed letter order, and the answer must be mapped back.
VIEWS = {
    "base": {},
    "value-first": {"system": VALUE_FIRST},
    "eliminate": {"system": ELIMINATE},
    "careful": {"system": CAREFUL},
    "reversed": {"reverse": True},
}
