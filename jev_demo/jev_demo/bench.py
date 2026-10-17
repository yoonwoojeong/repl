"""The phase-1 experiment: train on gold replays, run every method on the test set, report."""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

from jev_demo.baselines import single_shot
from jev_demo.claude_gen import FatalRequestError
from jev_demo.collect import LABELS_PATH, load_labels
from jev_demo.corebench import AuditedRepl, Auditor
from jev_demo.dataset import replay
from jev_demo.hybrid import HybridRanker
from jev_demo.model import SystemOneModel, expected_calibration_error
from jev_demo.premises import Lemma, Shortlister, dump_library
from jev_demo.search import FixedOrderRanker, ModelRanker, RandomRanker, SearchResult, prove
from jev_demo.theorems import DATA_DIR, Theorem

METHODS = ("model", "model_no_premise", "fixed", "random", "grind_only", "try_only")
BASELINES_FOR_SUCCESS = ("fixed", "grind_only", "try_only")
# Added after the first run (post hoc, not part of the success criterion): the planned
# fixed/random rankers report confidence 1.0, so the search only ever tries their first
# top_k = 3 actions per state. These variants report their top score (1/n) instead, so the
# search escalates and expands every menu item in that order.
SUPPLEMENTARY = ("fixed_expand_all", "random_expand_all")
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


class ExpandAll:
    """Wraps a ranker; confidence becomes the top action's score, as for ModelRanker, or the
    fixed `confidence` if given (0.0: the search always escalates and expands every action)."""

    def __init__(self, ranker, confidence: float | None = None):
        self.ranker, self.confidence = ranker, confidence

    def rank(self, goal: str):
        actions, _, value = self.ranker.rank(goal)
        return actions, actions[0][1] if self.confidence is None else self.confidence, value


