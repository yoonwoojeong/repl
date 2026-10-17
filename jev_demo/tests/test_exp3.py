import json

import pytest

from jev_demo.claude_gen import ClaudeGenerator
from jev_demo.theorems import Theorem, load_theorems

from test_claude_gen import FakeClient, resp

CORE = [
    {"name": "core_Nat_mul_add_mod", "lemma": "Nat.mul_add_mod",
     "statement": "∀ (m x y : Nat), (m * x + y) % m = y % m"},
    {"name": "core_Nat_add_mul_mod_self_left", "lemma": "Nat.add_mul_mod_self_left",
     "statement": "∀ (a b n : Nat), (a + b * n) % b = a % b"},
]


def test_core_rows_load_with_banned_lemma(tmp_path):
    p = tmp_path / "core.json"
    p.write_text(json.dumps(CORE), encoding="utf-8")
    t = load_theorems(str(p))
    assert t[0].banned == ("Nat.mul_add_mod",) and t[0].gold == () and t[0].difficulty == "hard"


@pytest.mark.lean
def test_exp3_end_to_end_with_fake_claude_and_audit(repl, tmp_path):
    from jev_demo import exp3
    p = tmp_path / "core.json"
    p.write_text(json.dumps(CORE), encoding="utf-8")
    # The banned lemma is proposed first: it must be filtered out (and the audit would reject it);
    # the clean `simp [...]` proof must be accepted.
    client = FakeClient(resp(["exact Nat.mul_add_mod", "intro m x y",
                              "simp [Nat.add_mod, Nat.mul_mod_right]"]))
    gen = ClaudeGenerator(client=client, cache_dir=str(tmp_path / "cache"), max_usd=1.0, log=lambda m: None)
    train = [Theorem("tr", "∀ n : Nat, n + 0 = n", "", ("intro n", "rfl"), "easy")]
    res = exp3.run(repl, train, load_theorems(str(p)), str(tmp_path / "out"), gen,
                   ["claude_search", "hybrid"], labels_out=str(tmp_path / "labels.json"), log=lambda m: None)
    rows = {r["name"]: r for r in res["claude_search"]["per_theorem"]}
    assert rows["core_Nat_mul_add_mod"]["proved"]
    # the banned lemma is named in every request and proposals citing it are never tried
    assert all("Forbidden lemmas" in c["messages"][0]["content"] for c in client.calls)
    assert "Nat.mul_add_mod" not in " ".join(rows["core_Nat_mul_add_mod"]["tactics"])
    assert res["analysis"]["pairs"][0]["a"] == "hybrid"
    labels = json.loads((tmp_path / "labels.json").read_text(encoding="utf-8"))
    assert labels["binary"] and labels["choice"]
    assert (tmp_path / "out" / "report.md").read_text(encoding="utf-8").startswith("# Jev proof demo")


@pytest.mark.lean
def test_exp3_claude_cap_and_lean_budget_are_applied(repl, tmp_path):
    from jev_demo import exp3
    p = tmp_path / "core.json"
    p.write_text(json.dumps(CORE[:1]), encoding="utf-8")
    client = FakeClient(resp(["omega"]))  # never proves it: exhausts a budget
    gen = ClaudeGenerator(client=client, cache_dir=str(tmp_path / "cache"), max_usd=1.0, log=lambda m: None)
    res = exp3.run(repl, [], load_theorems(str(p)), str(tmp_path / "out"), gen, ["claude_search"],
                   log=lambda m: None, lean_budget=5, claude_cap=2)
    row = res["claude_search"]["per_theorem"][0]
    assert row["claude_requests"] <= 2 and row["calls"] <= 5
    assert res["lean_budget"] == 5 and res["claude_cap"] == 2
