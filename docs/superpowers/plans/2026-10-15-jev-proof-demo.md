# Jev Proof Demo (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small Jev-style System One model that answers typed questions about a Lean proof state: which action kind, which premise lemma, and how close to done. Put it inside a best-first prover that uses this repo's Lean REPL as the checker, and measure it against strong core-Lean automation baselines on 20 held-out theorems.

**Architecture:** A Python package `jev_demo/` sits beside the Lean REPL, with one module per job:
- `repl_client` drives `lake exe repl` over JSON.
- `schema` defines the typed questions and answers.
- `model` is the System One model: one pass, calibrated probabilities.
- `actions` builds the action menu and parses tactics into (kind, premise).
- `premises` dumps the Lean library and shortlists lemmas for each goal.
- `search` is best-first with escalation.
- `data` replays the gold proofs into labels.
- `bench` runs every method and writes the report.

**Tech Stack:** Lean 4 v4.35.0 (this repo's REPL, core Lean only, no Mathlib), Python ≥ 3.11, NumPy, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-jev-proof-demo-design.md`

## Global Constraints

- Lean toolchain: `leanprover/lean4:v4.35.0` (from `lean-toolchain`). No Mathlib, no new Lean dependencies.
- Do not modify the REPL's Lean sources (`REPL/`, `REPL.lean`, `Test.lean`, `test/`).
- Python dependencies are limited to `numpy` (runtime) and `pytest` (dev), declared in `jev_demo/pyproject.toml`.
- Model answers contain only the options supplied in the question. Each choice distribution sums to 1 within 1e-6.
- A proof counts as proved only when the REPL returns `"proofStatus": "Completed"` with no `severity: "error"` message, **and** the assembled script re-checks in command mode with no errors and no `sorries`.
- Search: 64 REPL tactic calls per theorem, max depth 8, top-k = 3, τ = 0.5. Per-call timeout 10 s, except 60 s for the `try_only` baseline.
- Shortlist size 16. The top 4 premises by model probability are combined with the 5 templates (`rw [·]`, `simp [·]`, `grind [·]`, `exact ·`, `apply ·`).
- Data: 40 train theorems, 20 test theorems (8 easy, 12 hard). Test theorems are never used for training or calibration.
- Feature hashing dimension 2^16, using `zlib.crc32`. RNG seed 0 everywhere.
- Integration tests that need a built REPL are marked `@pytest.mark.lean` and skipped when `.lake/build/bin/repl` is missing.

## Review Focus

1. **A failing tactic reports `goals: []`.** The REPL returns empty goals plus an error and `proofStatus: "Incomplete: contains sorry"` (`test/invalid_tactic.expected.out`). Expected: this is a failure, never a closed goal. Pinned in Task 1 and Task 6.
2. **Slow automation:** `exact?`, `grind` and `try?` on a hard goal, or `decide` on a big Nat. Expected: the timeout kills and restarts the REPL, the call counts as failed and against the budget, and the search continues. Pinned in Task 1.
3. **A shortlisted lemma name that cannot be elaborated** in the current context. This covers private, deprecated, or auto-generated names, such as `Nat.foo.match_1` or names that need an `@`. Expected: the library dump filters internal names, a failing `rw [L]` is just a failed action, and nothing crashes. Pinned in Task 5.
4. **Search revisits the same goal through different orders.** Expected: states are deduped by their normalized goal string. Pinned in Task 6.
5. **`try?` or `exact?` "succeeds" only by printing a suggestion while the goal stays open.** Expected: success is judged only by `completed` plus `check_proof`, never by the presence of a "Try this" message. Pinned in Task 7.

---

### Task 1: REPL client

**Files:**
- Create: `jev_demo/pyproject.toml`, `jev_demo/jev_demo/__init__.py`, `jev_demo/jev_demo/repl_client.py`
- Test: `jev_demo/tests/conftest.py`, `jev_demo/tests/test_repl_client.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class TacticResult: proof_state: int | None; goals: list[str]; ok: bool; completed: bool; error: str | None; infos: list[str]`
  - `class ReplClient: __init__(self, repl_path: str = ".lake/build/bin/repl", cwd: str = <repo root>, timeout_s: float = 10.0)`, `command(self, cmd: str, env: int | None = None, timeout_s: float | None = None) -> dict`, `start_theorem(self, statement: str, prelude: str = "") -> tuple[int, str]` (returns `(proof_state, goal)` of the single `sorry` in `theorem t : <statement> := by sorry`), `tactic(self, tac: str, proof_state: int, timeout_s: float | None = None) -> TacticResult`, `check_proof(self, statement: str, tactics: list[str], prelude: str = "") -> bool`, `close(self)`. It is also usable as a context manager.
  - `ok` means there is no `severity == "error"` message. `completed` means `ok` and `proofStatus == "Completed"`. `infos` holds the `data` of info-severity messages, such as "Try this" output.

- [ ] **Step 1: Set up the environment.** Install elan non-interactively (`curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y --default-toolchain none`), then run `lake build` in the repo root. Expected: `.lake/build/bin/repl` exists. Create `pyproject.toml` (package `jev_demo`, dep `numpy`, dev dep `pytest`, register the `lean` marker) and run `pip install -e 'jev_demo[dev]'`.
- [ ] **Step 2: Write the failing tests.** In `conftest.py`, add a session-scoped `repl` fixture that skips if the binary is missing.

```python
@pytest.mark.lean
def test_closing_tactic_is_completed(repl):
    ps, goal = repl.start_theorem("∀ n : Nat, n + 0 = n")
    r = repl.tactic("intro n; simp", ps)
    assert "⊢" in goal and r.ok and r.completed and r.goals == []

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
        ps2, _ = c.start_theorem("1 = 1")
        assert c.tactic("rfl", ps2).completed

@pytest.mark.lean
def test_check_proof_rechecks_whole_script(repl):
    assert repl.check_proof("∀ n : Nat, 0 + n = n", ["intro n", "simp"])
    assert not repl.check_proof("∀ n : Nat, 0 + n = n", ["intro n"])
```

- [ ] **Step 3: Run** `pytest jev_demo/tests/test_repl_client.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 4: Implement `ReplClient`.**
  - Write each request as one JSON line followed by a blank line. Read stdout until a blank line and parse that block.
  - Enforce the timeout with a reader thread and a queue. On timeout, kill the process, start a fresh one, and return `ok=False, error="timeout"`.
  - Proof-state ids from a dead process are invalid. `tactic` on such an id returns `ok=False` rather than raising.
  - `check_proof` runs `theorem t : <stmt> := by\n  <tac1>\n  <tac2>…` (with the prelude first) in command mode. It passes iff there are no error messages and no `sorries`.
- [ ] **Step 5: Run.** Expected: 5 passed.
- [ ] **Step 6: Commit.** `git commit -m "feat(jev_demo): JSON client for the Lean REPL"`

### Task 2: Typed question schema

**Files:**
- Create: `jev_demo/jev_demo/schema.py`
- Test: `jev_demo/tests/test_schema.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class ChoiceQuestion: name: str; options: tuple[str, ...]`. Options must be non-empty and unique, else `ValueError`.
  - `@dataclass(frozen=True) class BinaryQuestion: name: str; option: str | None = None`. `option` is `None` for a question about the state itself.
  - `@dataclass(frozen=True) class ChoiceAnswer: probs: dict[str, float]` with properties `top -> str` and `confidence -> float`.
  - `@dataclass(frozen=True) class BinaryAnswer: p_true: float`
  - `Question = ChoiceQuestion | BinaryQuestion`, `Answer = ChoiceAnswer | BinaryAnswer`
  - `validate(question: Question, answer: Answer) -> None`, which raises `ValueError` on a key mismatch, a probability outside [0, 1], or a sum ≠ 1 ± 1e-6.

- [ ] **Step 1: Write the failing tests.**
  - `test_choice_rejects_duplicate_options`
  - `test_choice_rejects_empty`
  - `test_validate_rejects_extra_option`
  - `test_validate_rejects_bad_sum` ({a: .6, b: .6})
  - `test_top_and_confidence` ({a: .2, b: .8} → top "b", confidence .8)
  - `test_binary_range` (p_true 1.2 → ValueError)
- [ ] **Step 2: Run** `pytest jev_demo/tests/test_schema.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the dataclasses and `validate`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(jev_demo): typed question/answer schema"`

### Task 3: System One model

**Files:**
- Create: `jev_demo/jev_demo/model.py`
- Test: `jev_demo/tests/test_model.py`

**Interfaces:**
- Consumes: `schema.*` (Task 2)
- Produces:
  - `featurize(state: str, option: str | None = None, dim: int = 2**16) -> dict[int, float]`: sparse hashed features. It uses word unigrams and bigrams of the goal (tokenized after splitting on `( ) [ ] , : ⊢ ·`), the option's head token and full text, the dotted-name components of the option (`Nat.gcd_succ` → `Nat`, `gcd`, `succ`), and the cross features `option token × goal token`. Each question name is mixed into the hash, so different questions do not share weights.
  - `@dataclass class ChoiceExample: question: str; state: str; options: tuple[str, ...]; gold: str`
  - `@dataclass class BinaryExample: question: str; state: str; option: str | None; label: bool`
  - `class SystemOneModel: __init__(self, dim: int = 2**16, seed: int = 0)`, `fit(self, choice: list[ChoiceExample], binary: list[BinaryExample], epochs: int = 30, lr: float = 0.1, l2: float = 1e-4) -> None`, `calibrate(self, choice: list[ChoiceExample]) -> dict[str, float]` (fits one temperature per choice-question name by grid search over [0.25, 4] in steps of 0.05, minimizing NLL), `evaluate(self, state: str, questions: list[Question]) -> dict[str, Answer]`, `save(self, path: str)`, and the classmethod `load(cls, path: str) -> SystemOneModel`.
  - `expected_calibration_error(model, choice: list[ChoiceExample], bins: int = 10) -> float`

- [ ] **Step 1: Write the failing tests.**

```python
def test_answers_cover_exactly_supplied_options_even_unseen():
    m = SystemOneModel(); m.fit([ChoiceExample("kind", "⊢ a = a", ("rfl", "simp"), "rfl")], [], epochs=5)
    q = ChoiceQuestion("kind", ("induction l <;> grind", "omega", "rw [·]"))
    a = m.evaluate("l : List Nat ⊢ l ++ [] = l", [q])["kind"]
    assert set(a.probs) == set(q.options); validate(q, a)

def test_learns_separable_choice():
    data = [ChoiceExample("kind", f"n : Nat ⊢ n + {i} = {i} + n", ("omega", "rfl"), "omega") for i in range(20)] + \
           [ChoiceExample("kind", f"⊢ x{i} = x{i}", ("omega", "rfl"), "rfl") for i in range(20)]
    m = SystemOneModel(); m.fit(data, [], epochs=30)
    assert m.evaluate("n : Nat ⊢ n + 99 = 99 + n", [ChoiceQuestion("kind", ("omega", "rfl"))])["kind"].top == "omega"

def test_one_pass_answers_three_questions(): ...       # keys {"kind","premise","near_done"}; each validates
def test_premise_head_uses_lemma_name_tokens(): ...    # trained on gcd goals → "Nat.gcd_succ" ranked above "List.length_append"
def test_calibration_temperature_reduces_nll(): ...    # overconfident model (weights ×10): NLL after calibrate ≤ before
def test_featurize_is_deterministic(): ...
def test_save_load_roundtrip(tmp_path): ...
```

- [ ] **Step 2: Run** `pytest jev_demo/tests/test_model.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Use one shared sparse weight vector; question names are separated by the hashing. Choice questions use listwise softmax over options, and binary questions use the logistic loss. Train with plain SGD, shuffled with `numpy.random.default_rng(seed)`. Save the weights, the temperatures and `dim` with `numpy.savez`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(jev_demo): System One model with typed answers and calibration"`

### Task 4: Action space and theorem sets

**Files:**
- Create: `jev_demo/jev_demo/actions.py`, `jev_demo/jev_demo/theorems.py`, `jev_demo/data/train.json`, `jev_demo/data/test.json`
- Test: `jev_demo/tests/test_actions.py`, `jev_demo/tests/test_theorems.py`

**Interfaces:**
- Produces:
  - `BASE_MENU: tuple[str, ...] = ("rfl", "simp", "simp_all", "omega", "decide", "constructor", "assumption", "trivial", "simp [*] at *")`
  - `AUTOMATION: tuple[str, ...] = ("grind", "exact?")`
  - `TEMPLATES: tuple[str, ...] = ("rw [·]", "simp [·]", "grind [·]", "exact ·", "apply ·")`
  - `menu(goal: str, automation: bool = True) -> tuple[str, ...]`: `BASE_MENU`, then `AUTOMATION` if enabled, then the goal-specific items in this order:
    - `intro <binder names>` when the target starts with `∀ x y … : T,` or `∀ (x : T) (y : U),`.
    - `intro h` for an implication (`h1` if `h` is taken).
    - For each hypothesis `x : Nat` or `x : List _`: `induction x <;> simp_all`, `induction x <;> grind` and `cases x`.
    - For each `h : _ ∨ _`: `cases h`.

    The result is deduplicated, order-stable and non-empty.
  - `fill(template: str, premise: str) -> str` (replaces `·`)
  - `parse_action(tac: str) -> tuple[str, str | None]`: `"rw [Nat.add_comm]"` → `("rw [·]", "Nat.add_comm")`, and `"omega"` → `("omega", None)`.
  - `@dataclass(frozen=True) class Theorem: name: str; statement: str; prelude: str; gold: tuple[str, ...]; difficulty: Literal["easy", "hard"]`
  - `load_theorems(path: str) -> list[Theorem]`

- [ ] **Step 1: Write `test.json` with exactly these 20 statements.**

  **Easy (8):**
  1. `∀ n m : Nat, n + m = m + n`
  2. `∀ l₁ l₂ : List Nat, (l₁ ++ l₂).length = l₁.length + l₂.length`
  3. `∀ l : List Nat, l.reverse.reverse = l`
  4. `∀ n : Nat, n % 2 = 0 ∨ n % 2 = 1`
  5. `∀ p q : Prop, p ∨ q → q ∨ p`
  6. `∀ a b : Nat, a + b = 0 → a = 0`
  7. `∀ n : Nat, double n = 2 * n`, with prelude `def double : Nat → Nat | 0 => 0 | n+1 => double n + 2`
  8. `∀ n : Nat, sumTo n * 2 = n * (n + 1)`, with prelude `def sumTo : Nat → Nat | 0 => 0 | n+1 => sumTo n + (n+1)`

  **Hard (12):**
  1. `∀ n : Nat, sumOdd n = n * n`, with prelude `def sumOdd : Nat → Nat | 0 => 0 | n+1 => sumOdd n + (2*n+1)`
  2. `∀ n : Nat, sumSq n * 6 = n * (n + 1) * (2 * n + 1)`, with prelude `def sumSq : Nat → Nat | 0 => 0 | n+1 => sumSq n + (n+1)*(n+1)`
  3. `∀ n : Nat, n + 1 ≤ 2 ^ n`
  4. `∀ n : Nat, n * n % 4 = 0 ∨ n * n % 4 = 1`
  5. `∀ n : Nat, Nat.gcd n (n + 1) = 1`
  6. `∀ m n k : Nat, m ∣ n → m ∣ n * k`
  7. `∀ xs : List Nat, (xs.map (· * 2)).sum = 2 * xs.sum`
  8. `∀ l : List Nat, rev l = l.reverse`, with prelude `def revAux : List Nat → List Nat → List Nat | [], acc => acc | x :: xs, acc => revAux xs (x :: acc)` and `def rev (l : List Nat) : List Nat := revAux l []`
  9. `∀ n : Nat, 2 ∣ n * (n + 1)`
  10. `∀ n : Nat, fib n ≤ fib (n + 1)`, with prelude `def fib : Nat → Nat | 0 => 0 | 1 => 1 | n+2 => fib n + fib (n+1)`
  11. `∀ (l : List Nat) (f g : Nat → Nat), (l.map f).map g = l.map (g ∘ f)`
  12. `∀ a b : Nat, a ≤ b → a * a ≤ b * b`

  A test gold proof may use any Lean 4.35 core tactic, including `have`, `induction … with` and `calc`.
- [ ] **Step 2: Write `train.json` with 40 theorems**, none textually equal to a test statement:
  - 30 easy: 10 Nat arithmetic, 8 List, 6 propositional, 6 recursive-def induction.
  - 10 hard-style, where each gold proof uses at least one premise template (such as `rw [Nat.mul_comm]`, `simp [List.map_map]`, `exact Nat.dvd_mul_right_of_dvd h k`, `apply Nat.mul_le_mul`) or a two-step induction.

  Every train gold step must be producible by the action space: `parse_action(step)[0] ∈ menu(goal) ∪ TEMPLATES`.
- [ ] **Step 3: Write the failing tests.**
  - `test_menu_always_has_base_and_automation`
  - `test_menu_without_automation_excludes_grind_and_exact_q`
  - `test_intro_uses_binder_names` (`"⊢ ∀ (l₁ l₂ : List Nat), …"` → contains `"intro l₁ l₂"`)
  - `test_intro_h_for_implication`
  - `test_induction_offered_for_nat_and_list_hyps`
  - `test_cases_offered_for_or_hyp`
  - `test_parse_action_roundtrip` (for each template and a sample premise, `parse_action(fill(t, p)) == (t, p)`)
  - `test_splits_disjoint_and_sized` (40/20; test has 8 easy and 12 hard)
  - Lean-marked:
    - `test_every_gold_proof_checks` (both files, via `check_proof`)
    - `test_every_train_gold_step_is_in_action_space` (replay in tactic mode; assert the Step 2 rule at each step)
    - `test_menu_reachable_flags_written`: for each test theorem, compute whether every gold step is in the action space, and write the result to `jev_demo/data/test_reachability.json`.
- [ ] **Step 4: Run** `pytest jev_demo/tests/test_actions.py jev_demo/tests/test_theorems.py -v`. Expected: FAIL.
- [ ] **Step 5: Implement.** `menu` parses hypothesis lines (`a b : Nat` lines included) from the first goal's context, before `⊢`. `parse_action` matches the templates by prefix, and the premise is the remaining identifier text with surrounding brackets stripped.
- [ ] **Step 6: Run.** Expected: PASS. If a gold proof fails in core Lean 4.35, fix the proof. Replace the statement only if it cannot be proved in core Lean at all, using another theorem of the same difficulty and category, and record the swap in the commit message.
- [ ] **Step 7: Commit.** `git commit -m "feat(jev_demo): action space and train/test theorem sets"`

### Task 5: Premise library and shortlist

**Files:**
- Create: `jev_demo/jev_demo/premises.py`, `jev_demo/jev_demo/dump_library.lean`
- Test: `jev_demo/tests/test_premises.py`

**Interfaces:**
- Consumes: `ReplClient.command` (Task 1)
- Produces:
  - `@dataclass(frozen=True) class Lemma: name: str; type: str; tokens: frozenset[str]`
  - `dump_library(repl: ReplClient, cache_path: str = "jev_demo/data/library.json") -> list[Lemma]`
  - `class Shortlister: __init__(self, library: list[Lemma])` (precomputes IDF over the lemma token sets), `shortlist(self, goal: str, k: int = 16) -> tuple[str, ...]` (lemma names by descending IDF-weighted overlap, ties broken by shorter name then lexicographic order)
  - `option_text(lemma: Lemma) -> str`, which returns `"<name> : <type>"`. This is the string shown to the model as a premise option.
  - `shortlist_recall(shortlister, examples: list[tuple[str, str]]) -> float`, computed over `(goal, gold_premise)` pairs.

- [ ] **Step 1: Write `dump_library.lean`.** It is a single `#eval` in `MetaM` that iterates `(← getEnv).constants` and keeps only theorems:
  - whose root namespace is in `Nat`, `List`, `Bool`, `And`, `Or` or `Iff`;
  - excluding `n.isInternalDetail`, names containing `match_`, `proof_`, `_private`, `eq_` or `_sunfold`, and deprecated declarations (`Lean.Linter.isDeprecated`).

  For each kept theorem it prints one JSON line `{"name": …, "type": <ppExpr type>}`. The REPL returns the output as info messages.
- [ ] **Step 2: Write the failing tests.**
  - `test_shortlist_prefers_overlapping_lemma`: synthetic library `[gcd_succ: "gcd n (n+1) = 1", length_append: "(a ++ b).length = …"]`; goal `"n : Nat ⊢ Nat.gcd n (n + 1) = 1"` → first is `gcd_succ`.
  - `test_shortlist_size_and_determinism`
  - `test_idf_downweights_ubiquitous_tokens` (`Nat` and `=` contribute less than `gcd`)
  - Lean-marked:
    - `test_dump_contains_core_lemmas`: names include `Nat.add_comm`, `List.length_append` and `List.map_map`; none contain `match_`.
    - `test_bad_premise_is_plain_failure`: `rw [Nat.nonexistent]` → `ok=False`, no exception.
    - `test_train_shortlist_recall_reported`: compute the recall over the train gold premise steps, assert it is in [0, 1], and print it.
- [ ] **Step 3: Run** `pytest jev_demo/tests/test_premises.py -v`. Expected: FAIL.
- [ ] **Step 4: Implement.**
  - `dump_library` runs the `.lean` file's text through `repl.command` with `timeout_s=120`, then parses JSON lines from the info messages. Cache the result to `library.json`; delete the cache to rebuild.
  - Tokens are the name components plus the `featurize` tokenizer applied to the type.
  - Goal tokens use the same tokenizer, with dot-notation calls split, so `l.reverse` yields `reverse`.
- [ ] **Step 5: Run.** Expected: PASS.
- [ ] **Step 6: Commit.** `git commit -m "feat(jev_demo): premise library dump and IDF shortlist"`

### Task 6: Best-first search with escalation

**Files:**
- Create: `jev_demo/jev_demo/search.py`
- Test: `jev_demo/tests/test_search.py`

**Interfaces:**
- Consumes: `ReplClient`, `TacticResult` (Task 1); `SystemOneModel.evaluate`, questions (Tasks 2–3); `menu`, `TEMPLATES`, `fill`, `Theorem` (Task 4); `Shortlister`, `option_text` (Task 5)
- Produces:
  - `class Ranker(Protocol): def rank(self, goal: str) -> tuple[list[tuple[str, float]], float, float]`. It returns `(actions sorted by descending score, confidence, state_value)`.
  - `ModelRanker(model, shortlister, lib: dict[str, Lemma], premises: bool = True, automation: bool = True)`.
    - It makes one `evaluate` call with `ChoiceQuestion("kind", menu(goal, automation) + (TEMPLATES if premises else ()))`, `ChoiceQuestion("premise", tuple(option_text(lib[n]) for n in shortlist(goal)))` and `BinaryQuestion("near_done")`.
    - Action scores are `p(kind)` for a menu item and `p(kind = t) · p(premise = L)` for the top 4 premises L × each template t.
    - The scores are renormalized to sum to 1. Confidence is the top action's score, and `state_value` is `near_done.p_true`.
  - `FixedOrderRanker(automation: bool = True)`: menu order, no templates, uniform scores, confidence 1.0, `state_value` 0.5.
  - `RandomRanker(seed=0)`: the same, shuffled.
  - `@dataclass class SearchResult: proved: bool; tactics: list[str]; calls: int; escalations: int; seconds: float; trace: list[dict]`
  - `prove(thm: Theorem, repl: ReplClient, ranker: Ranker, budget: int = 64, max_depth: int = 8, top_k: int = 3, tau: float = 0.5) -> SearchResult`

- [ ] **Step 1: Write the failing tests.** Use a `FakeRepl` stub with `ReplClient`'s methods, scripted by a `(goal, tactic) → TacticResult` dict.
  - `test_fixed_order_proves_one_step`
  - `test_error_with_empty_goals_is_not_success`
  - `test_dedup_same_goal_reached_twice`
  - `test_budget_exhaustion_returns_unproved` (`calls == budget`)
  - `test_escalation_expands_all_when_low_confidence` (a stub with confidence 0.3 tries every action; `escalations == 1`)
  - `test_high_confidence_expands_top_k_only`
  - `test_final_proof_rechecked` (`check_proof` False → `proved` False)
  - `test_model_ranker_scores_sum_to_one_and_include_filled_templates` (uses a tiny trained model and a 3-lemma library)
  - `test_model_ranker_without_premises_has_no_templates`
  - Lean-marked: `test_fixed_order_proves_trivial_real_theorem`
- [ ] **Step 2: Run** `pytest jev_demo/tests/test_search.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `prove`.**
  - Keep a `heapq` frontier ordered by `-(cum_logp + log(state_value + 1e-3))`.
  - Pop a node and rank it. Expand the top `top_k` actions, or all of them when confidence < τ (incrementing `escalations`).
  - A `completed` child triggers `check_proof`; if it passes, stop.
  - An `ok` child with remaining goals is pushed, keyed by its normalized first goal (whitespace collapsed). Seen keys are skipped. Its `state_value` comes from one `rank` call when it is pushed.
  - Every `tactic` call counts against the budget. Each step appends `{goal, n_actions, chosen, score, confidence, outcome}` to `trace`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(jev_demo): best-first prover with premise actions and escalation"`

### Task 7: Training replay, baselines and benchmark CLI

**Files:**
- Create: `jev_demo/jev_demo/data.py`, `jev_demo/jev_demo/baselines.py`, `jev_demo/jev_demo/bench.py`, `jev_demo/jev_demo/__main__.py`, `jev_demo/README.md`
- Test: `jev_demo/tests/test_data.py`, `jev_demo/tests/test_baselines.py`, `jev_demo/tests/test_bench.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `replay(thm: Theorem, repl: ReplClient, shortlister: Shortlister, lib: dict[str, Lemma]) -> tuple[list[ChoiceExample], list[BinaryExample]]`. For gold step i at goal g, it yields:
    - a `kind` example (gold = `parse_action(step)[0]`);
    - a `premise` example when the step has a premise *and* that premise is in `shortlist(g)` (otherwise it records a recall miss);
    - a `near_done` example (label `len(gold) - i <= 2`).
  - `single_shot(thm: Theorem, repl: ReplClient, tactic: str, timeout_s: float) -> SearchResult`. It runs `intros` and then the tactic on the theorem's start state. If the tactic is not `completed` but its `infos` contain `Try this: <tac>`, it runs `<tac>` once (counted as a second call). The theorem is proved iff a run is `completed` and `check_proof` passes on the tactics actually run.
  - `run_experiment(repl, train, test, out_dir) -> dict`:
    1. Dump the library and build the shortlister.
    2. Replay the train set, then fit the model. Calibrate on a 20% hold-out of the train examples (seed 0), then refit on all train examples, keeping the temperatures.
    3. Run the methods `model`, `model_no_premise`, `fixed`, `random`, `grind_only` (`single_shot(..., "grind", 10)`) and `try_only` (`single_shot(..., "try?", 60)`) on every test theorem.
    4. Compute the `kind` ECE from the test replays (measurement only) and the shortlist recall on test.
    5. Write `results.json` and `report.md`.

    It returns `{method: {"proved": int, "proved_easy": int, "proved_hard": int, "mean_calls": float, "mean_seconds": float, "per_theorem": [...]}}` plus `"ece"`, `"temperatures"` and `"shortlist_recall"`.
  - The CLI is `python -m jev_demo run --out jev_demo/results`, run from the repo root.

- [ ] **Step 1: Write the failing tests.**
  - `test_replay_labels_kind_and_premise`
  - `test_replay_counts_recall_miss_when_premise_not_shortlisted`
  - `test_replay_near_done_labels`
  - `test_single_shot_follows_try_this_once`: a FakeRepl where `try?` leaves the goal open with info `Try this: omega`, and `omega` completes → proved, `calls == 2`.
  - `test_single_shot_suggestion_alone_is_not_success`: the suggestion fails → not proved.
  - `test_report_has_row_per_method_with_easy_hard_split`
  - `test_test_set_not_used_for_training`: spy on `fit`; no test goal appears in its inputs.
  - Lean-marked, slow: `test_end_to_end_runs` on 4 train and 2 test theorems; all six methods appear in the results.
- [ ] **Step 2: Run** `pytest jev_demo/tests/test_data.py jev_demo/tests/test_baselines.py jev_demo/tests/test_bench.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `replay`, `single_shot`, `run_experiment`, the CLI, and `README.md`. The README covers setup, how to run, what Jev is (two sentences from the spec), and why Lean 4 (the spec's three points).
- [ ] **Step 4: Run** `pytest jev_demo -v`. Expected: all pass.
- [ ] **Step 5: Run the experiment.** `python -m jev_demo run --out jev_demo/results`. Expected: `report.md` has six rows with easy/hard columns, plus ECE, temperatures and recall. Paste the table into the README under "Results", together with `test_reachability.json`'s count of menu-reachable hard theorems. State plainly whether the spec's success criterion was met.
- [ ] **Step 6: Commit.** `git commit -m "feat(jev_demo): training replay, baselines, benchmark CLI and results"`
