"""`python -m jev_demo run --out jev_demo/results` — run the phase-1 experiment."""

from __future__ import annotations

import argparse
import json
import os

from jev_demo.bench import run_experiment
from jev_demo.repl_client import ReplClient
from jev_demo.theorems import DATA_DIR, load_theorems


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m jev_demo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="train on train.json, evaluate every method on test.json")
    run.add_argument("--out", default=os.path.join("jev_demo", "results"))
    run.add_argument("--train", default=os.path.join(DATA_DIR, "train.json"))
    run.add_argument("--test", default=os.path.join(DATA_DIR, "test.json"))
    args = ap.parse_args(argv)
    reach_path = os.path.join(DATA_DIR, "test_reachability.json")
    reach = None
    if os.path.exists(reach_path):
        with open(reach_path, encoding="utf-8") as f:
            reach = json.load(f)
    with ReplClient() as repl:
        run_experiment(repl, load_theorems(args.train), load_theorems(args.test), args.out,
                       reachability=reach)
    with open(os.path.join(args.out, "report.md"), encoding="utf-8") as f:
        print(f.read())


if __name__ == "__main__":
    main()
