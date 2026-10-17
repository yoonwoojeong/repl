"""`python -m jev_demo run --out jev_demo/results` — run the phase-1 experiment.

Phase 2 (needs `ANTHROPIC_API_KEY`, and `ANTHROPIC_RUN_LIVE=1` to confirm spending money):
`python -m jev_demo collect` labels Claude's proposals on the training theorems, then
`python -m jev_demo run-phase2 --out jev_demo/results_phase2` runs the Claude methods."""

from __future__ import annotations

import argparse
import json
import os

from jev_demo.bench import PHASE1_RESULTS_PATH, rerender_report, run_experiment, run_phase2
from jev_demo.collect import LABELS_PATH, collect
from jev_demo.repl_client import ReplClient
from jev_demo.theorems import DATA_DIR, load_theorems, reachability_path


def _phase2(args) -> None:
    if os.environ.get("ANTHROPIC_RUN_LIVE") != "1":
        raise SystemExit(f"`{args.cmd}` calls the Anthropic API and spends money: set ANTHROPIC_API_KEY "
                         "and ANTHROPIC_RUN_LIVE=1 to confirm.")
    from jev_demo.claude_gen import ClaudeGenerator
    from jev_demo.premises import Shortlister, dump_library

    gen = ClaudeGenerator(model=args.claude_model, effort=args.effort, max_usd=args.max_usd)
    with ReplClient() as repl:
        if args.cmd == "collect":
            lemmas = dump_library(repl)
            choice, binary = collect(load_theorems(args.train), repl, gen, Shortlister(lemmas),
                                     {l.name: l for l in lemmas}, out_path=args.labels)
            print(f"wrote {len(choice)} choice and {len(binary)} binary labels to {args.labels}; "
                  f"{gen.usage}")
            return
        reach = _load_reachability(args.test)
        run_phase2(repl, load_theorems(args.train), load_theorems(args.test), args.out, gen,
                   phase1_path=args.phase1, labels_path=args.labels, reachability=reach)
    with open(os.path.join(args.out, "report.md"), encoding="utf-8") as f:
        print(f.read())


def _exp3(args) -> None:
    from jev_demo import exp3
    from jev_demo.claude_gen import ClaudeGenerator

    if not args.offline and os.environ.get("ANTHROPIC_RUN_LIVE") != "1":
        raise SystemExit("`exp3` calls the Anthropic API and spends money: set ANTHROPIC_API_KEY and "
                         "ANTHROPIC_RUN_LIVE=1 to confirm, or pass --offline to replay the disk cache.")
    gen = ClaudeGenerator(model=args.claude_model, effort=args.effort, max_usd=args.max_usd,
                          offline=args.offline, cache_dir=args.cache_dir)
    methods = [m for m in args.methods.split(",") if m]
    unknown = set(methods) - set(exp3.METHODS)
    if unknown:
        raise SystemExit(f"unknown methods {sorted(unknown)}; choose from {list(exp3.METHODS)}")
    labels = [p for p in args.labels.split(",") if p]
    with ReplClient() as repl:
        test = load_theorems(args.test)
        test = test[:args.limit] if args.limit else test
        train = [] if args.train == "none" else load_theorems(args.train)  # "none": labels only
        exp3.run(repl, train, test, args.out, gen, methods,
                 label_paths=labels, labels_out=args.labels_out, lean_budget=args.lean_budget,
                 claude_cap=args.claude_cap, library_path=args.library)
    with open(os.path.join(args.out, "report.md"), encoding="utf-8") as f:
        print(f.read())


def _load_reachability(test_path: str):
    path = reachability_path(test_path)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m jev_demo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="train on train.json, evaluate every method on test.json")
    run.add_argument("--out", default=os.path.join("jev_demo", "results"))
    run.add_argument("--train", default=os.path.join(DATA_DIR, "train.json"))
    run.add_argument("--test", default=os.path.join(DATA_DIR, "test.json"))
    rep = sub.add_parser("report", help="re-render report.md from an existing results.json")
    rep.add_argument("--out", default=os.path.join("jev_demo", "results"))
    rep.add_argument("--test", default=os.path.join(DATA_DIR, "test.json"))
    for name, help_ in (("collect", "label Claude's proposals on the training gold states (costs money)"),
                        ("run-phase2", "run the Claude methods on test.json (costs money)")):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--claude-model", default="claude-opus-5-5")
        sp.add_argument("--effort", default="medium")
        sp.add_argument("--max-usd", type=float, default=10.0)
        sp.add_argument("--train", default=os.path.join(DATA_DIR, "train.json"))
        sp.add_argument("--labels", default=LABELS_PATH)
        if name == "run-phase2":
            sp.add_argument("--out", default=os.path.join("jev_demo", "results_phase2"))
            sp.add_argument("--test", default=os.path.join(DATA_DIR, "test.json"))
            sp.add_argument("--phase1", default=PHASE1_RESULTS_PATH)
    e3 = sub.add_parser("exp3", help="Claude methods on a core-benchmark split, with paired stats "
                                     "(costs money unless --offline)")
    e3.add_argument("--test", required=True, help="e.g. jev_demo/data/core_dev.json")
    e3.add_argument("--out", required=True)
    e3.add_argument("--methods", default="claude_whole,claude_search,hybrid")
    e3.add_argument("--labels", default="", help="comma-separated label files for the hybrid model")
    e3.add_argument("--labels-out", default=None, help="write trace labels from claude_search here")
    e3.add_argument("--train", default=os.path.join(DATA_DIR, "train.json"))
    e3.add_argument("--claude-model", default="claude-opus-5-5")
    e3.add_argument("--effort", default="medium")
    e3.add_argument("--max-usd", type=float, default=10.0)
    e3.add_argument("--offline", action="store_true", help="replay the disk cache; never call the API")
    e3.add_argument("--limit", type=int, default=0, help="only the first N theorems (a cheap pilot)")
    e3.add_argument("--lean-budget", type=int, default=64, help="Lean calls per lemma")
    e3.add_argument("--claude-cap", type=int, default=16, help="Claude requests per lemma and method")
    e3.add_argument("--library", default=None, help="premise library JSON (default data/library.json)")
    e3.add_argument("--cache-dir", default="jev_demo/cache/claude",
                    help="Claude response cache; an empty directory gives fresh, independent samples")
    args = ap.parse_args(argv)
    if args.cmd == "exp3":
        _exp3(args)
        return
    if args.cmd in ("collect", "run-phase2"):
        _phase2(args)
        return
    if args.cmd == "report":
        print(rerender_report(args.out, load_theorems(args.test)))
        return
    reach = _load_reachability(args.test)
    with ReplClient() as repl:
        run_experiment(repl, load_theorems(args.train), load_theorems(args.test), args.out,
                       reachability=reach)
    with open(os.path.join(args.out, "report.md"), encoding="utf-8") as f:
        print(f.read())


if __name__ == "__main__":
    main()
