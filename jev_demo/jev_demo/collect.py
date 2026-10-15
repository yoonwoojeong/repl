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
from jev_demo.search import _key
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

    `shortlister` and `lib` are accepted for symmetry with `replay` (the premise/near_done
    examples still come from phase-1 replay). Raises AssertionError if a gold step fails.
    """
    choice: list[ChoiceExample] = []
    binary: list[BinaryExample] = []
    for thm in train:
        ps, goal = repl.start_theorem(thm.statement, thm.prelude)
        for step in thm.gold:
            items = menu(goal, True)
            extras = llm_options(generator.propose(goal, prelude=thm.prelude), items)
            first_done: str | None = None
            for opt, tactic in extras.items():
                res = repl.tactic(tactic, ps)
                changed = bool(res.goals) and _key(res.goals[0]) != _key(goal)
                useful = bool(res.ok and (res.completed or changed))
                binary.append(BinaryExample("useful", goal, opt, useful))
                if res.ok and res.completed and first_done is None:
                    first_done = opt
            kinds = items + TEMPLATES + tuple(extras)
            gold_kind, _ = parse_action(step)
            if gold_kind in kinds:
                choice.append(ChoiceExample("kind", goal, kinds, gold_kind))
            if first_done is not None:
                choice.append(ChoiceExample("kind", goal, kinds, first_done))
            res = repl.tactic(step, ps)
            if not res.ok:
                raise AssertionError(f"{thm.name}: gold step {step!r} failed: {res.error}")
            ps, goal = res.proof_state, (res.goals[0] if res.goals else "")
    if out_path is not None:
        save_labels(out_path, choice, binary)
    return choice, binary
