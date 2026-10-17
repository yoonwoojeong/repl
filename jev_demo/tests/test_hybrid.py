from jev_demo.actions import menu
from jev_demo.hybrid import LLM_PREFIX, HybridRanker, strip_llm
from jev_demo.premises import Shortlister
from jev_demo.schema import BinaryAnswer, ChoiceAnswer, ChoiceQuestion, answer_key

G0 = "⊢ a"
G1 = "⊢ b"
MENU = menu(G0)


class FakeGen:
    def __init__(self, props):
        self.props, self.calls = props, []

    def propose(self, goal, prelude="", failed=()):
        self.calls.append((goal, prelude, list(failed)))
        return list(self.props.get(goal, self.props.get("*", [])))


class StubModel:
    """Uniform `kind`, optional per-option overrides; records the questions it was asked."""

    def __init__(self, kind=None, useful=None):
        self.kind, self.useful, self.asked = kind or {}, useful or {}, []

    def evaluate(self, goal, questions):
        self.asked.append(questions)
        out = {}
        for q in questions:
            if isinstance(q, ChoiceQuestion):
                w = {o: self.kind.get(o, 1.0) for o in q.options}
                t = sum(w.values())
                out[q.name] = ChoiceAnswer({o: v / t for o, v in w.items()})
            else:
                out[answer_key(q)] = BinaryAnswer(self.useful.get(q.option, 0.5) if q.option else 0.5)
        return out


def make(props, order="jev", model=None, prelude="P"):
    gen = FakeGen(props)
    return HybridRanker(model or StubModel(), Shortlister([]), {}, gen, order=order, prelude=prelude), gen


def test_llm_options_prefixed_and_deduplicated():
    model = StubModel()
    r, _ = make({"*": ["nlinarith [h]", "simp", "nlinarith [h]", "  linarith "]}, model=model)
    actions, _, _ = r.rank(G0)
    kind = next(q for q in model.asked[0] if isinstance(q, ChoiceQuestion))
    llm_opts = [o for o in kind.options if o.startswith(LLM_PREFIX)]
    assert llm_opts == ["llm|0|nlinarith [h]", "llm|1|linarith"]  # "simp" is on the menu, dupes dropped
    assert len(kind.options) == len(set(kind.options))
    # one useful question per proposal, in the same evaluate call
    assert len(model.asked) == 1
    assert {q.option for q in model.asked[0] if q.name == "useful"} == set(llm_opts)
    # ranker output is executable: no prefix leaks
    assert all(not a.startswith(LLM_PREFIX) for a, _ in actions)
    assert {"nlinarith [h]", "linarith"} <= {a for a, _ in actions}


def test_strip_llm_roundtrip():
    assert strip_llm("llm|3|rw [foo|bar]") == "rw [foo|bar]"
    assert strip_llm(LLM_PREFIX + "0|simp") == "simp"
    assert strip_llm("simp") == "simp"


def test_jev_order_uses_model_scores():
    model = StubModel(kind={"llm|0|foo": 10.0}, useful={"llm|0|foo": 0.9, "llm|1|bar": 0.01})
    r, _ = make({"*": ["foo", "bar"]}, model=model)
    actions, conf, _ = r.rank(G0)
    sc = dict(actions)
    assert actions[0][0] == "foo" and conf == actions[0][1]
    assert abs(sum(sc.values()) - 1.0) < 1e-9
    # bar: uniform kind prob, but useful=0.01 pushes it below every menu item
    assert sc["bar"] < min(sc[m] for m in MENU)
    assert set(sc) == set(MENU) | {"foo", "bar"}


def test_llm_order_tries_claude_first():
    r, _ = make({"*": ["foo", "simp", "bar"]}, order="llm")
    actions, conf, _ = r.rank(G0)
    names = [a for a, _ in actions]
    assert names[:2] == ["foo", "bar"]  # Claude's order first (menu duplicates removed)
    assert names[2:] == list(MENU)
    assert conf == 0.0  # low confidence: search expands every action
    assert len({s for _, s in actions}) == 1


