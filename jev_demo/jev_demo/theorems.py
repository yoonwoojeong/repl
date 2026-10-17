"""Train/test theorem sets with checked gold proofs."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Literal

from jev_demo.actions import in_action_space

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


@dataclass(frozen=True)
class Theorem:
    name: str
    statement: str
    prelude: str
    gold: tuple[str, ...]
    difficulty: Literal["easy", "hard"]
    banned: tuple[str, ...] = ()  # constants a proof may not use directly (core benchmark)


def load_theorems(path: str) -> list[Theorem]:
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    # Core-benchmark rows (`corebench`) have no gold proof and name the lemma they restate,
    # which a proof may not use.
    return [
        Theorem(r["name"], r["statement"], r.get("prelude", ""), tuple(r.get("gold", ())),
                r.get("difficulty", "hard"), tuple(r.get("banned", [r["lemma"]] if "lemma" in r else [])))
        for r in rows
    ]


def replay_in_action_space(repl, thm: Theorem) -> bool:
    """Replay the gold proof step by step; True iff every step is in the action space at its goal.

    Raises AssertionError if a gold step fails or the proof does not complete.
    """
    ps, goal = repl.start_theorem(thm.statement, thm.prelude)
    reachable, result = True, None
    for step in thm.gold:
        reachable &= in_action_space(step, goal)
        result = repl.tactic(step, ps)
        if not result.ok:
            raise AssertionError(f"{thm.name}: gold step {step!r} failed: {result.error}")
        ps, goal = result.proof_state, (result.goals[0] if result.goals else "")
    if result is None or not result.completed:
        raise AssertionError(f"{thm.name}: gold proof does not complete")
    return reachable


def reachability_path(test_path: str) -> str:
    """`data/test.json` -> `data/test_reachability.json` (same for any other test set)."""
    return os.path.splitext(test_path)[0] + "_reachability.json"


def write_reachability(repl, test_path: str, out_path: str) -> dict[str, bool]:
    """Write `{name: menu_reachable}` for the theorems in `test_path` to `out_path`."""
    flags = {t.name: replay_in_action_space(repl, t) for t in load_theorems(test_path)}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(flags, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return flags


if __name__ == "__main__":
    if sys.argv[1:2] != ["--write-reachability"] or len(sys.argv) > 3:
        sys.exit("usage: python -m jev_demo.theorems --write-reachability [TEST_JSON]")
    from jev_demo.repl_client import ReplClient

    test_path = sys.argv[2] if len(sys.argv) == 3 else os.path.join(DATA_DIR, "test.json")
    with ReplClient() as client:
        flags = write_reachability(client, test_path, reachability_path(test_path))
    print(f"{sum(flags.values())}/{len(flags)} test theorems menu-reachable")
