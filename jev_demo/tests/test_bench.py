import json

import pytest

import jev_demo.model as model_mod
from jev_demo.bench import METHODS, format_report, run_experiment
from jev_demo.premises import make_lemma
from jev_demo.repl_client import TacticResult
from jev_demo.theorems import DATA_DIR, Theorem, load_theorems


def _row(proved, easy, hard):
    return {"proved": proved, "proved_easy": easy, "proved_hard": hard,
            "mean_calls": 3.0, "mean_seconds": 0.5, "per_theorem": []}


def test_report_has_row_per_method_with_easy_hard_split():
    results = {m: _row(3, 2, 1) for m in METHODS}
    results.update({"ece": 0.1, "temperatures": {"kind": 1.5}, "shortlist_recall": 0.25,
                    "n_easy": 8, "n_hard": 12})
    text = format_report(results)
    header = next(l for l in text.splitlines() if l.startswith("|") and "method" in l)
    assert "easy" in header and "hard" in header
    for m in METHODS:
        rows = [l for l in text.splitlines() if l.startswith(f"| {m} |")]
        assert len(rows) == 1 and "2/8" in rows[0] and "1/12" in rows[0]
    assert "ECE" in text and "kind" in text and "recall" in text.lower()


class GoldRepl:
    """Follows each theorem's gold proof; every other tactic fails. Goals are derived from
    the statement, so train and test goals are distinguishable."""

    def __init__(self, theorems):
        self.by_stmt = {t.statement: t for t in theorems}
        self.states = {}

    def _new(self, thm, i):
        ps = len(self.states)
        self.states[ps] = (thm, i)
        return ps

    def start_theorem(self, statement, prelude=""):
        thm = self.by_stmt[statement]
        return self._new(thm, 0), f"⊢ {statement} @0"

    def tactic(self, tac, proof_state, timeout_s=None):
        thm, i = self.states[proof_state]
        if i < len(thm.gold) and tac == thm.gold[i]:
            last = i + 1 == len(thm.gold)
            goals = [] if last else [f"⊢ {thm.statement} @{i + 1}"]
            return TacticResult(self._new(thm, i + 1), goals, True, last, None, [])
        return TacticResult(None, [], False, False, "no", [])

    def check_proof(self, statement, tactics, prelude=""):
        return tuple(tactics[-len(self.by_stmt[statement].gold):]) == self.by_stmt[statement].gold


def test_test_set_not_used_for_training(tmp_path, monkeypatch):
    train = [Theorem(f"tr{i}", f"train{i}", "", ("intro n", "omega"), "easy") for i in range(5)]
    test = [Theorem("te0", "test0", "", ("simp",), "easy"),
            Theorem("te1", "test1", "", ("intro h", "rfl"), "hard")]
    seen = []
    real_fit = model_mod.SystemOneModel.fit

    def spy(self, choice, binary, *a, **k):
        seen.extend(e.state for e in choice)
        seen.extend(e.state for e in binary)
        return real_fit(self, choice, binary, *a, **k)

    monkeypatch.setattr(model_mod.SystemOneModel, "fit", spy)
    lib = [make_lemma("Nat.add_comm", "∀ (n m : Nat), n + m = m + n")]
    res = run_experiment(GoldRepl(train + test), train, test, str(tmp_path), library=lib)
    assert seen and all("train" in s for s in seen)
    assert not any("test" in s for s in seen)
    assert set(METHODS) <= set(res)
    assert (tmp_path / "results.json").exists() and (tmp_path / "report.md").exists()


@pytest.mark.lean
def test_end_to_end_runs(repl, tmp_path):
    train = load_theorems(f"{DATA_DIR}/train.json")[:4]
    test = load_theorems(f"{DATA_DIR}/test.json")[:2]
    res = run_experiment(repl, train, test, str(tmp_path))
    for m in METHODS:
        assert m in res and len(res[m]["per_theorem"]) == 2
    on_disk = json.loads((tmp_path / "results.json").read_text())
    assert set(METHODS) <= set(on_disk) and "ece" in on_disk
    report = (tmp_path / "report.md").read_text()
    assert all(f"| {m} |" in report for m in METHODS)


def test_expand_all_ranker_uses_top_score_as_confidence():
    from jev_demo.bench import ExpandAll
    from jev_demo.search import FixedOrderRanker
    acts, conf, value = ExpandAll(FixedOrderRanker()).rank("⊢ a")
    assert conf == acts[0][1] < 0.5 and value == 0.5
    assert [a for a, _ in acts] == [a for a, _ in FixedOrderRanker().rank("⊢ a")[0]]
