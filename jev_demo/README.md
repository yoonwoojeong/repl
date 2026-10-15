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

Requires Python >= 3.10.

Toolchain fallback: in the dev container elan's release download returned 403, so `lake build`
could not fetch the toolchain. If that happens, download `lean-4.35.0-linux.tar.zst` from the
`leanprover/lean4` GitHub release (v4.35.0), unpack it into `~/.elan/toolchains/` (for example
`~/.elan/toolchains/lean-4.35.0-linux`), and register it with
`~/.elan/bin/elan toolchain link leanprover/lean4:v4.35.0 ~/.elan/toolchains/lean-4.35.0-linux`
(adjust the name to match `lean-toolchain`); then re-run `lake build`. The demo's own
toolchain was installed manually this way.

## Deviations from the design

- Test preludes carry `@[simp]` (ruling R4).
- Test gold proofs were rewritten to menu-only steps where one exists (R7, Task 4 I1); gold
  proofs are never seen by any method.
- "Hard" is qualified: 10 of the 12 hard theorems have a menu proof of at most 3 steps, and
  some close in a single `simp`.
- The calibration hold-out is 20% of the train *examples*, so states from one proof can sit on
  both sides of the split.
- The plan-mandated `eq_` substring filter in `dump_library.lean` also drops legitimate
  lemmas (e.g. `Nat.mul_eq_zero`) while auto-generated `.inj` / `.injEq` / `sizeOf_spec`
  names survive; this is part of the premise-recall limitation.
- The Lean toolchain was installed manually (see Setup).

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

## Phase 2: Claude as a tactic generator

**Status: results pending.** No Anthropic API key was available when this was built, so the
phase-2 experiment has not been run. Everything below is implemented and tested offline with a
fake generator; no phase-2 numbers exist yet, and none are reported here.

### Design

Phase 1 found that a learned ordering of a fixed tactic menu does not beat exhaustive search over
that menu, and that two hard theorems (`menu_reachable = false` in `data/test_reachability.json`)
lie outside the menu. Phase 2 asks whether an LLM that proposes open-ended tactics changes that,
and whether Jev adds anything on top of it. Each method is run on the 20 test theorems:

| method | what it is | question it answers |
|---|---|---|
| `claude_whole` | Claude writes 4 complete tactic scripts per theorem; proved if any passes `check_proof` | How far does Claude get with no search at all? |
| `claude_search` | the phase-1 best-first search, with `HybridRanker(order="llm")`: Claude's proposals first, then the fixed menu; confidence 0 so every action is expanded | What does the search add to Claude, and does Claude reach `menu_reachable = false` theorems? |
| `hybrid` | the same search with `HybridRanker(order="jev")`: Claude's proposals ranked together with the menu by the model, refit on the phase-1 gold replays plus `data/claude_labels.json` | Does Jev's ranking add value on top of Claude (more hard theorems than `claude_search`, at equal or lower USD)? |
| `hybrid_expand_all` | supplementary (ruling P11, not pre-registered): `hybrid` with confidence fixed at 0.0, so every ranked action is expanded (phase-1's expand-all wrapper); its Claude requests are mostly cache hits | Is a `hybrid` result due to Jev's ranking or to confidence gating (which hurt in phase 1)? |
| `phase1_best` | copied from the phase-1 `results/results.json` (best pre-registered method on hard) | Phase-1 reference |
| `phase1_fixed_expand_all` | copied from phase 1; post-hoc, the strongest phase-1 method (10/12 hard) | Phase-1 reference |

`report.md` computes the three pre-registered questions from the results: (1) `hybrid` vs
`claude_search` on hard theorems, (2) their USD, (3) how many `menu_reachable = false` hard
theorems any Claude method proved. Rows carry `claude_requests`, `claude_calls`, `usd`, `notional_usd`, `refusals`, `errors`,
`budget_capped` and `call_capped`.

Cost controls: `--max-usd` (default 10) is a hard cap, after which the generator returns no
proposals and the affected rows are flagged `budget_capped`; responses are cached on disk
(`jev_demo/cache/claude/`, git-ignored), so reruns are free; proposals are generated once per
goal and memoised per theorem; `run-phase2` and `collect` refuse to run unless
`ANTHROPIC_RUN_LIVE=1`. At most 16 Claude requests (cached or not) are made per theorem and method; rows that hit
this are flagged `call_capped`. Since the cache is shared, a later method can reuse proposals
for free, so the report shows both actual USD (billed) and notional USD (every request at its
original price, cached or not); the `hybrid` vs `claude_search` cost question uses notional USD.
An HTTP 400/401/403/404 from the API (bad request, key, permission or model) stops the run at the
first request; 429, 5xx and connection errors are counted as `errors` and yield no proposals.
Every Claude request logs one line to stderr (`cached` or `billed`, USD, `stop_reason`, and the
refusal category from `stop_details` when present). `collect` saves labels after every theorem,
and a proposal that times out is labelled not useful and the gold state re-derived.

### How to run

Run `collect` first (otherwise `hybrid` has no Claude labels), and give `run-phase2` a
`--max-usd 20` budget so the cap is not hit before every method has run:

```sh
export ANTHROPIC_API_KEY=...
export ANTHROPIC_RUN_LIVE=1
# 1. label Claude's proposals on the training gold states -> jev_demo/data/claude_labels.json
python -m jev_demo collect
# 2. run the Claude methods on the test set -> jev_demo/results_phase2/{results.json,report.md}
python -m jev_demo run-phase2 --out jev_demo/results_phase2 --max-usd 20
```

The same two steps can run on GitHub Actions instead (`.github/workflows/jev-phase2-live.yml`),
reading the key from the `ANTHROPIC_API_KEY` repository secret (Settings → Secrets and
variables → Actions). It never runs on push: add the `run-phase2-live` label to a pull request to
run it on that PR's branch, or start it from the Actions tab once the workflow is on the default
branch. It runs the offline tests first, uploads the logs, labels and results as an artifact, and
commits `data/claude_labels.json` and `results_phase2/` back to the branch.

Notes on cost accounting:

- Requests are sent with `fallbacks="default"`; a request served by the fallback model is still
  priced at `claude-opus-5-5` rates, because `usage.iterations` is not read yet (TODO in
  `claude_gen.py`), so USD may be slightly off for those requests.
- The system prompt is close to the 512-token minimum for prompt caching. Check the second
  billed request's log line / `cache_read_tokens` in `claude_usage`: non-zero cache-read tokens
  confirm caching is active.

Both accept `--claude-model` (default `claude-opus-5-5`), `--effort` (`medium`) and `--max-usd`
(`10`). Without `claude_labels.json`, `hybrid` is trained on the phase-1 replays alone.
