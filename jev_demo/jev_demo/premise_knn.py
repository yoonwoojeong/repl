"""A learned premise selector for Jev, trained only on Lean's own library (no API calls).

`data/premise_usage.json` (from `dump_premises.lean`) lists, for every core theorem, the library
theorems its proof term uses. That gives ~5,700 (statement -> premises) examples for free. The
selector is k-nearest-neighbour premise selection: to rank premises for a goal, find the training
statements most similar to the goal (TF-IDF cosine over statement tokens) and let each vote for
the premises its proof used, weighted by similarity; the plain TF-IDF score of each library lemma
against the goal (the old `Shortlister`) is added with weight `lam` so unseen premises can rank.

Leakage: theorems named in `exclude` (the benchmark's dev/test lemmas) are dropped from the
training examples, so a test lemma's own library proof never informs its premises.
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict

from jev_demo.premises import Lemma, Shortlister, text_tokens
from jev_demo.theorems import DATA_DIR

USAGE_PATH = os.path.join(DATA_DIR, "premise_usage.json")


class KnnPremises:
    def __init__(self, library: list[Lemma], usage: list[dict], exclude=(), k: int = 32,
                 lam: float = 0.5, power: float = 2.0):
        self.k, self.lam, self.power = k, lam, power
        self.tfidf = Shortlister(library)
        types = {l.name: l.type for l in library}
        excl = set(exclude)
        self.examples = [(r["name"], frozenset(text_tokens(types[r["name"]])), tuple(r["premises"]))
                         for r in usage if r["premises"] and r["name"] in types and r["name"] not in excl]
        n = len(self.examples)
        df: dict[str, int] = defaultdict(int)
        for _, toks, _ in self.examples:
            for t in toks:
                df[t] += 1
        self.idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}
        self._norm = [math.sqrt(sum(self.idf[t] ** 2 for t in toks)) or 1.0 for _, toks, _ in self.examples]
        self.names = {l.name for l in library}

    def _neighbours(self, goal: str) -> list[tuple[float, int]]:
        g = text_tokens(goal) & self.idf.keys()
        gn = math.sqrt(sum(self.idf[t] ** 2 for t in g)) or 1.0
        sims = []
        for i, (_, toks, _) in enumerate(self.examples):
            dot = sum(self.idf[t] ** 2 for t in toks & g)
            if dot:
                sims.append((dot / (gn * self._norm[i]), i))
        sims.sort(reverse=True)
        return sims[:self.k]

    def scores(self, goal: str) -> dict[str, float]:
        out: dict[str, float] = defaultdict(float)
        for s, i in self._neighbours(goal):
            for p in self.examples[i][2]:
                if p in self.names:
                    out[p] += s ** self.power
        if self.lam:
            for rank, name in enumerate(self.tfidf.shortlist(goal, k=256)):
                out[name] += self.lam / (rank + 1)
        return out

    def shortlist(self, goal: str, k: int = 16, banned=()) -> tuple[str, ...]:
        sc = self.scores(goal)
        ranked = sorted((n for n in sc if n not in banned), key=lambda n: (-sc[n], len(n), n))
        return tuple(ranked[:k])


def load_usage(path: str = USAGE_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
