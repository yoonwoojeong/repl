import json
import os

import pytest

import jev_demo.model as model_mod
from jev_demo.bench import (CALL_CAP, PHASE2_METHODS, _MeteredGen, format_report_phase2,
                            phase2_questions, run_phase2)
from jev_demo.claude_gen import Usage
from jev_demo.collect import save_labels
from jev_demo.model import BinaryExample, ChoiceExample
from jev_demo.premises import make_lemma
from jev_demo.theorems import Theorem
from test_bench import GoldRepl

LIB = [make_lemma("Nat.add_comm", "∀ (n m : Nat), n + m = m + n")]
TRAIN = [Theorem(f"tr{i}", f"train{i}", "", ("intro n", "omega"), "easy") for i in range(5)]
TEST = [Theorem("te0", "test0", "", ("simp",), "easy"),
        Theorem("te1", "test1", "", ("intro h", "rfl"), "hard"),
        Theorem("te2", "test2", "", ("intro h", "exact h"), "hard")]


class FakeGen:
    """Offline stand-in for ClaudeGenerator: knows the gold proof of every test theorem, and of
    only those named in `solves`; bills `price` USD per request that is not already cached."""

    def __init__(self, solves=("te0", "te1"), price=0.5, max_usd=10.0):
        self.solves, self.price, self.max_usd = set(solves), price, max_usd
        self.usage = Usage()
        self._seen = set()
        self.by_goal = {f"⊢ {t.statement} @{i}": t.gold[i]
                        for t in TEST if t.name in self.solves for i in range(len(t.gold))}
        self.by_stmt = {t.statement: list(t.gold) for t in TEST if t.name in self.solves}

    def _bill(self, key):
        self.usage.requests += 1
        if key in self._seen:  # cached: free, but still priced notionally
            self.usage.notional_usd += self.price
            return False
        if self.usage.usd >= self.max_usd:
            return False
        self._seen.add(key)
        self.usage.calls += 1
        self.usage.usd += self.price
        self.usage.notional_usd += self.price
        return True

    def propose(self, goal, prelude="", failed=()):
        if not self._bill(("p", goal, tuple(failed))):
            return []
        return [self.by_goal[goal]] if goal in self.by_goal else ["bogus"]

    def whole_proof(self, statement, prelude="", k=4):
        if not self._bill(("w", statement)):
            return []
        return [["bogus"], self.by_stmt.get(statement, ["nope"])][:k]


def phase1_file(tmp_path):
    def m(hard, easy=0):
        return {"proved": hard + easy, "proved_easy": easy, "proved_hard": hard, "mean_calls": 4.0,
                "mean_seconds": 0.1, "per_theorem": [
                    {"name": "te1", "difficulty": "hard", "proved": hard > 0, "calls": 3}]}
    res = {"model": m(8, 8), "try_only": m(7, 8), "fixed": m(2), "random": m(3), "grind_only": m(2),
           "model_no_premise": m(7, 8), "fixed_expand_all": m(10, 8), "n_easy": 8, "n_hard": 12}
    p = tmp_path / "phase1.json"
    p.write_text(json.dumps(res))
    return str(p)


def run(tmp_path, gen, labels=None, reach=None, **kw):
    tmp_path.mkdir(exist_ok=True)
    out = tmp_path / "out"
    return run_phase2(GoldRepl(TRAIN + TEST), TRAIN, TEST, str(out), gen,
                      phase1_path=phase1_file(tmp_path), labels_path=labels or str(tmp_path / "none.json"),
                      library=LIB, reachability=reach, log=lambda m: None, **kw), out


def test_phase2_report_rows_and_cost_columns(tmp_path):
    res, out = run(tmp_path, FakeGen(), reach={"te0": True, "te1": True, "te2": False})
    for m in PHASE2_METHODS:
        r = res[m]
        assert {"proved", "proved_easy", "proved_hard", "mean_calls", "claude_calls", "usd",
                "refusals", "errors", "budget_capped", "notional_usd", "call_capped", "per_theorem"} <= set(r)
        assert len(r["per_theorem"]) == 3
    assert res["claude_search"]["proved_hard"] == 1 and res["hybrid"]["claude_requests"] > 0
    assert res["claude_search"]["claude_calls"] > 0 and res["claude_search"]["usd"] > 0
    assert res["phase1_best"]["method"] == "model" and res["phase1_best"]["proved_hard"] == 8
    assert res["phase1_fixed_expand_all"]["proved_hard"] == 10
    on_disk = json.loads((out / "results.json").read_text())
    assert "partial" not in on_disk and "questions" in on_disk
    text = (out / "report.md").read_text()
    header = next(l for l in text.splitlines() if l.startswith("|") and "method" in l)
    assert "Claude requests" in header and "USD (actual)" in header and "USD (notional)" in header and "hard" in header
    for name in PHASE2_METHODS + ("phase1_best", "phase1_fixed_expand_all"):
        assert len([l for l in text.splitlines() if l.startswith(f"| {name}")]) >= 1
    assert "phase-1 reference" in text
    assert text == format_report_phase2(res, TEST)


