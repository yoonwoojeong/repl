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
        body = re.sub(r"--[^\n]*", "", m.group(2))  # line comments would swallow the joined rest
        thms.append(Theorem(m.group(1), " ".join(body.split()), "", (), "hard"))
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


def run_menu_search(repl, thms, budget: int = 64, extra_set: bool = False) -> dict:
    from jev_demo.search import FixedOrderRanker, prove
    if not extra_set:
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


_NAMES_CMD = """open Lean in
#eval show CoreM Unit from do
  let env ← getEnv
  let mut out : Array String := #[]
  for (n, ci) in env.constants.toList do
    if let .thmInfo _ := ci then
      if !n.isInternalDetail then out := out.push n.toString
  IO.println (String.intercalate "\\n" out.toList)"""


def theorem_names(repl) -> set[str]:
    """Names of all theorems in the REPL's base environment (here: Mathlib)."""
    reply = repl.command(_NAMES_CMD, timeout_s=1200)
    names = set()
    for m in reply.get("messages", []):
        if m.get("severity") == "info":
            names.update(x for x in m["data"].splitlines() if x)
    if not names:
        raise RuntimeError(f"theorem name dump failed: {str(reply)[:500]}")
    return names


class Bm25Premises:
    """BM25 premise retrieval over the LeanDojo Benchmark 4 corpus (Mathlib, Nov 2023), restricted
    to premise names that still exist in the benchmark's Mathlib, so retrieved names elaborate."""

    def __init__(self, names: set[str]):
        import bm25s

        from jev_demo.bm25_baseline import tok
        from jev_demo.looped import load_corpus
        corpus = load_corpus()
        self.premises = [p for p in corpus.all_premises if p.full_name in names]
        self.bm25 = bm25s.BM25()
        self.bm25.index(tok([p.serialize() for p in self.premises]), show_progress=False)
        self._cache: dict[str, list[str]] = {}

    def shortlist(self, goal: str, k: int = 4) -> list[str]:
        import bm25s
        import numpy as np

        from jev_demo.bm25_baseline import TOKEN_PATTERN
        if goal not in self._cache:
            q = bm25s.tokenize(goal, stopwords=None, token_pattern=TOKEN_PATTERN, show_progress=False,
                               return_ids=False)[0]
            if not q:
                self._cache[goal] = []
            else:
                s = self.bm25.get_scores(q)
                top = np.argsort(-s)[:k]
                self._cache[goal] = [self.premises[i].full_name for i in top if s[i] > 0]
        return self._cache[goal]


def premise_steps(premises: list[str]) -> list[str]:
    """Jev's own lemma-naming steps from the top BM25 premises (no Claude)."""
    if not premises:
        return []
    ps = ", ".join(premises[:4])
    return [f"simp [{ps}]", f"norm_num [{ps}]"] + [f"rw [{p}]" for p in premises[:2]]


def setup_menu(repl, names_cache: str | None = None) -> Bm25Premises:
    """Mathlib automation plus BM25-premise steps in every menu."""
    if names_cache and os.path.exists(names_cache):
        import gzip
        with gzip.open(names_cache, "rt", encoding="utf-8") as f:
            names = set(f.read().split())
    else:
        names = theorem_names(repl)
        if names_cache:
            import gzip
            with gzip.open(names_cache, "wt", encoding="utf-8") as f:
                f.write("\n".join(sorted(names)))
    bm25 = Bm25Premises(names)
    set_extra_menu(MATHLIB_MENU, goal_steps=lambda g: premise_steps(bm25.shortlist(g)))
    return bm25


