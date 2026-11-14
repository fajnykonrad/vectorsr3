# The Kangaroo Trainer

A learning platform on the board: adaptive practice per topic, an Elo rating
per topic, and a hint ladder that ends in the answer only on purpose.

## The pieces

| File | What it is |
| --- | --- |
| `topics.py` | The 9 topics: anchor sentences for tagging, strategy cues for hints |
| `elo.py` | The rating model: score from an attempt, Elo update for both sides |
| `selector.py` | Picks the next topic (75% adaptive + 25% uniform) and problem |
| `db.py` | SQLite: users, attempts, ratings, problem difficulty |
| `problems.py` | Loads train/val.jsonl plus data/tags.json |
| `hints.py` | The 4-rung hint ladder, leak-checked |
| `server.py` | The web server (stdlib only) + JSON API |
| `static/index.html` | The page: problem, image, 5 certainty sliders, hints, dashboard |
| `build_tags.py` | Tags every problem with a topic using anchor embeddings |
| `smoke.py` | Simulated students that prove the selector adapts |

## Run it

On the laptop for development (uses the stub data until preparation finishes):

```bash
.venv/bin/python -m trainer.server --port 8000
```

Open <http://127.0.0.1:8000>. Then on the board (after `scp -r trainer data`):

```bash
python3 -m trainer.server --host 0.0.0.0
```

Optional extras, when their servers are up:

```bash
# topics for every problem (needs the bge-small server, port 8082)
python3 -m trainer.build_tags --embed-url http://127.0.0.1:8082

# hint rung 1 from real embeddings, rung 3 from the 0.8B model (ports 8081/8082)
# the server picks these up on its own when data/index.db and the ports exist
```

## Test it without a student

```bash
.venv/bin/python -m trainer.smoke
```

Five simulated students, each strong in one topic (80% right) and weak in
another (25%). The checks prove the weak topic gets picked more over time and
ends rated below the strong one.

## The rating model, in one paragraph

Problems start at 800 + 100 per level (grade band 0-7) + 120 per difficulty
(easy / medium / hard, from the exercise number: 1-10, 11-20, 21-30); users
start at 800 per topic. An attempt becomes a score in [0, 1]: correctness
sets the side (right 0.76-1.00, wrong 0.24-0.00) and the certainty slider,
1 to 5, sets how far from the middle. A fast correct answer gains 0.10, a
slow one loses 0.10, and each hint rung used scales the score by 0.85. Both
sides then follow Elo with K = 56 for the user's first 10 attempts in a
topic, then 40, and K = 8 for the problem, so problem difficulty drifts
toward what students make of it. The next topic is chosen with probability
75% softmax(gap to the user's average rating) + 25% uniform, the next
DIFFICULTY follows the topic rating (800 -> easy, ~1160 -> hard, smooth in
between), and the next problem is the one whose rating sits nearest to the
topic rating + 60, never one of the last 20 seen.

## The hint ladder

1. A similar solved problem (embedding neighbour, else same topic at a lower
   level) — its answer stays behind a click.
2. The topic's strategy cue, written by hand, no model.
3. ONE sentence from the model, leak-checked in code: rejected if it contains
   any option value or names the correct letter; falls back to rung 2.
4. The reveal, only when asked for on purpose.
