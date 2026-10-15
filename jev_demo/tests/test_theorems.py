import json
import os

import pytest

from jev_demo.actions import TEMPLATES, menu, parse_action
from jev_demo.theorems import DATA_DIR, Theorem, load_theorems

TRAIN = os.path.join(DATA_DIR, "train.json")
TEST = os.path.join(DATA_DIR, "test.json")


def _replay_in_action_space(repl, thm: Theorem) -> bool:
    """Replay the gold proof step by step; True iff every step is in menu(goal) ∪ TEMPLATES."""
    ps, goal = repl.start_theorem(thm.statement, thm.prelude)
    reachable = True
    for step in thm.gold:
        kind = parse_action(step)[0]
        if kind not in set(menu(goal)) | set(TEMPLATES):
            reachable = False
        r = repl.tactic(step, ps)
        assert r.ok, (thm.name, step, r.error)
        ps, goal = r.proof_state, (r.goals[0] if r.goals else "")
    assert r.completed, thm.name
    return reachable


def test_splits_disjoint_and_sized():
    train, test = load_theorems(TRAIN), load_theorems(TEST)
    assert len(train) == 40 and len(test) == 20
    assert sum(t.difficulty == "easy" for t in test) == 8
    assert sum(t.difficulty == "hard" for t in test) == 12
    assert sum(t.difficulty == "easy" for t in train) == 30
    assert not {t.statement for t in train} & {t.statement for t in test}
    names = [t.name for t in train + test]
    assert len(names) == len(set(names))
    assert all(isinstance(t.gold, tuple) and t.gold for t in train + test)


@pytest.mark.lean
def test_every_gold_proof_checks(repl):
    failed = [t.name for t in load_theorems(TRAIN) + load_theorems(TEST)
              if not repl.check_proof(t.statement, list(t.gold), t.prelude)]
    assert failed == []


@pytest.mark.lean
def test_every_train_gold_step_is_in_action_space(repl):
    outside = [t.name for t in load_theorems(TRAIN) if not _replay_in_action_space(repl, t)]
    assert outside == []


@pytest.mark.lean
def test_menu_reachable_flags_written(repl):
    flags = {t.name: _replay_in_action_space(repl, t) for t in load_theorems(TEST)}
    with open(os.path.join(DATA_DIR, "test_reachability.json"), "w") as f:
        json.dump(flags, f, indent=2, ensure_ascii=False)
        f.write("\n")
    assert len(flags) == 20
