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

**Status: run once live (2026-10-15).** See [Phase 2 results](#phase-2-results) below.

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

### Phase 2 results

Run once, live, on GitHub Actions (run `38741999437`, workflow `jev-phase2-live.yml`) with
`claude-opus-5-5` at effort `medium` and a `--max-usd 20` cap, after the prompt's worked examples
were relabelled as good next steps. Outputs: `data/claude_labels.json`,
`results_phase2/{results.json,report.md}`, and the raw stderr logs `results_phase2/collect.log`
and `results_phase2/run-phase2.log`. No refusals; no budget or per-theorem request cap was hit.

| method | proved | easy | hard | mean calls (proved) | Claude requests | billed calls | USD (actual) | USD (notional) | refusals | errors |
|---|---|---|---|---|---|---|---|---|---|---|
| claude_whole | 20/20 | 8/8 | 12/12 | 1.00 | 80 | 80 | 0.6792 | 0.6792 | 0 | 0 |
| claude_search | 20/20 | 8/8 | 12/12 | 2.05 | 27 | 27 | 0.3118 | 0.3118 | 0 | 0 |
| hybrid | 20/20 | 8/8 | 12/12 | 4.05 | 43 | 19 | 0.2448 | 0.5300 | 0 | 0 |
| phase1_best (`model`, phase-1 reference) | 16/20 | 8/8 | 8/12 | 14.25 | – | – | – | – | – | – |
| phase1_fixed_expand_all (phase-1 post-hoc reference) | 18/20 | 8/8 | 10/12 | 15.72 | – | – | – | – | – | – |
| *supplementary:* hybrid_expand_all (not pre-registered) | 19/20 | 8/8 | 11/12 | 1.90 | 44 | 0 | 0.0000 | 0.5388 | 0 | 0 |

`hybrid_expand_all` is supplementary (ruling P11): `hybrid` with confidence fixed at 0.0, so it
expands every ranked action. All of its Claude requests were response-cache hits from the earlier
methods, so its actual USD is 0 and only its notional USD is meaningful. It missed
`test_rev_eq_reverse`, which `hybrid` proved only after 45 calls.

**Cost.** `run-phase2`: $1.2358 actual, $2.0597 notional (126 billed of 194 requests).
`collect`: $1.2296 actual (= notional; 105 billed requests, one of which hit `max_tokens`, cost
$0.3268 and is counted as an error). Total actual spend: **$2.4654**.

**Prompt caching.** Active, but only for byte-identical requests. In `run-phase2`, the second
billed request read 1352 cached tokens. 60 of 126 billed requests read the cache (1352–1433
tokens each), all in groups of three, which matches `claude_whole`'s 4 samples of the same
prompt. The other 66, and every one of `collect`'s 105 requests (cache_write 142,284 tokens,
cache_read 0), read nothing. So the shared system prompt is not being reused across different
goals. The likely cause is that the top-level `cache_control` places the breakpoint after the
user message, so a cache entry is only ever written for the whole prefix. Putting the breakpoint
on the system block instead would probably fix it; this run did not test that.

**Pre-registered questions**

1. *Does `hybrid` prove more hard theorems than `claude_search`?* **No.** Both prove 12/12. Every
   Claude method proved every test theorem, so this test set cannot separate them (ceiling effect).
2. *At equal or lower notional USD?* **No.** `hybrid` cost $0.5300 notional vs $0.3118 for
   `claude_search`, and used more search calls on average (4.05 vs 2.05). Its lower actual USD
   ($0.2448) comes from response-cache hits on proposals that `claude_search` had already paid for,
   not from the method itself.
3. *Did a Claude method prove the two hard theorems whose gold proof lies outside the phase-1 menu?*
   **Yes, 2/2.** `test_sq_mod_four` and `test_rev_eq_reverse` were each proved by `claude_whole`,
   `claude_search` and `hybrid`. No phase-1 method proved either.

**Conclusion.** This experiment does not show that the Jev-style ranking model adds value on top of
Claude. `hybrid` proved no more theorems than `claude_search` and cost more (notional). Claude on
its own closes every test theorem, including the two the phase-1 menu cannot reach, mostly in one
or two calls. A harder test set would be needed to measure any benefit from the ranking.

### Phase 2b: harder test set (written before the live run)

Every Claude method proved all 20 theorems in `data/test.json`, so the first run could not tell
the methods apart. Phase 2b reruns `run-phase2` on a new, harder test set,
`data/test_hard.json`. This section was committed before any Claude request was made on that
set.

**How the set was built.**
- 20 theorems, all `hard`, written for this round.
- Statements and names are disjoint from `train.json` and `test.json`.
- Each has a gold proof checked in Lean (`test_hard_gold_proofs_check_and_flags_current`).
- Topics:
  - accumulator recursions that need a generalised lemma (`sumAcc`, `prodAcc`, `revAcc`, fast
    `fibAux`);
  - insertion sort (length, sortedness, idempotence, element counts);
  - correctness of a stack-machine compiler;
  - Fibonacci identities (coprimality, the addition formula, `fib n < 2^n`);
  - Ackermann inequalities;
  - nonlinear arithmetic (sum of cubes, `6 ∣ n(n+1)(n+2)`, `n² ≤ 2ⁿ` for `n ≥ 4`);
  - strong induction (`isEven`).

