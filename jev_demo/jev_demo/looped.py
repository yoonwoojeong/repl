"""Looped-transformer premise retriever for Jev, trained and scored on LeanDojo Benchmark 4.

Task and metric are the standard ones from LeanDojo/ReProver: given a proof state (the state
before a tactic), retrieve the library premises the tactic uses, among the premises accessible at
that point; score R@1, R@10 and MRR with ReProver's evaluation (`reprover_common.evaluate`).

Model: a dual encoder (one shared encoder for states and premises, as in ReProver) over UTF-8
bytes (ReProver uses ByT5, also byte-level), mean-pooled and L2-normalised, trained with the
DPR-style in-batch contrastive loss. The encoder is a stack of PyTorch's standard
`nn.TransformerEncoderLayer`. Three variants isolate the effect of looping:

- `looped`:   1 layer applied `loops` times (weight-tied), re-injecting the input embedding at
              every iteration (as in looped/recurrent-depth transformers);
- `same_params`: the same single layer applied once (equal parameters, 1/loops of the compute);
- `same_flops`:  `loops` distinct layers applied once (equal compute, `loops` x the parameters).

Everything is CPU-sized (d=128 by default): the comparison between variants is the point, not
matching ReProver's 299M-parameter ByT5 numbers.
"""

from __future__ import annotations

import gzip
import json
import math
import os
import random
import sys
import time
from dataclasses import asdict, dataclass

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from jev_demo.ld4 import STD, AccessIndex, load_corpus, load_split  # noqa: F401 (re-exported)
from jev_demo.reprover_common import Corpus, evaluate, get_all_pos_premises
from jev_demo.theorems import DATA_DIR
PAD, CLS, OFFSET = 0, 1, 2  # byte b -> token b + OFFSET


@dataclass
class Config:
    variant: str = "looped"  # looped | same_params | same_flops
    d: int = 128
    heads: int = 4
    ff: int = 512
    loops: int = 4
    state_len: int = 256
    premise_len: int = 128
    batch: int = 32
    steps: int = 4000
    lr: float = 1e-3
    warmup: int = 200
    temperature: float = 0.05
    seed: int = 0
    split: str = "novel_premises"


def encode_bytes(texts: list[str], max_len: int) -> tuple[torch.Tensor, torch.Tensor]:
    ids = torch.full((len(texts), max_len), PAD, dtype=torch.long)
    for i, t in enumerate(texts):
        b = t.encode("utf-8")[:max_len - 1]
        ids[i, 0] = CLS
        if b:
            ids[i, 1:len(b) + 1] = torch.tensor(list(b), dtype=torch.long) + OFFSET
    return ids, ids != PAD


class Encoder(nn.Module):
    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        n_layers = cfg.loops if cfg.variant == "same_flops" else 1
        self.loops = cfg.loops if cfg.variant == "looped" else 1
        self.emb = nn.Embedding(256 + OFFSET, cfg.d)
        self.pos = nn.Embedding(max(cfg.state_len, cfg.premise_len), cfg.d)
        self.layers = nn.ModuleList(
            nn.TransformerEncoderLayer(cfg.d, cfg.heads, cfg.ff, dropout=0.0, batch_first=True, norm_first=True)
            for _ in range(n_layers))
        self.norm = nn.LayerNorm(cfg.d)

    def forward(self, ids: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        x0 = self.emb(ids) + self.pos(torch.arange(ids.shape[1], device=ids.device))[None]
        h = x0
        for t in range(self.loops):
            if t > 0:
                h = h + x0  # input injection
            for layer in self.layers:
                h = layer(h, src_key_padding_mask=~mask)
        h = self.norm(h) * mask[..., None]
        return F.normalize(h.sum(1) / mask.sum(1, keepdim=True).clamp(min=1), dim=-1)


def n_params(m: nn.Module) -> int:
    return sum(p.numel() for p in m.parameters())


# -- data -------------------------------------------------------------------------------------

def train_examples(corpus: Corpus, data: list[dict]) -> list[tuple[str, list]]:
    """(state, positive premises) for every tactic with at least one premise (ReProver: train)."""
    out = []
    for thm in data:
        for tac in thm["traced_tactics"]:
            pos = get_all_pos_premises(tac["annotated_tactic"], corpus)
            if pos:
                out.append((tac["state_before"], pos))
    return out


# -- training --------------------------------------------------------------------------------

def train(cfg: Config, corpus: Corpus, examples, log=print) -> Encoder:
    torch.manual_seed(cfg.seed)
    rng = random.Random(cfg.seed)
    model = Encoder(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / cfg.warmup) * 0.5 * (1 + math.cos(math.pi * min(s, cfg.steps) / cfg.steps)))
    t0 = time.perf_counter()
    for step in range(cfg.steps):
        batch = rng.sample(examples, cfg.batch)
        states = [s for s, _ in batch]
        pos = [rng.choice(p) for _, p in batch]
        sid, sm = encode_bytes(states, cfg.state_len)
        pid, pm = encode_bytes([p.serialize() for p in pos], cfg.premise_len)
        q, k = model(sid, sm), model(pid, pm)
        logits = q @ k.t() / cfg.temperature
        # another example's sampled premise may also be a positive of this one: not a negative
        same = torch.tensor([[pos[j] in set(batch[i][1]) and i != j for j in range(len(batch))]
                             for i in range(len(batch))])
        logits = logits.masked_fill(same, float("-inf"))
        loss = F.cross_entropy(logits, torch.arange(len(batch)))
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step % 100 == 0 or step == cfg.steps - 1:
            log(f"{cfg.variant} step {step} loss {loss.item():.3f} {time.perf_counter() - t0:.0f}s")
    return model


