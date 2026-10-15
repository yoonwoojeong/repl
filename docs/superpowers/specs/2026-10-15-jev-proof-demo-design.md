# Jev Proof Demo — Design

## Question

Can a **Jev-style System One model** help write mathematical proofs? Which proof
assistant should the experiment use: Lean 4 or Isabelle/HOL?

## What "Jev architecture" means here

TypeSafe AI's Jev is a "System One" model. The caller passes a **state** and a set
of **typed questions** (choice / score / yes-no). Jev answers all of them in **one
parallel pass**, returning **probabilities and a confidence**. Its outputs are
restricted to the schema, and it is meant to be calibrated, so callers act above a
confidence threshold and escalate below it. It does not generate free text.
(Sources: InfoQ 2026-10 "typesafe-ai-jev-released"; innFactory model page;
DataCamp "system-one-models-jev".)

We rebuild **the architecture only**, as a small local model. We do not call
TypeSafe's API, and we do not reverse-engineer their product, so the `rea` repo is
not needed.

## Consequence for proving

A System One model cannot write a proof script, but it **can choose**. It acts as
the policy and value function inside a search, and the Lean REPL verifies every
step, so a wrong proof cannot get through. Each proof state is evaluated in one
pass that answers three typed questions:

| Question | Type | Options / meaning |
|---|---|---|
| `kind` | choice | The action menu (below), with premise templates written with a `·` placeholder, e.g. `rw [·]` |
| `premise` | choice | 16 library lemmas shortlisted for this goal (retrieve-then-rank) |
| `near_done` | binary | Is this state at most 2 gold steps from closed? Used as the state value that orders the search frontier |

A concrete action is either a menu item, scored p(kind), or a template filled
with a lemma L, scored p(kind = template) · p(premise = L).

## Action space (phase 1)

- **Basic tactics:** `rfl`, `simp`, `simp_all`, `omega`, `decide`, `constructor`,
  `assumption`, `trivial`, `simp [*] at *`, `intro <binder names>`, `intro h`,
  `induction x <;> simp_all`, `induction x <;> grind`, `cases x`, `cases h`.
- **Core Lean automation (change 1):** `grind` and `exact?`. Both are in core Lean
  4.35, with no Mathlib. `apply?` and `rw?` are left out: they suggest steps without
  reliably changing the goal, so they are not well-defined actions.
- **Premise templates (change 2):** `rw [L]`, `simp [L]`, `grind [L]`, `exact L`,
  `apply L`, where L is drawn from the `premise` shortlist. The shortlist is
  built deterministically: a dump of the Lean library's `Nat`, `List`, `Bool`,
  `And`, `Or` and `Iff` theorems, ranked by IDF-weighted token overlap with the
  goal (in the spirit of the MePo selector). Jev then ranks the shortlist.

## Lean 4 vs Isabelle/HOL — decision: Lean 4

1. **Step-level JSON interface already exists.** This repo *is* the Lean REPL:
   `proofState` ids, a `goals` list, and `proofStatus`. Isabelle would need the
   Isabelle server/PIDE plus a custom bridge to get per-step goal states.
2. **Strong automation in core Lean** (`grind`, `exact?`, `try?`) without Mathlib,
   so setup stays at `elan` plus `lake build`.
3. **Phase 2 (Claude as the tactic generator)** depends on the LLM-prover
   ecosystem, which is mostly Lean. Isabelle's Sledgehammer is more mature than
   LeanHammer, but it already has its own learned premise selector, so a
   Jev-style ranker would add less there and be harder to measure.

## The experiment

- **Data:** 40 training theorems: 30 textbook theorems, plus 10 that need a premise
  lemma or multi-step induction. All training gold proofs use only phase-1
  actions. The 20 test theorems are 8 textbook and 12 hard (listed in the plan).
  Every test theorem has a checked gold proof, but hard ones may use tactics
  outside the action space. Those are flagged `menu_reachable = false`; they
  measure the ceiling and are the targets for phase 2.
- **Model:** hashed n-gram features with a linear scoring head per choice question
  (softmax over the supplied options), a logistic head for binary, and temperature
  scaling for calibration. NumPy only.
- **Search:** best-first, budget of 64 REPL tactic calls per theorem, max depth 8,
  top-k = 3, confidence threshold τ = 0.5 (below it, expand all candidates). The
  per-call timeout is 10 s.
- **Baselines (change 1):** each gets the same budget and timeout where it applies.
  - `fixed`: the same search, with the menu in fixed order and no premise templates.
  - `random`: the same search, in uniformly random order (seed 0).
  - `grind_only`: a single `grind` call.
  - `try_only`: a single `try?` call with a 60 s timeout.
  - `model_no_premise` (ablation): the model without premise templates.
- **Metrics:** for each method, theorems proved (overall, and easy vs hard), mean
  REPL calls and mean wall-clock seconds per proved theorem. Also reported: ECE (10
  bins) of `kind` on test gold steps, and shortlist recall (the fraction of gold
  premise steps whose lemma is in the top 16).
- **Success criterion:** on the 12 hard test theorems, `model` proves strictly more
  than the best of `fixed`, `grind_only` and `try_only`. Report honestly either way.

## Phase 2 (separate plan)

Claude proposes open-ended tactics and `have` subgoals for each state, and the
Jev-style model ranks Claude's proposals together with the phase-1 actions. See
`docs/superpowers/plans/2026-10-15-jev-proof-demo-phase2.md`.
