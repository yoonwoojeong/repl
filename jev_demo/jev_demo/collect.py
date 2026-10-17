"""Label Claude's proposals at gold states, so the model can learn which ones tend to work.

For every gold state of every training theorem: ask the generator for proposals, run each once
in the REPL, and record `useful` (the proposal succeeded and either closed the goal or changed
the first goal) plus `kind` choice examples over menu + templates + proposals. Labels are saved
to JSON so retraining needs no further API calls.
"""

from __future__ import annotations

import json
import os

from jev_demo.actions import TEMPLATES, menu, parse_action
from jev_demo.hybrid import llm_options
from jev_demo.model import BinaryExample, ChoiceExample
from jev_demo.premises import Lemma, Shortlister
from jev_demo.search import _is_stale, _is_timeout, _key, replay_state
from jev_demo.theorems import DATA_DIR, Theorem

LABELS_PATH = os.path.join(DATA_DIR, "claude_labels.json")


def save_labels(path: str, choice: list[ChoiceExample], binary: list[BinaryExample]) -> None:
    rows = {
        "choice": [{"question": c.question, "state": c.state, "options": list(c.options),
                    "gold": c.gold} for c in choice],
        "binary": [{"question": b.question, "state": b.state, "option": b.option,
                    "label": b.label} for b in binary],
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


def load_labels(path: str = LABELS_PATH) -> tuple[list[ChoiceExample], list[BinaryExample]]:
    """Saved labels, or `([], [])` if the file does not exist (loading is optional)."""
    try:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
    except FileNotFoundError:
        return [], []
    return (
        [ChoiceExample(r["question"], r["state"], tuple(r["options"]), r["gold"]) for r in rows["choice"]],
        [BinaryExample(r["question"], r["state"], r["option"], r["label"]) for r in rows["binary"]],
    )


def collect(train: list[Theorem], repl, generator, shortlister: Shortlister, lib: dict[str, Lemma],
            out_path: str | None = LABELS_PATH) -> tuple[list[ChoiceExample], list[BinaryExample]]:
    """Label proposals at every gold state; write the result to `out_path` unless it is None.

    Labels are saved after every theorem, so an exception keeps the theorems already labelled.
    A proposal that times out restarts the REPL: it is labelled not useful and the gold state is
    re-derived (start the theorem, replay the gold prefix) before the next proposal; a stale
    state is re-derived the same way and the tactic retried once, as in `search.prove`.

    When a proposal is the gold step itself (up to whitespace), the `kind` example has that
    proposal as its gold *instead of* the gold's menu/template kind: the template example would
    train the model against the correct proposal.

    `shortlister` and `lib` are accepted for symmetry with `replay` (the premise/near_done
    examples still come from phase-1 replay). Raises AssertionError if a gold step fails.
    """
    choice: list[ChoiceExample] = []
    binary: list[BinaryExample] = []
    for thm in train:
        ps, goal = repl.start_theorem(thm.statement, thm.prelude)
        for i, step in enumerate(thm.gold):
            def fresh() -> int:
                new = replay_state(repl, thm, list(thm.gold[:i]))
                if new is None:
                    raise AssertionError(f"{thm.name}: gold prefix {thm.gold[:i]!r} no longer replays")
                return new

            def run(tactic: str):
                """`repl.tactic` at the current gold state; None if it timed out (REPL restarted)."""
                nonlocal ps
                res = repl.tactic(tactic, ps)
                if _is_stale(res.error):
                    ps = fresh()
                    res = repl.tactic(tactic, ps)
                if _is_timeout(res.error) or _is_stale(res.error):
                    ps = fresh()
                    return None
                return res

            items = menu(goal, True)
            extras = llm_options(generator.propose(goal, prelude=thm.prelude), items)
            first_done: str | None = None
            gold_opt: str | None = None
            for opt, tactic in extras.items():
                if gold_opt is None and _key(tactic) == _key(step):
                    gold_opt = opt
                res = run(tactic)
                if res is None:
                    binary.append(BinaryExample("useful", goal, opt, False))
                    continue
                changed = bool(res.goals) and _key(res.goals[0]) != _key(goal)
                useful = bool(res.ok and (res.completed or changed))
                binary.append(BinaryExample("useful", goal, opt, useful))
                if res.ok and res.completed and first_done is None:
                    first_done = opt
            kinds = items + TEMPLATES + tuple(extras)
            gold_kind, _ = parse_action(step)
            if gold_opt is not None:
                choice.append(ChoiceExample("kind", goal, kinds, gold_opt))
            elif gold_kind in kinds:
                choice.append(ChoiceExample("kind", goal, kinds, gold_kind))
            if first_done is not None and first_done != gold_opt:
                choice.append(ChoiceExample("kind", goal, kinds, first_done))
            res = run(step)
            if res is None or not res.ok:
                err = "timeout" if res is None else res.error
                raise AssertionError(f"{thm.name}: gold step {step!r} failed: {err}")
            ps, goal = res.proof_state, (res.goals[0] if res.goals else "")
        if out_path is not None:
            save_labels(out_path, choice, binary)
    return choice, binary


def trace_labels(result, proposals: dict[str, list[str]]) -> tuple[list[ChoiceExample], list[BinaryExample]]:
    """Labels from one `claude_search` run (no gold proof needed, so this works on the core
    benchmark's training split).

    `result` is the SearchResult and `proposals` maps goal key -> Claude's proposals at that goal
    (`HybridRanker._proposals`). Every Claude proposal the search tried gives a `useful` example:
    True iff Lean accepted it and it closed or changed the goal (outcome ok, proved or
    duplicate). If the theorem was proved, each state on the final proof path gives a `kind`
    example whose gold is the step taken there (as an `llm|i|...` option when it came from
    Claude, else its menu/template kind)."""
    choice: list[ChoiceExample] = []
    binary: list[BinaryExample] = []

    def options(goal: str) -> tuple[tuple[str, ...], dict[str, str]]:
        items = menu(goal, True)
        extras = llm_options(proposals.get(_key(goal), []), items)
        return items + TEMPLATES + tuple(extras), {t: o for o, t in extras.items()}

    for e in result.trace:
        _, by_tactic = options(e["goal"])
        opt = by_tactic.get(e["chosen"].strip())
        if opt is not None and e["outcome"] in ("ok", "proved", "duplicate", "error", "rejected"):
            binary.append(BinaryExample("useful", e["goal"], opt, e["outcome"] in ("ok", "proved", "duplicate")))
    if result.proved and result.trace:
        goal = result.trace[0]["goal"]
        for step in result.tactics:
            hit = next((e for e in result.trace if _key(e["goal"]) == _key(goal)
                        and e["chosen"] == step and e["outcome"] in ("ok", "proved")), None)
            if hit is None:
                break
            kinds, by_tactic = options(goal)
            gold = by_tactic.get(step.strip()) or parse_action(step)[0]
            if gold in kinds:
                choice.append(ChoiceExample("kind", goal, kinds, gold))
            if hit["outcome"] == "proved" or hit["next_goal"] is None:
                break
            goal = hit["next_goal"]
    return choice, binary