def _write_results(results: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
        f.write("\n")


def add_flags(results: dict) -> dict:
    """Set `criterion_met` (pre-registered, R11: model hard-proved > best of the planned baselines)
    and `beats_exhaustive_search` (model hard-proved > best supplementary method). Replaces the
    old `success` key in place."""
    model_hard = results["model"]["proved_hard"]
    met = model_hard > max(results[m]["proved_hard"] for m in BASELINES_FOR_SUCCESS)
    supp = [results[m]["proved_hard"] for m in SUPPLEMENTARY if m in results]
    beats = bool(supp) and model_hard > max(supp)
    items = []
    for k, v in results.items():
        if k == "success":
            items.append(("criterion_met", met))
        elif k not in ("criterion_met", "beats_exhaustive_search"):
            items.append((k, v))
    out = dict(items)
    out.setdefault("criterion_met", met)
    out["beats_exhaustive_search"] = beats
    results.clear()
    results.update(out)
    return results


def _split(items: list, rng: np.random.Generator) -> tuple[list, list]:
    """(fit, hold-out) with a HOLDOUT_FRACTION hold-out."""
    perm = rng.permutation(len(items))
    n_hold = int(round(HOLDOUT_FRACTION * len(items)))
    hold = set(perm[:n_hold].tolist())
    return ([x for i, x in enumerate(items) if i not in hold], [x for i, x in enumerate(items) if i in hold])


def train_model(train: list[Theorem], repl, shortlister: Shortlister, lib: dict[str, Lemma],
                extra: tuple[list, list] | None = None):
    """Replay, fit on 80%, calibrate on the 20% hold-out, refit on all keeping the temperatures.
    `extra = (choice, binary)` examples (phase 2: Claude labels) are added to the replay ones."""
    stats: dict = {}
    choice, binary = [], []
    for thm in train:
        c, b = replay(thm, repl, shortlister, lib, stats=stats)
        choice += c
        binary += b
    if extra is not None:
        choice += list(extra[0])
        binary += list(extra[1])
        stats.update(n_claude_choice=len(extra[0]), n_claude_binary=len(extra[1]))
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
    lib = _without_banned(lib, thm)
    if method == "model":
        return prove(thm, repl, ModelRanker(model, shortlister, lib, premises=True))
    if method == "model_no_premise":
        return prove(thm, repl, ModelRanker(model, shortlister, lib, premises=False))
    if method == "fixed":
        return prove(thm, repl, FixedOrderRanker())
    if method == "random":
        return prove(thm, repl, RandomRanker(seed=SEED))  # fresh per theorem (ruling R10)
    if method == "fixed_expand_all":
        return prove(thm, repl, ExpandAll(FixedOrderRanker()))
    if method == "random_expand_all":
        return prove(thm, repl, ExpandAll(RandomRanker(seed=SEED)))
    if method == "grind_only":
        return single_shot(thm, repl, "grind", GRIND_TIMEOUT_S)
    if method == "try_only":
        return single_shot(thm, repl, "try?", TRY_TIMEOUT_S)
    raise ValueError(method)


def _summary(rows: list[dict], claude: bool = False) -> dict:
    proved = [r for r in rows if r["proved"]]

    def mean(key):
        return round(float(np.mean([r[key] for r in proved])), 3) if proved else None

    out = {
        "proved": len(proved),
        "proved_easy": sum(r["difficulty"] == "easy" for r in proved),
        "proved_hard": sum(r["difficulty"] == "hard" for r in proved),
        "mean_calls": mean("calls"),
        "mean_seconds": mean("seconds"),
    }
    if claude:  # phase 2: cost columns, summed over the per-theorem deltas
        out.update({
            "claude_requests": sum(r["claude_requests"] for r in rows),
            "claude_calls": sum(r["claude_calls"] for r in rows),
            "usd": round(sum(r["usd"] for r in rows), 6),
            "notional_usd": round(sum(r["notional_usd"] for r in rows), 6),
            "notional_unknown": sum(r["notional_unknown"] for r in rows),
            "call_capped": any(r["call_capped"] for r in rows),
            "refusals": sum(r["refusals"] for r in rows),
            "errors": sum(r["errors"] for r in rows),
            "budget_capped": any(r["budget_capped"] for r in rows),
        })
    out["per_theorem"] = rows
    return out


CALL_CAP = 16  # Claude requests (cached or billed) per theorem and method


class _MeteredGen:
    """Wraps a Claude generator: enforces the per-theorem request cap and reads usage deltas.
    Requests are counted inside the generator (`usage.requests`), so `whole_proof`'s k requests
    count k and cached requests count like billed ones (behaviour does not depend on run order)."""

    def __init__(self, gen, cap: int = CALL_CAP):
        self.gen, self.cap = gen, cap
        self.call_capped = False
        self._start = 0

    def begin(self) -> None:
        """Start a theorem: reset the per-theorem counter."""
        self._start, self.call_capped = self.gen.usage.requests, False

    def _used(self) -> int:
        return self.gen.usage.requests - self._start

    def propose(self, *a, **k):
        if self._used() >= self.cap:
            self.call_capped = True
            return []
        return self.gen.propose(*a, **k)

    def whole_proof(self, *a, **k):
        if self._used() >= self.cap:
            self.call_capped = True
            return []
        return self.gen.whole_proof(*a, **k)

    def snapshot(self) -> tuple:
        u = self.gen.usage
        return (u.requests, u.calls, u.usd, u.notional_usd, u.notional_unknown, u.refusals, u.errors)

    def delta(self, before: tuple) -> dict:
        r, c, usd, nu, unk, ref, err = (a - b for a, b in zip(self.snapshot(), before))
        return {"claude_requests": r, "claude_calls": c, "usd": round(usd, 6),
                "notional_usd": round(nu, 6), "notional_unknown": unk, "refusals": ref,
                "errors": err, "budget_capped": self.gen.usage.usd >= self.gen.max_usd,
                "call_capped": self.call_capped}


def _run_methods(methods, test: list[Theorem], run_one, repl, log, results: dict, out_dir: str,
                 metered: _MeteredGen | None = None, trace_methods=()) -> None:
    """Run each method on every test theorem into `results[method]` (shared by both phases).
    `run_one(method, thm, counting_repl)` returns a SearchResult. An exception becomes an unproved
    row; results.json is rewritten (marked partial) after each method. Theorems with `banned`
    constants (core benchmark) are checked through an `Auditor` REPL: a proof that uses a banned
    constant does not count."""
    auditor_repl = None
    if any(t.banned for t in test):
        from jev_demo.repl_client import ReplClient
        auditor_repl = ReplClient(timeout_s=60)
        auditor = Auditor(auditor_repl)
    try:
        _run_methods_inner(methods, test, run_one, repl, log, results, out_dir, metered,
                           trace_methods, auditor if auditor_repl else None)
    finally:
        if auditor_repl is not None:
            auditor_repl.close()


def _without_banned(lib: dict, thm: Theorem) -> dict:
    """The premise library minus the theorem's banned lemmas, so they are never suggested."""
    return {k: v for k, v in lib.items() if k not in thm.banned} if thm.banned else lib


def _run_methods_inner(methods, test, run_one, repl, log, results, out_dir, metered,
                       trace_methods, auditor) -> None:
    for method in methods:
        rows = []
        for thm in test:
            counting = _CountingRepl(repl)
            checked = AuditedRepl(counting, auditor, thm.banned) if thm.banned else counting
            if metered:
                metered.begin()
            before = metered.snapshot() if metered else None
            t0 = time.perf_counter()
            try:
                r = run_one(method, thm, checked)
            except FatalRequestError:  # misconfigured Claude access: stop instead of recording
                raise
            except Exception as e:  # keep the run going; record the failure as an unproved row
                row = {"name": thm.name, "difficulty": thm.difficulty, "proved": False, "calls": 0,
                       "escalations": 0, "seconds": round(time.perf_counter() - t0, 3), "tactics": [],
                       "timeouts": counting.timeouts, "dead_state_calls": counting.dead,
                       "error": f"{type(e).__name__}: {e}"}
                if metered:
                    row.update(metered.delta(before))
                rows.append(row)
                log(f"{method:17s} {thm.name:28s} ERROR {row['error']}")
                continue
            row = {"name": thm.name, "difficulty": thm.difficulty, "proved": r.proved,
                   "calls": r.calls, "escalations": r.escalations, "seconds": round(r.seconds, 3),
                   "tactics": r.tactics, "timeouts": counting.timeouts, "dead_state_calls": counting.dead}
            if thm.banned:
                row["audit_rejected"] = checked.rejected
            if metered:
                row.update(metered.delta(before))
            if method in trace_methods:
                row["trace"] = r.trace
            rows.append(row)
            cost = f" claude={row['claude_calls']} usd={row['usd']:.3f}" if metered else ""
            log(f"{method:17s} {thm.name:28s} {'PROVED' if r.proved else 'failed'} "
                f"calls={r.calls} {r.seconds:.1f}s timeouts={counting.timeouts}{cost}")
        results[method] = _summary(rows, claude=metered is not None)
        _write_results({**results, "partial": True}, out_dir)  # keep progress if a later step dies


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
    _run_methods(METHODS + SUPPLEMENTARY, test,
                 lambda method, thm, counting: _run_method(method, thm, counting, model, shortlister, lib),
                 repl, log, results, out_dir, trace_methods=("grind_only", "try_only"))

    # Measurement only: test replays never reach fit or calibrate.
    test_stats: dict = {}
    kind_test = []
    for thm in test:
        try:
            c, _ = replay(thm, repl, shortlister, lib, stats=test_stats)
        except Exception as e:  # measurement only: skip a theorem that cannot be replayed
            log(f"test replay of {thm.name} failed, skipped: {type(e).__name__}: {e}")
            continue
        kind_test += [e for e in c if e.question == "kind"]

    def recall(st):
        return st["premise_hits"] / st["premise_steps"] if st.get("premise_steps") else 0.0

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
    })
    add_flags(results)
    if reachability is not None:
        results["reachability"] = {t.name: reachability.get(t.name) for t in test}

    _write_results(results, out_dir)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(format_report(results, test))
    return results


