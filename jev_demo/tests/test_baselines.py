from jev_demo.baselines import single_shot
from jev_demo.repl_client import TacticResult
from jev_demo.theorems import Theorem

THM = Theorem("t", "∀ n : Nat, n = n", "", ("intro n", "rfl"), "hard")


def R(goals=(), ok=True, completed=False, ps=1, infos=()):
    return TacticResult(ps, list(goals), ok, completed, None if ok else "boom", list(infos))


class FakeRepl:
    def __init__(self, script):
        self.script, self.calls, self.checked = script, [], []

    def start_theorem(self, statement, prelude=""):
        return 0, "⊢ ∀ n : Nat, n = n"

    def tactic(self, tac, proof_state, timeout_s=None):
        self.calls.append((proof_state, tac, timeout_s))
        return self.script.get((proof_state, tac), R(ok=False))

    def check_proof(self, statement, tactics, prelude=""):
        self.checked.append(list(tactics))
        return True


def test_single_shot_follows_try_this_once():
    repl = FakeRepl({
        (0, "intros"): R(["n✝ : Nat\n⊢ n✝ = n✝"], ps=1),
        (1, "try?"): R(["n✝ : Nat\n⊢ n✝ = n✝"], ps=2, infos=["Try this: omega"]),
        (1, "omega"): R(completed=True, ps=3),
    })
    r = single_shot(THM, repl, "try?", 60)
    assert r.proved and r.calls == 2
    assert r.tactics == ["intros", "omega"] and repl.checked == [["intros", "omega"]]
    assert (1, "try?", 60) in repl.calls


def test_single_shot_suggestion_alone_is_not_success():
    repl = FakeRepl({
        (0, "intros"): R(["n✝ : Nat\n⊢ n✝ = n✝"], ps=1),
        (1, "try?"): R(["n✝ : Nat\n⊢ n✝ = n✝"], ps=2, infos=["Try this: omega"]),
        (1, "omega"): R(ok=False),
    })
    r = single_shot(THM, repl, "try?", 60)
    assert not r.proved and r.calls == 2 and repl.checked == []
