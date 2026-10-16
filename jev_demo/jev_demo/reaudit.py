"""Re-audit every proof in experiment-3 results with audit v2 (`corebench.analyse`). No API calls.

For each run and method: how many counted proofs (a) use a constant definitionally equal to the
target (now rejected) and (b) are one-lemma proofs (reported). Writes `results_exp3/reaudit.json`.
"""

from __future__ import annotations

import json
import os
import sys

from jev_demo.corebench import Auditor, analyse
from jev_demo.theorems import DATA_DIR, load_theorems

RUNS = {"test": "core_test.json", "dev_v1": "core_dev.json", "dev_v2": "core_dev.json",
        **{f"test_rep{r}_{m}": "core_test.json" for r in (1, 2) for m in ("claude_search", "jev_router")}}
RESULTS = os.path.join(os.path.dirname(DATA_DIR), "results_exp3")


def _methods(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["methods"]


def main() -> None:
    from jev_demo.repl_client import ReplClient

    path = os.path.join(RESULTS, "reaudit.json")
    out: dict = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    with ReplClient(timeout_s=120) as arepl:
        auditor = Auditor(arepl)
        for run, split in RUNS.items():
            key = run.rsplit("_", 2)[0] if run.startswith("test_rep") else run  # test_rep1_jev_router -> test_rep1
            path = os.path.join(RESULTS, run, "results.json")
            if not os.path.exists(path) or all(m in out.get(key, {}) for m in _methods(path)):
                continue  # missing, or already audited
            thms = {t.name: t for t in load_theorems(os.path.join(DATA_DIR, split))}
            res = json.load(open(path, encoding="utf-8"))
            for m in res["methods"]:
                rows = []
                for r in res[m]["per_theorem"]:
                    if not r["proved"]:
                        continue
                    t = thms[r["name"]]
                    a = analyse(auditor, t.statement, r["tactics"], t.banned, t.prelude)
                    rows.append({"name": r["name"], **(a or {"error": "did not re-elaborate"})})
                rejected = [x["name"] for x in rows if x.get("banned") or x.get("defeq_aliases")
                            or x.get("error")]
                one = [x["name"] for x in rows if x.get("one_lemma")]
                out.setdefault(key, {})[m] = {"proved": len(rows), "rejected_v2": rejected,
                                              "one_lemma": one, "rows": rows}
                print(f"{run:22s} {m:14s} proved {len(rows):3d}  rejected by v2 {len(rejected):2d}  "
                      f"one-lemma {len(one):2d}", file=sys.stderr, flush=True)
    with open(os.path.join(RESULTS, "reaudit.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