def _fmt(x) -> str:
    if isinstance(x, bool):
        return "yes" if x else "no"
    return "–" if x is None else f"{x:.2f}" if isinstance(x, float) else str(x)


def _table_head(cols: list[str]) -> list[str]:
    """A GFM table header and its delimiter row, which must have the same number of cells."""
    return ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]


PHASE1_COLS = ["method", "proved", "easy", "hard", "mean calls (proved)", "mean seconds (proved)"]


def format_report(results: dict, test: list[Theorem] | None = None) -> str:
    ne, nh = results["n_easy"], results["n_hard"]
    out = ["# Jev proof demo — phase 1 results", "", *_table_head(PHASE1_COLS)]
    for m in METHODS:
        r = results[m]
        out.append(f"| {m} | {r['proved']}/{ne + nh} | {r['proved_easy']}/{ne} | {r['proved_hard']}/{nh} "
                   f"| {_fmt(r['mean_calls'])} | {_fmt(r['mean_seconds'])} |")
    best = max(BASELINES_FOR_SUCCESS, key=lambda m: results[m]["proved_hard"])
    model_hard, best_hard = results["model"]["proved_hard"], results[best]["proved_hard"]
    met = model_hard > best_hard
    supp = [m for m in SUPPLEMENTARY if m in results]
    beaten_by = [m for m in supp if results[m]["proved_hard"] > model_hard]
    if met and beaten_by:
        verdict = f"met nominally ({model_hard} vs {best_hard})"
    else:
        verdict = f"**{'met' if met else 'not met'}**"
    out += ["", f"Success criterion (hard set: `model` proves strictly more than the best of "
            f"{', '.join(BASELINES_FOR_SUCCESS)}): {verdict} — "
            f"model {model_hard}/{nh} vs {best} {best_hard}/{nh}."]
    if beaten_by:
        top = max(beaten_by, key=lambda m: results[m]["proved_hard"])
        out.append(f"However, the model does not beat exhaustive search over the same menu "
                   f"({model_hard} vs {results[top]['proved_hard']} hard for post-hoc `{top}`), "
                   f"so this experiment does not show that the model helps.")
    out.append("")
    if supp:
        out += ["Supplementary, added after the first run and not part of the success criterion: "
                "the planned `fixed`/`random` rankers report confidence 1.0, so the search only tries "
                "their first 3 actions per state. With confidence = top score (1/n) the search escalates "
                "and expands the whole menu:", "", *_table_head(PHASE1_COLS)]
        for m in supp:
            r = results[m]
            out.append(f"| {m} | {r['proved']}/{ne + nh} | {r['proved_easy']}/{ne} | {r['proved_hard']}/{nh} "
                       f"| {_fmt(r['mean_calls'])} | {_fmt(r['mean_seconds'])} |")
        out.append("")
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
    shown = METHODS + tuple(supp)
    rows = {m: {r["name"]: r for r in results[m]["per_theorem"]} for m in shown}
    names = [t.name for t in test] if test else list(rows[METHODS[0]])
    if names:
        reach = results.get("reachability") or {}
        out += ["", "## Per theorem", "",
                *_table_head(["theorem", "difficulty", "menu-reachable", *shown])]
        for n in names:
            diff = rows[METHODS[0]][n]["difficulty"]
            cells = []
            for m in shown:
                r = rows[m][n]
                cells.append(f"yes ({r['calls']})" if r["proved"] else "–")
            out.append(f"| {n} | {diff} | {_fmt(reach.get(n))} | " + " | ".join(cells) + " |")
        out += ["", "Cells: `yes (calls)` when proved, `–` otherwise."]
    return "\n".join(out) + "\n"