def test_failed_tactics_passed_back_to_generator():
    r, gen = make({"*": ["foo", "bar"]})
    r.rank(G0)
    assert gen.calls[0] == (G0, "P", [])
    r.note_failed(G0, ["foo"])
    actions, _, _ = r.rank(G0)
    assert gen.calls[1] == (G0, "P", ["foo"])
    assert "foo" not in {a for a, _ in actions}  # known failures are not offered again
    r.note_failed(G0, ["foo", "bar"])
    assert r.rank(G0) and gen.calls[2][2] == ["foo", "bar"]


def test_one_generator_call_per_distinct_goal():
    r, gen = make({"*": ["foo"]})
    r.rank(G0)
    r.rank(G0)
    r.rank("⊢  a")  # same goal modulo whitespace
    assert len(gen.calls) == 1
    r.rank(G1)
    assert len(gen.calls) == 2


def test_filter_order_keeps_claude_order_and_defers_low_useful_proposals():
    from jev_demo.actions import menu
    from jev_demo.hybrid import HybridRanker

    class Gen:
        def propose(self, goal, prelude="", failed=(), **kw):
            return ["good_a", "bad_b", "good_c"]

    class Base:
        automation = True
        def p_useful(self, goal, extras):
            return {o: (0.1 if t == "bad_b" else 0.9) for o, t in extras.items()}

    r = HybridRanker.__new__(HybridRanker)
    r.base, r.generator, r.order, r.prelude, r.banned, r.tau = Base(), Gen(), "filter", "", (), 0.3
    r._root = None
    r._proposals, r._failed = {}, {}
    goal = "⊢ P"
    actions, conf, _ = r.rank(goal)
    names = [a for a, _ in actions]
    assert names[:2] == ["good_a", "good_c"] and names[-1] == "bad_b" and conf == 0.0
    assert names[2:-1] == list(menu(goal, True))


def _lazy_ranker(order, p_close=None):
    from jev_demo.hybrid import HybridRanker

    class Gen:
        calls = 0
        def propose(self, goal, prelude="", failed=(), **kw):
            Gen.calls += 1
            return ["claude_tac"]

    class Base:
        automation = True
        def p_closes(self, goal, tactics):
            return {t: (p_close or {}).get(t, 0.0) for t in tactics}

    r = HybridRanker.__new__(HybridRanker)
    r.base, r.generator, r.order, r.prelude, r.banned = Base(), Gen(), order, "", ()
    r.tau, r.route_tau, r.route_k, r._root = 0.3, 0.5, 3, None
    r._proposals, r._failed = {}, {}
    return r, Gen


def test_menu_first_asks_claude_first_only_at_the_root():
    from jev_demo.actions import menu
    from jev_demo.search import ASK_CLAUDE
    r, gen = _lazy_ranker("menu_first")
    root = [a for a, _ in r.rank("⊢ P")[0]]
    inner = [a for a, _ in r.rank("⊢ Q")[0]]
    assert root[0] == ASK_CLAUDE and inner[-1] == ASK_CLAUDE and inner[:-1] == list(menu("⊢ Q", True))
    assert gen.calls == 0  # ranking never calls Claude; only reaching ASK_CLAUDE does
    assert r.claude_actions("⊢ Q") == ["claude_tac"] and gen.calls == 1


def test_router_tries_likely_closers_before_claude_else_claude_first():
    from jev_demo.search import ASK_CLAUDE
    r, _ = _lazy_ranker("router", {"simp": 0.9, "omega": 0.7, "decide": 0.2})
    sure = [a for a, _ in r.rank("⊢ P")[0]]
    assert sure[:3] == ["simp", "omega", ASK_CLAUDE]
    r2, _ = _lazy_ranker("router", {})
    assert [a for a, _ in r2.rank("⊢ P")[0]][0] == ASK_CLAUDE
