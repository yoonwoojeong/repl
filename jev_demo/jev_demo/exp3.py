"""Experiment 3: Claude methods on the core-library benchmark (`corebench`), with paired stats.

Unlike phase 2 this runs any subset of methods on one core split, can turn `claude_search`
runs into `trace_labels` for training the hybrid ranker, can replay a previous run's Claude
responses offline (no API calls), and reports success rates with 95% Wilson intervals plus
paired comparisons (McNemar exact p, bootstrap CI of the difference) instead of raw counts.
"""

from __future__ import annotations

import json
import os
import sys

from jev_demo.bench import (CLAUDE_METHODS, PHASE2_SUPPLEMENTARY, _MeteredGen, _run_methods,
                            _run_phase2_method, _without_banned, _write_results, train_model)
from jev_demo.collect import load_labels, save_labels, trace_labels
from jev_demo.hybrid import HybridRanker
from jev_demo.premises import Shortlister, dump_library
from jev_demo.search import prove
from jev_demo.stats import compare, wilson
from jev_demo.theorems import Theorem

METHODS = CLAUDE_METHODS + PHASE2_SUPPLEMENTARY + ("hybrid_filter", "menu_first", "jev_router")
PAIRS = (("jev_router", "claude_search"), ("menu_first", "claude_search"), ("jev_router", "menu_first"),
         ("hybrid_filter", "claude_search"), ("hybrid", "claude_search"),
         ("claude_whole", "claude_search"), ("hybrid", "claude_whole"))


def run(repl, train: list[Theorem], test: list[Theorem], out_dir: str, generator, methods,
        label_paths=(), labels_out: str | None = None, log=None) -> dict:
    log = log or (lambda m: print(m, file=sys.stderr, flush=True))
    lemmas = dump_library(repl)
    lib = {l.name: l for l in lemmas}
    shortlister = Shortlister(lemmas)
    choice, binary = [], []
    for p in label_paths:
        c, b = load_labels(p)
        choice += c
        binary += b
    log(f"fitting on {len(train)} gold-replay theorems + {len(choice)}/{len(binary)} label examples")
    model, train_stats = train_model(train, repl, shortlister, lib, extra=(choice, binary))
    metered = _MeteredGen(generator)
    traces: dict[str, tuple] = {}

    def run_one(method, thm, counting):
        if method == "claude_search" and labels_out:
            ranker = HybridRanker(model, shortlister, _without_banned(lib, thm), metered, order="llm",
                                  prelude=thm.prelude, banned=thm.banned)
            r = prove(thm, counting, ranker)
            traces[thm.name] = (r, dict(ranker._proposals))
            return r
        return _run_phase2_method(method, thm, counting, model, shortlister, lib, metered)

    results: dict = {}
    _run_methods(list(methods), test, run_one, repl, log, results, out_dir, metered=metered)
    if labels_out:
        lc, lb = [], []
        for r, props in traces.values():
            c, b = trace_labels(r, props)
            lc += c
            lb += b
        save_labels(labels_out, lc, lb)
        log(f"wrote {len(lc)} choice and {len(lb)} useful labels to {labels_out}")
    u = generator.usage
    results.update({
        "methods": list(methods), "n": len(test), "train_stats": train_stats,
        "claude_model": getattr(generator, "model", None), "effort": getattr(generator, "effort", None),
        "max_usd": generator.max_usd, "offline": getattr(generator, "offline", False),
        "total_usd": round(u.usd, 6), "claude_usage": dict(vars(u)),
        "budget_capped": any(results[m]["budget_capped"] for m in methods),
    })
    results["analysis"] = analyse(results)
    _write_results(results, out_dir)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(format_report(results))
    return results


def _proved(results: dict, m: str) -> list[bool]:
    return [r["proved"] for r in sorted(results[m]["per_theorem"], key=lambda r: r["name"])]


def analyse(results: dict) -> dict:
    ms = [m for m in results.get("methods", []) if m in results]
    out = {"rates": {}, "pairs": []}
    for m in ms:
        k, n = sum(_proved(results, m)), len(_proved(results, m))
        lo, hi = wilson(k, n)
        usd = results[m]["notional_usd"]
        out["rates"][m] = {"proved": k, "n": n, "rate": round(k / n, 4) if n else 0.0,
                           "ci95": [round(lo, 4), round(hi, 4)], "notional_usd": usd,
                           "usd_per_proved": round(usd / k, 4) if k else None,
                           "claude_requests": results[m]["claude_requests"],
                           "requests_per_proved": round(results[m]["claude_requests"] / k, 3) if k else None,
                           "lean_calls": sum(r["calls"] for r in results[m]["per_theorem"])}
    for a, b in PAIRS:
        if a in ms and b in ms:
            out["pairs"].append(compare(a, _proved(results, a), b, _proved(results, b)))
    return out


def format_report(results: dict) -> str:
    a = results["analysis"]
    out = ["# Jev proof demo — experiment 3 (core-library benchmark)", "",
           f"{results['n']} theorems; `{results.get('claude_model')}`, effort `{results.get('effort')}`"
           + (" — **offline replay** (cache misses give no proposals)" if results.get("offline") else "")
           + ".", ""]
    if results.get("budget_capped"):
        out += ["**Budget cap reached**: some requests were refused locally; rows are not comparable.", ""]
    out += ["| method | proved | rate | 95% CI | notional USD | USD per proved | Claude requests "
            "| requests per proved | Lean calls | audit-rejected proofs |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for m, r in a["rates"].items():
        rej = sum(x.get("audit_rejected", 0) for x in results[m]["per_theorem"])
        per = f"{r['usd_per_proved']:.4f}" if r["usd_per_proved"] is not None else "–"
        rpp = f"{r['requests_per_proved']:.2f}" if r.get("requests_per_proved") is not None else "–"
        out.append(f"| {m} | {r['proved']}/{r['n']} | {r['rate']:.2f} | {r['ci95'][0]:.2f}–{r['ci95'][1]:.2f} "
                   f"| {r['notional_usd']:.4f} | {per} | {r.get('claude_requests', '–')} | {rpp} "
                   f"| {r.get('lean_calls', '–')} | {rej} |")
    if a["pairs"]:
        out += ["", "Paired comparisons (same theorems): difference in success rate a − b with a 95% "
                "bootstrap CI, discordant pairs, and the exact McNemar p-value.", "",
                "| a | b | a only | b only | a − b | 95% CI | McNemar p |", "|---|---|---|---|---|---|---|"]
        for p in a["pairs"]:
            out.append(f"| {p['a']} | {p['b']} | {p['a_only']} | {p['b_only']} | {p['diff']:+.3f} "
                       f"| {p['ci95'][0]:+.3f}–{p['ci95'][1]:+.3f} | {p['p_mcnemar']:.4f} |")
    out += ["", f"Total Claude spend (actual): ${results.get('total_usd', 0.0):.4f} of "
            f"${results.get('max_usd')}.", ""]
    ms = [m for m in results["methods"] if m in results]
    rows = {m: {r["name"]: r for r in results[m]["per_theorem"]} for m in ms}
    names = sorted(rows[ms[0]]) if ms else []
    out += ["## Per theorem", "", "| theorem | " + " | ".join(ms) + " |", "|---|" + "---|" * len(ms)]
    for n in names:
        out.append(f"| {n} | " + " | ".join(f"yes ({rows[m][n]['calls']})" if rows[m][n]["proved"]
                                              else "–" for m in ms) + " |")
    return "\n".join(out) + "\n"