**Screen.** 32 candidates were written. Any candidate closed on its own by a generic one-liner
was dropped, which removed 12 and left exactly 20. The one-liners tried were `grind`,
`simp_all`, `omega`, `decide`, `intros; simp_all`, `intros; grind`, and
`intro …; induction x <;> simp_all [defs] <;> omega` or `… <;> grind [defs]` for every bound
variable `x`, where `defs` are the definitions in the prelude. No Claude API call was used to
choose or screen theorems.

The theorems were written by a Claude model in a Claude Code session, and several are textbook
exercises. Claude may therefore find them easier than unseen problems would be.

**Menu reachability.** All 20 are `menu_reachable = false`. Every gold proof uses structured
`induction … with` blocks or `have` lemmas, which are not phase-1 menu actions. So question 3
below covers the whole set. The flag says only that the written gold proof is outside the menu,
not that no menu path exists.

**Phase-1 reference on this set** (run locally, free; `results_hard/`):

| method | hard proved |
|---|---|
| try_only | 5/20 |
| model | 1/20 |
| model_no_premise | 1/20 |
| fixed_expand_all (post hoc) | 1/20 |
| random_expand_all (post hoc) | 1/20 |
| fixed, random, grind_only | 0/20 |

`try_only` is the best pre-registered phase-1 method here, so it is the `phase1_best` reference
row.

**Settings, unchanged from the first run.**
- `claude-opus-5-5`, effort `medium`, `--max-usd 20`, at most 16 Claude requests per theorem
  and method.
- The same prompt, and the same `hybrid` refit on the phase-1 replays plus the
  `data/claude_labels.json` from run 38741999437. `collect` is not rerun.
- The run starts on GitHub Actions with
  `run-phase2 --test jev_demo/data/test_hard.json --phase1 jev_demo/results_hard/results.json
  --out jev_demo/results_phase2_hard`.

**Questions** (the same three, computed by `phase2_questions`):
1. Does `hybrid` prove more hard theorems than `claude_search`?
2. Does it do so at equal or lower notional USD?
3. How many of the 20 `menu_reachable = false` hard theorems does any Claude method prove?

The answers will be reported as computed, including when `hybrid` does not beat
`claude_search`.

### Phase 2b results

From GitHub Actions run `38747209836` on `data/test_hard.json` (`results_phase2_hard/`, raw log
`results_phase2_hard/run-phase2.log`). `collect` was skipped and the existing labels were reused.
There were no errors or refusals, and neither the budget nor the per-theorem request cap was
hit.

| method | hard proved | mean calls (proved) | Claude requests | billed calls | USD (actual) | USD (notional) |
|---|---|---|---|---|---|---|
| claude_whole | 17/20 | 1.41 | 80 | 80 | 2.3547 | 2.3547 |
| claude_search | 16/20 | 10.62 | 79 | 79 | 1.5316 | 1.5316 |
| hybrid | 11/20 | 7.64 | 81 | 27 | 0.5314 | 1.6740 |
| phase1_best (`try_only`, phase-1 reference) | 5/20 | 1.00 | – | – | – | – |
| phase1_fixed_expand_all (phase-1 post-hoc reference) | 1/20 | 36.00 | – | – | – | – |
| *supplementary:* hybrid_expand_all (not pre-registered) | 10/20 | 11.20 | 90 | 19 | 0.1968 | 1.5646 |

**Cost.** $4.6144 actual and $7.1249 notional (205 billed of 330 requests). Including the first
run ($2.4654), total actual spend on Phase 2 is $7.0798. In this run the second billed request
read 1429 cached tokens. Caching shows the same pattern as before: reads come only from repeated
identical prompts (86,904 cache-read tokens, 211,987 cache-write tokens).

**Pre-registered questions**

1. *Does `hybrid` prove more hard theorems than `claude_search`?* **No.** `hybrid` proved 11/20 and
   `claude_search` 16/20. This time the set is hard enough to separate the methods, and `hybrid`
   is clearly worse. It lost `h2_sum_acc`, `h2_isort_length`, `h2_rev2_append`, `h2_prod_acc` and
   `h2_fast_fib`, which `claude_search` proved, and it proved nothing that `claude_search` missed.
   The supplementary `hybrid_expand_all` (10/20) does no better, so the gap is not explained by
   confidence gating alone. The Jev ranking itself puts Claude's useful proposals too low on this
   set.
2. *At equal or lower notional USD?* **No.** `hybrid` cost $1.6740 notional against $1.5316 for
   `claude_search`. Its lower actual USD ($0.5314) again comes from response-cache hits on
   proposals that the earlier methods had already paid for.
3. *How many of the 20 menu-unreachable hard theorems did any Claude method prove?* **19/20.** Only
   `h2_sq_le_two_pow` (`n² ≤ 2ⁿ` for `n ≥ 4`) was proved by no method. Phase-1 methods proved at
   most 5 of the 20 (`try_only`).

Not pre-registered, but visible in the table: `claude_whole` was the strongest method (17/20,
about 1.4 whole-script attempts per proved theorem). It was the only method to prove
`h2_isort_sorted`, `h2_ack_succ` and `h2_isort_idem`, the three theorems whose gold proofs need two
or more auxiliary lemmas.

**Conclusion.** On a test set hard enough to separate the methods, adding the Jev-style ranking
model on top of Claude made the step-by-step search worse (11/20 vs 16/20) and did not make it
cheaper. This experiment does not show that the Jev-style model adds value on top of Claude.
Claude's own proposals, and especially its complete proof scripts, do most of the work. Caveats:
there is one run per method (no repeated samples), the set has only 20 theorems, and the
theorems were written by a Claude model.
