import json

import pytest

from jev_demo.minif2f import (Bm25Premises, closes_labels, is_premise_step, load, menu_only_labels,
                              premise_steps)
from jev_demo.theorems import Theorem


def test_load_parses_binders_and_drops_comments(tmp_path):
    d = tmp_path / "MiniF2F" / "Valid"
    d.mkdir(parents=True)
    head = "import Mathlib\n\nset_option maxHeartbeats 0\n\nopen BigOperators Real Nat Topology Rat\n\n"
    (d / "a.lean").write_text(head + "theorem a (x : ℕ) -- note\n  (h : x = 1) : x + 1 = 2 := by sorry", encoding="utf-8")
    (d / "b.lean").write_text(head + "theorem b : 2 + 2 = 4 := by sorry", encoding="utf-8")
    header, thms = load(str(tmp_path), "valid")
    assert "maxHeartbeats 200000" in header and "open BigOperators" in header
    assert [t.statement for t in thms] == ["(x : ℕ) (h : x = 1) : x + 1 = 2", ": 2 + 2 = 4"]


def test_premise_steps():
    assert premise_steps([]) == []
    s = premise_steps(["Nat.add_comm", "Nat.mul_comm", "a", "b", "c"])
    assert s[0] == "simp [Nat.add_comm, Nat.mul_comm, a, b]" and s[-1] == "rw [Nat.mul_comm]"


def test_menu_only_labels_drop_premise_steps(tmp_path):
    from jev_demo.collect import BinaryExample, load_labels, save_labels
    steps = premise_steps(["Nat.add_comm", "Nat.mul_comm"])
    assert all(is_premise_step(t) for t in steps)
    menu = ["simp [*] at *", "norm_num [*] at *", "simp", "induction n <;> grind"]
    assert not any(is_premise_step(t) for t in menu)
    src, dst = tmp_path / "a.json", tmp_path / "b.json"
    save_labels(str(src), [], [BinaryExample("closes", "s", t, False) for t in steps + menu])
    assert menu_only_labels(str(src), str(dst)) == len(menu)
    assert [b.option for b in load_labels(str(dst))[1]] == menu


def test_bm25_premises_restricted_to_existing_names():
    names = {"Nat.add_comm", "Nat.mul_comm"}
    b = Bm25Premises(names)
    assert {p.full_name for p in b.premises} <= names
    assert set(b.shortlist("a b : ℕ\n⊢ a + b = b + a", k=2)) <= names


@pytest.mark.lean
def test_closes_labels_on_core_goals(repl):
    thms = [Theorem("t", "∀ n : Nat, n + 0 = n", "", (), "hard")]
    labels = closes_labels(repl, thms, max_states=2, log=lambda m: None)
    assert labels and any(b.label for b in labels) and all(b.question == "closes" for b in labels)
