# Jev Proof Demo (Phase 2: Claude Generator) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Claude as an open-ended tactic generator. The Jev-style System One model from phase 1 ranks Claude's proposals together with the phase-1 actions, so we can measure whether a fast, calibrated chooser adds value on top of an LLM.

**Architecture:** This builds on phase 1 and does not change its interfaces.
- `claude_gen.ClaudeGenerator` returns N structured tactic proposals per goal. It uses a disk cache, a cost meter and a hard dollar cap.
- `HybridRanker` adds those proposals as extra options of the `kind` question.
- `collect` labels the proposals on train states so the model learns which LLM suggestions tend to work.
- `bench` gains three Claude-based methods.

**Tech Stack:** Phase 1 stack plus the `anthropic` Python SDK and `pydantic`. Model `claude-opus-5-5`.

**Spec:** `docs/superpowers/specs/2026-10-15-jev-proof-demo-design.md` (section "Phase 2"). Phase 1's plan `docs/superpowers/plans/2026-10-15-jev-proof-demo.md` must be complete first.

## Global Constraints

- Model: `claude-opus-5-5`, configurable via `--claude-model`. Effort is set explicitly; the default is `"medium"`, configurable via `--effort`. Omit `thinking`, which runs adaptive on this model. Do not send `budget_tokens`, `temperature`, prefill, or forced `tool_choice`: each returns a 400 on this model.
- Structured output: a Pydantic model returned through the SDK's parse helper. Never regex the response text.
- Refusal fallback: send `betas=["server-side-fallback-2026-07-01"]` and `fallbacks="default"`. Check `stop_reason` before reading output, and treat `"refusal"` as zero proposals and log it.
- Prompt caching: top-level `cache_control={"type": "ephemeral"}`. The system prompt is a frozen module-level constant, with no timestamps and no per-call text; all per-goal text goes in the user message.
- Costs: at most 16 Claude calls per theorem and 8 proposals per call. A per-run cap of `--max-usd` (default 10.0) stops new calls once spent, after which the generator returns `[]`. Prices for `claude-opus-5-5`: $4 per million input tokens, $20 per million output, $0.20 per million for cache reads. Cache writes cost 1.25 × the input price.
- Responses are cached on disk under `jev_demo/cache/claude/`, keyed by sha256 of (model, effort, system-prompt hash, user message). Re-runs make no API calls, and the cache directory is git-ignored.
- Credentials are whatever the SDK resolves: `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, or an `ant auth login` profile. Never hard-code a key.
- Unit tests never touch the network. Live tests are marked `@pytest.mark.claude` and skipped unless `ANTHROPIC_RUN_LIVE=1`.
- Phase-1 constraints all still apply. In particular, proved means `completed` plus a passing `check_proof`.

## Review Focus

1. **Claude proposes a multi-line or `sorry`-containing tactic, or one that uses a Mathlib-only tactic** (`ring`, `linarith`, `norm_num`). Expected: proposals containing `sorry`/`admit` are dropped before execution; multi-line text is joined with `; ` or `<;>` as given; Mathlib-only tactics simply fail in the REPL. Pinned in Task 1.
2. **Duplicate proposals across calls, or proposals identical to menu actions.** Expected: options are deduplicated before the `kind` question is built, so the option set stays unique and the schema's uniqueness check never raises. Pinned in Task 2.
3. **The cost cap is reached mid-theorem.** Expected: the search continues with phase-1 actions only, and the report marks the theorem `budget_capped`. Pinned in Task 1 and Task 3.
4. **The API is unavailable or rate-limited** (429/5xx after SDK retries). Expected: that call yields `[]`, the error is counted in the report, and the run does not crash. Pinned in Task 1.
5. **Cache hits must not count toward the dollar spend.** Expected: the cost meter only adds usage from real responses. Pinned in Task 1.

---

### Task 1: Claude tactic generator

**Files:**
- Create: `jev_demo/jev_demo/claude_gen.py`, `jev_demo/jev_demo/prompts.py`
- Modify: `jev_demo/pyproject.toml` (add `anthropic`, `pydantic`; register the `claude` marker), `.gitignore` (add `jev_demo/cache/`)
- Test: `jev_demo/tests/test_claude_gen.py`

**Interfaces:**
- Produces:
  - `class Proposals(pydantic.BaseModel): tactics: list[str]` (the structured-output schema; the prompt asks for 1–8 entries, most promising first)
  - `SYSTEM_PROMPT: str` in `prompts.py`. It covers:
    - Lean 4 v4.35 core only, with no Mathlib, so no `ring`/`linarith`/`norm_num`.
    - One tactic step per entry. `have h : P := by <tac>` and `<;>` combinators are allowed; `sorry`/`admit` are forbidden.
    - Use the hypothesis names exactly as shown in the goal.
    - Five worked examples (goal → good tactics) drawn from train theorems, never test ones.
  - `@dataclass class Usage: calls: int; input_tokens: int; output_tokens: int; cache_read_tokens: int; cache_write_tokens: int; usd: float; refusals: int; errors: int`
  - `class ClaudeGenerator: __init__(self, client=None, model: str = "claude-opus-5-5", effort: str = "medium", n: int = 8, cache_dir: str = "jev_demo/cache/claude", max_usd: float = 10.0)`. `client=None` means `anthropic.Anthropic()`, and tests inject a fake.
    - `propose(self, goal: str, prelude: str = "", failed: list[str] = ()) -> list[str]`
    - `whole_proof(self, statement: str, prelude: str = "", k: int = 4) -> list[list[str]]`: k independent calls, each asking for a complete tactic script as `Proposals`.
    - `usage: Usage`
  - The user message contains, in this fixed order: the prelude, the goal, and the "already failed here" list, so Claude does not repeat failed tactics.

- [ ] **Step 1: Check the installed SDK before writing code.** Run `pip install anthropic pydantic`, then:
  - `python -c "import anthropic, inspect; print(inspect.signature(anthropic.Anthropic().beta.messages.parse))"`. Confirm it accepts `output_format`, `output_config`, `betas`, `fallbacks` and `cache_control`.
  - If `parse` is missing on `beta` or rejects `fallbacks`, use `client.beta.messages.create` with `output_config={"format": {"type": "json_schema", "schema": Proposals.model_json_schema()}}` and validate the text with `Proposals.model_validate_json`.

  Record which path is used in a module docstring.
- [ ] **Step 2: Write the failing tests.** Use a `FakeClient` whose `beta.messages.parse` (or `create`) returns canned objects with `.parsed_output` (or a JSON text block), plus `.stop_reason` and `.usage`.
  - `test_propose_returns_parsed_tactics_in_order`
  - `test_request_shape`: the captured kwargs have `model == "claude-opus-5-5"`, `output_config["effort"] == "medium"`, top-level `cache_control`, `fallbacks == "default"`, the beta `server-side-fallback-2026-07-01`, `system == SYSTEM_PROMPT`, and no `thinking`, `temperature` or `tool_choice`.
  - `test_drops_sorry_and_admit`
  - `test_refusal_yields_empty_and_counts`
  - `test_api_error_yields_empty_and_counts`: the fake raises `anthropic.RateLimitError`.
  - `test_disk_cache_hit_makes_no_call_and_no_cost`
  - `test_cost_meter_prices`: usage of 1,000,000 input and 100,000 output tokens gives `usd == 4.0 + 2.0`.
  - `test_cap_stops_calls`: with `max_usd=0.0`, `propose` returns `[]` without calling the client.
  - `test_failed_list_in_user_message`
  - `@pytest.mark.claude test_live_proposes_for_simple_goal`: the goal `n : Nat ⊢ n + 0 = n` returns ≥ 1 tactic and `usage.calls == 1`.
- [ ] **Step 3: Run** `pytest jev_demo/tests/test_claude_gen.py -v`. Expected: FAIL.
- [ ] **Step 4: Implement** the generator.
  - Use `max_tokens=4000`, which is enough for 8 short tactics.
  - Catch errors most-specific first: `anthropic.RateLimitError`, then `anthropic.APIStatusError`, then `anthropic.APIConnectionError`. Increment `errors` and return `[]`.
  - Write the cache file only on a successful parse.
- [ ] **Step 5: Run.** Expected: PASS (live test skipped).
- [ ] **Step 6: Commit.** `git commit -m "feat(jev_demo): Claude tactic generator with caching and cost cap"`

### Task 2: Hybrid ranker and proposal labels

**Files:**
- Create: `jev_demo/jev_demo/hybrid.py`, `jev_demo/jev_demo/collect.py`
- Test: `jev_demo/tests/test_hybrid.py`, `jev_demo/tests/test_collect.py`

**Interfaces:**
- Consumes: `ModelRanker` internals, `menu`, `TEMPLATES`, `Shortlister` and `prove` (phase 1); `ClaudeGenerator` (Task 1)
- Produces:
  - `LLM_PREFIX = "llm|"`. The kind option for proposal i is `f"llm|{i}|{tactic}"`, so `featurize` sees both the source and Claude's own rank. `strip_llm(option) -> str` recovers the tactic.
  - `HybridRanker(model, shortlister, lib, generator, order: Literal["jev", "llm"] = "jev")`. It implements phase 1's `Ranker`.
    - `rank(goal)` calls `generator.propose(goal, failed=<tactics already tried at this goal>)` once per distinct goal (memoized).
    - The proposals are deduplicated against each other and against the menu. With `order="jev"`, the proposals are added to the `kind` options and scored by the model exactly as in phase 1.
    - With `order="llm"` (the "Claude alone" control), the proposals are tried in Claude's order first, then the menu in fixed order. Scores are uniform and confidence is 1.0.
  - `collect(train: list[Theorem], repl, generator, shortlister, lib) -> tuple[list[ChoiceExample], list[BinaryExample]]`.
    - At each gold state, ask for proposals and run every proposal once in the REPL.
    - Each proposal yields a `BinaryExample("useful", goal, option, ok and (completed or the first goal changed))`.
    - Add a `kind` `ChoiceExample` over menu + templates + proposals, where gold is the gold step's kind.
    - If some proposal `completed` the goal, add a second `kind` example whose gold is the first such proposal.
    - The results are saved to `jev_demo/data/claude_labels.json`, so retraining needs no API calls.
  - `HybridRanker` with `order="jev"` also asks `BinaryQuestion("useful", option=o)` for each proposal in the same `evaluate` call, and multiplies its p_true into that proposal's score before renormalizing.

- [ ] **Step 1: Write the failing tests** (fake generator, `FakeRepl`):
  - `test_llm_options_prefixed_and_deduplicated`
  - `test_strip_llm_roundtrip`
  - `test_jev_order_uses_model_scores`
  - `test_llm_order_tries_claude_first`
  - `test_failed_tactics_passed_back_to_generator`
  - `test_one_generator_call_per_distinct_goal`
  - `test_collect_labels_useful_and_completed_proposals`
  - `test_collect_saves_and_reloads_labels`
- [ ] **Step 2: Run** `pytest jev_demo/tests/test_hybrid.py jev_demo/tests/test_collect.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `hybrid.py` and `collect.py`. The search executes `strip_llm(option)` as the tactic.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(jev_demo): hybrid Jev+Claude ranker and proposal labelling"`

