"""System One model: one pass, many typed questions, calibrated probabilities.

A single sparse hashed weight vector scores (state, option) pairs. The question
name is mixed into every feature hash, so different questions never share weights.
Choice questions are a listwise softmax over the supplied options; binary
questions are logistic. Per-question temperatures calibrate choice answers.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass

import numpy as np

from jev_demo.schema import (
    Answer,
    BinaryAnswer,
    BinaryQuestion,
    ChoiceAnswer,
    ChoiceQuestion,
    Question,
    answer_key,
    parse_llm,
)

_SPLIT = re.compile(r"[()\[\],:⊢·\s]+")
_TEMP_GRID = [round(0.25 + 0.05 * i, 2) for i in range(76)]  # 0.25 .. 4.0


def tokenize(text: str) -> list[str]:
    """Split on ``( ) [ ] , : ⊢ ·`` and whitespace; drop empty pieces."""
    return [t for t in _SPLIT.split(text) if t]


def _h(question: str, kind: str, feat: str, dim: int) -> int:
    return zlib.crc32(f"{question}\x1f{kind}\x1f{feat}".encode("utf-8")) % dim


def featurize(
    state: str, option: str | None = None, dim: int = 2**16, question: str = ""
) -> dict[int, float]:
    """Sparse hashed features of a goal and (optionally) an option, namespaced by ``question``."""
    feats: dict[int, float] = {}

    def add(kind: str, feat: str) -> None:
        i = _h(question, kind, feat, dim)
        feats[i] = feats.get(i, 0.0) + 1.0

    add("bias", "")
    goal = tokenize(state)
    for t in goal:
        add("g1", t)
    for a, b in zip(goal, goal[1:]):
        add("g2", f"{a} {b}")
    if option is not None:
        llm = parse_llm(option)
        if llm is not None:  # Claude's proposal: source + rank features, then the bare tactic
            add("src", "llm")
            add("rank", str(llm[0]))
            option = llm[1]
        toks = tokenize(option)
        head = toks[0] if toks else ""
        add("ofull", option)
        add("ohead", head)
        parts = [p for p in re.split(r"[.\s_]+", head) if p] if head else []
        # head itself plus its dotted components; crosses use this small set
        # to keep the feature count bounded
        otoks = [head] + parts if head else []
        for p in parts:
            add("opart", p)
        for o in otoks:
            for t in sorted(set(goal)):
                add("x", f"{o}\x1e{t}")
    return feats


@dataclass
class ChoiceExample:
    question: str
    state: str
    options: tuple[str, ...]
    gold: str


@dataclass
class BinaryExample:
    question: str
    state: str
    option: str | None
    label: bool


class SystemOneModel:
    def __init__(self, dim: int = 2**16, seed: int = 0):
        self.dim = dim
        self.seed = seed
        self.w = np.zeros(dim, dtype=np.float64)
        self.temps: dict[str, float] = {}

    # -- scoring -----------------------------------------------------------
    def _score(self, feats: dict[int, float]) -> float:
        if not feats:
            return 0.0
        idx = np.fromiter(feats.keys(), dtype=np.int64, count=len(feats))
        val = np.fromiter(feats.values(), dtype=np.float64, count=len(feats))
        return float(self.w[idx] @ val)

    def _choice_logits(self, name: str, state: str, options: tuple[str, ...]) -> np.ndarray:
        return np.array([self._score(featurize(state, o, self.dim, name)) for o in options])

    @staticmethod
    def _softmax(z: np.ndarray) -> np.ndarray:
        z = z - z.max()
        e = np.exp(z)
        return e / e.sum()

    def _update(self, feats: dict[int, float], g: float, lr: float, l2: float) -> None:
        for i, v in feats.items():
            self.w[i] -= lr * (g * v + l2 * self.w[i])

    # -- training ----------------------------------------------------------
    def fit(
        self,
        choice: list[ChoiceExample],
        binary: list[BinaryExample],
        epochs: int = 30,
        lr: float = 0.1,
        l2: float = 1e-4,
    ) -> None:
        rng = np.random.default_rng(self.seed)
        items: list[tuple[str, int]] = [("c", i) for i in range(len(choice))] + [
            ("b", i) for i in range(len(binary))
        ]
        cache_c = [
            [featurize(e.state, o, self.dim, e.question) for o in e.options] for e in choice
        ]
        cache_b = [featurize(e.state, e.option, self.dim, e.question) for e in binary]
        for _ in range(epochs):
            for k in rng.permutation(len(items)):
                kind, i = items[k]
                if kind == "c":
                    ex = choice[i]
                    fs = cache_c[i]
                    z = np.array([self._score(f) for f in fs])
                    p = self._softmax(z)
                    gold = ex.options.index(ex.gold)
                    for j, f in enumerate(fs):
                        self._update(f, p[j] - (1.0 if j == gold else 0.0), lr, l2)
                else:
                    ex_b = binary[i]
                    f = cache_b[i]
                    p = 1.0 / (1.0 + np.exp(-np.clip(self._score(f), -30, 30)))
                    self._update(f, p - (1.0 if ex_b.label else 0.0), lr, l2)

    def calibrate(self, choice: list[ChoiceExample]) -> dict[str, float]:
        """Fit one temperature per choice-question name by grid search on NLL."""
        by_name: dict[str, list[tuple[np.ndarray, int]]] = {}
        for ex in choice:
            z = self._choice_logits(ex.question, ex.state, ex.options)
            by_name.setdefault(ex.question, []).append((z, ex.options.index(ex.gold)))
        for name, rows in by_name.items():
            best_t, best = 1.0, float("inf")
            for t in _TEMP_GRID:
                nll = 0.0
                for z, g in rows:
                    s = z / t
                    s = s - s.max()
                    nll -= s[g] - np.log(np.exp(s).sum())
                if nll < best - 1e-12:
                    best, best_t = nll, t
            self.temps[name] = best_t
        return dict(self.temps)

    # -- inference ---------------------------------------------------------
    def evaluate(self, state: str, questions: list[Question]) -> dict[str, Answer]:
        out: dict[str, Answer] = {}
        for q in questions:
            if isinstance(q, ChoiceQuestion):
                z = self._choice_logits(q.name, state, q.options) / self.temps.get(q.name, 1.0)
                p = self._softmax(z)
                out[q.name] = ChoiceAnswer({o: float(pi) for o, pi in zip(q.options, p)})
            elif isinstance(q, BinaryQuestion):
                s = self._score(featurize(state, q.option, self.dim, q.name))
                out[answer_key(q)] = BinaryAnswer(float(1.0 / (1.0 + np.exp(-np.clip(s, -30, 30)))))
            else:
                raise ValueError(f"unknown question type: {type(q).__name__}")
        return out

    # -- persistence -------------------------------------------------------
    def save(self, path: str) -> None:
        names = sorted(self.temps)
        with open(path, "wb") as f:
            np.savez(
                f,
                w=self.w,
                dim=np.array(self.dim),
                seed=np.array(self.seed),
                temp_names=np.array(names, dtype=str),
                temp_values=np.array([self.temps[n] for n in names], dtype=np.float64),
            )

    @classmethod
    def load(cls, path: str) -> SystemOneModel:
        with np.load(path, allow_pickle=False) as d:
            m = cls(dim=int(d["dim"]), seed=int(d["seed"]))
            m.w = d["w"].astype(np.float64)
            m.temps = {str(n): float(v) for n, v in zip(d["temp_names"], d["temp_values"])}
        return m


def expected_calibration_error(model: SystemOneModel, choice: list[ChoiceExample], bins: int = 10) -> float:
    """Top-label ECE over choice examples, using the model's (calibrated) answers."""
    if not choice:
        return 0.0
    conf, correct = [], []
    for ex in choice:
        a = model.evaluate(ex.state, [ChoiceQuestion(ex.question, ex.options)])[ex.question]
        conf.append(a.confidence)
        correct.append(1.0 if a.top == ex.gold else 0.0)
    conf_a, corr_a = np.array(conf), np.array(correct)
    idx = np.minimum((conf_a * bins).astype(int), bins - 1)
    ece = 0.0
    for b in range(bins):
        mask = idx == b
        if mask.any():
            ece += mask.mean() * abs(conf_a[mask].mean() - corr_a[mask].mean())
    return float(ece)
