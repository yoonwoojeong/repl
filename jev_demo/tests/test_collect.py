import pytest

from jev_demo.actions import TEMPLATES, menu
from jev_demo.collect import collect, load_labels
from jev_demo.premises import Shortlister
from jev_demo.repl_client import TacticResult
from jev_demo.theorems import Theorem

G0, G1 = "⊢ a", "⊢ b"
GOLD = menu(G0)[0]
THM = Theorem("t", "stmt", "pre", (GOLD,), "easy")


def R(goals=(), ok=True, completed=False, ps=1):
    return TacticResult(ps, list(goals), ok, completed, None if ok else "boom", [])


class FakeRepl:
    def __init__(self, script):
        self.script, self.calls = script, []

    def start_theorem(self, statement, prelude=""):
        return 0, G0

    def tactic(self, tac, proof_state, timeout_s=None):
        self.calls.append((proof_state, tac))
        return self.script.get((proof_state, tac), R(ok=False))


class FakeGen:
    def __init__(self, props):
        self.props, self.calls = props, []

    def propose(self, goal, prelude="", failed=()):
        self.calls.append((goal, prelude))
        return list(self.props)


def run(script, props, tmp_path, name="labels.json"):
    repl, gen = FakeRepl(script), FakeGen(props)
    out = collect([THM], repl, gen, Shortlister([]), {}, out_path=str(tmp_path / name))
    return out, repl, gen


SCRIPT = {
    (0, "good"): R([G1], ps=2),       # changes the goal -> useful
    (0, "same"): R([G0], ps=3),       # ok but goal unchanged -> not useful
    (0, "done"): R(completed=True),   # completes -> useful
    (0, "done2"): R(completed=True),
    (0, GOLD): R([G1], ps=9),
}


def test_collect_labels_useful_and_completed_proposals(tmp_path):
    (choice, binary), repl, gen = run(SCRIPT, ["good", "same", "bad", "done", "done2"], tmp_path)
    assert gen.calls == [(G0, "pre")]
    labels = {b.option: b.label for b in binary if b.question == "useful"}
    assert labels == {"llm|0|good": True, "llm|1|same": False, "llm|2|bad": False,
                      "llm|3|done": True, "llm|4|done2": True}
    assert all(b.state == G0 for b in binary)
    ran = [t for _, t in repl.calls]
    assert all(t in ran for t in ("good", "same", "bad", "done", "done2")) and ran.count("good") == 1
    kinds = [c for c in choice if c.question == "kind"]
    assert len(kinds) == 2
    first, second = kinds
    assert first.gold == GOLD
    assert set(first.options) == set(menu(G0)) | set(TEMPLATES) | {f"llm|{i}|{t}" for i, t in
                                                                   enumerate(["good", "same", "bad", "done", "done2"])}
    assert second.gold == "llm|3|done"  # the first proposal that completed the goal
    assert second.options == first.options


def test_no_second_example_without_completion(tmp_path):
    (choice, _), _, _ = run(SCRIPT, ["good"], tmp_path)
    assert len(choice) == 1


def test_collect_saves_and_reloads_labels(tmp_path):
    (choice, binary), _, _ = run(SCRIPT, ["good", "done"], tmp_path)
    c2, b2 = load_labels(str(tmp_path / "labels.json"))
    assert c2 == choice and b2 == binary
    assert all(isinstance(c.options, tuple) for c in c2)
    assert load_labels(str(tmp_path / "missing.json")) == ([], [])


# -- I1: a proposal that times out restarts the REPL ------------------------------------------

G2 = "⊢ c"
STEP2 = "exact foo"
THM2 = Theorem("t2", "stmt2", "", (GOLD, STEP2), "easy")
BAD = Theorem("bad", "stmt-bad", "", ("nope",), "easy")


class RestartingRepl:
    """States are (epoch, statement, path). `slow` times out and bumps the epoch, so every
    earlier proof state becomes invalid, as in the real ReplClient after a restart."""

    STEPS = {
        (): {GOLD: ([G1], False), "good": ([G1], False), "done": ([], True)},
        (GOLD,): {STEP2: ([], True), "good": ([G2], False), "same": ([G1], False)},
    }

    def __init__(self):
        self.epoch, self.states, self.calls, self.starts = 0, {}, [], 0

    def _new(self, stmt, path):
        self.states[len(self.states)] = (self.epoch, stmt, path)
        return len(self.states) - 1

    def start_theorem(self, statement, prelude=""):
        self.starts += 1
        return self._new(statement, ()), G0

    def tactic(self, tac, proof_state, timeout_s=None):
        self.calls.append((proof_state, tac))
        epoch, stmt, path = self.states[proof_state]
        if epoch != self.epoch:
            return TacticResult(None, [], False, False, "invalid proof state (REPL was restarted)", [])
        if tac == "slow":
            self.epoch += 1
            return TacticResult(None, [], False, False, "timeout", [])
        hit = self.STEPS.get(path, {}).get(tac)
        if hit is None:
            return R(ok=False)
        goals, completed = hit
        return TacticResult(self._new(stmt, path + (tac,)), goals, True, completed, None, [])


