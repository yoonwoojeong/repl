import re
import zlib

from jev_demo.model import SystemOneModel, featurize, tokenize
from jev_demo.schema import BinaryQuestion


def _ref_featurize(state, option=None, dim=2**16, question=""):
    """The phase-1 featurizer, frozen verbatim as a reference."""
    feats = {}

    def add(kind, feat):
        i = zlib.crc32(f"{question}\x1f{kind}\x1f{feat}".encode("utf-8")) % dim
        feats[i] = feats.get(i, 0.0) + 1.0

    add("bias", "")
    goal = tokenize(state)
    for t in goal:
        add("g1", t)
    for a, b in zip(goal, goal[1:]):
        add("g2", f"{a} {b}")
    if option is not None:
        toks = tokenize(option)
        head = toks[0] if toks else ""
        add("ofull", option)
        add("ohead", head)
        parts = [p for p in re.split(r"[.\s_]+", head) if p] if head else []
        otoks = [head] + parts if head else []
        for p in parts:
            add("opart", p)
        for o in otoks:
            for t in sorted(set(goal)):
                add("x", f"{o}\x1e{t}")
    return feats


STATE = "n : Nat ⊢ n + 0 = n"


def test_prefixed_option_has_source_rank_and_tactic_features():
    f = featurize(STATE, "llm|2|Nat.add_zero [n]", question="kind")
    plain = featurize(STATE, "Nat.add_zero [n]", question="kind")
    h = lambda kind, feat: zlib.crc32(f"kind\x1f{kind}\x1f{feat}".encode()) % 2**16
    assert h("src", "llm") in f and h("rank", "2") in f
    assert h("src", "llm") not in plain
    # everything the bare tactic has is present, and the only extras are src/rank
    assert set(plain) <= set(f)
    assert set(f) - set(plain) == {h("src", "llm"), h("rank", "2")}
    assert all(f[i] == plain[i] for i in plain)
    assert featurize(STATE, "llm|0|x", question="kind") != featurize(STATE, "llm|1|x", question="kind")


def test_unprefixed_options_unchanged_from_phase1():
    for opt in ["simp", "rfl", "simp [*] at *", "intro h", "induction n <;> simp_all", "rw [·]",
                "exact ·", "Nat.add_comm (a b : Nat) : a + b = b + a", "llm", "llm|x", "llm|abc|y", ""]:
        for q in ("kind", "premise", "useful"):
            assert featurize(STATE, opt, question=q) == _ref_featurize(STATE, opt, question=q), opt
    assert featurize(STATE) == _ref_featurize(STATE)


def test_evaluate_two_useful_questions_distinct_answers():
    m = SystemOneModel()
    f = featurize(STATE, "llm|0|foo", question="useful")
    for i in f:
        m.w[i] += 1.0  # make this option score high
    qs = [BinaryQuestion("useful", option="llm|0|foo"), BinaryQuestion("useful", option="llm|1|bar")]
    out = m.evaluate(STATE, qs)
    assert len(out) == 2
    a, b = out["useful|llm|0|foo"].p_true, out["useful|llm|1|bar"].p_true
    assert a > 0.9 and a != b