def closes_labels(repl, thms, depth: int = 1, max_states: int = 6, log=print) -> list:
    """Lean-only `closes` labels (as `posttrain`): every menu tactic at each problem's root and at
    up to `max_states` states one step below it. No audit (miniF2F bans no lemma)."""
    from jev_demo.posttrain import label_state
    from jev_demo.search import _key
    out = []
    for i, t in enumerate(thms):
        try:
            ps, goal = repl.start_theorem(t.statement, t.prelude)
        except RuntimeError:
            continue
        frontier, seen, n = [(ps, goal, 1, [], 0)], set(), 0
        while frontier and n < max_states:
            ps, goal, ng, prefix, d = frontier.pop(0)
            if _key(goal) in seen:
                continue
            seen.add(_key(goal))
            n += 1
            kids = label_state(repl, None, t, ps, goal, ng, prefix, False, out, log)
            if d < depth:
                frontier += [(p, g, k, pre, d + 1) for p, g, k, pre in kids]
        log(f"[{i + 1}/{len(thms)}] {t.name}: {len(out)} labels, {sum(b.label for b in out)} closing")
    return out


def run_claude(repl, thms, out_dir: str, methods, labels: str, max_usd: float, cache_dir: str,
               model: str = "claude-opus-5-5", effort: str = "medium") -> dict:
    """Paid: the Claude methods of experiment 3 (`claude_search`, `jev_router`) on miniF2F."""
    if os.environ.get("ANTHROPIC_RUN_LIVE") != "1":
        raise SystemExit("set ANTHROPIC_RUN_LIVE=1 to call the Anthropic API (this spends money)")
    from jev_demo import exp3
    from jev_demo.claude_gen import ClaudeGenerator
    from jev_demo.prompts import MATHLIB_SYSTEM_PROMPT
    gen = ClaudeGenerator(model=model, effort=effort, max_usd=max_usd, cache_dir=cache_dir,
                          system_prompt=MATHLIB_SYSTEM_PROMPT)
    return exp3.run(repl, [], thms, out_dir, gen, list(methods), label_paths=[labels])


def main(argv=None) -> None:
    import argparse
    from jev_demo.collect import save_labels
    from jev_demo.repl_client import ReplClient

    ap = argparse.ArgumentParser(prog="python -m jev_demo.minif2f")
    ap.add_argument("mode", choices=("single", "menu_search", "jev_search", "labels", "claude"))
    ap.add_argument("root")
    ap.add_argument("split", choices=("valid", "test"))
    ap.add_argument("repl_bin")
    ap.add_argument("--out", default=None)
    ap.add_argument("--names-cache", default=None)
    ap.add_argument("--labels", default=None)
    ap.add_argument("--methods", default="claude_search,jev_router")
    ap.add_argument("--max-usd", type=float, default=1.0)
    ap.add_argument("--cache-dir", default="jev_demo/cache/minif2f")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    header, thms = load(a.root, a.split)
    thms = thms[:a.limit] if a.limit else thms
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results_free", "minif2f")
    os.makedirs(base, exist_ok=True)
    with ReplClient(repl_path=a.repl_bin, cwd=a.root, timeout_s=20, header=header) as repl:
        if a.mode == "single":
            res = run_single(repl, thms)
        elif a.mode == "menu_search":
            res = run_menu_search(repl, thms)
        elif a.mode == "jev_search":  # menu + BM25-premise steps, no Claude
            setup_menu(repl, a.names_cache)
            res = run_menu_search(repl, thms, extra_set=True)
            res["method"] = "jev_search"
        elif a.mode == "labels":
            setup_menu(repl, a.names_cache)
            labels = closes_labels(repl, thms, log=lambda m: print(m, file=sys.stderr, flush=True))
            save_labels(a.out, [], labels)
            print(f"wrote {len(labels)} closes labels ({sum(b.label for b in labels)} closing) to {a.out}")
            return
        else:
            setup_menu(repl, a.names_cache)
            run_claude(repl, thms, a.out, a.methods.split(","), a.labels, a.max_usd, a.cache_dir)
            return
    res.update(split=a.split, header=header)
    with open(os.path.join(base, f"{a.split}_{res['method']}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    print(f"miniF2F {a.split} {res['method']}: {res['proved']}/{res['n']}")


if __name__ == "__main__":
    main()
