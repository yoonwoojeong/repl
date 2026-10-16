"""Hybrid ranker: Claude's proposals ranked together with the phase-1 action space.

Inside model questions and training examples a proposal is the kind option `llm|{i}|{tactic}`
(`i` = Claude's rank after deduplication), so the featurizer sees both the source and Claude's own
rank. `HybridRanker.rank` returns executable tactics only: the prefix is stripped.
"""

from __future__ import annotations

from typing import Literal

from jev_demo.actions import menu
from jev_demo.premises import Lemma, Shortlister
from jev_demo.schema import LLM_PREFIX, parse_llm
from jev_demo.search import ASK_CLAUDE, ModelRanker, Ranking, _key



def strip_llm(option: str) -> str:
    """Recover the tactic from `llm|{i}|{tactic}`; other options are returned unchanged."""
    parsed = parse_llm(option)
    return option if parsed is None else parsed[1]


def llm_options(proposals, items, exclude=()) -> dict[str, str]:
    """`{llm option: tactic}` for the proposals, stripped, deduplicated against each other, the
    menu `items` and `exclude`. Claude's order is kept; `i` counts the survivors."""
    seen = set(items) | set(exclude)
    out: dict[str, str] = {}
    for t in proposals:
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            out[f"{LLM_PREFIX}{len(out)}|{t}"] = t
    return out


class HybridRanker:
    def __init__(self, model, shortlister: Shortlister, lib: dict[str, Lemma], generator,
                 order: Literal["jev", "llm", "filter", "menu_first", "router"] = "jev", prelude: str = "",
                 banned: tuple[str, ...] = (), tau: float = 0.3, route_tau: float = 0.5,
                 route_k: int = 3):
        """One ranker per theorem: `prelude` is passed to the generator with every goal."""
        self.base = ModelRanker(model, shortlister, lib)
        self.generator, self.order, self.prelude, self.banned = generator, order, prelude, banned
        self.tau = tau  # order="filter": proposals with p(useful) below this are tried last
        # order="router": if some menu tactic has p(closes) >= route_tau, try the route_k most
        # likely ones before asking Claude at this state
        self.route_tau, self.route_k = route_tau, route_k
        self._root: str | None = None  # key of the first goal ranked: the theorem itself
        self._proposals: dict[str, list[str]] = {}  # goal key -> Claude's proposals (memo)
        self._failed: dict[str, list[str]] = {}  # goal key -> tactics tried there that failed

    def note_failed(self, goal: str, tactics) -> None:
        """Record tactics that were tried at `goal` and did not succeed. The next `rank(goal)`
        asks the generator again, telling it what failed, and does not offer those tactics."""
        k = _key(goal)
        known = self._failed.setdefault(k, [])
        new = [t.strip() for t in tactics if t.strip() not in known]
        if new:
            known += new
            self._proposals.pop(k, None)

    def _propose(self, goal: str) -> list[str]:
        k = _key(goal)
        if k not in self._proposals:
            failed = self._failed.get(k, [])
            kw = {"banned": self.banned} if self.banned else {}
            got = self.generator.propose(goal, prelude=self.prelude, failed=list(failed), **kw)
            self._proposals[k] = [t for t in got if t.strip() not in failed]
        return self._proposals[k]

    def claude_actions(self, goal: str) -> list[str]:
        """Claude's proposals at `goal`, minus menu items (they are already in the ranking)."""
        items = menu(goal, self.base.automation)
        return list(llm_options(self._propose(goal), items).values())

    def rank(self, goal: str) -> Ranking:
        if self._root is None:
            self._root = _key(goal)
        if self.order in ("menu_first", "router"):
            return self._rank_lazy(goal)
        proposals = self._propose(goal)
        items = menu(goal, self.base.automation)
        extras = llm_options(proposals, items)
        if self.order == "llm":
            # Claude alone: Claude's order, then the fixed menu; confidence 0 makes the search
            # expand every action rather than only the top few.
            actions = list(extras.values()) + list(items)
            return [(a, 1.0 / len(actions)) for a in actions], 0.0, 0.5
        if self.order == "filter":
            # Claude's order, but proposals the model predicts Lean will reject (p(useful) < tau)
            # move behind the menu. On held-out training labels Claude's order ranks the proof
            # step better than the model does (top-3 0.85 vs 0.64), while the model predicts
            # acceptance better than Claude's rank does (AUC 0.73 vs 0.61): so the model only
            # defers, it never reorders. Confidence 0: every action is tried, as in "llm".
            useful = self.base.p_useful(goal, extras) if extras else {}
            keep = [t for o, t in extras.items() if useful[o] >= self.tau]
            late = [t for o, t in extras.items() if useful[o] < self.tau]
            actions = keep + list(items) + late
            return [(a, 1.0 / len(actions)) for a in actions], 0.0, 0.5
        return self.base.rank_with(goal, extras)

    def _rank_lazy(self, goal: str) -> Ranking:
        """Efficiency orders: Claude is asked (lazily, via ASK_CLAUDE) only after cheap menu tactics.

        `menu_first` (no learning): at the theorem itself Claude first, as in `claude_search`; at
        every later state the whole menu first, then Claude.
        `router` (Jev): at any state, the menu tactics the model gives p(closes) >= route_tau (at
        most route_k, most likely first), then Claude, then the rest of the menu; if none
        qualifies, Claude first, as in `claude_search`."""
        items = list(menu(goal, self.base.automation))
        if self.order == "menu_first":
            first = [] if _key(goal) == self._root else items
            rest = [] if first else items
        else:
            p = self.base.p_closes(goal, items)
            sure = sorted((t for t in items if p[t] >= self.route_tau), key=lambda t: -p[t])[:self.route_k]
            first, rest = sure, [t for t in items if t not in sure]
        actions = first + [ASK_CLAUDE] + rest
        return [(a, 1.0 / len(actions)) for a in actions], 0.0, 0.5
