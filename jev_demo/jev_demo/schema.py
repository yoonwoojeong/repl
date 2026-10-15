"""Typed questions and answers about a Lean proof state."""

from __future__ import annotations

from dataclasses import dataclass

_SUM_TOLERANCE = 1e-6

LLM_PREFIX = "llm|"


def parse_llm(option: str) -> tuple[int, str] | None:
    """`(rank, tactic)` for a `llm|{i}|{tactic}` option, else None."""
    if option.startswith(LLM_PREFIX):
        idx, sep, tactic = option[len(LLM_PREFIX):].partition("|")
        if sep and idx.isdigit():
            return int(idx), tactic
    return None


@dataclass(frozen=True)
class ChoiceQuestion:
    """A question whose answer is one of several named options."""

    name: str
    options: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.options:
            raise ValueError("ChoiceQuestion needs at least one option")
        if len(set(self.options)) != len(self.options):
            raise ValueError(f"ChoiceQuestion options must be unique: {self.options!r}")


@dataclass(frozen=True)
class BinaryQuestion:
    """A yes/no question. ``option`` is None for a question about the state itself."""

    name: str
    option: str | None = None


@dataclass(frozen=True)
class ChoiceAnswer:
    probs: dict[str, float]

    @property
    def top(self) -> str:
        return max(self.probs, key=self.probs.__getitem__)

    @property
    def confidence(self) -> float:
        return self.probs[self.top]


@dataclass(frozen=True)
class BinaryAnswer:
    p_true: float


Question = ChoiceQuestion | BinaryQuestion
Answer = ChoiceAnswer | BinaryAnswer


def answer_key(question: Question) -> str:
    """Key of a question's answer in `evaluate` output: the name, plus the option for a binary
    question about an option (so several of those can share a name)."""
    if isinstance(question, BinaryQuestion) and question.option is not None:
        return f"{question.name}|{question.option}"
    return question.name


def _check_prob(p: float) -> None:
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"probability out of range [0, 1]: {p!r}")


def validate(question: Question, answer: Answer) -> None:
    """Raise ValueError if ``answer`` is not a well-formed answer to ``question``."""
    if isinstance(question, ChoiceQuestion):
        if not isinstance(answer, ChoiceAnswer):
            raise ValueError("ChoiceQuestion requires a ChoiceAnswer")
        if set(answer.probs) != set(question.options):
            raise ValueError(
                f"answer keys {sorted(answer.probs)} do not match options {list(question.options)}"
            )
        for p in answer.probs.values():
            _check_prob(p)
        total = sum(answer.probs.values())
        if abs(total - 1.0) > _SUM_TOLERANCE:
            raise ValueError(f"probabilities must sum to 1, got {total!r}")
    elif isinstance(question, BinaryQuestion):
        if not isinstance(answer, BinaryAnswer):
            raise ValueError("BinaryQuestion requires a BinaryAnswer")
        _check_prob(answer.p_true)
    else:
        raise ValueError(f"unknown question type: {type(question).__name__}")
