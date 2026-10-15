"""Premise library (core-Lean theorems) and IDF-weighted shortlisting for template actions."""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass

from jev_demo.model import tokenize
from jev_demo.theorems import DATA_DIR

LIBRARY_PATH = os.path.join(DATA_DIR, "library.json")
_LEAN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dump_library.lean")


@dataclass(frozen=True)
class Lemma:
    name: str
    type: str
    tokens: frozenset[str]


# Operator symbol -> word tokens (ruling R8), so goals written with symbols match lemma names.
OPERATOR_WORDS = {
    "+": ("add",), "*": ("mul",), "-": ("sub",), "/": ("div",), "%": ("mod",), "∣": ("dvd",),
    "≤": ("le",), "<": ("lt",), "≥": ("le", "ge"), ">": ("lt", "gt"), "++": ("append",),
    "::": ("cons",), "∘": ("comp",), "^": ("pow",), "¬": ("not",), "∧": ("and",), "∨": ("or",),
    "↔": ("iff",), "≠": ("ne",), "=": ("eq",),
}


def text_tokens(text: str) -> frozenset[str]:
    """Shared tokenizer for lemma types and goals; dotted tokens also yield their components,
    so `l.reverse` contributes `reverse`."""
    toks: set[str] = set()
    for t in tokenize(text):
        toks.add(t)
        toks.update(OPERATOR_WORDS.get(t, ()))
        if "." in t:
            toks.update(p for p in t.split(".") if p)
    return frozenset(toks)


def make_lemma(name: str, type_: str) -> Lemma:
    return Lemma(name, type_, text_tokens(type_) | frozenset(p for p in re.split(r"[._]", name) if p)
        | frozenset(p for p in name.split(".") if p) | {name})


def option_text(lemma: Lemma) -> str:
    return f"{lemma.name} : {lemma.type}"


def dump_library(repl, cache_path: str | None = None) -> list[Lemma]:
    """Theorems of core Lean (Nat/List/Bool/And/Or/Iff), cached as JSON; delete the cache to rebuild."""
    cache_path = cache_path or LIBRARY_PATH
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            rows = json.load(f)
    else:
        with open(_LEAN_FILE, encoding="utf-8") as f:
            reply = repl.command(f.read(), timeout_s=120, fresh=True)  # `import Lean` needs a fresh env
        rows = []
        for m in reply.get("messages", []):
            if m.get("severity") != "info":
                continue
            for line in m["data"].splitlines():
                line = line.strip()
                if line.startswith("{"):
                    rows.append(json.loads(line))
        if not rows:
            raise RuntimeError(f"library dump produced no lemmas: {reply}")
        rows = sorted(({"name": r["name"], "type": " ".join(r["type"].split())} for r in rows),
                      key=lambda r: r["name"])
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=0)
    return [make_lemma(r["name"], r["type"]) for r in rows]


class Shortlister:
    def __init__(self, library: list[Lemma]):
        self.library = list(library)
        n = len(self.library)
        df: dict[str, int] = {}
        for lem in self.library:
            for t in lem.tokens:
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}
        self._order = sorted(self.library, key=lambda l: (len(l.name), l.name))
        self._norm = {l.name: math.sqrt(sum(self.idf[t] ** 2 for t in l.tokens)) for l in self.library}

    def shortlist(self, goal: str, k: int = 16) -> tuple[str, ...]:
        """Top-k lemma names by TF-IDF cosine over token sets (ruling R9)."""
        idf = self.idf
        gtoks = text_tokens(goal) & idf.keys()  # tokens unseen in the library have no idf
        gnorm = math.sqrt(sum(idf[t] ** 2 for t in gtoks)) or 1.0
        scored = []
        for lem in self._order:
            dot = sum(idf[t] ** 2 for t in lem.tokens & gtoks)
            s = dot / (gnorm * self._norm[lem.name]) if dot else 0.0
            scored.append((-s, len(lem.name), lem.name))
        scored.sort()
        return tuple(name for _, _, name in scored[:k])


def shortlist_recall(shortlister: Shortlister, examples: list[tuple[str, str]]) -> float:
    if not examples:
        return 0.0
    return sum(gold in shortlister.shortlist(goal) for goal, gold in examples) / len(examples)
