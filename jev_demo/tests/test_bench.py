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

    real_cal = model_mod.SystemOneModel.calibrate

    def spy_cal(self, examples, *a, **k):
        seen.extend(e.state for e in examples)
        return real_cal(self, examples, *a, **k)

    monkeypatch.setattr(model_mod.SystemOneModel, "fit", spy)
    monkeypatch.setattr(model_mod.SystemOneModel, "calibrate", spy_cal)
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


def _results(model_hard, supp_hard):
    from jev_demo.bench import SUPPLEMENTARY
    res = {m: _row(3, 2, 1) for m in METHODS}
    res["model"] = _row(model_hard, 0, model_hard)
    res["try_only"] = _row(model_hard - 1, 0, model_hard - 1)
    res.update({m: _row(supp_hard, 0, supp_hard) for m in SUPPLEMENTARY})
    res.update({"ece": 0.1, "temperatures": {"kind": 1.5}, "shortlist_recall": 0.25,
                "n_easy": 8, "n_hard": 12})
    return res


def test_report_qualifies_success_when_supplementary_beats_model():
    text = format_report(_results(8, 10))
    assert "met nominally (8 vs 7)" in text
    assert "does not beat exhaustive" in text and "does not show that the model helps" in text
    assert "**met**" not in text
    plain = format_report(_results(8, 8))
    assert "**met**" in plain and "does not show that the model helps" not in plain


def test_rerender_report_from_results_json(tmp_path):
    from jev_demo.bench import rerender_report
    (tmp_path / "results.json").write_text(json.dumps(_results(8, 10)))
    text = rerender_report(str(tmp_path))
    assert (tmp_path / "report.md").read_text() == text and "met nominally" in text


class ExplodingRepl(GoldRepl):
    """start_theorem raises for one test theorem while `explode` is set (during the method runs)."""

    explode = False

    def start_theorem(self, statement, prelude=""):
        if self.explode and statement == "test1":
            raise RuntimeError("could not start theorem 'test1'")
        return super().start_theorem(statement, prelude)


def test_exception_in_one_theorem_is_recorded_and_run_completes(tmp_path, monkeypatch):
    import jev_demo.bench as bench
    train = [Theorem(f"tr{i}", f"train{i}", "", ("intro n", "omega"), "easy") for i in range(5)]
    test = [Theorem("te0", "test0", "", ("simp",), "easy"),
            Theorem("te1", "test1", "", ("intro h", "rfl"), "hard")]
    repl = ExplodingRepl(train + test)
    real_run = bench._run_method

    def run(method, thm, r, *a):
        repl.explode = True
        return real_run(method, thm, r, *a)

    writes = []
    real_write = bench._write_results
    monkeypatch.setattr(bench, "_run_method", run)
    monkeypatch.setattr(bench, "_write_results",
                        lambda results, out_dir: (writes.append(set(results)), real_write(results, out_dir))[1])
    lib = [make_lemma("Nat.add_comm", "∀ (n m : Nat), n + m = m + n")]
    res = run_experiment(repl, train, test, str(tmp_path), library=lib)
    for m in METHODS:
        rows = {r["name"]: r for r in res[m]["per_theorem"]}
        assert set(rows) == {"te0", "te1"}
    rows = {r["name"]: r for r in res["fixed"]["per_theorem"]}
    assert rows["te1"]["proved"] is False and "could not start" in rows["te1"]["error"]
    assert rows["te1"]["difficulty"] == "hard" and "calls" in rows["te1"]
    assert len(writes) > len(METHODS)  # results.json written after each method
    assert (tmp_path / "results.json").exists() and (tmp_path / "report.md").exists()


def test_flags_criterion_met_and_beats_exhaustive():
    from jev_demo.bench import add_flags
    res = _results(8, 10)
    add_flags(res)
    assert res["criterion_met"] is True and res["beats_exhaustive_search"] is False
    assert "success" not in res
    res = _results(8, 8)
    add_flags(res)
    assert res["criterion_met"] is True and res["beats_exhaustive_search"] is False
    res = _results(8, 6)
    add_flags(res)
    assert res["beats_exhaustive_search"] is True


def test_report_renders_reachability_as_yes_no():
    res = _results(8, 8)
    for m in list(METHODS) + ["fixed_expand_all", "random_expand_all"]:
        res[m]["per_theorem"] = [{"name": "a", "difficulty": "easy", "proved": False, "calls": 1}]
    res["reachability"] = {"a": True, "b": False}
    text = format_report(res, [Theorem("a", "s", "", ("simp",), "easy")])
    line = next(l for l in text.splitlines() if l.startswith("| a |"))
    assert "| yes |" in line and "True" not in text and "False" not in text
    res["reachability"] = {"a": False}
    text = format_report(res, [Theorem("a", "s", "", ("simp",), "easy")])
    assert "| no |" in next(l for l in text.splitlines() if l.startswith("| a |"))


def test_rerender_rewrites_success_flag(tmp_path):
    from jev_demo.bench import rerender_report
    res = _results(8, 10)
    res["success"] = True
    (tmp_path / "results.json").write_text(json.dumps(res))
    rerender_report(str(tmp_path))
    out = json.loads((tmp_path / "results.json").read_text())
    assert "success" not in out and out["criterion_met"] is True
    assert out["beats_exhaustive_search"] is False