def rerender_report(out_dir: str, test: list[Theorem] | None = None) -> str:
    """Rewrite `report.md` from an existing `results.json` without re-running anything."""
    with open(os.path.join(out_dir, "results.json"), encoding="utf-8") as f:
        results = json.load(f)
    add_flags(results)
    _write_results(results, out_dir)
    text = format_report(results, test)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(text)
    return text


# ---------------------------------------------------------------------------------------------
# Phase 2: Claude as a tactic generator
# ---------------------------------------------------------------------------------------------

PHASE2_METHODS = ("claude_whole", "claude_search", "hybrid")
CLAUDE_METHODS = PHASE2_METHODS
# Supplementary (ruling P11, not part of the pre-registered questions): `hybrid` with confidence
# fixed at 0.0, so the search expands every ranked action. It separates Jev's ranking from
# confidence gating (in phase 1 the gating hurt). Its Claude requests are mostly cache hits.
PHASE2_SUPPLEMENTARY = ("hybrid_expand_all",)
WHOLE_PROOF_K = 4
PHASE1_RESULTS_PATH = os.path.join(os.path.dirname(DATA_DIR), "results", "results.json")


def _run_phase2_method(method: str, thm: Theorem, repl, model, shortlister, lib, gen,
                       budget: int = 64) -> SearchResult:
    lib = _without_banned(lib, thm)
    if method == "claude_whole":
        t0 = time.perf_counter()
        calls, proof = 0, None
        kw = {"banned": thm.banned} if thm.banned else {}
        for script in gen.whole_proof(thm.statement, thm.prelude, k=WHOLE_PROOF_K, **kw):
            calls += 1
            if repl.check_proof(thm.statement, list(script), thm.prelude):
                proof = list(script)
                break
        return SearchResult(proof is not None, proof or [], calls, 0, time.perf_counter() - t0)
    if method in ("claude_search", "hybrid", "hybrid_filter", "menu_first", "jev_router"):
        order = {"claude_search": "llm", "hybrid": "jev", "hybrid_filter": "filter",
                 "menu_first": "menu_first", "jev_router": "router"}[method]
        return prove(thm, repl, HybridRanker(model, shortlister, lib, gen, order=order, prelude=thm.prelude,
                                             banned=thm.banned), budget=budget)
    if method == "hybrid_expand_all":
        ranker = HybridRanker(model, shortlister, lib, gen, order="jev", prelude=thm.prelude,
                              banned=thm.banned)
        return prove(thm, repl, ExpandAll(ranker, confidence=0.0), budget=budget)
    raise ValueError(method)


