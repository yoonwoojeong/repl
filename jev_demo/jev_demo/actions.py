"""The action space: a fixed tactic menu, goal-specific items, and premise templates."""

from __future__ import annotations

import re

BASE_MENU: tuple[str, ...] = (
    "rfl", "simp", "simp_all", "omega", "decide", "constructor", "assumption", "trivial", "simp [*] at *",
)
AUTOMATION: tuple[str, ...] = ("grind", "exact?")
# Benchmark-specific extra menu items (e.g. Mathlib automation for miniF2F); empty for core Lean.
EXTRA_MENU: list[str] = []
MATHLIB_MENU: tuple[str, ...] = ("norm_num", "linarith", "nlinarith", "positivity", "ring_nf", "field_simp",
                                  "aesop", "norm_num [*] at *", "omega", "decide")


GOAL_STEPS: list = []  # optional goal -> extra tactics (e.g. BM25-premise steps on miniF2F)


def set_extra_menu(tactics, goal_steps=None) -> None:
    """Add benchmark-specific tactics to every menu (call once, before searching); `goal_steps`
    maps a goal to further goal-dependent tactics."""
    EXTRA_MENU[:] = list(tactics)
    GOAL_STEPS[:] = [goal_steps] if goal_steps else []
TEMPLATES: tuple[str, ...] = ("rw [·]", "simp [·]", "grind [·]", "exact ·", "apply ·")

_HOLE = "·"
_OPEN, _CLOSE = "([{⟨", ")]}⟩"
_HYP = re.compile(r"^(\S.*?) : (.*)$")
_IDENT = re.compile(r"[^\W\d][\w'.!?✝]*")


def _top_level(text: str, sym: str) -> bool:
    """True iff `sym` occurs in `text` outside every bracket pair."""
    depth = 0
    for i, ch in enumerate(text):
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth -= 1
        elif depth == 0 and text.startswith(sym, i):
            return True
    return False


def _split_goal(goal: str) -> tuple[list[tuple[list[str], str]], str]:
    """Hypotheses `(names, type)` and the target of the first goal in `goal`."""
    context, _, rest = goal.partition("⊢")
    target = rest.split("\n\n")[0]  # stop at the next goal, if several are printed
    lines: list[str] = []
    for line in context.split("\n"):
        if not line.strip() or line.startswith("case "):
            continue
        if line[0].isspace() and lines:  # wrapped continuation of a long type
            lines[-1] += " " + line.strip()
        else:
            lines.append(line.strip())
    hyps = []
    for line in lines:
        m = _HYP.match(line)
        if m:
            hyps.append((m.group(1).split(), m.group(2).strip()))
    return hyps, " ".join(target.split())


def _binder_names(target: str) -> list[str]:
    """Names bound by a leading `∀ x y : T,` or `∀ (x : T) (y : U),` in `target`."""
    if not target.startswith("∀"):
        return []
    s = target[1:].lstrip()
    names: list[str] = []
    if s[:1] in "({":
        while s[:1] in "({":
            depth, end = 0, None
            for i, ch in enumerate(s):
                depth += ch in _OPEN
                depth -= ch in _CLOSE
                if depth == 0:
                    end = i
                    break
            if end is None:
                return []
            names += s[1:end].split(" : ")[0].split()
            s = s[end + 1:].lstrip()
        return names
    head = s.split(",")[0]
    names = head.split(" : ")[0].split()
    # `∀ x ∈ l,` and other binder notations are not plain names: offer no intro.
    return names if all(_IDENT.fullmatch(n) for n in names) else []


def _referable(name: str) -> bool:
    return "✝" not in name  # inaccessible names cannot be written in a tactic


def menu(goal: str, automation: bool = True) -> tuple[str, ...]:
    hyps, target = _split_goal(goal)
    taken = {n for names, _ in hyps for n in names}
    items = list(BASE_MENU) + EXTRA_MENU + (list(AUTOMATION) if automation else [])
    for f in GOAL_STEPS:
        items += f(goal)
    binders = _binder_names(target)
    if binders:
        items.append("intro " + " ".join(binders))
    elif _top_level(target, "→"):
        name, k = "h", 1
        while name in taken:
            name, k = f"h{k}", k + 1
        items.append(f"intro {name}")
    for names, typ in hyps:
        if typ in ("Nat", "ℕ") or typ.startswith("List "):
            for x in filter(_referable, names):
                items += [f"induction {x} <;> simp_all", f"induction {x} <;> grind", f"cases {x}"]
    for names, typ in hyps:
        if _top_level(typ, "∨"):
            items += [f"cases {x}" for x in filter(_referable, names)]
    return tuple(dict.fromkeys(items))


def fill(template: str, premise: str) -> str:
    return template.replace(_HOLE, premise)


def parse_action(tac: str) -> tuple[str, str | None]:
    """Split a tactic into `(template, premise)`; non-template tactics give `(tac, None)`."""
    tac = tac.strip()
    if tac in BASE_MENU or tac in AUTOMATION:
        return tac, None
    for t in TEMPLATES:
        prefix, suffix = t.split(_HOLE)
        if tac.startswith(prefix) and tac.endswith(suffix) and len(tac) > len(prefix) + len(suffix):
            return t, tac[len(prefix):len(tac) - len(suffix)].strip()
    return tac, None


_BARE_PREMISE = re.compile(r"[^\W\d][\w'!?]*(?:\.[^\W\d][\w'!?]*)*")


def in_action_space(step: str, goal: str, automation: bool = True) -> bool:
    """True iff `step` is a menu item at `goal`, or a template filled with a bare lemma name.

    The ranker fills templates with a single (possibly dotted) identifier, so a premise
    that is a term with arguments, a list, or `← lemma` is not producible.
    """
    kind, premise = parse_action(step)
    if kind in TEMPLATES:
        return premise is not None and _BARE_PREMISE.fullmatch(premise) is not None
    return kind in menu(goal, automation)
