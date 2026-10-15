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
