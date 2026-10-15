"""The phase-1 experiment: train on gold replays, run every method on the test set, report."""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

from jev_demo.baselines import single_shot
from jev_demo.dataset import replay
from jev_demo.model import SystemOneModel, expected_calibration_error
from jev_demo.premises import Lemma, Shortlister, dump_library
from jev_demo.search import FixedOrderRanker, ModelRanker, RandomRanker, SearchResult, prove
from jev_demo.theorems import Theorem

METHODS = ("model", "model_no_premise", "fixed", "random", "grind_only", "try_only")
BASELINES_FOR_SUCCESS = ("fixed", "grind_only", "try_only")
HOLDOUT_FRACTION = 0.2
SEED = 0
GRIND_TIMEOUT_S = 10
TRY_TIMEOUT_S = 60
_DEAD = ("timeout", "invalid proof state")


class _CountingRepl:
    """Delegates to a REPL client and counts tactic calls that timed out or hit a dead state
    (a timeout restarts the REPL, which invalidates every earlier proof state)."""

    def __init__(self, repl):
        self._repl = repl
        self.timeouts = self.dead = 0

    def tactic(self, tac, proof_state, timeout_s=None):
        res = self._repl.tactic(tac, proof_state, timeout_s=timeout_s)
        err = res.error or ""
        self.timeouts += err == "timeout"
        self.dead += err.startswith("invalid proof state")
        return res

    def __getattr__(self, name):
        return getattr(self._repl, name)


def _split(items: list, rng: np.random.Generator) -> tuple[list, list]:
    """(fit, hold-out) with a HOLDOUT_FRACTION hold-out."""
    perm = rng.permutation(len(items))
    n_hold = int(round(HOLDOUT_FRACTION * len(items)))
    hold = set(perm[:n_hold].tolist())
    return ([x for i, x in enumerate(items) if i not in hold], [x for i, x in enumerate(items) if i in hold])


def train_model(train: list[Theorem], repl, shortlister: Shortlister, lib: dict[str, Lemma]):
    """Replay, fit on 80%, calibrate on the 20% hold-out, refit on all keeping the temperatures."""
    stats: dict = {}
    choice, binary = [], []
    for thm in train:
        c, b = replay(thm, repl, shortlister, lib, stats=stats)
        choice += c
        binary += b
    rng = np.random.default_rng(SEED)
    c_fit, c_hold = _split(choice, rng)
    b_fit, _ = _split(binary, rng)
    probe = SystemOneModel(seed=SEED)
    probe.fit(c_fit, b_fit)
    temps = probe.calibrate(c_hold)
    model = SystemOneModel(seed=SEED)
    model.fit(choice, binary)
    model.temps = dict(temps)
    stats.update(n_choice=len(choice), n_binary=len(binary), n_holdout_choice=len(c_hold))
    return model, stats


def _run_method(method: str, thm: Theorem, repl, model, shortlister, lib) -> SearchResult:
    if method == "model":
        return prove(thm, repl, ModelRanker(model, shortlister, lib, premises=True))
    if method == "model_no_premise":
        return prove(thm, repl, ModelRanker(model, shortlister, lib, premises=False))
    if method == "fixed":
        return prove(thm, repl, FixedOrderRanker())
    if method == "random":
        return prove(thm, repl, RandomRanker(seed=SEED))  # fresh per theorem (ruling R10)
    if method == "grind_only":
        return single_shot(thm, repl, "grind", GRIND_TIMEOUT_S)
    if method == "try_only":
        return single_shot(thm, repl, "try?", TRY_TIMEOUT_S)
    raise ValueError(method)


def _summary(rows: list[dict]) -> dict:
    proved = [r for r in rows if r["proved"]]

    def mean(key):
        return round(float(np.mean([r[key] for r in proved])), 3) if proved else None

    return {
        "proved": len(proved),
        "proved_easy": sum(r["difficulty"] == "easy" for r in proved),
        "proved_hard": sum(r["difficulty"] == "hard" for r in proved),
        "mean_calls": mean("calls"),
        "mean_seconds": mean("seconds"),
        "per_theorem": rows,
    }


