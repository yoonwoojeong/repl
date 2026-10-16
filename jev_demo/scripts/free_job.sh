#!/usr/bin/env bash
# Job 2: LeanDojo Benchmark 4 (Zenodo 10114185) in a compact form for training on CPU elsewhere:
# corpus.jsonl gzipped as-is, and per split (random, novel_premises) x (train, val, test) the
# theorems with, per traced tactic, only the tactic, state_before and the premise provenances
# (state_after and annotated text dropped). Nothing is filtered, so ReProver's protocol applies.
set -euo pipefail
OUT=jev_demo/data/standard
mkdir -p "$OUT" /tmp/ld
url=$(curl -sSL https://zenodo.org/api/records/10114185 | python3 -c "import json,sys; print(json.load(sys.stdin)['files'][0]['links']['self'])")
curl -sSL "$url" -o /tmp/ld/ld4.tar.gz
md5sum /tmp/ld/ld4.tar.gz | tee "$OUT/ld4_source_md5.txt"
cd /tmp/ld && tar xzf ld4.tar.gz && cd - > /dev/null
B=/tmp/ld/leandojo_benchmark_4
gzip -9 -c $B/corpus.jsonl > "$OUT/ld4_corpus.jsonl.gz"
cp $B/metadata.json "$OUT/ld4_metadata.json"
python3 - "$B" "$OUT" <<'PY'
import gzip, json, os, sys
B, OUT = sys.argv[1], sys.argv[2]
for split in ("random", "novel_premises"):
    for part in ("train", "val", "test"):
        data = json.load(open(f"{B}/{split}/{part}.json"))
        rows = []
        for t in data:
            rows.append({"file_path": t["file_path"], "full_name": t["full_name"], "start": t["start"],
                         "traced_tactics": [{"tactic": x["tactic"], "state_before": x["state_before"],
                                             "annotated_tactic": [None, [{"def_path": p["def_path"], "def_pos": p["def_pos"],
                                                                          "full_name": p["full_name"]}
                                                                         for p in x["annotated_tactic"][1]]]}
                                            for x in t["traced_tactics"]]})
        path = f"{OUT}/ld4_{split}_{part}.json.gz"
        with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as f:
            json.dump(rows, f, ensure_ascii=False)
        print(split, part, len(rows), sum(len(r["traced_tactics"]) for r in rows), os.path.getsize(path))
PY
ls -la "$OUT"
