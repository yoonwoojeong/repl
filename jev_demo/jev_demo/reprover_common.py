"""Vendored from ReProver (https://github.com/lean-dojo/ReProver, commit fd6d99c, MIT License,
Copyright (c) 2023 LeanDojo Team): the retrieval corpus, accessible premises, gold premises of a
tactic, premise serialization, and the R@1 / R@10 / MRR evaluation (`retrieval/evaluate.py`).

Kept as close to the original as possible so results are comparable with published numbers.
Changes: `Pos` is a local stand-in for `lean_dojo.Pos` (ordered (line, column)), so the heavy
dependencies of `common.py` (lean_dojo, pytorch_lightning, deepspeed) are not needed; Corpus can
also be built from already-loaded rows (`Corpus.from_rows`); logging uses `warnings`;
`get_all_pos_premises` skips a provenance whose file is not in the corpus (the original raises);
`Premise.serialize` escapes the name in its regex.
"""

from __future__ import annotations

import json
import re
import warnings
from dataclasses import dataclass, field
from functools import total_ordering
from typing import Any, Dict, Generator, List, Optional, Tuple

import networkx as nx
import numpy as np

MARK_START_SYMBOL = "<a>"
MARK_END_SYMBOL = "</a>"


@total_ordering
@dataclass(frozen=True)
class Pos:
    line_nb: int
    column_nb: int

    def __lt__(self, other: "Pos") -> bool:
        return (self.line_nb, self.column_nb) < (other.line_nb, other.column_nb)


@dataclass(unsafe_hash=True)
class Premise:
    """Premises are "documents" in our retrieval setup."""

    path: str
    full_name: str
    start: Pos = field(repr=False)
    end: Pos = field(repr=False, compare=False)
    code: str = field(compare=False)

    def __post_init__(self) -> None:
        assert isinstance(self.path, str)
        assert isinstance(self.full_name, str)
        assert isinstance(self.start, Pos) and isinstance(self.end, Pos) and self.start <= self.end
        assert isinstance(self.code, str) and self.code != ""

    def serialize(self) -> str:
        """Serialize the premise into a string for Transformers."""
        annot_full_name = f"{MARK_START_SYMBOL}{self.full_name}{MARK_END_SYMBOL}"
        code = self.code.replace(f"_root_.{self.full_name}", annot_full_name)
        fields = self.full_name.split(".")
        for i in range(len(fields)):
            prefix = ".".join(fields[i:])
            new_code = re.sub(rf"(?<=\s)«?{re.escape(prefix)}»?", annot_full_name, code)
            if new_code != code:
                code = new_code
                break
        return code


class PremiseSet:
    """A set of premises indexed by their paths and full names."""

    def __init__(self) -> None:
        self.path2premises: Dict[str, Dict[str, Premise]] = {}

    def __iter__(self) -> Generator[Premise, None, None]:
        for _, premises in self.path2premises.items():
            for p in premises.values():
                yield p

    def add(self, p: Premise) -> None:
        if p.path in self.path2premises:
            self.path2premises[p.path][p.full_name] = p
        else:
            self.path2premises[p.path] = {p.full_name: p}

    def update(self, premises: List[Premise]) -> None:
        for p in premises:
            self.add(p)

    def __contains__(self, p: Premise) -> bool:
        return p.path in self.path2premises and p.full_name in self.path2premises[p.path]

    def __len__(self) -> int:
        return sum(len(premises) for premises in self.path2premises.values())


@dataclass(frozen=True)
class File:
    path: str
    premises: List[Premise] = field(repr=False, compare=False)

    @classmethod
    def from_data(cls, file_data: Dict[str, Any]) -> "File":
        path = file_data["path"]
        premises = []
        for p in file_data["premises"]:
            full_name = p["full_name"]
            if full_name is None:
                continue
            if "user__.n" in full_name or p["code"] == "":
                continue  # ill-formed premises (often due to errors in ASTs)
            if full_name.startswith("[") and full_name.endswith("]"):
                continue  # mutual definitions
            premises.append(Premise(path, p["full_name"], Pos(*p["start"]), Pos(*p["end"]), p["code"]))
        return cls(path, premises)


