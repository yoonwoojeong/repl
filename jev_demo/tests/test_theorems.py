import json
import os

import pytest

from jev_demo.theorems import DATA_DIR, load_theorems, replay_in_action_space, write_reachability

TRAIN = os.path.join(DATA_DIR, "train.json")
TEST = os.path.join(DATA_DIR, "test.json")
REACHABILITY = os.path.join(DATA_DIR, "test_reachability.json")


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
    outside = [t.name for t in load_theorems(TRAIN) if not replay_in_action_space(repl, t)]
    assert outside == []


@pytest.mark.lean
def test_menu_reachable_flags_written(repl, tmp_path):
    out = tmp_path / "test_reachability.json"
    flags = write_reachability(repl, TEST, str(out))
    assert len(flags) == 20
    with open(REACHABILITY, encoding="utf-8") as f:
        assert json.load(f) == flags, "committed test_reachability.json is stale: run `python -m jev_demo.theorems --write-reachability`"
    assert out.read_text(encoding="utf-8") == open(REACHABILITY, encoding="utf-8").read()
