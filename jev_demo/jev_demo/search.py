"""Best-first proof search: a ranker proposes actions, the Lean REPL verifies each one, and
low ranker confidence widens the expansion (Jev's "escalate")."""

from __future__ import annotations

import heapq
import math
import random
import time
from dataclasses import dataclass, field
from typing import Protocol

from jev_demo.actions import TEMPLATES, fill, menu
from jev_demo.premises import Lemma, Shortlister, option_text
from jev_demo.repl_client import ReplClient
from jev_demo.schema import BinaryQuestion, ChoiceQuestion
from jev_demo.theorems import Theorem

TOP_PREMISES = 4

Ranking = tuple[list[tuple[str, float]], float, float]


class Ranker(Protocol):
    def rank(self, goal: str) -> Ranking:
        """Return `(actions sorted by descending score, confidence, state_value)`."""


class ModelRanker:
    def __init__(self, model, shortlister: Shortlister, lib: dict[str, Lemma],
                 premises: bool = True, automation: bool = True):
        self.model, self.shortlister, self.lib = model, shortlister, lib
        self.premises, self.automation = premises, automation

    def rank(self, goal: str) -> Ranking:
        items = menu(goal, self.automation)
        # option_text -> lemma name (ruling R2); dict.fromkeys keeps options unique.
        opt_to_name: dict[str, str] = {}
        if self.premises:
            for n in self.shortlister.shortlist(goal):
                if n in self.lib:
                    opt_to_name.setdefault(option_text(self.lib[n]), n)
        use_templates = bool(opt_to_name)
        kinds = items + (TEMPLATES if use_templates else ())
        questions = [ChoiceQuestion("kind", kinds), BinaryQuestion("near_done")]
        if use_templates:
            questions.append(ChoiceQuestion("premise", tuple(opt_to_name)))
        ans = self.model.evaluate(goal, questions)
        pk = ans["kind"].probs
        scores: dict[str, float] = {a: pk[a] for a in items}
        if use_templates:
            pp = ans["premise"].probs
            for opt in sorted(pp, key=pp.__getitem__, reverse=True)[:TOP_PREMISES]:
                for t in TEMPLATES:
                    scores.setdefault(fill(t, opt_to_name[opt]), pk[t] * pp[opt])
        total = sum(scores.values())
        if total <= 0:
            scores = {a: 1.0 for a in scores}
            total = float(len(scores))
        ranked = sorted(((a, s / total) for a, s in scores.items()), key=lambda x: -x[1])
        return ranked, ranked[0][1], ans["near_done"].p_true


class FixedOrderRanker:
    def __init__(self, automation: bool = True):
        self.automation = automation

    def _order(self, goal: str) -> list[str]:
        return list(menu(goal, self.automation))

    def rank(self, goal: str) -> Ranking:
        order = self._order(goal)
        return [(a, 1.0 / len(order)) for a in order], 1.0, 0.5


class RandomRanker(FixedOrderRanker):
    def __init__(self, seed: int = 0, automation: bool = True):
        super().__init__(automation)
        self._rng = random.Random(seed)

    def _order(self, goal: str) -> list[str]:
        order = super()._order(goal)
        self._rng.shuffle(order)
        return order


@dataclass
class SearchResult:
    proved: bool
    tactics: list[str]
    calls: int
    escalations: int
    seconds: float
    trace: list[dict] = field(default_factory=list)


def _key(goal: str) -> str:
    return " ".join(goal.split())


def prove(thm: Theorem, repl: ReplClient, ranker: Ranker, budget: int = 64, max_depth: int = 8,
          top_k: int = 3, tau: float = 0.5) -> SearchResult:
    t0 = time.perf_counter()
    calls = escalations = 0
    trace: list[dict] = []
    ps, goal = repl.start_theorem(thm.statement, thm.prelude)
    seen = {_key(goal)}
    frontier: list = []
    counter = 0

    def push(cum_logp: float, ps: int, goal: str, tactics: list[str]) -> None:
        nonlocal counter
        ranking = ranker.rank(goal)
        prio = cum_logp + math.log(ranking[2] + 1e-3)
        heapq.heappush(frontier, (-prio, counter, cum_logp, ps, goal, tactics, ranking))
        counter += 1

    def done(proved: bool, tactics: list[str]) -> SearchResult:
        return SearchResult(proved, tactics, calls, escalations, time.perf_counter() - t0, trace)

    push(0.0, ps, goal, [])
    while frontier and calls < budget:
        _, _, cum_logp, ps, goal, tactics, (actions, confidence, _) = heapq.heappop(frontier)
        if len(tactics) >= max_depth:
            continue
        if confidence < tau:
            escalations += 1
            chosen = actions
        else:
            chosen = actions[:top_k]
        for action, score in chosen:
            if calls >= budget:
                break
            calls += 1
            res = repl.tactic(action, ps)
            outcome = "error"
            if res.ok and res.completed:
                if repl.check_proof(thm.statement, tactics + [action], thm.prelude):
                    outcome = "proved"
                else:
                    outcome = "rejected"
            elif res.ok and res.goals:
                key = _key(res.goals[0])
                if key in seen:
                    outcome = "duplicate"
                else:
                    seen.add(key)
                    outcome = "ok"
                    push(cum_logp + math.log(max(score, 1e-12)), res.proof_state, res.goals[0],
                         tactics + [action])
            trace.append({"goal": goal, "n_actions": len(actions), "chosen": action,
                          "score": score, "confidence": confidence, "outcome": outcome})
            if outcome == "proved":
                return done(True, tactics + [action])
    return done(False, [])