def run_experiment(repl, train: list[Theorem], test: list[Theorem], out_dir: str,
                   library: list[Lemma] | None = None, reachability: dict[str, bool] | None = None,
                   log=None) -> dict:
    log = log or (lambda msg: print(msg, file=sys.stderr, flush=True))
    lemmas = library if library is not None else dump_library(repl)
    lib = {l.name: l for l in lemmas}
    shortlister = Shortlister(lemmas)

    log(f"replaying {len(train)} train theorems and fitting")
    model, train_stats = train_model(train, repl, shortlister, lib)

    results: dict = {}
    for method in METHODS:
        rows = []
        for thm in test:
            counting = _CountingRepl(repl)
            r = _run_method(method, thm, counting, model, shortlister, lib)
            row = {"name": thm.name, "difficulty": thm.difficulty, "proved": r.proved,
                   "calls": r.calls, "escalations": r.escalations, "seconds": round(r.seconds, 3),
                   "tactics": r.tactics, "timeouts": counting.timeouts, "dead_state_calls": counting.dead}
            if method in ("grind_only", "try_only"):
                row["trace"] = r.trace
            rows.append(row)
            log(f"{method:17s} {thm.name:28s} {'PROVED' if r.proved else 'failed'} "
                f"calls={r.calls} {r.seconds:.1f}s timeouts={counting.timeouts}")
        results[method] = _summary(rows)

    # Measurement only: test replays never reach fit or calibrate.
    test_stats: dict = {}
    kind_test = []
    for thm in test:
        c, _ = replay(thm, repl, shortlister, lib, stats=test_stats)
        kind_test += [e for e in c if e.question == "kind"]

    def recall(st):
        return st["premise_hits"] / st["premise_steps"] if st.get("premise_steps") else 0.0

    hard_best = max(results[m]["proved_hard"] for m in BASELINES_FOR_SUCCESS)
    results.update({
        "ece": round(expected_calibration_error(model, kind_test), 4),
        "ece_examples": len(kind_test),
        "temperatures": dict(model.temps),
        "shortlist_recall": round(recall(test_stats), 4),
        "shortlist_recall_train": round(recall(train_stats), 4),
        "train_stats": train_stats,
        "test_stats": test_stats,
        "n_easy": sum(t.difficulty == "easy" for t in test),
        "n_hard": sum(t.difficulty == "hard" for t in test),
        "success": results["model"]["proved_hard"] > hard_best,
    })
    if reachability is not None:
        results["reachability"] = {t.name: reachability.get(t.name) for t in test}

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(format_report(results, test))
    return results


def _fmt(x) -> str:
    return "–" if x is None else f"{x:.2f}" if isinstance(x, float) else str(x)


def format_report(results: dict, test: list[Theorem] | None = None) -> str:
    ne, nh = results["n_easy"], results["n_hard"]
    out = ["# Jev proof demo — phase 1 results", "",
           "| method | proved | easy | hard | mean calls (proved) | mean seconds (proved) |",
           "|---|---|---|---|---|---|"]
    for m in METHODS:
        r = results[m]
        out.append(f"| {m} | {r['proved']}/{ne + nh} | {r['proved_easy']}/{ne} | {r['proved_hard']}/{nh} "
                   f"| {_fmt(r['mean_calls'])} | {_fmt(r['mean_seconds'])} |")
    best = max(BASELINES_FOR_SUCCESS, key=lambda m: results[m]["proved_hard"])
    met = results["model"]["proved_hard"] > results[best]["proved_hard"]
    out += ["", f"Success criterion (hard set: `model` proves strictly more than the best of "
            f"{', '.join(BASELINES_FOR_SUCCESS)}): **{'met' if met else 'not met'}** — "
            f"model {results['model']['proved_hard']}/{nh} vs {best} {results[best]['proved_hard']}/{nh}.", ""]
    temps = ", ".join(f"`{k}` = {v}" for k, v in sorted(results["temperatures"].items())) or "none"
    out += [f"- ECE (10 bins) of `kind` on test gold steps: {_fmt(results['ece'])}"
            + (f" ({results['ece_examples']} steps)" if "ece_examples" in results else ""),
            f"- Calibrated temperatures: {temps}",
            f"- Premise shortlist recall@16 on test gold premise steps: {_fmt(results['shortlist_recall'])}"]
    if "shortlist_recall_train" in results:
        out.append(f"- Premise shortlist recall@16 on train gold premise steps: "
                   f"{_fmt(results['shortlist_recall_train'])}")
    for key, label in (("train_stats", "Train replay"), ("test_stats", "Test replay")):
        if key in results:
            st = results[key]
            out.append(f"- {label}: {st.get('steps', 0)} gold steps, {st.get('kind_skipped', 0)} outside the "
                       f"`kind` options, {st.get('premise_hits', 0)}/{st.get('premise_steps', 0)} premise "
                       f"steps shortlisted")
    rows = {m: {r["name"]: r for r in results[m]["per_theorem"]} for m in METHODS}
    names = [t.name for t in test] if test else list(rows[METHODS[0]])
    if names:
        reach = results.get("reachability") or {}
        out += ["", "## Per theorem", "",
                "| theorem | difficulty | menu-reachable | " + " | ".join(METHODS) + " |",
                "|---|---|---|" + "---|" * len(METHODS)]
        for n in names:
            diff = rows[METHODS[0]][n]["difficulty"]
            cells = []
            for m in METHODS:
                r = rows[m][n]
                cells.append(f"yes ({r['calls']})" if r["proved"] else "–")
            out.append(f"| {n} | {diff} | {_fmt(reach.get(n))} | " + " | ".join(cells) + " |")
        out += ["", "Cells: `yes (calls)` when proved, `–` otherwise."]
    return "\n".join(out) + "\n"