def phase1_references(path: str) -> dict:
    """From a phase-1 `results.json`: `phase1_best` (the best pre-registered method on hard, ties
    broken by METHODS order) and `phase1_fixed_expand_all` (strongest phase-1 method, post hoc)."""
    with open(path, encoding="utf-8") as f:
        p1 = json.load(f)
    best = max(METHODS, key=lambda m: (p1[m]["proved_hard"], -METHODS.index(m)))
    return {"phase1_best": {"method": best, **p1[best]},
            "phase1_fixed_expand_all": {"method": "fixed_expand_all", **p1["fixed_expand_all"]},
            "phase1_n_easy": p1.get("n_easy"), "phase1_n_hard": p1.get("n_hard")}


def phase2_questions(results: dict) -> dict:
    """The pre-registered phase-2 questions, computed from `results` (never typed in by hand)."""
    hyb, cs = results["hybrid"], results["claude_search"]
    reach = results.get("reachability") or {}
    hard = {r["name"] for m in CLAUDE_METHODS for r in results[m]["per_theorem"]
            if r["difficulty"] == "hard"}
    unreachable = [n for n in reach if reach[n] is False and n in hard]
    proved_by = {}
    for n in unreachable:
        who = [m for m in CLAUDE_METHODS
               if any(r["name"] == n and r["proved"] for r in results[m]["per_theorem"])]
        if who:
            proved_by[n] = who
    return {
        "hybrid_hard": hyb["proved_hard"], "claude_search_hard": cs["proved_hard"],
        "hybrid_beats_claude_search": hyb["proved_hard"] > cs["proved_hard"],
        "hybrid_usd": hyb["notional_usd"], "claude_search_usd": cs["notional_usd"],
        "hybrid_usd_not_higher": hyb["notional_usd"] <= cs["notional_usd"],
        "unreachable_hard": unreachable,
        "unreachable_hard_proved": proved_by,
        "unreachable_hard_proved_count": len(proved_by),
    }


