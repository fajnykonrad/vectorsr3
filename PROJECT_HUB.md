# BORRADOR — Arduino Project Hub (copy-paste y editar)

Estado: DRAFT. Falta: foto/vídeo de la placa funcionando, el enlace al
repo revisado, y rellenar el número del run oficial cuando la placa esté.

---

## Title

Kangaroo Trainer + Copilot on the Arduino UNO Q: one board that teaches and reasons

## Introduction

Math proficiency in Catalonia is falling, and students practice with
one-size-fits-all worksheets. We built a single-board learning companion on
the Arduino UNO Q that runs entirely offline: it **teaches** with adaptive
practice, per-topic Elo ratings and a leak-checked hint ladder, and it
**reasons** over Kangaroo-style multiple-choice problems with a small LLM
backed by a 1,863-problem retrieval bank built from M3Kang. Nothing leaves
the device.

**Key numbers**: [OFFICIAL RUN NUMBER] accuracy on 562 cat+eng validation
problems in under 60 s each (mean ~12 s); adaptive next-problem selection in
under 1 s; hint rungs 1-2 under 1 s, rung 3 ~4 s with a code-enforced no-leak
check (measured 80% served, 0 leaks on the probe set).

## Components and apps

- Arduino UNO Q (4 GB), USB-C power
- Arduino App Lab (board setup, LED matrix bricks)
- llama.cpp (pinned commit 2cbe0ec) serving:
  - Qwen3.5 0.8B Q8_0 as a chat server on 127.0.0.1:8081
  - bge-small-en-v1.5 Q8_0 as an embedding server on 127.0.0.1:8082
- M3Kang (qualcomm/M3Kang), OCR'd on a laptop with RapidOCR to recover the
  A-E options that only exist in the problem images
- Our team repository: [LINK]

## Architecture

A diagram (to add) and the text version:

```
            +---------------- Arduino UNO Q ----------------+
            |  Linux (QRB2210, 4 GB RAM)                    |
            |  llama-server 8081 (Qwen 0.8B)                |
            |  llama-server 8082 (bge-small embeddings)     |
            |                                               |
  browser ->|  trainer web app  <---->  SQLite (profile,    |
  (student) |  (Elo, hints, dashboard)      ratings, tags)  |
            |        |                                      |
            |  predict.py / eval.py (official Reason path)  |
            |        |                |                     |
            |  data/index.db (1,863 vectors)  data/tags.json|
            |        |                                      |
            |  Bridge -> MCU: LED matrix (verdict, level)   |
            +-----------------------------------------------+
```

- **Teach**: the student answers A-E plus a certainty on a web page served by
  the board. Elo updates both sides (user per topic, problem difficulty), the
  selector picks the next topic 75% adaptively and the next problem nearest
  the target difficulty, and the hint ladder climbs: (1) a similar solved
  problem from the embedding bank, (2) the topic's strategy cue, (3) one
  model sentence that is rejected in code if it leaks the answer, (4) the
  reveal, only on purpose.
- **Reason**: for the official run, `predict.py` answers one letter per
  problem with a grammar (root ::= [A-E]), temperature 0, a fixed seed, a
  60 s per-problem budget and a D fallback.
- **Trained, not fine-tuned**: the board only runs inference. What we trained
  from M3Kang is everything around the model: the retrieval bank (2,600
  problems embedded; 1,863 kept for cat+eng), the topic tags (anchor
  embeddings, one taxonomy for both halves), and a letter-bias correction
  fitted on 4,073 collected signals with a cross-validation gate that ships
  it only where it generalizes.

## Step by step

1. Board bring-up: our `BOARD_CHECKLIST.md` condenses the repository's steps
   0-8 with checks (services systemd on boot, models verified by SHA256).
2. Data: on a laptop, `laptop/prepare_m3kang.py --languages eng,cat`
   (RapidOCR reads the options from the images; cached). Copy train/val to
   the board.
3. Bank: `laptop/build_index_local.py --only-with-options --languages eng,cat`
   builds the same SQLite schema the board expects (bge-small, 384 dims).
4. Signals: `collect.py` records, per training problem, the model's A-E
   log-probabilities and its neighbours' label votes (resumable, tmux).
5. Fit: `fit_model.py --languages eng,cat --margin 2.0` — a multinomial
   logistic fit (6 parameters) with a per-group cross-validation gate that
   writes `data/model.json` with honest held-out metrics.
6. Measure: `eval.py --name <experiment>`; every run lands in
   `results/ablations.csv` with the git commit.
7. Trainer: `python3 -m trainer.server --host 0.0.0.0` on the board; the web
   app, Elo, hints and the LED verdict run from the same servers.

## Results

- Full ablation table on 789 validation problems (see the repository README,
  section "Team results"): raw 22.3%, fusion 21.8%, RAG 22.2%, 5-view
  ensemble 19.5%, 4B 22.5%, 4B+reasoning 11.7%. Always-D floor: 22.7%.
- Official board run (cat+eng, 562 problems): [NUMBER - pending]
- Error analysis by topic, language, level and options: see the repository
  README. Weakest topics: geometry, area_volume. Strongest: numbers.
- What didn't work, measured honestly: the fitted fusion overfit twice (we
  caught it with letter tables and held-out checks, gated it, and finally
  removed it from the default path); RAG examples share topics but not
  answers; prompt-view ensembles fail because the errors are correlated; a
  4B model without reasoning repeats the small model's pattern at twice the
  cost. The conclusion we defend: without weight updates, this class of
  model guesses at the always-D floor, and calibration tricks rearrange the
  guesses.

## What we learned (and what we'd do next)

- Measure everything on the full set: every "gain" we saw on samples of 50
  or 300 evaporated on 789. The letter table (predicted vs true) caught two
  overfits before the validation numbers did.
- The board's real budget is prefill: ~11 tokens/s reading means the prompt,
  not the answer, dominates. Every idea must be priced in tokens first.
- With a GPU, the next step is a LoRA fine-tune of the 0.8B/4B on the 1,863
  cat+eng training problems with options — the only lever that can move the
  model past the guessing floor — then quantize to GGUF and re-verify on the
  board. (We did not have one during the datathon.)
- Cite: M3Kang, Torres-Camps et al., 2026, arXiv:2601.16218 (research-only
  license; we publish no dataset content, only code and derived metrics).

## Team

[roster to fill]