def test_timed_out_proposal_is_false_and_later_proposals_use_a_fresh_state(tmp_path):
    repl, gen = RestartingRepl(), FakeGen(["slow", "good", "done", "same"])
    path = tmp_path / "labels.json"
    choice, binary = collect([THM2], repl, gen, Shortlister([]), {}, out_path=str(path))
    by_state = {}
    for b in binary:
        by_state.setdefault(b.state, {})[b.option] = b.label
    assert by_state[G0] == {"llm|0|slow": False, "llm|1|good": True, "llm|2|done": True,
                            "llm|3|same": False}
    # at G1 the state is re-derived by replaying the gold prefix, so `good` is labelled correctly
    assert by_state[G1] == {"llm|0|slow": False, "llm|1|good": True, "llm|2|done": False,
                            "llm|3|same": False}
    assert repl.starts == 3  # initial + one re-derivation per timeout
    assert path.exists() and load_labels(str(path)) == (choice, binary)


def test_labels_saved_after_each_theorem_survive_a_later_exception(tmp_path):
    path = tmp_path / "labels.json"
    with pytest.raises(AssertionError, match="gold step"):
        collect([THM2, BAD], RestartingRepl(), FakeGen(["good"]), Shortlister([]), {}, out_path=str(path))
    choice, binary = load_labels(str(path))
    assert binary and all(b.state in (G0, G1) for b in binary)
    assert any(c.gold == GOLD for c in choice)


# -- I2: a proposal identical to the gold step ---------------------------------------------------

RW = "rw [Nat.add_comm]"
THM_RW = Theorem("trw", "stmt", "", (RW,), "easy")


def test_proposal_equal_to_gold_is_the_kind_gold(tmp_path):
    script = {(0, RW): R(completed=True), (0, "rw  [Nat.add_comm]"): R(completed=True)}
    repl, gen = FakeRepl(script), FakeGen(["simp_all [foo]", "rw  [Nat.add_comm]"])
    choice, _ = collect([THM_RW], repl, gen, Shortlister([]), {}, out_path=str(tmp_path / "l.json"))
    kinds = [c for c in choice if c.question == "kind"]
    # the template example `rw [·]` is replaced: it would train against the correct proposal
    assert [c.gold for c in kinds] == ["llm|1|rw  [Nat.add_comm]"]
    assert "rw [·]" in kinds[0].options


def test_trace_labels_from_a_search_run():
    from jev_demo.collect import trace_labels
    from jev_demo.search import SearchResult
    g0, g1 = "n : Nat\n⊢ P n", "n : Nat\n⊢ Q n"
    trace = [
        {"goal": g0, "chosen": "bad_tac", "outcome": "error", "next_goal": None},
        {"goal": g0, "chosen": "induction n", "outcome": "ok", "next_goal": g1},
        {"goal": g1, "chosen": "omega", "outcome": "proved", "next_goal": None},
    ]
    r = SearchResult(True, ["induction n", "omega"], 3, 0, 0.1, trace)
    choice, binary = trace_labels(r, {"n : Nat ⊢ P n": ["bad_tac", "induction n"]})
    assert [(b.option, b.label) for b in binary] == [("llm|0|bad_tac", False), ("llm|1|induction n", True)]
    assert [c.gold for c in choice] == ["llm|1|induction n", "omega"]
    assert all(c.gold in c.options for c in choice)


def test_trace_labels_unproved_gives_only_useful_examples():
    from jev_demo.collect import trace_labels
    from jev_demo.search import SearchResult
    g0 = "⊢ P"
    r = SearchResult(False, [], 1, 0, 0.1, [{"goal": g0, "chosen": "x", "outcome": "error", "next_goal": None}])
    choice, binary = trace_labels(r, {"⊢ P": ["x"]})
    assert choice == [] and [b.label for b in binary] == [False]
