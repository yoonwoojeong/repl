import torch

from jev_demo.looped import AccessIndex, Config, Encoder, encode_bytes, n_params, predict, train
from jev_demo.reprover_common import Corpus, Pos, evaluate

ROWS = [
    {"path": "A.lean", "imports": [], "premises": [
        {"full_name": "a_one", "code": "theorem a_one : 1 = 1 := rfl", "start": [1, 1], "end": [1, 30], "kind": "x"},
        {"full_name": "a_two", "code": "theorem a_two : 2 = 2 := rfl", "start": [2, 1], "end": [2, 30], "kind": "x"}]},
    {"path": "B.lean", "imports": ["A.lean"], "premises": [
        {"full_name": "b_late", "code": "theorem b_late : 3 = 3 := rfl", "start": [50, 1], "end": [50, 30], "kind": "x"}]},
]


def test_variants_share_or_scale_parameters():
    base = dict(d=32, heads=2, ff=64, loops=3, state_len=32, premise_len=32)
    p = {v: n_params(Encoder(Config(variant=v, **base))) for v in ("looped", "same_params", "same_flops")}
    assert p["looped"] == p["same_params"] < p["same_flops"]
    ids, m = encode_bytes(["⊢ 1 = 1", ""], 32)
    out = Encoder(Config(variant="looped", **base))(ids, m)
    assert out.shape == (2, 32) and torch.allclose(out.norm(dim=-1), torch.ones(2), atol=1e-5)


def test_access_mask_matches_reprover_rule():
    c = Corpus.from_rows(ROWS)
    acc = AccessIndex(c)
    names = [p.full_name for p in c.all_premises]
    m = acc.mask("B.lean", Pos(10, 1))  # imports A; b_late is later in the same file
    assert [n for n, x in zip(names, m) if x] == ["a_one", "a_two"]
    assert acc.mask("B.lean", Pos(60, 1))[names.index("b_late")]


def test_train_predict_evaluate_end_to_end():
    c = Corpus.from_rows(ROWS)
    a_one = c.all_premises[0]
    data = [{"file_path": "B.lean", "full_name": "t", "start": [10, 1], "traced_tactics": [
        {"state_before": "⊢ 1 = 1", "annotated_tactic": [None, [{"def_path": "A.lean", "def_pos": [1, 9], "full_name": "a_one"}]]}]}]
    cfg = Config(d=32, heads=2, ff=64, loops=2, state_len=32, premise_len=48, batch=1, steps=3, warmup=1)
    model = train(cfg, c, [("⊢ 1 = 1", [a_one])], log=lambda m: None)
    from jev_demo.looped import embed_premises
    preds = predict(model, c, AccessIndex(c), data, cfg, embed_premises(model, c, cfg), k=1)
    r1, r10, mrr = evaluate(data, preds)
    assert 0 <= r1 <= 100 and len(next(iter(preds.values()))["retrieved_premises"]) == 1
