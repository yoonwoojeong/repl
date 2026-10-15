# Jev Proof Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small Jev-style System One model that ranks Lean tactics, put it inside a best-first prover that uses this repo's Lean REPL as the checker, and measure whether it beats model-free baselines on 20 held-out textbook theorems.

**Architecture:** A Python package `jev_demo/` sits beside the Lean REPL. `repl_client` drives `lake exe repl` over JSON. `schema` defines the typed questions and answers. `model` is the System One model: one pass, typed probabilistic answers, temperature-calibrated. `candidates` builds each state's tactic menu. `search` is best-first with escalation below a confidence threshold. `data` replays the gold proofs into training examples. `bench` runs the experiment and writes a report.

**Tech Stack:** Lean 4 v4.35.0 (this repo's REPL, core Lean only, no Mathlib), Python ≥ 3.11, NumPy, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-jev-proof-demo-design.md`

## Global Constraints

- Lean toolchain: `leanprover/lean4:v4.35.0` (from `lean-toolchain`). No Mathlib, no new Lean dependencies.
- Do not modify the REPL's Lean sources (`REPL/`, `REPL.lean`, `Test.lean`, `test/`).
- Python dependencies are limited to `numpy` (runtime) and `pytest` (dev), declared in `jev_demo/pyproject.toml`.
- The model's answers must only contain options supplied in the question. Each choice distribution sums to 1 within 1e-6.
- A proof counts as proved only when the REPL returns `"proofStatus": "Completed"` with no `severity: "error"` message, **and** the assembled tactic script re-checks in command mode with no errors and no `sorries`.
- Search budget: 64 REPL tactic calls per theorem, max depth 8, top-k = 3, confidence threshold τ = 0.5.
- Data split: 30 train theorems, 20 test theorems. Test theorems are never used for training or calibration.
- Feature hashing dimension 2^16. RNG seed 0 everywhere.
- Integration tests that need a built REPL are marked `@pytest.mark.lean` and skipped when `.lake/build/bin/repl` is missing.

## Review Focus

1. **A failing tactic reports `goals: []`.** The REPL returns empty goals plus an error and `proofStatus: "Incomplete: contains sorry"` (see `test/invalid_tactic.expected.out`). Expected: this is treated as a failure, never as a closed goal. Pinned in Task 1 and Task 5.
2. **A non-terminating or slow tactic, such as `simp` looping or `decide` on a large Nat.** Expected: a per-call timeout (10 s) kills and restarts the REPL, the call counts as failed and against the budget, and the search continues. Pinned in Task 1.
3. **Candidate options never seen in training**, such as `induction l` where training only saw `induction n`. Expected: a valid distribution over exactly the supplied options, with no crash and no missing keys. Pinned in Task 3.
4. **Search revisits the same goal through different tactic orders**, for example `intro` followed by `simp` versus `simp` followed by `intro`. Expected: states are deduped by their normalized goal string, so the budget is not burned in cycles. Pinned in Task 5.
5. **The model's top answer is confident but wrong.** Expected: the confidence comes from calibrated probabilities. Escalation (expand all candidates when top probability < τ) is observable in the search trace, and ECE is reported. Pinned in Task 3 (calibration) and Task 5 (escalation).

---

### Task 1: REPL client

**Files:**
- Create: `jev_demo/pyproject.toml`, `jev_demo/jev_demo/__init__.py`, `jev_demo/jev_demo/repl_client.py`
- Test: `jev_demo/tests/test_repl_client.py`, `jev_demo/tests/conftest.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class TacticResult: proof_state: int | None; goals: list[str]; ok: bool; completed: bool; error: str | None`
  - `class ReplClient: __init__(self, repl_path: str = ".lake/build/bin/repl", cwd: str = <repo root>, timeout_s: float = 10.0)`, `command(self, cmd: str, env: int | None = None) -> dict`, `start_theorem(self, statement: str, prelude: str = "") -> tuple[int, str]` (returns `(proof_state, goal)` from the single `sorry` in `theorem t : <statement> := by sorry`), `tactic(self, tac: str, proof_state: int) -> TacticResult`, `check_proof(self, statement: str, tactics: list[str], prelude: str = "") -> bool`, `close(self)`; also usable as a context manager.
  - `ok` is True iff the result has no `severity == "error"` message. `completed` is True iff `ok` and `proofStatus == "Completed"`.

- [ ] **Step 1: Set up the environment.** Install elan non-interactively (`curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y --default-toolchain none`), then run `lake build` in the repo root. Expected: `.lake/build/bin/repl` exists. Create `pyproject.toml` (package `jev_demo`, deps `numpy`, dev dep `pytest`, register the `lean` marker) and run `pip install -e 'jev_demo[dev]'`.
- [ ] **Step 2: Write the failing tests.** In `conftest.py`, add a session-scoped fixture `repl` that skips if the binary is missing.

```python
@pytest.mark.lean
def test_closing_tactic_is_completed(repl):
    ps, goal = repl.start_theorem("∀ n : Nat, n + 0 = n")
    assert "⊢" in goal
    r = repl.tactic("intro n; simp", ps)
    assert r.ok and r.completed and r.goals == []

@pytest.mark.lean
def test_invalid_tactic_is_failure_even_with_empty_goals(repl):
    ps, _ = repl.start_theorem("∀ x : Nat, x = x")
    r = repl.tactic("exact my_fake_premise", ps)
    assert not r.ok and not r.completed and "my_fake_premise" in r.error

@pytest.mark.lean
def test_partial_progress_is_ok_not_completed(repl):
    ps, _ = repl.start_theorem("∀ p q : Prop, p ∧ q → q ∧ p")
    r = repl.tactic("intro p q h", ps)
    assert r.ok and not r.completed and len(r.goals) == 1

@pytest.mark.lean
def test_timeout_restarts_and_reports_failure():
    with ReplClient(timeout_s=0.5) as c:
        ps, _ = c.start_theorem("2 ^ 200000 % 7 = 2 ^ 200000 % 7 + 0")
        r = c.tactic("decide", ps)
        assert not r.ok and "timeout" in r.error
        ps2, _ = c.start_theorem("1 = 1")       # client still usable
        assert c.tactic("rfl", ps2).completed

@pytest.mark.lean
def test_check_proof_rechecks_whole_script(repl):
    assert repl.check_proof("∀ n : Nat, 0 + n = n", ["intro n", "simp"])
    assert not repl.check_proof("∀ n : Nat, 0 + n = n", ["intro n"])
```

- [ ] **Step 3: Run the tests.** `pytest jev_demo/tests/test_repl_client.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 4: Implement `ReplClient`.** Write each request as one JSON line followed by a blank line. Read stdout until a blank line and parse that block. Use a reader thread plus a queue to enforce `timeout_s`. On timeout, kill the process, start a fresh one, and return `TacticResult(ok=False, error="timeout", ...)`. Proof-state ids from the dead process are invalid after a restart, so `tactic` on such an id must return `ok=False` rather than crash. `check_proof` runs `theorem t : <stmt> := by\n  <tac1>\n  <tac2>…` in command mode and passes iff there are no error messages and no `sorries`.
- [ ] **Step 5: Run the tests.** Expected: all 5 pass.
- [ ] **Step 6: Commit.** `git commit -m "feat(jev_demo): JSON client for the Lean REPL"`

### Task 2: Typed question schema

**Files:**
- Create: `jev_demo/jev_demo/schema.py`
- Test: `jev_demo/tests/test_schema.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class ChoiceQuestion: name: str; options: tuple[str, ...]` (non-empty and unique, else `ValueError`)
  - `@dataclass(frozen=True) class BinaryQuestion: name: str`
  - `@dataclass(frozen=True) class ChoiceAnswer: probs: dict[str, float]` with property `top -> str` and property `confidence -> float` (the max probability)
  - `@dataclass(frozen=True) class BinaryAnswer: p_true: float`
  - `Question = ChoiceQuestion | BinaryQuestion`, `Answer = ChoiceAnswer | BinaryAnswer`
  - `validate(question: Question, answer: Answer) -> None`, which raises `ValueError` on a key mismatch, a probability outside [0, 1], or a sum ≠ 1 ± 1e-6

- [ ] **Step 1: Write the failing tests.** `test_choice_rejects_duplicate_options`, `test_choice_rejects_empty`, `test_validate_rejects_extra_option` (answer has key "x" not in options), `test_validate_rejects_bad_sum` ({a: .6, b: .6}), `test_top_and_confidence` ({a: .2, b: .8} → top "b", confidence .8), `test_binary_range` (p_true 1.2 → ValueError).
- [ ] **Step 2: Run** `pytest jev_demo/tests/test_schema.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the dataclasses and `validate` in `schema.py`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(jev_demo): typed question/answer schema"`

### Task 3: System One model

**Files:**
- Create: `jev_demo/jev_demo/model.py`
- Test: `jev_demo/tests/test_model.py`

**Interfaces:**
- Consumes: `schema.*` (Task 2)
- Produces:
  - `featurize(state: str, option: str | None = None, dim: int = 2**16) -> dict[int, float]`: sparse hashed features. These are word unigrams and bigrams of the goal (whitespace tokenized after splitting on `( ) , : ⊢`), the option's head token and full text, and the cross features `head(option) × each goal token`. Use `zlib.crc32` for the hash so it is stable across runs, not Python's `hash`.
  - `@dataclass class ChoiceExample: state: str; options: tuple[str, ...]; gold: str`
  - `@dataclass class BinaryExample: state: str; option: str; label: bool`
  - `class SystemOneModel: __init__(self, dim: int = 2**16, seed: int = 0)`, `fit(self, choice: list[ChoiceExample], binary: list[BinaryExample], epochs: int = 30, lr: float = 0.1, l2: float = 1e-4) -> None`, `calibrate(self, choice: list[ChoiceExample]) -> float` (fits the temperature T on held-out examples by grid search over [0.25, 4] in steps of 0.05, minimizing NLL, and returns T), `evaluate(self, state: str, questions: list[Question], context: dict[str, str] | None = None) -> dict[str, Answer]`, `save(self, path: str)`, `load(cls, path: str) -> SystemOneModel`
  - In `evaluate`, choice answers are `softmax(w·featurize(state, opt) / T)` over exactly the question's options. A `BinaryQuestion` is scored against `context[q.name]` (the option being judged) as `sigmoid(v·featurize(state, option))`. Every answer passes `schema.validate`.
  - `expected_calibration_error(model, choice: list[ChoiceExample], bins: int = 10) -> float`

- [ ] **Step 1: Write the failing tests.**

```python
def test_answers_cover_exactly_supplied_options_even_unseen():
    m = SystemOneModel(); m.fit([ChoiceExample("⊢ a = a", ("rfl", "simp"), "rfl")], [], epochs=5)
    q = ChoiceQuestion("next_tactic", ("induction l", "omega", "rfl"))
    a = m.evaluate("l : List Nat ⊢ l ++ [] = l", [q])["next_tactic"]
    assert set(a.probs) == set(q.options); validate(q, a)

def test_learns_separable_choice():
    data = [ChoiceExample(f"n : Nat ⊢ n + {i} = {i} + n", ("omega", "rfl"), "omega") for i in range(20)] + \
           [ChoiceExample(f"⊢ x{i} = x{i}", ("omega", "rfl"), "rfl") for i in range(20)]
    m = SystemOneModel(); m.fit(data, [], epochs=30)
    assert m.evaluate("n : Nat ⊢ n + 99 = 99 + n", [ChoiceQuestion("t", ("omega", "rfl"))])["t"].top == "omega"

def test_one_pass_answers_choice_and_binary():
    # one evaluate call returns both answers; binary uses context
    ...  # assert keys {"next_tactic", "closes_now"} and 0 <= p_true <= 1

def test_calibration_temperature_reduces_nll(): ...   # nll after calibrate <= nll before, on a deliberately overconfident model (w scaled ×10)
def test_featurize_is_deterministic(): ...            # same input -> same dict, across two calls
def test_save_load_roundtrip(tmp_path): ...           # identical probs after load
```

- [ ] **Step 2: Run** `pytest jev_demo/tests/test_model.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Use one weight vector `w` for the choice head (a conditional-logit or listwise softmax over options) and one `v` for the binary head. Train with plain SGD over sparse dicts, shuffled with `numpy.random.default_rng(seed)`. Save with `numpy.savez` (w, v, T, dim).
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(jev_demo): System One model with typed answers and calibration"`

### Task 4: Candidate tactics and theorem sets

**Files:**
- Create: `jev_demo/jev_demo/candidates.py`, `jev_demo/data/train.json`, `jev_demo/data/test.json`, `jev_demo/jev_demo/theorems.py`
- Test: `jev_demo/tests/test_candidates.py`, `jev_demo/tests/test_theorems.py`

**Interfaces:**
- Produces:
  - `FIXED_MENU: tuple[str, ...] = ("rfl", "simp", "simp_all", "omega", "decide", "grind", "intro", "constructor", "assumption", "trivial", "simp [*] at *")`
  - `candidates(goal: str) -> tuple[str, ...]` returns, in this order:
    - `FIXED_MENU`.
    - If the target starts with `∀ x y … : T,` or `∀ (x : T) (y : U),`, the tactic `intro x y …` using the binder names. Plain `intro` would leave inaccessible `x✝` names that later tactics cannot mention.
    - If the target is an implication, `intro h` (or `h1` if `h` is taken).
    - For each hypothesis `x : Nat` or `x : List _` in the goal context: `induction x <;> simp_all`, `induction x <;> grind` and `cases x`.
    - For each `h : _ ∨ _`: `cases h`.

    The result is deduplicated, order-stable, and never empty.
  - `@dataclass(frozen=True) class Theorem: name: str; statement: str; prelude: str; gold: tuple[str, ...]`
  - `load_theorems(path: str) -> list[Theorem]`. The JSON is a list of `{name, statement, prelude, gold}`.

- [ ] **Step 1: Write `test.json` with exactly these 20 statements.** `prelude` defaults to `""`. Every gold step must be a member of `candidates(goal_at_that_step)`, so a perfect chooser can reproduce it.
  1. `∀ n : Nat, 0 + n = n`
  2. `∀ n m : Nat, n + m = m + n`
  3. `∀ a b c : Nat, a + b + c = a + (b + c)`
  4. `∀ n : Nat, n * 1 = n`
  5. `∀ n : Nat, 2 * n = n + n`
  6. `∀ l : List Nat, l ++ [] = l`
  7. `∀ l : List Nat, [] ++ l = l`
  8. `∀ l₁ l₂ : List Nat, (l₁ ++ l₂).length = l₁.length + l₂.length`
  9. `∀ l : List Nat, l.reverse.reverse = l`
  10. `∀ l : List Nat, l.map id = l`
  11. `∀ n : Nat, n < n + 1`
  12. `∀ a b : Nat, a ≤ a + b`
  13. `∀ n : Nat, n % 2 = 0 ∨ n % 2 = 1`
  14. `∀ p q : Prop, p ∧ q → q ∧ p`
  15. `∀ p q : Prop, p ∨ q → q ∨ p`
  16. `∀ a b : Nat, a + b = 0 → a = 0`
  17. `∀ n : Nat, double n = 2 * n`, with prelude `def double : Nat → Nat | 0 => 0 | n+1 => double n + 2`
  18. `∀ n : Nat, sumTo n * 2 = n * (n + 1)`, with prelude `def sumTo : Nat → Nat | 0 => 0 | n+1 => sumTo n + (n+1)`
  19. `∀ l : List Nat, (l.map (· + 0)) = l`
  20. `∀ (l : List Nat) (x : Nat), (x :: l).length = l.length + 1`
- [ ] **Step 2: Write `train.json` with 30 theorems** in the same categories, none textually equal to a test statement. Use 10 Nat arithmetic, 8 List, 6 propositional logic, and 6 recursive-def induction (each with its own prelude def, such as `triple`, `len'`, `pow2`).
- [ ] **Step 3: Write the failing tests.** `test_menu_always_present`; `test_intro_uses_binder_names` (`"⊢ ∀ (l₁ l₂ : List Nat), …"` → contains `"intro l₁ l₂"`); `test_intro_h_for_implication` (`"a b : Nat\n⊢ a + b = 0 → a = 0"` → contains `"intro h"`); `test_induction_offered_for_nat_and_list_hyps` (goal `"n : Nat\nl : List Nat\n⊢ …"` → contains `"induction n <;> simp_all"`, `"induction n <;> grind"` and `"induction l <;> simp_all"`); `test_cases_offered_for_or_hyp`; `test_no_duplicates`. Lean-marked tests: `test_every_gold_proof_checks` (for both files, `repl.check_proof(t.statement, list(t.gold), t.prelude)`), and `test_every_gold_step_is_a_candidate` (replay each gold proof in tactic mode and assert each step ∈ `candidates(current_goal)`). Also add `test_splits_disjoint`.
- [ ] **Step 4: Run** `pytest jev_demo/tests/test_candidates.py jev_demo/tests/test_theorems.py -v`. Expected: FAIL.
- [ ] **Step 5: Implement** `candidates` by parsing hypothesis lines (`name : Type`) before `⊢`. Handle multi-name lines such as `a b : Nat` and multiple goals (use only the first goal's context). Implement `load_theorems`.
- [ ] **Step 6: Run.** Expected: PASS. If a gold proof does not check in core Lean 4.35, fix the gold proof. Do not change the statement unless no menu-only proof exists; in that case replace it with another theorem of the same category and note the swap in the commit message.
- [ ] **Step 7: Commit.** `git commit -m "feat(jev_demo): tactic candidates and train/test theorem sets"`

### Task 5: Best-first search with escalation

**Files:**
- Create: `jev_demo/jev_demo/search.py`
- Test: `jev_demo/tests/test_search.py`

**Interfaces:**
- Consumes: `ReplClient`, `TacticResult` (Task 1); `SystemOneModel.evaluate`, `ChoiceQuestion`, `BinaryQuestion` (Tasks 2–3); `candidates`, `Theorem` (Task 4)
- Produces:
  - `class Ranker(Protocol): def rank(self, goal: str, options: tuple[str, ...]) -> tuple[list[tuple[str, float]], float]`. It returns options with priority scores in descending order, plus a confidence.
  - `ModelRanker(model)`: makes one `evaluate` call with `ChoiceQuestion("next_tactic", options)` and `BinaryQuestion("closes_now")`, where the context is the top option. The score is the choice probability, the confidence is the top probability, and the frontier priority is the parent's log-probability plus log(p) + log(closes_now + 1e-3) for the top child.
  - `FixedOrderRanker()`: menu order, uniform scores, confidence 1.0, so it never escalates.
  - `RandomRanker(seed=0)`: a shuffled order with uniform scores and confidence 1.0.
  - `@dataclass class SearchResult: proved: bool; tactics: list[str]; calls: int; escalations: int; trace: list[dict]`
  - `prove(thm: Theorem, repl: ReplClient, ranker: Ranker, budget: int = 64, max_depth: int = 8, top_k: int = 3, tau: float = 0.5) -> SearchResult`

- [ ] **Step 1: Write the failing tests.** Use a `FakeRepl` stub with the same methods as `ReplClient`, scripted by a dict mapping `(goal, tactic)` to a `TacticResult`.
  - `test_fixed_order_proves_one_step`
  - `test_error_with_empty_goals_is_not_success`: a scripted `ok=False, goals=[]` result must not end the search as proved.
  - `test_dedup_same_goal_reached_twice`: two paths reach goal "G2", which is expanded only once (assert the count in the trace).
  - `test_budget_exhaustion_returns_unproved`: `calls == budget`.
  - `test_escalation_expands_all_when_low_confidence`: a stub ranker with confidence 0.3 makes every candidate get tried, and `escalations == 1`.
  - `test_high_confidence_expands_top_k_only`
  - `test_final_proof_rechecked`: `check_proof` is called once on success. If it returns False, `proved` is False.
  - Lean-marked: `test_model_free_proves_trivial_real_theorem` (`∀ n : Nat, n + 0 = n` with `FixedOrderRanker`).
- [ ] **Step 2: Run** `pytest jev_demo/tests/test_search.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `prove`.** Use a `heapq` priority frontier of nodes (priority, proof_state, goal, tactics so far). Pop a node, rank `candidates(goal)`, and expand the top `top_k` (or all of them if confidence < τ, incrementing `escalations`). A child with `completed` triggers `check_proof`, and the search stops if it passes. A child with `ok` and goals pushes the child keyed on the normalized first goal (whitespace collapsed); already-seen keys are skipped. Every `tactic` call counts against the budget. Append `{goal, options, chosen, confidence, outcome}` to `trace`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(jev_demo): best-first prover with confidence escalation"`

### Task 6: Training data from gold proofs, plus the benchmark CLI

**Files:**
- Create: `jev_demo/jev_demo/data.py`, `jev_demo/jev_demo/bench.py`, `jev_demo/jev_demo/__main__.py`, `jev_demo/README.md`
- Test: `jev_demo/tests/test_data.py`, `jev_demo/tests/test_bench.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `replay(thm: Theorem, repl: ReplClient) -> tuple[list[ChoiceExample], list[BinaryExample]]`. For each gold step, this yields a `ChoiceExample(goal, candidates(goal), gold_step)`. For each candidate it actually tries at that state, it yields a `BinaryExample(goal, cand, completed)`, so every candidate is run once per gold state.
  - `run_experiment(repl: ReplClient, train: list[Theorem], test: list[Theorem], out_dir: str) -> dict`. It trains on train replays and calibrates on a 20% hold-out of the train choice examples (rng seed 0). It then runs `prove` on each test theorem with `ModelRanker`, `FixedOrderRanker` and `RandomRanker`, and computes the test-step ECE from test gold replays (used only for measurement). It writes `results.json` and `report.md` to `out_dir`, and returns a dict with keys `{"model","fixed","random"}`, each holding `{"proved": int, "mean_calls": float, "per_theorem": [...]}`, plus `"ece": float` and `"temperature": float`.
  - The CLI runs as `python -m jev_demo run --out jev_demo/results` from the repo root.

- [ ] **Step 1: Write the failing tests.**
  - `test_replay_labels_gold_as_chosen` (FakeRepl)
  - `test_replay_binary_label_true_only_for_closing_tactic`
  - `test_report_contains_table`: with stubbed `prove` results, `report.md` has a row for each of the three rankers, with proved/20 and mean calls.
  - `test_test_set_not_used_for_training`: spy on `SystemOneModel.fit`; no test statement's goal appears in its inputs.
  - Lean-marked, slow: `test_end_to_end_runs` on 3 train and 2 test theorems; it asserts the result keys exist and `0 <= proved <= 2`.
- [ ] **Step 2: Run** `pytest jev_demo/tests/test_data.py jev_demo/tests/test_bench.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `replay`, `run_experiment`, the CLI, and `README.md`. The README covers setup commands, how to run, what Jev is (two sentences quoting the spec), and why Lean 4 over Isabelle/HOL (point list copied from the spec).
- [ ] **Step 4: Run** `pytest jev_demo -v`. Expected: all pass (lean-marked included, since the REPL is built).
- [ ] **Step 5: Run the experiment.** `python -m jev_demo run --out jev_demo/results`. Expected: `jev_demo/results/report.md` exists with the three-row table, ECE and temperature. Paste the table into `jev_demo/README.md` under "Results". State plainly whether the spec's success criterion was met (model proved ≥ fixed, with fewer mean calls).
- [ ] **Step 6: Commit.** `git commit -m "feat(jev_demo): training replay, benchmark CLI and results"`
