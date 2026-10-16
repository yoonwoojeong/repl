"""How far Jev gets with no Claude at all, with lower-level (premise) actions. No API calls.

Claude's successful proof steps are usually one compound step that names library lemmas, e.g.
`intro xs; induction xs <;> simp [List.foo, List.bar]` (74% of steps name a lemma). The router's
own actions are only the fixed menu (`simp`, `omega`, `intro`, `induction x <;> simp_all`, ...),
so every such step is a Claude request. Here Jev composes those steps itself from a premise
shortlist: premise sets (`simp [P]`, `simp_all [P]`, `grind [P]`), structure + premises
(`induction x <;> simp_all [P]`, `cases x <;> simp_all [P]`) and single premises (`rw [p]`,
`exact p`, `apply p`, `simp [p]`).

Variants: `menu` (the fixed menu only), `tfidf` (premises from the untrained TF-IDF shortlist)
and `knn` (premises from `premise_knn.KnnPremises`, trained on the library's own proofs). Every
proof is audited (the banned lemma and aliases are rejected), as in experiment 3.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time

from jev_demo.actions import menu
from jev_demo.corebench import Auditor, AuditedRepl
from jev_demo.premise_knn import KnnPremises, load_usage
from jev_demo.premises import Shortlister, make_lemma
from jev_demo.search import prove
from jev_demo.theorems import DATA_DIR, load_theorems

N_SET, N_SINGLE = 8, 6
_INDUCT = re.compile(r"^induction (\S+) <;> simp_all$")


def premise_actions(goal: str, premises: list[str]) -> list[str]:
    items = list(menu(goal, True))
    if not premises:
        return items
    ps = ", ".join(premises[:N_SET])
    out = [t for t in items if not t.startswith(("induction", "cases"))]
    out += [f"simp [{ps}]", f"simp_all [{ps}]", f"grind [{', '.join(premises[:4])}]"]
    for t in items:
        m = _INDUCT.match(t)
        if m:
            out += [f"induction {m.group(1)} <;> simp_all [{ps}]", f"cases {m.group(1)} <;> simp_all [{ps}]"]
    out += [t for t in items if t.startswith(("induction", "cases"))]
    for p in premises[:N_SINGLE]:
        out += [f"rw [{p}]", f"exact {p}", f"apply {p}", f"simp [{p}]"]
    return list(dict.fromkeys(out))


class PremiseRanker:
    """Fixed order over `premise_actions`; confidence 0, so the search tries every action."""

    def __init__(self, selector, banned: tuple[str, ...], k: int = 16):
        self.selector, self.banned, self.k = selector, banned, k

    def rank(self, goal: str):
        if self.selector is None:
            prem = []
        else:
            prem = [p for p in self.selector.shortlist(goal, k=self.k + len(self.banned))
                    if p not in self.banned][:self.k]
        acts = premise_actions(goal, prem)
        return [(a, 1.0 / len(acts)) for a in acts], 0.0, 0.5

    def claude_actions(self, goal: str) -> list[str]:
        return []


def run(split_path: str, variant: str, budget: int = 64, log=print) -> dict:
    from jev_demo.repl_client import ReplClient

    with open(os.path.join(DATA_DIR, "library.json"), encoding="utf-8") as f:
        lib = [make_lemma(r["name"], r["type"]) for r in json.load(f)]
    thms = load_theorems(split_path)
    held_out = set()
    for s in ("core_dev.json", "core_test.json"):
        held_out |= {t.banned[0] for t in load_theorems(os.path.join(DATA_DIR, s))}
    selector = {"menu": None, "tfidf": Shortlister(lib),
                "knn": KnnPremises(lib, load_usage(), exclude=held_out, k=128, lam=2.0, power=2.0)}[variant]
    rows = []
    with ReplClient(timeout_s=20) as repl, ReplClient(timeout_s=60) as arepl:
        auditor = Auditor(arepl)
        for i, thm in enumerate(thms):
            checked = AuditedRepl(repl, auditor, thm.banned)
            t0 = time.perf_counter()
            r = prove(thm, checked, PremiseRanker(selector, thm.banned), budget=budget)
            rows.append({"name": thm.name, "proved": r.proved, "tactics": r.tactics, "calls": r.calls,
                         "seconds": round(time.perf_counter() - t0, 2)})
            log(f"[{i + 1}/{len(thms)}] {variant} {'yes' if r.proved else '-  '} {r.calls:3d} {thm.name} "
                f"{r.tactics if r.proved else ''}")
    return {"variant": variant, "split": os.path.basename(split_path), "budget": budget,
            "proved": sum(r["proved"] for r in rows), "n": len(rows), "per_theorem": rows}


if __name__ == "__main__":
    split, variant = sys.argv[1], sys.argv[2]
    out = run(os.path.join(DATA_DIR, f"core_{split}.json"), variant,
              log=lambda m: print(m, file=sys.stderr, flush=True))
    d = os.path.join(os.path.dirname(DATA_DIR), "results_exp3", "jev_alone")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{split}_{variant}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"{split} {variant}: {out['proved']}/{out['n']}")