### Task 3: Phase-2 benchmark

**Files:**
- Modify: `jev_demo/jev_demo/bench.py`, `jev_demo/jev_demo/__main__.py`, `jev_demo/README.md`
- Test: `jev_demo/tests/test_bench_phase2.py`

**Interfaces:**
- Produces:
  - `python -m jev_demo run-phase2 --out jev_demo/results_phase2 [--claude-model claude-opus-5-5] [--effort medium] [--max-usd 10]`
  - Methods, each on the 20 test theorems:
    - `claude_whole`: `whole_proof(k=4)`; proved if any script passes `check_proof`.
    - `claude_search`: `prove` with `HybridRanker(order="llm")`.
    - `hybrid`: `prove` with `HybridRanker(order="jev")`, using the model retrained on phase-1 labels plus `claude_labels.json`.
    - `phase1_best`: copied from the phase-1 `results.json`.
  - Per-method fields as in phase 1, plus `claude_calls`, `usd`, `refusals`, `errors` and `budget_capped`.

- [ ] **Step 1: Write the failing tests** (fake generator):
  - `test_phase2_report_rows_and_cost_columns`
  - `test_whole_proof_counts_any_valid_script`
  - `test_budget_capped_flag_propagates`
  - `test_retrained_model_includes_claude_labels`
- [ ] **Step 2: Run** `pytest jev_demo/tests/test_bench_phase2.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the `run-phase2` subcommand.
- [ ] **Step 4: Run** `pytest jev_demo -v`. Expected: all pass, with live tests skipped.
- [ ] **Step 5: Run the experiment** with real credentials: `ANTHROPIC_RUN_LIVE=1 python -m jev_demo run-phase2 --out jev_demo/results_phase2`. Expected: `report.md` has four rows with proved (easy/hard), mean calls, Claude calls and USD, and the total USD is ≤ `--max-usd`. Paste the table into the README under "Phase 2 results" and state plainly:
  1. Does `hybrid` prove more hard theorems than `claude_search`? This answers whether Jev added value on top of Claude.
  2. Does it do so at equal or lower USD?
  3. How many of the `menu_reachable = false` hard theorems did any Claude method prove?
- [ ] **Step 6: Commit.** `git commit -m "feat(jev_demo): phase-2 benchmark with Claude generator"`
