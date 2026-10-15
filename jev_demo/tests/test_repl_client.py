import pytest

from jev_demo.repl_client import ReplClient


@pytest.mark.lean
def test_closing_tactic_is_completed(repl):
    ps, goal = repl.start_theorem("∀ n : Nat, n + 0 = n")
    r = repl.tactic("intro n; simp", ps)
    assert "⊢" in goal and r.ok and r.completed and r.goals == []


@pytest.mark.lean
def test_invalid_tactic_is_failure_even_with_empty_goals(repl):
    ps, _ = repl.start_theorem("∀ x : Nat, x = x")
    r = repl.tactic("exact my_fake_premise", ps)
    assert not r.ok and not r.completed and "my_fake_premise" in r.error


@pytest.mark.lean
def test_partial_progress_is_ok_not_completed(repl):
    ps, _ = repl.start_theorem("∀ p q : Prop, p ∧ q → q ∧ p")
    r = repl.tactic("intro p q h", ps)
    assert r.ok and not r.completed and len(r.goals) == 1


@pytest.mark.lean
def test_timeout_restarts_and_reports_failure():
    with ReplClient(timeout_s=0.5) as c:
        ps, _ = c.start_theorem("∀ a b : Fin 300, a.val + b.val = b.val + a.val")
        r = c.tactic("set_option maxRecDepth 100000 in decide", ps)
        assert not r.ok and "timeout" in r.error
        ps2, _ = c.start_theorem("1 = 1")
        assert c.tactic("rfl", ps2).completed
        stale = c.tactic("rfl", ps)  # id from the killed process
        assert not stale.ok and not stale.completed


@pytest.mark.lean
def test_check_proof_rechecks_whole_script(repl):
    assert repl.check_proof("∀ n : Nat, 0 + n = n", ["intro n", "simp"])
    assert not repl.check_proof("∀ n : Nat, 0 + n = n", ["intro n"])


@pytest.mark.lean
def test_prelude_definitions_are_visible_in_tactic_mode(repl):
    prelude = "def double : Nat → Nat | 0 => 0 | n+1 => double n + 2"
    ps, goal = repl.start_theorem("∀ n : Nat, double n = 2 * n", prelude)
    r = repl.tactic("intro n; induction n <;> grind [double]", ps)
    assert r.ok and r.completed, r.error
