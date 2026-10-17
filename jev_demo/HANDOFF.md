# Handoff: state of jev_demo (2026-10-17)

Branch `claude/youthful-ptolemy-vxnza1`, draft PR yoonwoojeong/repl#1. This file is for a new
session continuing the work; the README holds the results write-up.

## Rules the user set (keep them)
- Never ask for the API key in chat; never inspect or print credentials.
- **Get budget approval before any API spend.** Never fabricate or estimate a number as if a
  run produced it.
- Pre-register hypotheses in the README before each paid run; report results as computed.
- Use standard benchmarks and metrics, not home-made ones (user's explicit request). Reuse
  standard code where possible instead of building from scratch.
- Compute: CPU only (user's choice). No force-push / history rewrites on the branch.

## Spend so far (actual): $60.67
Phase 2 $7.08; experiment 3 $53.59 (incl. replication $23.25 of an approved $26). Nothing spent
since.

## Where things stand
1. **Experiments 1-3 (core-Lean "corebench", now history per the user):** Jev router saves
   ~49% Claude requests at equal success (independently replicated). README sections up to
   "Replication results".
2. **Switched to standard methods (user request):**
   - Premise retrieval on **LeanDojo Benchmark 4** (Zenodo 10114185), stored compactly in
     `data/standard/`, scored with ReProver's protocol (`jev_demo/reprover_common.py`, vendored
     MIT code; `jev_demo/ld4.py` loads data). Results in `results_free/looped/`:
     novel_premises test R@10: BM25 14.0 (R@1 4.73); tiny CPU neural dual encoders ~5-6
     (same_params 5.66, looped 5.60, same_flops 5.07): looping made no measurable difference at
     this scale, and all neural variants are far below BM25, so the looped-transformer question
     is inconclusive on CPU (`jev_demo/looped.py`, `bm25_baseline.py`).
   - **miniF2F** (yangky11/miniF2F-lean4, Lean v4.24.0 + Mathlib; `jev_demo/minif2f.py`).
     Lean-only valid baselines (`results_free/minif2f/`): single tactics 94/244, menu search
     102/244 (before a loader fix for one problem with a `--` comment; being re-run).
3. **Option 3 (user chose it): miniF2F efficiency run, claude_search vs jev_router on test.**
   Free prep done: Mathlib system prompt (`prompts.MATHLIB_SYSTEM_PROMPT`, examples from valid
   only), BM25-premise steps from the LeanDojo corpus filtered to theorem names that exist in
   the benchmark's Mathlib (`results_free/minif2f/mathlib_theorem_names.txt.gz`, 265,426 names;
   97,656 corpus premises survive), Lean-only `closes` labels for the router from **valid**.
   Paid stages `mf-pilot` / `mf-test` exist in `scripts/exp3_stage.sh` with **placeholder caps
   ($4 / $40) — not approved, not started.**

## In flight
- Job 5 landed (run 39014532633): valid single 94, menu_search 102, jev_search 102 (same
  problems); BM25 steps closed no state the menu could not, so they are **dropped** from the paid
  path (`minif2f.py` claude mode uses the plain menu; router trains on `router_labels.json`,
  menu-tactic labels only). README "miniF2F efficiency run" holds the pre-registration.
- **Free job 6** (`scripts/free_job.sh`): Lean-only `single` / `menu_search` on **test**, as the
  reference for the paid run.
- **Waiting on the user's budget approval** for `mf-pilot` and `mf-test` (caps in
  `scripts/exp3_stage.sh` are still placeholders $4 / $40).

## Next steps
1. Report job 6's test baselines in the README.
2. On approval: set the stage caps to the approved amounts; the user adds the PR label
   `exp3-mf-pilot` (workflow `jev-exp3-live.yml`). Check the pilot's measured cost per request
   and requests per problem; if the projected test cost exceeds the approved test budget, go
   back to the user before `exp3-mf-test`.
3. Score the test run as pre-registered (`replication.saving_ci`, `stats.compare`).
4. README restructure: miniF2F headline, corebench as history; update the PR description.

## Practical notes
- Long runs die if the cloud container idles: run anything long in GitHub Actions (free-job
  workflow), not in the session.
- GitHub logs of a running job are not downloadable; outputs arrive as commits.
- Tests: `cd jev_demo && python -m pytest -q tests` (Lean REPL must be built; torch, networkx,
  bm25s installed for the retrieval tests).
