"""Score the pre-registered independent replication (README "Overcoming the limits, 2"). No API calls.

Inputs: `results_exp3/test_rep{1,2}_{claude_search,jev_router}/results.json` (each method run
with its own empty response cache), and optionally `results_exp3/reaudit.json` for strict scoring.
Pairs are by lemma within a replicate; the pooled analysis has 2 x 148 = 296 pairs.

- request saving: 1 - sum(router requests) / sum(claude_search requests), 95% percentile
  bootstrap over pairs (10,000 resamples, seed 0);
- success difference: `stats.paired_bootstrap` (router - claude_search);
- stability: proved/requests per replicate and lemmas whose outcome flips between replicates.

Writes `results_exp3/replication.json`.
"""

from __future__ import annotations

import json
import os
import random
import sys

from jev_demo.stats import compare, mcnemar
from jev_demo.theorems import DATA_DIR

RESULTS = os.path.join(os.path.dirname(DATA_DIR), "results_exp3")
METHODS = ("claude_search", "jev_router")
REPS = (1, 2)


def load(rep: int, m: str, root: str = RESULTS) -> dict[str, dict]:
    with open(os.path.join(root, f"test_rep{rep}_{m}", "results.json"), encoding="utf-8") as f:
        res = json.load(f)
    return {r["name"]: r for r in res[m]["per_theorem"]}


def saving_ci(base: list[int], new: list[int], iters: int = 10000, seed: int = 0) -> tuple[float, float, float]:
    """(1 - sum(new)/sum(base), lower, upper): percentile bootstrap over paired items."""
    n = len(base)
    rng = random.Random(seed)
    point = 1 - sum(new) / sum(base)
    samples = []
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        b = sum(base[i] for i in idx)
        samples.append(1 - sum(new[i] for i in idx) / b if b else 0.0)
    samples.sort()
    return point, samples[int(0.025 * iters)], samples[min(iters - 1, int(0.975 * iters))]


def _pairs(runs: dict, reps, proved_key) -> tuple[list, list, list, list]:
    cs_p, jr_p, cs_r, jr_r = [], [], [], []
    for rep in reps:
        cs, jr = runs[(rep, "claude_search")], runs[(rep, "jev_router")]
        for name in sorted(cs):
            cs_p.append(proved_key(rep, "claude_search", cs[name]))
            jr_p.append(proved_key(rep, "jev_router", jr[name]))
            cs_r.append(cs[name]["claude_requests"])
            jr_r.append(jr[name]["claude_requests"])
    return cs_p, jr_p, cs_r, jr_r


def score(runs: dict, proved_key=lambda rep, m, r: r["proved"]) -> dict:
    out: dict = {"per_replicate": {}, "pooled": {}}
    for label, reps in [*((f"rep{r}", (r,)) for r in REPS), ("pooled", REPS)]:
        cs_p, jr_p, cs_r, jr_r = _pairs(runs, reps, proved_key)
        s, lo, hi = saving_ci(cs_r, jr_r)
        c = compare("jev_router", jr_p, "claude_search", cs_p)
        row = {"n": len(cs_p), "claude_search_proved": sum(cs_p), "jev_router_proved": sum(jr_p),
               "claude_search_requests": sum(cs_r), "jev_router_requests": sum(jr_r),
               "request_saving": round(s, 4), "request_saving_ci95": [round(lo, 4), round(hi, 4)],
               "router_fewer_requests": sum(j < c_ for c_, j in zip(cs_r, jr_r)),
               "router_more_requests": sum(j > c_ for c_, j in zip(cs_r, jr_r)),
               "success": c}
        if label == "pooled":
            out["pooled"] = row
        else:
            out["per_replicate"][label] = row
    flips = {}
    for m in METHODS:
        a, b = runs[(1, m)], runs[(2, m)]
        names = sorted(a)
        pa = [proved_key(1, m, a[n]) for n in names]
        pb = [proved_key(2, m, b[n]) for n in names]
        flips[m] = {"only_rep1": [n for n, x, y in zip(names, pa, pb) if x and not y],
                    "only_rep2": [n for n, x, y in zip(names, pa, pb) if y and not x],
                    "p_mcnemar": round(mcnemar(pa, pb), 5)}
    out["flips_between_replicates"] = flips
    out["hypotheses"] = {
        "1_efficiency": out["pooled"]["request_saving_ci95"][0] > 0,
        "2_no_meaningful_loss": out["pooled"]["success"]["ci95"][0] > -0.05,
    }
    return out


def main(root: str = RESULTS) -> dict:
    runs = {(rep, m): load(rep, m, root) for rep in REPS for m in METHODS}
    spend = {}
    for rep in REPS:
        for m in METHODS:
            with open(os.path.join(root, f"test_rep{rep}_{m}", "results.json"), encoding="utf-8") as f:
                r = json.load(f)
            spend[f"rep{rep}_{m}"] = {"usd": round(r["total_usd"], 4), "cap": r["max_usd"],
                                      "budget_capped": r["budget_capped"],
                                      "errors": r["claude_usage"]["errors"],
                                      "refusals": r["claude_usage"]["refusals"]}
    out = {"primary": score(runs), "spend": spend,
           "total_usd": round(sum(s["usd"] for s in spend.values()), 4)}
    path = os.path.join(root, "reaudit.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            ra = json.load(f)
        bad = {}
        for rep in REPS:
            for m in METHODS:
                entry = ra.get(f"test_rep{rep}", {}).get(m)
                if entry is not None:
                    bad[(rep, m)] = set(entry["rejected_v2"]) | set(entry["one_lemma"])
        if len(bad) == len(REPS) * len(METHODS):
            out["strict"] = score(runs, lambda rep, m, r: r["proved"] and r["name"] not in bad[(rep, m)])
    with open(os.path.join(root, "replication.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    return out


if __name__ == "__main__":
    res = main()
    json.dump({k: v for k, v in res.items()}, sys.stdout, indent=1)
    print()
