"""miniF2F (Lean 4 port, github.com/yangky11/miniF2F-lean4, Lean v4.24.0 + Mathlib) for Jev.

The standard benchmark replacing corebench: 244 validation and 244 test problems; a problem is
solved when Lean accepts the proof with no `sorry` (the REPL reports sorries and errors). Results
are reported as solve rate under a fixed budget (pass@1 of one search per problem, with the
search budget stated), plus Claude requests and USD for Claude methods.

This module loads the problems and runs the Lean-only baselines (no API calls):
- `single`: each tactic of `MATHLIB_MENU + BASE_MENU + AUTOMATION` alone (a problem counts as
  solved if any one tactic proves it);
- `menu_search`: best-first search over the fixed menu (64 Lean calls per problem).
Deviation: `maxHeartbeats` is Lean's default (200000) instead of the files' 0 (unlimited), so a
runaway tactic fails inside Lean instead of hanging the REPL. It expects LEAN_PATH to point at the miniF2F project's Mathlib (`lake env printenv LEAN_PATH`).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time

from jev_demo.actions import AUTOMATION, BASE_MENU, MATHLIB_MENU, set_extra_menu
from jev_demo.theorems import Theorem

HEARTBEATS = 200000  # Lean's default; the problem files say 0 (unlimited)
_DECL = re.compile(r"theorem\s+(\S+)\s*(.*?):=\s*by\s+sorry\s*$", re.S)
_OPEN = re.compile(r"^open .*$", re.M)


def load(root: str, split: str) -> tuple[str, list[Theorem]]:
    """(header, problems) from `<root>/MiniF2F/<Valid|Test>/*.lean`. The header (imports,
    options, `open`) is the same for every problem file and becomes the REPL's base env."""
    d = os.path.join(root, "MiniF2F", split.capitalize())
    thms, headers = [], set()
    for fn in sorted(os.listdir(d)):
        text = open(os.path.join(d, fn), encoding="utf-8").read()
        m = _DECL.search(text)
        if not m:
            raise ValueError(f"cannot parse {fn}")
        headers.add(text[:m.start()].strip())
        thms.append(Theorem(m.group(1), " ".join(m.group(2).split()), "", (), "hard"))
    if len(headers) != 1:
        raise ValueError(f"problem headers differ: {headers}")
    header = headers.pop().replace("set_option maxHeartbeats 0", f"set_option maxHeartbeats {HEARTBEATS}")
    return header, thms


def run_single(repl, thms) -> dict:
    tactics = list(dict.fromkeys(MATHLIB_MENU + BASE_MENU + AUTOMATION))
    rows = []
    for t in thms:
        ok = [tac for tac in tactics if repl.check_proof(t.statement, [tac])]
        rows.append({"name": t.name, "proved": bool(ok), "tactics": ok})
    return {"method": "single", "tactics": tactics, "proved": sum(r["proved"] for r in rows),
            "n": len(rows), "per_theorem": rows}


def run_menu_search(repl, thms, budget: int = 64) -> dict:
    from jev_demo.search import FixedOrderRanker, prove
    set_extra_menu(MATHLIB_MENU)
    rows = []
    for t in thms:
        t0 = time.perf_counter()
        try:
            r = prove(t, repl, FixedOrderRanker(), budget=budget)
            rows.append({"name": t.name, "proved": r.proved, "tactics": r.tactics, "calls": r.calls,
                         "seconds": round(time.perf_counter() - t0, 1)})
        except RuntimeError as e:  # statement did not elaborate
            rows.append({"name": t.name, "proved": False, "error": str(e)[:300]})
    return {"method": "menu_search", "budget": budget, "proved": sum(r["proved"] for r in rows),
            "n": len(rows), "per_theorem": rows}


if __name__ == "__main__":
    from jev_demo.repl_client import ReplClient

    root, split, method, repl_bin = sys.argv[1:5]
    header, thms = load(root, split)
    with ReplClient(repl_path=repl_bin, cwd=root, timeout_s=20, header=header) as repl:
        res = (run_single if method == "single" else run_menu_search)(repl, thms)
    res.update(split=split, header=header)
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results_free", "minif2f")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, f"{split}_{method}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    print(f"miniF2F {split} {method}: {res['proved']}/{res['n']}")