@torch.no_grad()
def embed_premises(model: Encoder, corpus: Corpus, cfg: Config, bs: int = 512) -> torch.Tensor:
    model.eval()
    out = []
    for i in range(0, len(corpus.all_premises), bs):
        ids, m = encode_bytes([p.serialize() for p in corpus.all_premises[i:i + bs]], cfg.premise_len)
        out.append(model(ids, m))
    return torch.cat(out)


@torch.no_grad()
def predict(model: Encoder, corpus: Corpus, access: AccessIndex, data: list[dict], cfg: Config,
            prem_emb: torch.Tensor, k: int = 100) -> dict:
    """ReProver's prediction protocol: top-k accessible premises per tactic, keyed by
    (file_path, full_name, start, tactic_idx), with the gold premises of each tactic."""
    from jev_demo.reprover_common import Pos
    model.eval()
    preds = {}
    rows = [(thm, i, tac) for thm in data for i, tac in enumerate(thm["traced_tactics"])]
    for b in range(0, len(rows), 256):
        chunk = rows[b:b + 256]
        ids, m = encode_bytes([tac["state_before"] for _, _, tac in chunk], cfg.state_len)
        sims = (model(ids, m) @ prem_emb.t()).numpy()
        for (thm, i, tac), s in zip(chunk, sims):
            acc = access.mask(thm["file_path"], Pos(*thm["start"]))
            s = np.where(acc, s, -np.inf)
            top = np.argpartition(-s, k)[:k]
            top = top[np.argsort(-s[top])]
            preds[(thm["file_path"], thm["full_name"], tuple(thm["start"]), i)] = {
                "all_pos_premises": get_all_pos_premises(tac["annotated_tactic"], corpus),
                "retrieved_premises": [corpus.all_premises[j] for j in top]}
    return preds


def run(cfg: Config, parts=("val", "test"), log=print) -> dict:
    corpus = load_corpus()
    access = AccessIndex(corpus)
    ex = train_examples(corpus, load_split(cfg.split, "train"))
    log(f"{len(corpus.all_premises)} premises, {len(ex)} training (state, premises) examples")
    model = train(cfg, corpus, ex, log)
    prem = embed_premises(model, corpus, cfg)
    out = {"config": asdict(cfg), "params": n_params(model)}
    for part in parts:
        data = load_split(cfg.split, part)
        r1, r10, mrr = evaluate(data, predict(model, corpus, access, data, cfg, prem))
        out[part] = {"R@1": round(r1, 2), "R@10": round(r10, 2), "MRR": round(mrr, 4)}
        log(f"{cfg.variant} {cfg.split}/{part}: R@1 {r1:.2f}  R@10 {r10:.2f}  MRR {mrr:.4f}")
    return out


if __name__ == "__main__":
    kw = dict(a.split("=", 1) for a in sys.argv[1:])
    cfg = Config(**{k: type(getattr(Config, k))(v) for k, v in kw.items()})
    res = run(cfg, log=lambda m: print(m, file=sys.stderr, flush=True))
    d = os.path.join(os.path.dirname(DATA_DIR), "results_free", "looped")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{cfg.split}_{cfg.variant}_L{cfg.loops}_s{cfg.seed}.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res))
