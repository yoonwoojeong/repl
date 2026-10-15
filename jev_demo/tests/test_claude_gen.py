import os
from types import SimpleNamespace

import anthropic
import httpx2 as httpx
import pytest

from jev_demo.claude_gen import ClaudeGenerator, Proposals
from jev_demo.prompts import EXAMPLE_SOURCES, SYSTEM_PROMPT
from jev_demo.theorems import DATA_DIR, load_theorems


def resp(tactics, stop="end_turn", inp=100, out=50, read=0, write=0, text=None):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text if text is not None else
                                 Proposals(tactics=tactics or []).model_dump_json())],
        stop_reason=stop,
        usage=SimpleNamespace(input_tokens=inp, output_tokens=out,
                              cache_read_input_tokens=read, cache_creation_input_tokens=write),
    )


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._parse))

    def _parse(self, **kw):
        self.calls.append(kw)
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(r, Exception):
            raise r
        return r


def gen(client, tmp_path, **kw):
    return ClaudeGenerator(client=client, cache_dir=str(tmp_path / "c"), **kw)


def test_propose_returns_parsed_tactics_in_order(tmp_path):
    g = gen(FakeClient(resp(["intro n", "simp", "omega"])), tmp_path)
    assert g.propose("⊢ ∀ n : Nat, n + 0 = n") == ["intro n", "simp", "omega"]
    assert g.usage.calls == 1