def run_phase2(repl, train: list[Theorem], test: list[Theorem], out_dir: str, generator,
               phase1_path: str = PHASE1_RESULTS_PATH, labels_path: str = LABELS_PATH,
               library: list[Lemma] | None = None, reachability: dict[str, bool] | None = None,
               log=None) -> dict:
    """claude_whole, claude_search and hybrid on the test set, next to the phase-1 references.
    `hybrid` uses the model refit on the replay examples plus the saved Claude labels."""
    log = log or (lambda msg: print(msg, file=sys.stderr, flush=True))
    refs = phase1_references(phase1_path)  # fail before any spend if phase 1 is missing
    lemmas = library if library is not None else dump_library(repl)
    lib = {l.name: l for l in lemmas}
    shortlister = Shortlister(lemmas)
    labels = load_labels(labels_path)
    log(f"replaying {len(train)} train theorems, fitting with {len(labels[0])} + {len(labels[1])} "
        f"Claude label examples")
    model, train_stats = train_model(train, repl, shortlister, lib, extra=labels)

    metered = _MeteredGen(generator)
    results: dict = {}
    _run_methods(PHASE2_METHODS + PHASE2_SUPPLEMENTARY, test,
                 lambda method, thm, counting: _run_phase2_method(method, thm, counting, model,
                                                                  shortlister, lib, metered),
                 repl, log, results, out_dir, metered=metered)
    results.update(refs)
    results.update({
        "temperatures": dict(model.temps),
        "train_stats": train_stats,
        "n_easy": sum(t.difficulty == "easy" for t in test),
        "n_hard": sum(t.difficulty == "hard" for t in test),
        "claude_model": getattr(generator, "model", None),
        "effort": getattr(generator, "effort", None),
        "max_usd": generator.max_usd,
        "total_usd": round(generator.usage.usd, 6),
        "claude_usage": dict(vars(generator.usage)),
        "call_capped": any(results[m]["call_capped"] for m in PHASE2_METHODS + PHASE2_SUPPLEMENTARY),
        "budget_capped": any(results[m]["budget_capped"] for m in PHASE2_METHODS + PHASE2_SUPPLEMENTARY),
    })
    if reachability is not None:
        results["reachability"] = {t.name: reachability.get(t.name) for t in test}
    results["questions"] = phase2_questions(results)
    _write_results(results, out_dir)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(format_report_phase2(results, test))
    return results


