# Jev proof demo (phase 1)

Can a Jev-style "System One" model help write mathematical proofs? This demo rebuilds
the architecture as a small local NumPy model, uses it as the policy and value function
of a best-first proof search over the Lean 4 REPL in this repository, and compares it
with fixed-order, random and core-Lean automation baselines.

Design: `docs/superpowers/specs/2026-10-15-jev-proof-demo-design.md`.

## What Jev is

TypeSafe AI's Jev is a "System One" model: the caller passes a state and a set of typed
questions (choice / score / yes-no), and Jev answers all of them in one parallel pass,
returning probabilities and a confidence. Its outputs are restricted to the schema and
calibrated, so callers act above a confidence threshold and escalate below it; it does
not generate free text. We rebuild the architecture only, not TypeSafe's product.

## Why Lean 4 (not Isabelle/HOL)

1. **Step-level JSON interface already exists.** This repo is the Lean REPL: `proofState`
   ids, a `goals` list and `proofStatus`. Isabelle would need the Isabelle server/PIDE plus
   a custom bridge to get per-step goal states.
2. **Strong automation in core Lean** (`grind`, `exact?`, `try?`) without Mathlib, so setup
   stays at `elan` plus `lake build`.
3. **Phase 2 (Claude as the tactic generator)** depends on the LLM-prover ecosystem, which is
   mostly Lean. Isabelle's Sledgehammer already has its own learned premise selector, so a
   Jev-style ranker would add less there and be harder to measure.

## Setup

From the repository root:

```sh
curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y --default-toolchain none
~/.elan/bin/lake build                 # builds .lake/build/bin/repl (toolchain from lean-toolchain)
pip install -e 'jev_demo[dev]'         # numpy, pytest
python -m pytest jev_demo -v           # Lean-marked tests skip if the REPL is not built
```

## How to run

```sh
python -m jev_demo run --out jev_demo/results
```

This replays the 40 training gold proofs to build examples, fits the model (calibrating
temperatures on a 20% hold-out, seed 0), runs the six methods on the 20 test theorems,
measures `kind` ECE and premise-shortlist recall on the test gold proofs (measurement only),
and writes `results.json` and `report.md` to the output directory. The premise library is
read from the committed cache `jev_demo/data/library.json`.

## Results

Run: `python -m jev_demo run --out jev_demo/results` (full output in
[`results/report.md`](results/report.md) and [`results/results.json`](results/results.json)).
Test set: 8 easy and 12 hard theorems. Budget 64 REPL calls, depth 8, top-k 3, τ = 0.5,
10 s per call (60 s for `try?`).

| method | proved | easy | hard | mean calls (proved) | mean seconds (proved) |
|---|---|---|---|---|---|
| model | 16/20 | 8/8 | 8/12 | 14.25 | 0.49 |
| model_no_premise | 15/20 | 8/8 | 7/12 | 8.67 | 0.37 |
| fixed | 5/20 | 3/8 | 2/12 | 2.00 | 0.15 |
| random | 9/20 | 6/8 | 3/12 | 1.44 | 0.15 |
| grind_only | 8/20 | 6/8 | 2/12 | 1.00 | 0.18 |
| try_only | 15/20 | 8/8 | 7/12 | 1.00 | 0.90 |

- **Menu reachability** (`data/test_reachability.json`): 10 of the 12 hard theorems (and
  8/8 easy) have a gold proof inside the phase-1 action space; `test_sq_mod_four` and
  `test_rev_eq_reverse` do not. No method proved either of them.
- **ECE** (10 bins) of `kind` on the 52 test gold steps whose kind is in the options: 0.06.
- **Calibrated temperatures** (20% train hold-out): `kind` = 2.3, `premise` = 4.0 (the top
  of the grid; only 2 train premise examples exist, so this value is barely informed).
- **Premise shortlist recall@16**: 0.25 on train (2/8 gold premise steps) and 0.25 on test
  (1/4). Retrieval was frozen before this run (known limitation). No proof found by `model`
  uses a premise template.

Success criterion: met nominally (8 vs 7). On the 12 hard theorems `model` proves 8, and the
best of `fixed` (2), `grind_only` (2) and `try_only` (7) proves 7.

**Caveat.** The planned `fixed` and `random` rankers report confidence
1.0, so the shared best-first search only ever tries their first three actions per state
(`rfl`, `simp`, `simp_all` for `fixed`) and stops after 2-6 calls with most of the budget
unused. After seeing that, we added two supplementary methods (post hoc, not part of the
criterion) whose confidence is their top score (1/n), so the search escalates and expands
the whole menu in fixed or random order:

| method | proved | easy | hard | mean calls (proved) | mean seconds (proved) |
|---|---|---|---|---|---|
| fixed_expand_all | 18/20 | 8/8 | 10/12 | 15.72 | 0.54 |
| random_expand_all | 18/20 | 8/8 | 10/12 | 15.56 | 0.93 |

Both prove 10/12 hard theorems — every menu-reachable one — against the model's 8/12. The
model loses `test_succ_le_two_pow` and `test_two_dvd_mul_succ` (gold: `intro n; induction n <;>
grind`) because it is confident (≥ τ, no escalation) in its top three actions at both states it
expands, none of which leads to a proof, so the search exhausts its frontier after 6 calls with 58 calls of budget unused. On this
test set and budget, a learned ordering of the menu therefore does not beat exhaustive search
over the same menu; its margin over the planned `fixed`/`random` comes largely from
escalating past three actions per state (its uniform-confidence rivals never do), not from
better ranking. The model needs fewer calls than
exhaustive search on some theorems (e.g. `test_map_double_sum` 6 vs 25) and more on others.

**Bottom line:** the criterion was met only nominally. The model does not beat exhaustive
fixed-order search over the same menu (8 vs 10 hard), so this experiment does not show that
the model helps.

Other observations: `try?` in Lean v4.35.0 either closes the goal itself (reporting
`Try these:` suggestions as info) or fails with an error; it never left a goal open with a
suggestion, so the "follow `Try this` once" path of `single_shot` was not exercised in the
run. No REPL call timed out. `model` and `model_no_premise` differ on `test_mul_self_le`
even though the `model` proof (`exact?`) uses no premise: adding the template options
changes the `kind` softmax and hence the ranking and escalation.
