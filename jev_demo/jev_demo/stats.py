"""Paired statistics for comparing two provers on the same theorems (no SciPy needed).

A comparison is only *meaningful* here when it is paired (same theorems, same budget) and the
difference is larger than what chance would give: `mcnemar` gives the exact two-sided p-value on
the discordant pairs, `paired_bootstrap` a confidence interval for the difference in success rate,
and `wilson` an interval for one method's success rate.
"""

from __future__ import annotations

import math
import random


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def discordant(a: list[bool], b: list[bool]) -> tuple[int, int]:
    """(# a proved and b did not, # b proved and a did not) over paired results."""
    if len(a) != len(b):
        raise ValueError("paired results must have the same length")
    return (sum(x and not y for x, y in zip(a, b)), sum(y and not x for x, y in zip(a, b)))


def mcnemar(a: list[bool], b: list[bool]) -> float:
    """Exact two-sided McNemar p-value (binomial test on the discordant pairs)."""
    n01, n10 = discordant(a, b)
    n, k = n01 + n10, min(n01, n10)
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def paired_bootstrap(a: list[bool], b: list[bool], iters: int = 10000, seed: int = 0,
                     level: float = 0.95) -> tuple[float, float, float]:
    """(rate(a) - rate(b), lower, upper): percentile bootstrap over theorems."""
    if len(a) != len(b) or not a:
        raise ValueError("need non-empty paired results")
    n = len(a)
    diffs = [int(x) - int(y) for x, y in zip(a, b)]
    rng = random.Random(seed)
    samples = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    lo = samples[int((1 - level) / 2 * iters)]
    hi = samples[min(iters - 1, int((1 + level) / 2 * iters))]
    return (sum(diffs) / n, lo, hi)


def compare(name_a: str, a: list[bool], name_b: str, b: list[bool]) -> dict:
    """Everything the report needs for one paired comparison."""
    n01, n10 = discordant(a, b)
    d, lo, hi = paired_bootstrap(a, b)
    return {"a": name_a, "b": name_b, "n": len(a), "a_proved": sum(a), "b_proved": sum(b),
            "a_only": n01, "b_only": n10, "diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)],
            "p_mcnemar": round(mcnemar(a, b), 5)}


def required_n(p_a: float, p_b: float, alpha: float = 0.05, power: float = 0.8,
               discordance: float | None = None) -> int:
    """Approximate number of paired theorems needed for McNemar to detect p_a vs p_b.
    `discordance` is the expected fraction of discordant pairs (default: assume independence)."""
    za, zb = 1.959964, 0.841621 if power == 0.8 else 1.281552
    psi = discordance if discordance is not None else p_a * (1 - p_b) + p_b * (1 - p_a)
    delta = abs(p_a - p_b)
    if delta == 0:
        return 10 ** 9
    return math.ceil((za * math.sqrt(psi) + zb * math.sqrt(psi - delta * delta)) ** 2 / delta ** 2)
