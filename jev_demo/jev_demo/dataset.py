"""Training examples from gold-proof replays: one `kind`, optional `premise` and one
`near_done` example per gold step."""

from __future__ import annotations

from jev_demo.actions import TEMPLATES, menu, parse_action
from jev_demo.model import BinaryExample, ChoiceExample
from jev_demo.premises import Lemma, Shortlister, option_text
from jev_demo.theorems import Theorem


def replay(thm: Theorem, repl, shortlister: Shortlister, lib: dict[str, Lemma],
           stats: dict | None = None) -> tuple[list[ChoiceExample], list[BinaryExample]]:
    """Replay `thm.gold` in the REPL and label every visited goal.

    Options match what `ModelRanker(premises=True, automation=True)` asks (ruling R2), so a
    step whose gold kind is not among them is skipped and counted in `stats["kind_skipped"]`.
    A premise step whose lemma is not shortlisted is a recall miss (`premise_steps` counts all
    premise steps, `premise_hits` the shortlisted ones). Raises AssertionError if a gold step fails.
    """
    st = stats if stats is not None else {}
    for k in ("steps", "kind_skipped", "premise_steps", "premise_hits"):
        st.setdefault(k, 0)
    choice: list[ChoiceExample] = []
    binary: list[BinaryExample] = []
    ps, goal = repl.start_theorem(thm.statement, thm.prelude)
    n = len(thm.gold)
    for i, step in enumerate(thm.gold):
        st["steps"] += 1
        kind, premise = parse_action(step)
        kinds = menu(goal, True) + TEMPLATES
        if kind in kinds:
            choice.append(ChoiceExample("kind", goal, kinds, kind))
        else:
            st["kind_skipped"] += 1
        if premise is not None:
            st["premise_steps"] += 1
            names = shortlister.shortlist(goal)
            if premise in names and premise in lib:
                st["premise_hits"] += 1
                options = tuple(option_text(lib[m]) for m in names if m in lib)
                choice.append(ChoiceExample("premise", goal, options, option_text(lib[premise])))
        binary.append(BinaryExample("near_done", goal, None, n - i <= 2))
        res = repl.tactic(step, ps)
        if not res.ok:
            raise AssertionError(f"{thm.name}: gold step {step!r} failed: {res.error}")
        ps, goal = res.proof_state, (res.goals[0] if res.goals else "")
    return choice, binary
