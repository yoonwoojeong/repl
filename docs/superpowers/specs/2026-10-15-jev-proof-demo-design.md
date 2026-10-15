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

A System One model cannot write a proof script. It **can pick**, which makes it a
policy and value function inside a search loop:

- **State:** the current Lean goal string from the REPL.
- **Choice question `next_tactic`:** options are the candidate tactics generated for
  this state (fixed menu plus `induction <var>` / `cases <var>` for each variable in
  the goal). The model returns a probability per option.
- **Binary question `closes_now`:** the probability that the top tactic closes the
  goal outright. This is the value signal used to order the search frontier.
- **Verifier:** the Lean REPL checks every step, so the model can never produce a
  wrong proof. It can only waste search budget. This is exactly the
  "never hallucinates" property, made literal.

## Lean 4 vs Isabelle/HOL — decision: Lean 4

1. **Step-level JSON interface already exists.** This repo *is* the Lean REPL:
   `proofState` ids, a `goals` list, and `proofStatus`. A System One model needs a
   discrete state → discrete action loop, and the REPL provides it with no extra
   tooling. Isabelle would need the Isabelle server/PIDE plus a custom bridge to get
   per-step goal states.
2. **The action space is a small closed menu.** Core Lean 4.35 has `simp`, `omega`,
   `decide`, `grind`, `rfl`, `induction`, `cases`, `constructor`, and `intro`, which
   is enough for textbook theorems without Mathlib. Isabelle's strength is
   Sledgehammer, a single "solve it" call that would hide the model's contribution
   and make the experiment uninformative.
3. **No Mathlib needed.** Setup is `elan` plus `lake build`, measured in minutes.
   Mathlib or AFP would add gigabytes and long builds for no benefit at this scale.
4. **Where Isabelle would win:** readable Isar proofs and stronger one-shot
   automation. Neither matters for measuring whether a chooser helps.

## The experiment

- **Data:** 30 training theorems with hand-written gold tactic proofs, and 20 held-out
  test theorems. All are core Lean (Nat, List, Prop). The gold proofs are replayed
  through the REPL to get labelled (goal, candidates, chosen tactic) examples.
- **Model:** hashed n-gram features of goal and tactic, a linear scoring head for
  choice (softmax over the candidates supplied), a logistic head for binary, and
  temperature scaling for calibration. NumPy only.
- **Search:** best-first, budget of 64 REPL tactic calls per theorem, max depth 8.
  If the top choice probability is below the confidence threshold τ = 0.5, the
  search widens: it expands all candidates instead of the top k = 3. This is Jev's
  "escalate below threshold".
- **Baselines** (same search, same budget):
  - (a) fixed menu order, no model
  - (b) uniformly random order, seed 0
- **Metrics:** theorems proved out of 20, mean REPL calls per proved theorem, and the
  expected calibration error (ECE, 10 bins) of `next_tactic` on the test-set steps
  where the gold tactic is known.
- **Success criterion:** the model proves at least as many as baseline (a), with
  fewer mean REPL calls. Report honestly either way.
