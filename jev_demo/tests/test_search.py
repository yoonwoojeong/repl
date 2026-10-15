import pytest

from jev_demo.actions import TEMPLATES, menu
from jev_demo.model import BinaryExample, ChoiceExample, SystemOneModel
from jev_demo.premises import Shortlister, make_lemma, option_text
from jev_demo.repl_client import TacticResult
from jev_demo.search import FixedOrderRanker, ModelRanker, prove
from jev_demo.theorems import Theorem

THM = Theorem("t", "stmt", "", ("x",), "easy")
G0 = "⊢ a"
FIRST, SECOND = menu(G0)[0], menu(G0)[1]


def R(goals=(), ok=True, completed=False, ps=1):
    return TacticResult(ps, list(goals), ok, completed, None if ok else "boom", [])


class FakeRepl:
    def __init__(self, script, check=True):
        self.script, self.check, self.calls, self.checked = script, check, [], []

    def start_theorem(self, statement, prelude=""):
        return 0, G0

    def tactic(self, tac, proof_state, timeout_s=None):
        self.calls.append((proof_state, tac))
        return self.script.get((proof_state, tac), R(ok=False))

    def check_proof(self, statement, tactics, prelude=""):
        self.checked.append(list(tactics))
        return self.check


class StubRanker:
    def __init__(self, confidence=1.0, n=5):
        self.confidence, self.n = confidence, n

    def rank(self, goal):
        acts = [(f"t{i}", 1.0 / self.n) for i in range(self.n)]
        return acts, self.confidence, 0.5


def test_fixed_order_proves_one_step():
    repl = FakeRepl({(0, FIRST): R(completed=True)})
    r = prove(THM, repl, FixedOrderRanker())
    assert r.proved and r.tactics == [FIRST] and r.calls == 1 and r.escalations == 0
    assert r.trace[-1]["outcome"] == "proved"


def test_error_with_empty_goals_is_not_success():
    repl = FakeRepl({(0, FIRST): R(goals=(), ok=False, completed=False)})
    r = prove(THM, repl, FixedOrderRanker(), budget=1)
    assert not r.proved and repl.checked == []


def test_dedup_same_goal_reached_twice():
    repl = FakeRepl({(0, FIRST): R(["⊢ b"], ps=1), (0, SECOND): R(["⊢  b"], ps=2)})
    r = prove(THM, repl, FixedOrderRanker(), budget=len(menu(G0)) + 1, top_k=len(menu(G0)))
    assert not r.proved
    assert [t for t in r.trace if t["outcome"] == "duplicate"]
    assert not any(ps == 2 for ps, _ in repl.calls)  # the duplicate was never expanded


def test_budget_exhaustion_returns_unproved():
    class Loop(FakeRepl):
        n = 0
        def tactic(self, tac, proof_state, timeout_s=None):
            self.calls.append((proof_state, tac))
            Loop.n += 1
            return R([f"⊢ g{Loop.n}"], ps=Loop.n)
    r = prove(THM, Loop({}), FixedOrderRanker(), budget=7, max_depth=50)
    assert not r.proved and r.calls == 7


def test_escalation_expands_all_when_low_confidence():
    repl = FakeRepl({})
    r = prove(THM, repl, StubRanker(confidence=0.3, n=5), budget=100, top_k=1)
    assert r.calls == 5 and r.escalations == 1


def test_high_confidence_expands_top_k_only():
    repl = FakeRepl({})
    r = prove(THM, repl, StubRanker(confidence=0.9, n=5), budget=100, top_k=2)
    assert r.calls == 2 and r.escalations == 0


def test_final_proof_rechecked():
    repl = FakeRepl({(0, FIRST): R(completed=True)}, check=False)
    r = prove(THM, repl, FixedOrderRanker(), budget=3)
    assert not r.proved and repl.checked == [[FIRST]]


def _tiny_model():
    lib = [make_lemma("Nat.add_comm", "∀ n m : Nat, n + m = m + n"),
           make_lemma("List.length_append", "length (l ++ m) = length l + length m"),
           make_lemma("Nat.mul_comm", "∀ n m : Nat, n * m = m * n")]
    goal = "n m : Nat ⊢ n + m = m + n"
    kinds = menu(goal) + TEMPLATES
    prem = tuple(option_text(l) for l in lib)
    m = SystemOneModel()
    m.fit([ChoiceExample("kind", goal, kinds, "rw [·]"), ChoiceExample("premise", goal, prem, prem[0])] * 5,
          [BinaryExample("near_done", goal, None, False)] * 5, epochs=5)
    return m, lib, goal


def test_model_ranker_scores_sum_to_one_and_include_filled_templates():
    m, lib, goal = _tiny_model()
    ranker = ModelRanker(m, Shortlister(lib), {l.name: l for l in lib})
    actions, conf, value = ranker.rank(goal)
    assert sum(s for _, s in actions) == pytest.approx(1.0)
    assert [s for _, s in actions] == sorted((s for _, s in actions), reverse=True)
    assert conf == actions[0][1] and 0.0 <= value <= 1.0
    names = [a for a, _ in actions]
    assert len(set(names)) == len(names)
    assert any(a.startswith("rw [") and "Nat.add_comm" in a for a in names)
    assert "exact Nat.add_comm" in names


def test_model_ranker_without_premises_has_no_templates():
    m, lib, goal = _tiny_model()
    ranker = ModelRanker(m, Shortlister(lib), {l.name: l for l in lib}, premises=False)
    actions, _, _ = ranker.rank(goal)
    assert {a for a, _ in actions} == set(menu(goal))
    assert sum(s for _, s in actions) == pytest.approx(1.0)


@pytest.mark.lean
def test_fixed_order_proves_trivial_real_theorem(repl):
    thm = Theorem("triv", "∀ n : Nat, n + 0 = n", "", ("intro n", "rfl"), "easy")
    r = prove(thm, repl, FixedOrderRanker(), budget=64)
    assert r.proved and r.calls <= 64
    assert repl.check_proof(thm.statement, r.tactics)
