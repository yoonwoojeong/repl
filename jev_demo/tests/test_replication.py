import json

from jev_demo.replication import main, saving_ci


def test_saving_ci_point_and_bounds():
    s, lo, hi = saving_ci([4, 4, 4, 4], [2, 2, 2, 2])
    assert s == lo == hi == 0.5
    s, lo, hi = saving_ci([10, 2, 6, 8], [3, 2, 1, 8], iters=500)
    assert lo <= s <= hi and abs(s - (1 - 14 / 26)) < 1e-9


def _write(root, rep, m, proved, requests, usd):
    d = root / f"test_rep{rep}_{m}"
    d.mkdir()
    rows = [{"name": f"t{i}", "proved": p, "claude_requests": q} for i, (p, q) in enumerate(zip(proved, requests))]
    (d / "results.json").write_text(json.dumps({
        m: {"per_theorem": rows}, "total_usd": usd, "max_usd": 10, "budget_capped": False,
        "claude_usage": {"errors": 0, "refusals": 0}}))


def test_main_scores_pooled_and_flips(tmp_path):
    _write(tmp_path, 1, "claude_search", [True, True, False], [8, 8, 8], 1.0)
    _write(tmp_path, 1, "jev_router", [True, True, False], [4, 4, 8], 0.5)
    _write(tmp_path, 2, "claude_search", [True, False, False], [8, 8, 8], 1.0)
    _write(tmp_path, 2, "jev_router", [True, True, False], [4, 4, 8], 0.5)
    out = main(str(tmp_path))
    p = out["primary"]
    assert p["pooled"]["n"] == 6
    assert p["pooled"]["claude_search_requests"] == 48 and p["pooled"]["jev_router_requests"] == 32
    assert p["flips_between_replicates"]["claude_search"]["only_rep1"] == ["t1"]
    assert p["flips_between_replicates"]["jev_router"]["only_rep1"] == []
    assert out["total_usd"] == 3.0 and "strict" not in out
    assert (tmp_path / "replication.json").exists()