def test_request_shape(tmp_path):
    c = FakeClient(resp(["rfl"]))
    gen(c, tmp_path).propose("⊢ 1 = 1")
    kw = c.calls[0]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["output_config"]["effort"] == "medium"
    assert kw["cache_control"] == {"type": "ephemeral"}
    assert kw["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in kw["betas"]
    assert kw["system"] == SYSTEM_PROMPT
    assert kw["max_tokens"] == 16000
    fmt = kw["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"]["additionalProperties"] is False and fmt["schema"]["required"] == ["tactics"]
    for bad in ("thinking", "temperature", "tool_choice"):
        assert bad not in kw


def test_drops_sorry_and_admit(tmp_path):
    g = gen(FakeClient(resp(["sorry", "simp", "admit", "exact sorry", "have h : 1 = 1 := by admit",
                             "simp", "omega"])), tmp_path)
    assert g.propose("⊢ g") == ["simp", "omega"]


def test_refusal_yields_empty_and_counts(tmp_path):
    g = gen(FakeClient(resp(None, stop="refusal", text="I cannot help with that.")), tmp_path)
    assert g.propose("⊢ g") == []
    assert g.usage.refusals == 1 and g.usage.errors == 0
    assert g.usage.usd > 0 and g.usage.input_tokens == 100
    assert not os.path.exists(tmp_path / "c")


def test_invalid_json_counts_error_and_is_metered(tmp_path):
    g = gen(FakeClient(resp(None, text='{"tactics": ["simp"', inp=1_000_000, out=0)), tmp_path)
    assert g.propose("⊢ g") == []
    assert g.usage.errors == 1 and g.usage.refusals == 0
    assert g.usage.usd == pytest.approx(4.0)
    assert not os.path.exists(tmp_path / "c")


def test_max_tokens_counts_error_and_is_metered(tmp_path):
    g = gen(FakeClient(resp(None, stop="max_tokens", text='{"tactics": ["si', inp=0, out=1_000_000)), tmp_path)
    assert g.propose("⊢ g") == []
    assert g.usage.errors == 1 and g.usage.usd == pytest.approx(20.0)
    assert not os.path.exists(tmp_path / "c")


def test_billed_failures_count_toward_cap(tmp_path):
    c = FakeClient(resp(None, text="oops", inp=1_000_000, out=0))
    g = gen(c, tmp_path, max_usd=4.0)
    assert g.propose("⊢ a") == []
    assert g.propose("⊢ b") == []
    assert len(c.calls) == 1


def test_api_error_yields_empty_and_counts(tmp_path):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    err = anthropic.RateLimitError("slow down", response=httpx.Response(429, request=req), body=None)
    g = gen(FakeClient(err), tmp_path)
    assert g.propose("⊢ g") == []
    assert g.usage.errors == 1
    assert not os.path.exists(tmp_path / "c") or not os.listdir(tmp_path / "c")


def test_disk_cache_hit_makes_no_call_and_no_cost(tmp_path):
    c = FakeClient(resp(["simp"]))
    g1 = gen(c, tmp_path)
    assert g1.propose("⊢ g", "def f := 1", ["rfl"]) == ["simp"]
    c2 = FakeClient(resp(["WRONG"]))
    g2 = gen(c2, tmp_path)
    assert g2.propose("⊢ g", "def f := 1", ["rfl"]) == ["simp"]
    assert c2.calls == [] and g2.usage.calls == 0 and g2.usage.usd == 0.0


def test_cost_meter_prices(tmp_path):
    g = gen(FakeClient(resp(["simp"], inp=1_000_000, out=100_000)), tmp_path)
    g.propose("⊢ g")
    assert g.usage.usd == pytest.approx(4.0 + 2.0)
    assert (g.usage.input_tokens, g.usage.output_tokens) == (1_000_000, 100_000)


def test_cache_tokens_priced(tmp_path):
    g = gen(FakeClient(resp(["simp"], inp=0, out=0, read=1_000_000, write=1_000_000)), tmp_path)
    g.propose("⊢ g")
    assert g.usage.usd == pytest.approx(0.20 + 5.0)
    assert (g.usage.cache_read_tokens, g.usage.cache_write_tokens) == (1_000_000, 1_000_000)


def test_cap_stops_calls(tmp_path):
    c = FakeClient(resp(["simp"]))
    g = gen(c, tmp_path, max_usd=0.0)
    assert g.propose("⊢ g") == []
    assert c.calls == [] and g.usage.calls == 0


def test_failed_list_in_user_message(tmp_path):
    c = FakeClient(resp(["omega"]))
    gen(c, tmp_path).propose("n : Nat\n⊢ n = n", "def f := 1", ["simp", "rfl"])
    msg = c.calls[0]["messages"][0]["content"]
    assert msg.index("def f := 1") < msg.index("n : Nat") < msg.index("- simp") < msg.index("- rfl")


def test_whole_proof_k_independent_calls(tmp_path):
    c = FakeClient(resp(["intro n", "simp"]), resp(["intro n", "omega"]), resp(["sorry"]))
    g = gen(c, tmp_path)
    out = g.whole_proof("∀ n : Nat, n + 0 = n", k=3)
    assert len(c.calls) == 3 and g.usage.calls == 3
    assert out == [["intro n", "simp"], ["intro n", "omega"]]


def test_prompt_examples_are_train_only():
    train = {t.name for t in load_theorems(os.path.join(DATA_DIR, "train.json"))}
    test = {t.name for t in load_theorems(os.path.join(DATA_DIR, "test.json"))}
    assert len(EXAMPLE_SOURCES) == 5
    assert set(EXAMPLE_SOURCES) <= train and not set(EXAMPLE_SOURCES) & test
    for t in load_theorems(os.path.join(DATA_DIR, "test.json")):
        assert t.name not in SYSTEM_PROMPT and t.statement not in SYSTEM_PROMPT


@pytest.mark.claude
@pytest.mark.skipif(os.environ.get("ANTHROPIC_RUN_LIVE") != "1", reason="set ANTHROPIC_RUN_LIVE=1 to call the API")
def test_live_proposes_for_simple_goal(tmp_path):
    g = ClaudeGenerator(cache_dir=str(tmp_path / "live"))
    assert len(g.propose("n : Nat\n⊢ n + 0 = n")) >= 1
    assert g.usage.calls == 1
