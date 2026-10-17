import pytest

from jev_demo.schema import BinaryAnswer, BinaryQuestion, ChoiceAnswer, ChoiceQuestion, validate


def test_choice_rejects_duplicate_options():
    with pytest.raises(ValueError):
        ChoiceQuestion(name="q", options=("a", "a"))


def test_choice_rejects_empty():
    with pytest.raises(ValueError):
        ChoiceQuestion(name="q", options=())


def test_validate_rejects_extra_option():
    q = ChoiceQuestion(name="q", options=("a", "b"))
    with pytest.raises(ValueError):
        validate(q, ChoiceAnswer(probs={"a": 0.5, "b": 0.25, "c": 0.25}))


def test_validate_rejects_bad_sum():
    q = ChoiceQuestion(name="q", options=("a", "b"))
    with pytest.raises(ValueError):
        validate(q, ChoiceAnswer(probs={"a": 0.6, "b": 0.6}))


def test_top_and_confidence():
    ans = ChoiceAnswer(probs={"a": 0.2, "b": 0.8})
    assert ans.top == "b"
    assert ans.confidence == pytest.approx(0.8)


def test_binary_range():
    with pytest.raises(ValueError):
        validate(BinaryQuestion(name="q"), BinaryAnswer(p_true=1.2))