def test_whole_proof_counts_any_valid_script(tmp_path):
    res, _ = run(tmp_path, FakeGen(solves=("te0",)))
    rows = {r["name"]: r for r in res["claude_whole"]["per_theorem"]}
    assert rows["te0"]["proved"] is True and rows["te0"]["tactics"] == ["simp"]
    assert rows["te1"]["proved"] is False and rows["te2"]["proved"] is False
    assert res["claude_whole"]["proved"] == 1 and rows["te0"]["claude_calls"] == 1


def test_budget_capped_flag_propagates(tmp_path):
    gen = FakeGen(price=1.0, max_usd=1.0)  # the very first request exhausts the budget
    res, out = run(tmp_path, gen)
    assert res["claude_whole"]["budget_capped"] is True
    assert res["hybrid"]["budget_capped"] is True and res["budget_capped"] is True
    assert "budget" in (out / "report.md").read_text().lower()
    ok, _ = run(tmp_path / "x", FakeGen(price=0.01))
    assert ok["budget_capped"] is False and ok["claude_whole"]["budget_capped"] is False


def test_retrained_model_includes_claude_labels(tmp_path, monkeypatch):
    labels = tmp_path / "labels.json"
    save_labels(str(labels),
                [ChoiceExample("kind", "claude-label-state", ("rfl", "llm|0|simp"), "llm|0|simp")],
                [BinaryExample("useful", "claude-label-state", "llm|0|simp", True)])
    seen = []
    real_fit = model_mod.SystemOneModel.fit

    def spy(self, choice, binary, *a, **k):
        seen.extend(e.state for e in choice + binary)
        return real_fit(self, choice, binary, *a, **k)

    monkeypatch.setattr(model_mod.SystemOneModel, "fit", spy)
    res, _ = run(tmp_path, FakeGen(), labels=str(labels))
    assert "claude-label-state" in seen
    assert res["train_stats"]["n_claude_choice"] == 1 and res["train_stats"]["n_claude_binary"] == 1
    seen.clear()
    run(tmp_path / "y", FakeGen())
    assert "claude-label-state" not in seen


class BogusGen(FakeGen):
    """Never solves anything and proposes a fresh bogus tactic for every goal and failure list."""

    def propose(self, goal, prelude="", failed=()):
        self._bill(("p", goal, tuple(failed)))
        return [f"bogus{len(failed)}"]


class EndlessRepl(GoldRepl):
    """Every tactic succeeds and opens a brand-new goal, so the search keeps asking for proposals."""

    n = 0

    def tactic(self, tac, proof_state, timeout_s=None):
        from jev_demo.repl_client import TacticResult
        self.n += 1
        return TacticResult(self.n + 1000, [f"⊢ goal {self.n}"], True, False, None, [])


def test_call_cap_per_theorem_counts_requests_and_flags_row(tmp_path):
    out = tmp_path / "out"
    tmp_path.mkdir(exist_ok=True)
    res = run_phase2(EndlessRepl(TRAIN + TEST), TRAIN, TEST, str(out), BogusGen(solves=()),
                     phase1_path=phase1_file(tmp_path), labels_path=str(tmp_path / "none.json"),
                     library=LIB, log=lambda m: None)
    for m in ("claude_search", "hybrid"):
        for r in res[m]["per_theorem"]:
            assert r["claude_requests"] <= CALL_CAP
    assert res["claude_search"]["call_capped"] is True and res["call_capped"] is True
    assert any(r["call_capped"] and r["claude_requests"] == CALL_CAP
               for r in res["claude_search"]["per_theorem"])


def test_call_cap_counts_whole_proof_requests_and_resets_per_theorem():
    gen = FakeGen()
    mg = _MeteredGen(gen, cap=5)
    mg.begin()
    mg.whole_proof("test0")  # one FakeGen request
    for i in range(10):
        mg.propose(f"g{i}")
    assert gen.usage.requests == 5 and mg.call_capped
    mg.begin()
    assert not mg.call_capped and mg.propose("again") and gen.usage.requests == 6


def test_cached_run_keeps_notional_usd_while_actual_is_zero(tmp_path):
    from test_claude_gen import FakeClient, gen as mkgen, resp
    c = FakeClient(resp(["omega"], inp=1_000_000))
    g = mkgen(c, tmp_path)
    g.propose("⊢ a")
    first = g.usage.usd
    assert first > 0 and g.usage.notional_usd == pytest.approx(first)
    c2 = FakeClient()
    g2 = mkgen(c2, tmp_path)
    assert g2.propose("⊢ a") == ["omega"]
    assert g2.usage.usd == 0.0 and g2.usage.requests == 1
    assert g2.usage.notional_usd == pytest.approx(first) and g2.usage.notional_unknown == 0
    # an old cache entry without a price is counted as unknown
    import glob
    for f in glob.glob(str(tmp_path / "c" / "*.json")):
        with open(f) as fh:
            d = json.load(fh)
        d.pop("usd")
        with open(f, "w") as fh:
            json.dump(d, fh)
    g3 = mkgen(FakeClient(), tmp_path)
    assert g3.propose("⊢ a") == ["omega"] and g3.usage.notional_unknown == 1


