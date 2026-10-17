"""Offline ranking quality on the core training labels (no API calls).

For every `kind` example in `data/claude_labels_core.json` (a state on a proved theorem's final
path, gold = the step actually taken there), compare where the gold lands under several rankers,
with 5-fold cross-validation over theorems' states. Rankers:

- `claude`: Claude's own order (its proposals by rank, then the menu): what `claude_search` does.
- `jev`: the hybrid model's score (kind probability, times `useful` for Claude's proposals),
  trained on the phase-1 replays plus all labels outside the fold: what `hybrid` does.
- `claude_then_jev`: Claude's proposals first, reordered by the model, then the menu by the model.
- `jev_llm_prior`: the model's score times a prior that decays with Claude's rank.

Metrics: top-1 and top-3 hit rate and mean reciprocal rank of the gold option.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

from jev_demo.bench import SEED, train_model
from jev_demo.collect import load_labels
from jev_demo.premises import Shortlister, dump_library
from jev_demo.schema import BinaryQuestion, ChoiceQuestion, answer_key, parse_llm
from jev_demo.theorems import DATA_DIR, load_theorems


def _llm_rank(option: str) -> int | None:
    p = parse_llm(option)
    return None if p is None else p[0]


def rank_options(name: str, model, ex) -> list[str]:
    opts = list(ex.options)
    llm = [o for o in opts if _llm_rank(o) is not None]
    rest = [o for o in opts if _llm_rank(o) is None]
    if name == "claude":
        return sorted(llm, key=_llm_rank) + rest
    qs = [ChoiceQuestion("kind", tuple(opts))] + [BinaryQuestion("useful", option=o) for o in llm]
    ans = model.evaluate(ex.state, qs)
    pk = ans["kind"].probs
    score = {o: pk[o] for o in rest}
    for o in llm:
        score[o] = pk[o] * ans[answer_key(BinaryQuestion("useful", option=o))].p_true
    if name == "jev":
        return sorted(opts, key=lambda o: -score[o])
    if name == "claude_then_jev":
        return sorted(llm, key=lambda o: -score[o]) + sorted(rest, key=lambda o: -score[o])
    if name == "jev_llm_prior":
        prior = {o: (0.5 ** _llm_rank(o) if o in llm else 0.05) for o in opts}
        return sorted(opts, key=lambda o: -score[o] * prior[o])
    raise ValueError(name)


RANKERS = ("claude", "jev", "claude_then_jev", "jev_llm_prior")


def evaluate(repl, folds: int = 5, log=lambda m: print(m, file=sys.stderr, flush=True)) -> dict:
    core_c, core_b = load_labels(os.path.join(DATA_DIR, "claude_labels_core.json"))
    old_c, old_b = load_labels(os.path.join(DATA_DIR, "claude_labels.json"))
    train = load_theorems(os.path.join(DATA_DIR, "train.json"))
    lemmas = dump_library(repl)
    lib = {l.name: l for l in lemmas}
    shortlister = Shortlister(lemmas)
    rng = np.random.default_rng(SEED)
    fold_of = rng.integers(0, folds, size=len(core_c))
    held_states = {}
    out = {r: {"top1": 0, "top3": 0, "rr": 0.0, "n": 0} for r in RANKERS}
    for k in range(folds):
        test = [c for c, f in zip(core_c, fold_of) if f == k]
        states = {c.state for c in test}
        fit_c = [c for c, f in zip(core_c, fold_of) if f != k]
        fit_b = [b for b in core_b if b.state not in states]
        model, _ = train_model(train, repl, shortlister, lib, extra=(old_c + fit_c, old_b + fit_b))
        log(f"fold {k}: {len(test)} held-out kind examples")
        for ex in test:
            for r in RANKERS:
                order = rank_options(r, model, ex)
                pos = order.index(ex.gold) + 1
                s = out[r]
                s["n"] += 1
                s["top1"] += pos == 1
                s["top3"] += pos <= 3
                s["rr"] += 1.0 / pos
        held_states.update({c.state: k for c in test})
    for r, s in out.items():
        n = max(s["n"], 1)
        s.update(top1=round(s["top1"] / n, 3), top3=round(s["top3"] / n, 3), mrr=round(s["rr"] / n, 3))
        del s["rr"]
    return out


if __name__ == "__main__":
    from jev_demo.repl_client import ReplClient

    with ReplClient() as repl:
        res = evaluate(repl)
    print(json.dumps(res, indent=1))
