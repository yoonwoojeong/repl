"""Train/test theorem sets with checked gold proofs."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


@dataclass(frozen=True)
class Theorem:
    name: str
    statement: str
    prelude: str
    gold: tuple[str, ...]
    difficulty: Literal["easy", "hard"]


def load_theorems(path: str) -> list[Theorem]:
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    return [
        Theorem(r["name"], r["statement"], r.get("prelude", ""), tuple(r["gold"]), r["difficulty"])
        for r in rows
    ]
