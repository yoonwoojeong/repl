from jev_demo.actions import TEMPLATES, menu
from jev_demo.dataset import replay
from jev_demo.premises import Shortlister, make_lemma, option_text
from jev_demo.repl_client import TacticResult
from jev_demo.theorems import Theorem

GOALS = ["a b : Nat\n⊢ a * b = b * a", "⊢ x", "⊢ y"]


class ScriptRepl:
    """Gold step i at proof state i leads to state i+1 with goal GOALS[i+1]; the last step completes."""

    def __init__(self, gold):
        self.gold = gold

    def start_theorem(self, statement, prelude=""):
        return 0, GOALS[0]

    def tactic(self, tac, proof_state, timeout_s=None):
        assert tac == self.gold[proof_state]
        last = proof_state == len(self.gold) - 1
        goals = [] if last else [GOALS[proof_state + 1]]
        return TacticResult(proof_state + 1, goals, True, last, None, [])


def _lib():
    lems = [make_lemma("Nat.mul_comm", "∀ (n m : Nat), n * m = m * n"),
            make_lemma("List.length_nil", "[].length = 0")]
    return lems, {l.name: l for l in lems}


def test_replay_labels_kind_and_premise():
    lems, lib = _lib()
    thm = Theorem("t", "s", "", ("rw [Nat.mul_comm]",), "easy")
    choice, binary = replay(thm, ScriptRepl(thm.gold), Shortlister(lems), lib)
    kind = [e for e in choice if e.question == "kind"]
    prem = [e for e in choice if e.question == "premise"]
    assert len(kind) == 1 and kind[0].gold == "rw [·]"
    assert kind[0].options == menu(GOALS[0], True) + TEMPLATES and kind[0].state == GOALS[0]
    assert len(prem) == 1 and prem[0].gold == option_text(lib["Nat.mul_comm"])
    assert prem[0].options == tuple(option_text(lib[n]) for n in Shortlister(lems).shortlist(GOALS[0]))


def test_replay_counts_recall_miss_when_premise_not_shortlisted():
    lems, lib = _lib()
    thm = Theorem("t", "s", "", ("rw [Nat.not_in_library]",), "easy")
    stats = {}
    choice, _ = replay(thm, ScriptRepl(thm.gold), Shortlister(lems), lib, stats=stats)
    assert not [e for e in choice if e.question == "premise"]
    assert [e.gold for e in choice if e.question == "kind"] == ["rw [·]"]
    assert stats["premise_steps"] == 1 and stats["premise_hits"] == 0


def test_replay_near_done_labels():
    lems, lib = _lib()
    thm = Theorem("t", "s", "", ("simp", "omega", "rfl"), "easy")
    _, binary = replay(thm, ScriptRepl(thm.gold), Shortlister(lems), lib)
    assert [(b.question, b.state, b.option, b.label) for b in binary] == [
        ("near_done", GOALS[0], None, False),
        ("near_done", GOALS[1], None, True),
        ("near_done", GOALS[2], None, True),
    ]
