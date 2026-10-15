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
from jev_demo.theorems import DATA_DIR, load_theorems


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
        reach = _load_reachability()
        run_phase2(repl, load_theorems(args.train), load_theorems(args.test), args.out, gen,
                   phase1_path=args.phase1, labels_path=args.labels, reachability=reach)
    with open(os.path.join(args.out, "report.md"), encoding="utf-8") as f:
        print(f.read())


def _load_reachability():
    path = os.path.join(DATA_DIR, "test_reachability.json")
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
    args = ap.parse_args(argv)
    if args.cmd in ("collect", "run-phase2"):
        _phase2(args)
        return
    if args.cmd == "report":
        print(rerender_report(args.out, load_theorems(args.test)))
        return
    reach = _load_reachability()
    with ReplClient() as repl:
        run_experiment(repl, load_theorems(args.train), load_theorems(args.test), args.out,
                       reachability=reach)
    with open(os.path.join(args.out, "report.md"), encoding="utf-8") as f:
        print(f.read())


if __name__ == "__main__":
    main()
