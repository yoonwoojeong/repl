"""LeanDojo Benchmark 4 data as stored by free job 2 (`data/standard/`): the premise corpus,
splits, and ReProver's accessible-premise rule as a numpy mask. No torch, so BM25 and miniF2F
can use it without the neural retriever's dependencies."""

from __future__ import annotations

import gzip
import json
import os

import numpy as np

from jev_demo.reprover_common import Corpus
from jev_demo.theorems import DATA_DIR

STD = os.path.join(DATA_DIR, "standard")


# -- data ------------------------------------------------------------------------------------

def load_corpus() -> Corpus:
    with gzip.open(os.path.join(STD, "ld4_corpus.jsonl.gz"), "rt", encoding="utf-8") as f:
        return Corpus.from_rows([json.loads(line) for line in f])


def load_split(split: str, part: str) -> list[dict]:
    with gzip.open(os.path.join(STD, f"ld4_{split}_{part}.json.gz"), "rt", encoding="utf-8") as f:
        return json.load(f)


class AccessIndex:
    """`Corpus.get_accessible_premise_indexes` as a numpy mask: a premise is accessible at
    (path, pos) iff it is in a (transitively) imported file, or earlier in the same file."""

    def __init__(self, corpus: Corpus):
        self.corpus = corpus
        files = list(corpus.transitive_dep_graph.nodes)
        self.fid = {p: i for i, p in enumerate(files)}
        self.pfile = np.array([self.fid[p.path] for p in corpus.all_premises])
        self.pend = [p.end for p in corpus.all_premises]
        self._imp: dict[str, np.ndarray] = {}

    def mask(self, path: str, pos) -> np.ndarray:
        if path not in self._imp:
            deps = np.zeros(len(self.fid), dtype=bool)
            for q in self.corpus.transitive_dep_graph.successors(path):
                deps[self.fid[q]] = True
            self._imp[path] = deps[self.pfile]
        m = self._imp[path].copy()
        same = np.nonzero(self.pfile == self.fid[path])[0]
        for i in same:
            if self.pend[i] <= pos:
                m[i] = True
        return m
