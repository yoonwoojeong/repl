"""Claude as an open-ended Lean tactic generator (Phase 2).

SDK path (verified against the installed anthropic 1.14.0 with `inspect.signature`):
`client.beta.messages.parse(...)` exists and accepts `output_format`, `output_config`, `betas`,
`fallbacks` (typed `Iterable[BetaFallbackParam] | Literal["default"]`) and top-level
`cache_control`.  So the `parse` path is used: `output_format=Proposals` is merged by the SDK into
`output_config` next to our `{"effort": ...}`, and the reply is read from `.parsed_output`.
The `create` + `json_schema` + `model_validate_json` fallback was NOT needed.

Model rules for claude-opus-5-5: `thinking` is omitted (adaptive by default), effort is set via
`output_config`, and no `temperature`, `budget_tokens`, prefill or forced `tool_choice` is sent.
`stop_reason == "refusal"` is checked before the output is read.  `fallbacks="default"` needs the
beta header `server-side-fallback-2026-07-01`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass

import anthropic
import pydantic

from jev_demo.prompts import SYSTEM_PROMPT

BETA_FALLBACK = "server-side-fallback-2026-07-01"
MAX_TOKENS = 4000

# USD per million tokens, claude-opus-5-5.  Cache write is the 5-minute-TTL rate (1.25x input).
PRICE_INPUT = 4.0
PRICE_OUTPUT = 20.0
PRICE_CACHE_READ = 0.20
PRICE_CACHE_WRITE = 5.0

_FORBIDDEN = re.compile(r"(?<![\w'])(sorry|admit)(?![\w'])")


class Proposals(pydantic.BaseModel):
    """Structured output: 1-8 tactics, most promising first."""

    tactics: list[str]


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    usd: float = 0.0
    refusals: int = 0
    errors: int = 0


def _clean(tactics: list[str], n: int) -> list[str]:
    out: list[str] = []
    for t in tactics:
        t = t.strip()
        if not t or _FORBIDDEN.search(t) or t in out:
            continue
        out.append(t)
    return out[:n]


class ClaudeGenerator:
    def __init__(self, client=None, model: str = "claude-opus-5-5", effort: str = "medium", n: int = 8,
                 cache_dir: str = "jev_demo/cache/claude", max_usd: float = 10.0):
        self.client = client if client is not None else anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.n = n
        self.cache_dir = cache_dir
        self.max_usd = max_usd
        self.usage = Usage()

    # -- public API --------------------------------------------------------------------------

    def propose(self, goal: str, prelude: str = "", failed: list[str] = ()) -> list[str]:
        failed_block = "\n".join(f"- {t}" for t in failed) if failed else "(none)"
        user = (f"Prelude:\n{prelude or '(none)'}\n\n"
                f"Goal:\n{goal}\n\n"
                f"Already failed here (do not repeat):\n{failed_block}\n\n"
                f"Propose up to {self.n} next tactics, most promising first.")
        return self._ask(user, sample=0)

    def whole_proof(self, statement: str, prelude: str = "", k: int = 4) -> list[list[str]]:
        user = (f"Prelude:\n{prelude or '(none)'}\n\n"
                f"Goal:\n⊢ {statement}\n\n"
                "Already failed here (do not repeat):\n(none)\n\n"
                "Give ONE complete tactic script that proves the goal, one tactic step per entry, "
                "in order.")
        scripts = [self._ask(user, sample=i, limit=64) for i in range(k)]
        return [s for s in scripts if s]

    # -- internals ---------------------------------------------------------------------------

    def _path(self, user: str, sample: int) -> str:
        key = json.dumps([self.model, self.effort, self.n, SYSTEM_PROMPT, user, sample],
                         ensure_ascii=False)
        return os.path.join(self.cache_dir, hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json")

    def _ask(self, user: str, sample: int, limit: int | None = None) -> list[str]:
        limit = limit or self.n
        path = self._path(user, sample)
        try:
            with open(path, encoding="utf-8") as f:
                return list(json.load(f)["tactics"])
        except (OSError, ValueError, KeyError):
            pass
        if self.usage.usd >= self.max_usd:
            return []
        self.usage.calls += 1
        try:
            resp = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user}],
                output_format=Proposals,
                output_config={"effort": self.effort},
                cache_control={"type": "ephemeral"},
                fallbacks="default",
                betas=[BETA_FALLBACK],
            )
        except anthropic.RateLimitError:
            self.usage.errors += 1
            return []
        except anthropic.APIStatusError:
            self.usage.errors += 1
            return []
        except anthropic.APIConnectionError:
            self.usage.errors += 1
            return []
        except pydantic.ValidationError:
            self.usage.errors += 1
            return []
        self._meter(getattr(resp, "usage", None))
        if resp.stop_reason == "refusal":
            self.usage.refusals += 1
            return []
        parsed = getattr(resp, "parsed_output", None)
        if parsed is None:
            self.usage.errors += 1
            return []
        tactics = _clean(parsed.tactics, limit)
        os.makedirs(self.cache_dir, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"tactics": tactics}, f, ensure_ascii=False)
        os.replace(tmp, path)
        return tactics

    def _meter(self, u) -> None:
        if u is None:
            return
        inp = getattr(u, "input_tokens", 0) or 0
        out = getattr(u, "output_tokens", 0) or 0
        read = getattr(u, "cache_read_input_tokens", 0) or 0
        write = getattr(u, "cache_creation_input_tokens", 0) or 0
        s = self.usage
        s.input_tokens += inp
        s.output_tokens += out
        s.cache_read_tokens += read
        s.cache_write_tokens += write
        s.usd += (inp * PRICE_INPUT + out * PRICE_OUTPUT + read * PRICE_CACHE_READ
                  + write * PRICE_CACHE_WRITE) / 1_000_000
