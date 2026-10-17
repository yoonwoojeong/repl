"""Score experiment 4 (generality, README "Experiment 4"). No API calls.

Each condition changes one setting from the test run (generator model, effort, per-lemma budgets,
or benchmark family) and runs `claude_search` and `jev_router` with their own empty response
caches: `results_exp3/g-<condition>_{claude_search,jev_router}/results.json`. Per condition:
request saving with a 95% bootstrap CI (`replication.saving_ci`), the paired success difference
(`stats.compare`), cost per proved lemma, and the two pre-registered pass/fail checks. Writes
`results_exp3/generality.json`.
"""

from __future__ import annotations

import json
import os
import sys

from jev_demo.replication import RESULTS, saving_ci
from jev_demo.stats import compare

CONDITIONS = ("g-haiku", "g-sonnet", "g-opus-low", "g-tight", "g-ext")


def _load(root: str, cond: str, m: str) -> dict | None:
    path = os.path.join(root, f"{cond}_{m}", "results.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def score_condition(cs_res: dict, jr_res: dict) -> dict:
    cs = {r["name"]: r for r in cs_res["claude_search"]["per_theorem"]}
    jr = {r["name"]: r for r in jr_res["jev_router"]["per_theorem"]}
    names = sorted(cs)
    if sorted(jr) != names:
        raise ValueError("the two runs are not on the same lemmas")
    cs_p, jr_p = [cs[n]["proved"] for n in names], [jr[n]["proved"] for n in names]
    cs_r, jr_r = [cs[n]["claude_requests"] for n in names], [jr[n]["claude_requests"] for n in names]
    s, lo, hi = saving_ci(cs_r, jr_r)
    c = compare("jev_router", jr_p, "claude_search", cs_p)
    usd = {"claude_search": cs_res["total_usd"], "jev_router": jr_res["total_usd"]}
    proved = {"claude_search": sum(cs_p), "jev_router": sum(jr_p)}
    return {
        "n": len(names), "claude_model": cs_res.get("claude_model"), "effort": cs_res.get("effort"),
        "lean_budget": cs_res.get("lean_budget"), "claude_cap": cs_res.get("claude_cap"),
        "proved": proved,
        "claude_requests": {"claude_search": sum(cs_r), "jev_router": sum(jr_r)},
        "usd": {k: round(v, 4) for k, v in usd.items()},
        "usd_per_proved": {k: (round(usd[k] / proved[k], 4) if proved[k] else None) for k in usd},
        "request_saving": round(s, 4), "request_saving_ci95": [round(lo, 4), round(hi, 4)],
        "router_fewer_requests": sum(j < c_ for c_, j in zip(cs_r, jr_r)),
        "router_more_requests": sum(j > c_ for c_, j in zip(cs_r, jr_r)),
        "success": c,
        "errors": {"claude_search": cs_res["claude_usage"]["errors"], "jev_router": jr_res["claude_usage"]["errors"]},
        "refusals": {"claude_search": cs_res["claude_usage"]["refusals"],
                     "jev_router": jr_res["claude_usage"]["refusals"]},
        "budget_capped": cs_res["budget_capped"] or jr_res["budget_capped"],
        "hypotheses": {"1_efficiency": lo > 0, "2_no_meaningful_loss": c["ci95"][0] > -0.05},
    }


def main(root: str = RESULTS) -> dict:
    out: dict = {"conditions": {}, "missing": []}
    for cond in CONDITIONS:
        cs, jr = _load(root, cond, "claude_search"), _load(root, cond, "jev_router")
        if cs is None or jr is None:
            out["missing"].append(cond)
            continue
        out["conditions"][cond] = score_condition(cs, jr)
    out["total_usd"] = round(sum(sum(c["usd"].values()) for c in out["conditions"].values()), 4)
    with open(os.path.join(root, "generality.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    return out


if __name__ == "__main__":
    json.dump(main(), sys.stdout, indent=1)
    print()
