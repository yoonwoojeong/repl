"""Post-training data for the Jev router, generated with Lean only (no API calls).

For each core training lemma that `claude_search` proved (`results_exp3/train`), replay its proof
and take every state on the path, then explore up to `depth` menu steps further from each. At
every state, run every menu tactic once and record `BinaryExample("closes", state, tactic, y)`:
y is True iff the tactic closes the first goal (the proof completes, or fewer goals remain).
At a lemma's root a closing tactic only counts if the `Auditor` finds no banned constant in it
(otherwise `simp`/`exact?` would be labelled as closing via the lemma itself).

Output: `data/jev_closes_labels.json` (the `save_labels` format; choice list empty).
"""

from __future__ import annotations

import json
import os
import sys

from jev_demo.actions import menu
from jev_demo.collect import save_labels
from jev_demo.corebench import Auditor
from jev_demo.model import BinaryExample
from jev_demo.search import _key
from jev_demo.theorems import DATA_DIR, load_theorems

OUT_PATH = os.path.join(DATA_DIR, "jev_closes_labels.json")


def _closes(res, n_before: int) -> bool:
    return bool(res.ok and (res.completed or len(res.goals) < n_before))


def label_state(repl, auditor, thm, ps, goal, n_goals, prefix, at_root, out, log) -> list:
    """Try every menu tactic at one state; append labels; return advancing children."""
    children = []
    for tac in menu(goal, True):
        res = repl.tactic(tac, ps)
        y = _closes(res, n_goals)
        if y and at_root:
            y = auditor.violations(thm.statement, prefix + [tac], thm.banned) == []
        out.append(BinaryExample("closes", goal, tac, y))
        if res.ok and res.goals and _key(res.goals[0]) != _key(goal) and not y:
            children.append((res.proof_state, res.goals[0], len(res.goals), prefix + [tac]))
    return children


def generate(repl, auditor, results_path: str, train_path: str, depth: int = 1,
             max_states: int = 40, log=lambda m: print(m, file=sys.stderr, flush=True)) -> list:
    with open(results_path, encoding="utf-8") as f:
        res = json.load(f)
    thms = {t.name: t for t in load_theorems(train_path)}
    proved = [r for r in res["claude_search"]["per_theorem"] if r["proved"]]
    out: list[BinaryExample] = []
    for i, r in enumerate(proved):
        thm = thms[r["name"]]
        ps, goal = repl.start_theorem(thm.statement, thm.prelude)
        frontier = [(ps, goal, 1, [], 0)]
        for step in r["tactics"]:  # the proof path itself
            x = repl.tactic(step, frontier[-1][0])
            if not x.ok or not x.goals:
                break
            frontier.append((x.proof_state, x.goals[0], len(x.goals), frontier[-1][3] + [step], 0))
        seen, n = set(), 0
        while frontier and n < max_states:
            ps, goal, ng, prefix, d = frontier.pop(0)
            if _key(goal) in seen:
                continue
            seen.add(_key(goal))
            n += 1
            kids = label_state(repl, auditor, thm, ps, goal, ng, prefix, not prefix, out, log)
            if d < depth:
                frontier += [(p, g, k, pre, d + 1) for p, g, k, pre in kids]
        log(f"[{i + 1}/{len(proved)}] {thm.name}: {n} states, {len(out)} labels so far, "
            f"{sum(b.label for b in out)} closing")
    return out


if __name__ == "__main__":
    from jev_demo.repl_client import ReplClient

    with ReplClient(timeout_s=10) as repl, ReplClient(timeout_s=60) as arepl:
        labels = generate(repl, Auditor(arepl),
                          os.path.join(os.path.dirname(DATA_DIR), "results_exp3", "train", "results.json"),
                          os.path.join(DATA_DIR, "core_train.json"))
    save_labels(OUT_PATH, [], labels)
    print(f"wrote {len(labels)} closes labels ({sum(b.label for b in labels)} closing) to {OUT_PATH}")
