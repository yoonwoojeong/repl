import os

import pytest

from jev_demo.actions import parse_action
from jev_demo.premises import Lemma, Shortlister, dump_library, make_lemma, option_text, shortlist_recall
from jev_demo.theorems import DATA_DIR, load_theorems


def _lib():
    return [
        make_lemma("gcd_succ", "gcd n (n+1) = 1"),
        make_lemma("length_append", "(a ++ b).length = a.length + b.length"),
        make_lemma("Nat.add_comm", "∀ (n m : Nat), n + m = m + n"),
    ]


def test_shortlist_prefers_overlapping_lemma():
    sl = Shortlister(_lib())
    assert sl.shortlist("n : Nat ⊢ Nat.gcd n (n + 1) = 1")[0] == "gcd_succ"


def test_shortlist_size_and_determinism():
    lib = [make_lemma(f"L.lemma{i}", f"f{i % 5} x = g{i % 3} y") for i in range(60)]
    sl = Shortlister(lib)
    goal = "x : Nat ⊢ f1 x = g2 y"
    a = sl.shortlist(goal)
    assert len(a) == 16 and len(set(a)) == 16
    assert a == Shortlister(list(reversed(lib))).shortlist(goal) == sl.shortlist(goal)
    assert len(sl.shortlist(goal, k=5)) == 5
    assert len(Shortlister(lib[:3]).shortlist(goal)) == 3


def test_idf_downweights_ubiquitous_tokens():
    lib = [make_lemma(f"Nat.l{i}", "Nat = x") for i in range(20)] + [make_lemma("Nat.g", "gcd = y")]
    sl = Shortlister(lib)
    assert sl.idf["Nat"] < sl.idf["gcd"]
    assert sl.idf["="] < sl.idf["gcd"]


def test_option_text_and_dot_notation():
    lem = make_lemma("List.reverse_reverse", "l.reverse.reverse = l")
    assert option_text(lem) == "List.reverse_reverse : l.reverse.reverse = l"
    assert {"List", "reverse_reverse", "reverse"} <= lem.tokens
    sl = Shortlister([lem, make_lemma("Nat.zero_add", "0 + n = n")])
    assert sl.shortlist("l : List Nat ⊢ l.reverse = l", k=1) == ("List.reverse_reverse",)


def test_operators_map_to_name_words():
    lib = [
        make_lemma("List.length_append", "(a ++ b).length = a.length + b.length"),
        make_lemma("Nat.mul_add", "∀ (n m k : Nat), n * (m + k) = n * m + n * k"),
        make_lemma("Nat.zero_lt_succ", "0 < succ n"),
    ]
    sl = Shortlister(lib)
    assert sl.shortlist("a b c : Nat ⊢ a * (b + c) = a * b + a * c")[0] == "Nat.mul_add"
    assert {"Nat", "mul", "add"} <= make_lemma("Nat.mul_add", "x").tokens


def test_shortlist_recall_basic():
    sl = Shortlister(_lib())
    ex = [("⊢ gcd n (n+1) = 1", "gcd_succ"), ("⊢ a", "missing")]
    assert shortlist_recall(sl, ex) == 0.5
    assert shortlist_recall(sl, []) == 0.0


@pytest.fixture(scope="module")
def library(repl):
    # cache lives under data/; tests must not rewrite a committed cache
    return dump_library(repl)


@pytest.mark.lean
def test_dump_contains_core_lemmas(library):
    names = {l.name for l in library}
    assert {"Nat.add_comm", "List.length_append", "List.map_map"} <= names
    assert not any("match_" in n for n in names)
    assert all(isinstance(l, Lemma) and l.type for l in library)


@pytest.mark.lean
def test_dumped_names_elaborate(repl, library):
    ps, _ = repl.start_theorem("∀ a b : Nat, a + b = b + a")
    r = repl.tactic("intro a b", ps)
    assert repl.tactic("rw [Nat.add_comm]", r.proof_state).ok
    # a deterministic sample of dumped names must all be referable
    sample = [l.name for l in library][:: max(1, len(library) // 40)]
    for n in sample:
        res = repl.command(f"#check @{n}")
        assert not any(m.get("severity") == "error" for m in res.get("messages", [])), n


@pytest.mark.lean
def test_bad_premise_is_plain_failure(repl):
    ps, _ = repl.start_theorem("∀ a b : Nat, a + b = b + a")
    r = repl.tactic("intro a b", ps)
    res = repl.tactic("rw [Nat.nonexistent]", r.proof_state)
    assert res.ok is False


@pytest.mark.lean
def test_train_shortlist_recall_reported(repl, library):
    sl = Shortlister(library)
    examples = []
    for thm in load_theorems(os.path.join(DATA_DIR, "train.json")):
        ps, goal = repl.start_theorem(thm.statement, thm.prelude)
        for step in thm.gold:
            _, premise = parse_action(step)
            if premise is not None:
                examples.append((goal, premise))
            res = repl.tactic(step, ps)
            assert res.ok, (thm.name, step, res.error)
            ps, goal = res.proof_state, (res.goals[0] if res.goals else "")
    recall = shortlist_recall(sl, examples)
    print(f"\ntrain shortlist recall@16: {recall:.3f} over {len(examples)} premise steps, library {len(library)}")
    assert 0.0 <= recall <= 1.0
