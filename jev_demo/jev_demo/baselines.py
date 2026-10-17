"""Single-call automation baselines (`grind`, `try?`)."""

from __future__ import annotations

import time

from jev_demo.search import SearchResult
from jev_demo.theorems import Theorem


def suggestion(infos: list[str]) -> str | None:
    """The first tactic suggested by a `Try this:` / `Try these:` info message, if any."""
    for info in infos:
        lines = info.splitlines()
        for j, line in enumerate(lines):
            s = line.strip()
            if s.startswith("Try this:"):
                tac = s[len("Try this:"):].strip()
            elif s.startswith("Try these:") and j + 1 < len(lines):
                tac = lines[j + 1].strip()
            else:
                continue
            for prefix in ("[apply] ", "• "):
                if tac.startswith(prefix):
                    tac = tac[len(prefix):].strip()
            if tac:
                return tac
    return None


def single_shot(thm: Theorem, repl, tactic: str, timeout_s: float) -> SearchResult:
    """`intros`, then `tactic` once; if it leaves goals open but suggests a tactic, run that once.

    `intros` is not counted as a call. Success needs a `completed` run and a passing
    `check_proof` of the tactics actually run, never a suggestion alone.
    """
    t0 = time.perf_counter()
    trace: list[dict] = []
    ps, _ = repl.start_theorem(thm.statement, thm.prelude)
    prefix: list[str] = []
    r = repl.tactic("intros", ps)
    if r.ok and r.proof_state is not None and not r.completed:
        ps, prefix = r.proof_state, ["intros"]
    calls = 0

    def run(tac: str):
        nonlocal calls
        calls += 1
        res = repl.tactic(tac, ps, timeout_s=timeout_s)
        proved = res.ok and res.completed and repl.check_proof(thm.statement, prefix + [tac], thm.prelude)
        trace.append({"chosen": tac, "ok": res.ok, "completed": res.completed, "error": res.error,
                      "infos": res.infos, "proved": proved})
        return res, proved

    def done(proved: bool, tactics: list[str]) -> SearchResult:
        return SearchResult(proved, tactics, calls, 0, time.perf_counter() - t0, trace)

    res, proved = run(tactic)
    if proved:
        return done(True, prefix + [tactic])
    follow = None if res.completed else suggestion(res.infos)
    if follow is not None:
        _, proved = run(follow)
        if proved:
            return done(True, prefix + [follow])
    return done(False, [])
