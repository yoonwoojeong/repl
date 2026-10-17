"""BM25 premise retrieval on LeanDojo Benchmark 4 (the lexical baseline of the LeanDojo paper),
scored with ReProver's protocol and evaluation. Uses the `bm25s` package (BM25, sparse scoring;
`rank_bm25` was too slow for 152k premises x 18k queries within a CI job) with its default
tokenizer, keeping one-character tokens (`TOKEN_PATTERN`; Lean goals are full of `x`, `n`, `0`)."""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import bm25s

from jev_demo.ld4 import AccessIndex, load_corpus, load_split
from jev_demo.reprover_common import Pos, evaluate, get_all_pos_premises
from jev_demo.theorems import DATA_DIR

TOKEN_PATTERN = r"(?u)\b\w+\b"


def tok(texts):
    return bm25s.tokenize(texts, stopwords=None, token_pattern=TOKEN_PATTERN, show_progress=False)

def main(split: str = "novel_premises", parts=("val", "test"), k: int = 100) -> dict:
    corpus = load_corpus()
    access = AccessIndex(corpus)
    bm25 = bm25s.BM25()
    bm25.index(tok([p.serialize() for p in corpus.all_premises]), show_progress=False)
    out = {"method": "bm25", "split": split}
    for part in parts:
        data = load_split(split, part)
        preds = {}
        for thm in data:
            acc = access.mask(thm["file_path"], Pos(*thm["start"]))
            for i, tac in enumerate(thm["traced_tactics"]):
                pos = get_all_pos_premises(tac["annotated_tactic"], corpus)
                if not pos:  # not scored by the evaluation; skip the expensive search
                    preds[(thm["file_path"], thm["full_name"], tuple(thm["start"]), i)] = {
                        "all_pos_premises": [], "retrieved_premises": []}
                    continue
                q = bm25s.tokenize(tac["state_before"], stopwords=None, token_pattern=TOKEN_PATTERN,
                                   show_progress=False, return_ids=False)[0]
                raw = bm25.get_scores(q) if q else np.zeros(len(corpus.all_premises))
                s = np.where(acc, raw, -np.inf)
                top = np.argpartition(-s, k)[:k]
                top = top[np.argsort(-s[top])]
                preds[(thm["file_path"], thm["full_name"], tuple(thm["start"]), i)] = {
                    "all_pos_premises": pos, "retrieved_premises": [corpus.all_premises[j] for j in top]}
        r1, r10, mrr = evaluate(data, preds)
        out[part] = {"R@1": round(r1, 2), "R@10": round(r10, 2), "MRR": round(mrr, 4)}
        print(f"bm25 {split}/{part}: R@1 {r1:.2f} R@10 {r10:.2f} MRR {mrr:.4f}", file=sys.stderr, flush=True)
    d = os.path.join(os.path.dirname(DATA_DIR), "results_free", "looped")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{split}_bm25.json"), "w") as f:
        json.dump(out, f, indent=1)
    return out


if __name__ == "__main__":
    main(*(sys.argv[1:2] or ["novel_premises"]))
