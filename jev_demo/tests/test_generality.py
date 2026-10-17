import json

from jev_demo.generality import main


def _write(root, cond, m, proved, requests, usd):
    d = root / f"{cond}_{m}"
    d.mkdir()
    rows = [{"name": f"t{i}", "proved": p, "claude_requests": q} for i, (p, q) in enumerate(zip(proved, requests))]
    (d / "results.json").write_text(json.dumps({
        m: {"per_theorem": rows}, "total_usd": usd, "max_usd": 10, "budget_capped": False,
        "claude_model": "claude-haiku-5-5", "effort": "medium", "lean_budget": 64, "claude_cap": 16,
        "claude_usage": {"errors": 0, "refusals": 0}}))


def test_scores_present_conditions_and_lists_missing(tmp_path):
    _write(tmp_path, "g-haiku", "claude_search", [True, True, False, True], [8, 8, 16, 4], 0.2)
    _write(tmp_path, "g-haiku", "jev_router", [True, True, False, True], [4, 4, 8, 2], 0.1)
    out = main(str(tmp_path))
    c = out["conditions"]["g-haiku"]
    assert c["request_saving"] == 0.5 and c["request_saving_ci95"] == [0.5, 0.5]
    assert c["hypotheses"]["1_efficiency"] and c["hypotheses"]["2_no_meaningful_loss"]
    assert c["usd_per_proved"] == {"claude_search": round(0.2 / 3, 4), "jev_router": round(0.1 / 3, 4)}
    assert "g-sonnet" in out["missing"] and out["total_usd"] == 0.3