class Corpus:
    """A DAG of files; each file defines premises that can be retrieved."""

    def __init__(self, jsonl_path: Optional[str] = None, rows: Optional[List[dict]] = None) -> None:
        dep_graph = nx.DiGraph()
        self.all_premises: List[Premise] = []
        if rows is None:
            rows = [json.loads(line) for line in open(jsonl_path, encoding="utf-8")]
        for file_data in rows:
            path = file_data["path"]
            assert not dep_graph.has_node(path)
            file = File.from_data(file_data)
            dep_graph.add_node(path, file=file)
            self.all_premises.extend(file.premises)
            for p in file_data["imports"]:
                assert dep_graph.has_node(p)
                dep_graph.add_edge(path, p)
        assert nx.is_directed_acyclic_graph(dep_graph)
        self.transitive_dep_graph = nx.transitive_closure_dag(dep_graph)
        self.imported_premises_cache: Dict[str, List[Premise]] = {}
        for path in self.transitive_dep_graph.nodes:
            self._get_imported_premises(path)

    @classmethod
    def from_rows(cls, rows: List[dict]) -> "Corpus":
        return cls(rows=rows)

    def _get_file(self, path: str) -> File:
        return self.transitive_dep_graph.nodes[path]["file"]

    def __len__(self) -> int:
        return len(self.all_premises)

    def get_premises(self, path: str) -> List[Premise]:
        return self._get_file(path).premises

    def locate_premise(self, path: str, pos: Pos) -> Optional[Premise]:
        for p in self.get_premises(path):
            if p.start <= pos <= p.end:
                return p
        return None

    def _get_imported_premises(self, path: str) -> List[Premise]:
        premises = self.imported_premises_cache.get(path)
        if premises is not None:
            return premises
        premises = []
        for p in self.transitive_dep_graph.successors(path):
            premises.extend(self._get_file(p).premises)
        self.imported_premises_cache[path] = premises
        return premises

    def get_accessible_premises(self, path: str, pos: Pos) -> PremiseSet:
        """Premises defined in the (transitively) imported files or earlier in the same file."""
        premises = PremiseSet()
        for p in self.get_premises(path):
            if p.end <= pos:
                premises.add(p)
        premises.update(self._get_imported_premises(path))
        return premises


def get_all_pos_premises(annot_tac, corpus: Corpus) -> List[Premise]:
    """All premises used in the tactic ``annot_tac``."""
    _, provenances = annot_tac
    all_pos_premises = set()
    for prov in provenances:
        if prov["def_path"] not in corpus.transitive_dep_graph:
            warnings.warn(f"Cannot locate premise: {prov}")
            continue
        p = corpus.locate_premise(prov["def_path"], Pos(*prov["def_pos"]))
        if p is not None:
            all_pos_premises.add(p)
        else:
            warnings.warn(f"Cannot locate premise: {prov}")
    return list(all_pos_premises)


def evaluate(data, preds_map) -> Tuple[float, float, float]:
    """`retrieval/evaluate.py::_eval`: R@1 (%), R@10 (%), MRR over tactics with >= 1 gold premise."""
    R1, R10, MRR = [], [], []
    for thm in data:
        for i, _ in enumerate(thm["traced_tactics"]):
            pred = preds_map[(thm["file_path"], thm["full_name"], tuple(thm["start"]), i)]
            all_pos_premises = set(pred["all_pos_premises"])
            if len(all_pos_premises) == 0:
                continue
            retrieved_premises = pred["retrieved_premises"]
            TP1 = retrieved_premises[0] in all_pos_premises
            R1.append(float(TP1) / len(all_pos_premises))
            TP10 = len(all_pos_premises.intersection(retrieved_premises[:10]))
            R10.append(float(TP10) / len(all_pos_premises))
            for j, p in enumerate(retrieved_premises):
                if p in all_pos_premises:
                    MRR.append(1.0 / (j + 1))
                    break
            else:
                MRR.append(0.0)
    return 100 * float(np.mean(R1)), 100 * float(np.mean(R10)), float(np.mean(MRR))