def format_report_phase2(results: dict, test: list[Theorem] | None = None) -> str:
    ne, nh = results["n_easy"], results["n_hard"]
    n1e, n1h = results.get("phase1_n_easy") or ne, results.get("phase1_n_hard") or nh
    head = _table_head(["method", "proved", "easy", "hard", "mean calls (proved)", "Claude requests",
                        "billed calls", "USD (actual)", "USD (notional)", "refusals", "errors"])

    def row(label, r, e, h, claude):
        c = (f"{r['claude_requests']} | {r['claude_calls']} | {r['usd']:.4f} | "
             f"{r['notional_usd']:.4f}{'+?' if r['notional_unknown'] else ''} | {r['refusals']} | {r['errors']}"
             if claude else "– | – | – | – | – | –")
        return (f"| {label} | {r['proved']}/{e + h} | {r['proved_easy']}/{e} | {r['proved_hard']}/{h} "
                f"| {_fmt(r['mean_calls'])} | {c} |")

    out = ["# Jev proof demo — phase 2 results", ""]
    if results.get("budget_capped"):
        out += [f"**Budget cap reached** (`--max-usd` {results['max_usd']}): some Claude requests were "
                "refused locally and returned no proposals, so the affected rows are not comparable.", ""]
    def label(m):  # caps are flagged inside the method cell, so the row keeps the header's cells
        r = results[m]
        flags = (["budget capped"] if r["budget_capped"] else []) + \
                ([f"call cap ({CALL_CAP}/theorem) hit"] if r["call_capped"] else [])
        return m + (f" ({'; '.join(flags)})" if flags else "")

    out += head
    for m in PHASE2_METHODS:
        out.append(row(label(m), results[m], ne, nh, True))
    b = results["phase1_best"]
    out.append(row(f"phase1_best (`{b['method']}`, phase-1 reference)", b, n1e, n1h, False))
    out += ["", "Reference, post hoc in phase 1 (the strongest phase-1 method, not pre-registered):", "",
            *head,
            row("phase1_fixed_expand_all (phase-1 reference)", results["phase1_fixed_expand_all"], n1e, n1h, False),
            "", "`phase1_*` rows are copied from the phase-1 `results.json`. `claude_whole` asks for "
            f"{WHOLE_PROOF_K} complete scripts and counts a theorem as proved if any passes `check_proof`; "
            "`claude_search` expands Claude's proposals first, then the fixed menu; `hybrid` ranks "
            "Claude's proposals together with the menu using the model refit on phase-1 replays plus "
            "Claude labels. USD (actual) is what was billed; USD (notional) prices every request at its original "
            f"cost, cached or not (`+?`: some cache entries carry no price), and is what question 2 "
            f"compares. At most {CALL_CAP} Claude requests are made per theorem and method.", ""]
    supp = [m for m in PHASE2_SUPPLEMENTARY if m in results]
    if supp:
        out += ["Supplementary (ruling P11, not part of the pre-registered questions): `hybrid_expand_all` "
                "is `hybrid` with confidence fixed at 0.0, so the search expands every ranked action "
                "instead of the top 3 when confident. It separates Jev's ranking from confidence gating. "
                "Its Claude requests are mostly cache hits (USD actual near zero); USD (notional) counts "
                "them at their original price.", "", *head]
        out += [row(label(m), results[m], ne, nh, True) for m in supp]
        out.append("")
    q = results.get("questions") or phase2_questions(results)
    out += ["## Pre-registered questions", "",
            f"1. Does `hybrid` prove more hard theorems than `claude_search` (did Jev add value on top "
            f"of Claude)? **{_fmt(q['hybrid_beats_claude_search'])}**: {q['hybrid_hard']}/{nh} vs "
            f"{q['claude_search_hard']}/{nh}.",
            f"2. At equal or lower USD? **{_fmt(q['hybrid_usd_not_higher'])}**: `hybrid` "
            f"notional ${q['hybrid_usd']:.4f} vs `claude_search` ${q['claude_search_usd']:.4f}.",
            f"3. Hard theorems with no gold proof inside the phase-1 menu (`menu_reachable = false`) "
            f"that any Claude method proved: **{q['unreachable_hard_proved_count']}/"
            f"{len(q['unreachable_hard'])}**"
            + (" (" + "; ".join(f"`{n}` by {', '.join(ms)}" for n, ms in q["unreachable_hard_proved"].items()) + ")"
               if q["unreachable_hard_proved"] else "") + ".",
            "", f"Total Claude spend: ${results.get('total_usd', 0.0):.4f} of ${results.get('max_usd')} "
            f"(`{results.get('claude_model')}`, effort `{results.get('effort')}`).", ""]
    shown = PHASE2_METHODS + tuple(supp) + ("phase1_best", "phase1_fixed_expand_all")
    rows = {m: {r["name"]: r for r in results[m]["per_theorem"]} for m in shown}
    names = [t.name for t in test] if test else [r["name"] for r in results[PHASE2_METHODS[0]]["per_theorem"]]
    reach = results.get("reachability") or {}
    out += ["## Per theorem", "", *_table_head(["theorem", "difficulty", "menu-reachable", *shown])]
    for n in names:
        diff = rows[PHASE2_METHODS[0]][n]["difficulty"]
        cells = []
        for m in shown:
            r = rows[m].get(n)
            cells.append(f"yes ({r['calls']})" if r and r["proved"] else "–")
        out.append(f"| {n} | {diff} | {_fmt(reach.get(n))} | " + " | ".join(cells) + " |")
    out += ["", "Cells: `yes (calls)` when proved, `–` otherwise."]
    return "\n".join(out) + "\n"
