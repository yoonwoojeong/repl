import math

import numpy as np

from jev_demo.model import (
    BinaryExample,
    ChoiceExample,
    SystemOneModel,
    expected_calibration_error,
    featurize,
    tokenize,
)
from jev_demo.schema import BinaryQuestion, ChoiceQuestion, validate


def test_tokenize_splits_on_punctuation_and_whitespace():
    assert tokenize("n : Nat ⊢ f (a, b) · [x]") == ["n", "Nat", "f", "a", "b", "x"]
    assert tokenize("") == []


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


def _multi_data():
    opts = ("omega", "rfl")
    choice = [ChoiceExample("kind", f"n : Nat ⊢ n + {i} = {i} + n", opts, "omega") for i in range(10)] + \
             [ChoiceExample("kind", f"⊢ x{i} = x{i}", opts, "rfl") for i in range(10)]
    lem = ("Nat.gcd_succ : ∀ n, gcd n (n+1) = 1", "List.length_append : length (l ++ m) = length l + length m")
    choice += [ChoiceExample("premise", f"a : Nat ⊢ gcd a (a + {i}) = 1", lem, lem[0]) for i in range(10)]
    binary = [BinaryExample("near_done", f"⊢ x{i} = x{i}", None, True) for i in range(10)] + \
             [BinaryExample("near_done", f"n : Nat ⊢ n + {i} = {i} + n", None, False) for i in range(10)]
    return choice, binary, opts, lem


def test_one_pass_answers_three_questions():
    choice, binary, opts, lem = _multi_data()
    m = SystemOneModel(); m.fit(choice, binary, epochs=10)
    qs = [ChoiceQuestion("kind", opts), ChoiceQuestion("premise", lem), BinaryQuestion("near_done")]
    out = m.evaluate("⊢ gcd 3 4 = 1", qs)
    assert set(out) == {"kind", "premise", "near_done"}
    for q in qs:
        validate(q, out[q.name])


def test_premise_head_uses_lemma_name_tokens():
    lem = ("Nat.gcd_succ : ∀ n, gcd n (n+1) = 1", "List.length_append : length (l ++ m) = length l + length m")
    data = [ChoiceExample("premise", f"a : Nat ⊢ gcd a (a + {i}) = 1", lem, lem[0]) for i in range(10)] + \
           [ChoiceExample("premise", f"l : List Nat ⊢ length (l ++ l{i}) = 2", lem, lem[1]) for i in range(10)]
    m = SystemOneModel(); m.fit(data, [], epochs=30)
    a = m.evaluate("b : Nat ⊢ gcd b (b + 7) = 1", [ChoiceQuestion("premise", lem)])["premise"]
    assert a.probs[lem[0]] > a.probs[lem[1]]
    assert a.top == lem[0]


def _nll(m, data):
    tot = 0.0
    for ex in data:
        a = m.evaluate(ex.state, [ChoiceQuestion(ex.question, ex.options)])[ex.question]
        tot -= math.log(max(a.probs[ex.gold], 1e-12))
    return tot / len(data)


def test_calibration_temperature_reduces_nll():
    opts = ("omega", "rfl")
    # Noisy labels: 1 in 5 golds is flipped (same states, conflicting golds, so no memorising), so a confident model is overconfident.
    data = []
    for i in range(40):
        good = "omega" if i % 2 == 0 else "rfl"
        gold = good if i % 5 else ("rfl" if good == "omega" else "omega")
        state = "n : Nat ⊢ n + 1 = 1 + n" if good == "omega" else "⊢ x = x"
        data.append(ChoiceExample("kind", state, opts, gold))
    m = SystemOneModel(); m.fit(data, [], epochs=20)
    m.w *= 10.0
    before = _nll(m, data)
    temps = m.calibrate(data)
    after = _nll(m, data)
    assert after <= before
    assert temps["kind"] > 1.0
    assert 0.25 <= temps["kind"] <= 4.0
    assert 0.0 <= expected_calibration_error(m, data) <= 1.0


def test_featurize_is_deterministic():
    a = featurize("n : Nat ⊢ gcd n 1 = 1", "Nat.gcd_succ : x")
    b = featurize("n : Nat ⊢ gcd n 1 = 1", "Nat.gcd_succ : x")
    assert a == b and a
    assert all(0 <= k < 2**16 for k in a)
    assert featurize("⊢ a", None, question="kind") != featurize("⊢ a", None, question="premise")
    assert featurize("⊢ a", dim=64).keys() <= set(range(64))


def test_save_load_roundtrip(tmp_path):
    choice, binary, opts, lem = _multi_data()
    m = SystemOneModel(); m.fit(choice, binary, epochs=5); m.calibrate(choice)
    path = str(tmp_path / "m.npz")
    m.save(path)
    m2 = SystemOneModel.load(path)
    qs = [ChoiceQuestion("kind", opts), ChoiceQuestion("premise", lem), BinaryQuestion("near_done")]
    o1, o2 = m.evaluate("⊢ x = x", qs), m2.evaluate("⊢ x = x", qs)
    assert o1 == o2
    assert m2.temps == m.temps and m2.dim == m.dim