def test_questions_computed_from_results():
    def m(hard, usd, proved):
        return {"proved_hard": hard, "notional_usd": usd, "per_theorem": [
            {"name": n, "difficulty": "hard", "proved": n in proved} for n in "abcd"]}
    res = {"claude_whole": m(1, 1.0, "a"), "claude_search": m(2, 3.0, "ab"),
           "hybrid": m(3, 2.0, "abc"), "n_hard": 4,
           "reachability": {"a": True, "b": False, "c": False, "d": False}}
    q = phase2_questions(res)
    assert q["hybrid_hard"] == 3 and q["claude_search_hard"] == 2 and q["hybrid_beats_claude_search"] is True
    assert q["hybrid_usd_not_higher"] is True
    assert q["unreachable_hard"] == ["b", "c", "d"]
    assert q["unreachable_hard_proved"] == {"b": ["claude_search", "hybrid"], "c": ["hybrid"]}
    assert q["unreachable_hard_proved_count"] == 2


def test_run_phase2_cli_refuses_without_live_flag(monkeypatch, capsys, tmp_path):
    from jev_demo.__main__ import main
    monkeypatch.delenv("ANTHROPIC_RUN_LIVE", raising=False)
    monkeypatch.chdir(tmp_path)  # the default --out is relative; committed results live in the repo
    for cmd in ("run-phase2", "collect"):
        with pytest.raises(SystemExit, match="ANTHROPIC_RUN_LIVE"):
            main([cmd])
    assert not os.path.exists(os.path.join("jev_demo", "results_phase2"))


# -- I4: every table row has the header's cell count -------------------------------------------

def _tables(text):
    blocks, cur = [], []
    for line in text.splitlines() + [""]:
        if line.startswith("|"):
            cur.append(line)
        elif cur:
            blocks.append(cur)
            cur = []
    return blocks


def _cells(line):
    return len(line.strip().strip("|").split("|"))


def assert_tables_well_formed(text):
    tables = _tables(text)
    assert tables
    for t in tables:
        n = _cells(t[0])
        assert set(t[1].strip("|").split("|")) == {"---"}, t[1]
        assert all(_cells(l) == n for l in t), (n, [(l, _cells(l)) for l in t if _cells(l) != n])


def test_phase1_report_tables_have_header_cell_count():
    from jev_demo.bench import METHODS, SUPPLEMENTARY, format_report
    from test_bench import _results
    res = _results(8, 10)
    for m in METHODS + SUPPLEMENTARY:
        res[m]["per_theorem"] = [{"name": "x", "difficulty": "hard", "proved": True, "calls": 2}]
    assert_tables_well_formed(format_report(res))


def test_phase2_report_tables_have_header_cell_count(tmp_path):
    res, _ = run(tmp_path, FakeGen(price=1.0, max_usd=1.0), reach={"te0": True, "te1": True, "te2": False})
    res["claude_search"]["call_capped"] = True
    assert res["budget_capped"]
    text = format_report_phase2(res, TEST)
    assert_tables_well_formed(text)
    assert "call cap" in text and "budget capped" in text


# -- P11: hybrid_expand_all (supplementary) ------------------------------------------------------

def test_hybrid_expand_all_runs_and_is_reported_as_supplementary(tmp_path):
    from jev_demo.bench import PHASE2_SUPPLEMENTARY
    assert PHASE2_SUPPLEMENTARY == ("hybrid_expand_all",)
    res, out = run(tmp_path, FakeGen())
    assert len(res["hybrid_expand_all"]["per_theorem"]) == 3
    assert "hybrid_expand_all" not in json.dumps(res["questions"])
    text = (out / "report.md").read_text()
    supp = text.index("Supplementary")
    assert text.index("| hybrid_expand_all") > supp > text.index("| hybrid |")
    assert text.index("| hybrid_expand_all") < text.index("## Pre-registered questions")


def test_hybrid_expand_all_ranker_always_expands_everything():
    from jev_demo.bench import ExpandAll

    class Confident:
        def rank(self, goal):
            return [("a", 0.9), ("b", 0.1)], 0.9, 0.3

    acts, conf, value = ExpandAll(Confident(), confidence=0.0).rank("⊢ g")
    assert conf == 0.0 and value == 0.3 and acts == [("a", 0.9), ("b", 0.1)]
    assert ExpandAll(Confident()).rank("⊢ g")[1] == 0.9  # phase-1 behaviour unchanged


def test_fatal_claude_error_stops_the_run(tmp_path):
    from jev_demo.claude_gen import FatalRequestError

    class Broken(FakeGen):
        def whole_proof(self, statement, prelude="", k=4):
            raise FatalRequestError("Claude request failed with HTTP 401")

    with pytest.raises(FatalRequestError):
        run(tmp_path, Broken())
