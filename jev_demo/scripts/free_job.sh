#!/usr/bin/env bash
# Job 1: fetch LeanDojo Benchmark 4 (Zenodo 10114185) and record its layout and sample records.
set -euo pipefail
OUT=jev_demo/results_free/leandojo_inventory
mkdir -p "$OUT" /tmp/ld
curl -sSL https://zenodo.org/api/records/10114185 > "$OUT/record.json"
python3 - "$OUT/record.json" > /tmp/ld/urls <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
for f in r["files"]:
    print(f["links"]["self"], f["key"], f["size"])
PY
cat /tmp/ld/urls | tee "$OUT/files.txt"
read -r url key size < /tmp/ld/urls
curl -sSL "$url" -o "/tmp/ld/$key"
cd /tmp/ld && tar xzf "$key" && cd - > /dev/null
find /tmp/ld -maxdepth 3 -type f -printf "%s %p\n" | sort -k2 > "$OUT/tree.txt"
python3 - /tmp/ld "$OUT" <<'PY'
import json, os, sys, glob
root, out = sys.argv[1], sys.argv[2]
def trunc(x, n=400):
    if isinstance(x, str): return x[:n]
    if isinstance(x, list): return [trunc(v, n) for v in x[:3]] + (["..."] if len(x) > 3 else [])
    if isinstance(x, dict): return {k: trunc(v, n) for k, v in x.items()}
    return x
summary = {}
for p in sorted(glob.glob(root + "/**/*.json", recursive=True)):
    d = json.load(open(p))
    n_tac = sum(len(t.get("traced_tactics", [])) for t in d) if isinstance(d, list) else None
    summary[os.path.relpath(p, root)] = {"n": len(d), "tactics": n_tac, "sample": trunc(d[0]) if isinstance(d, list) else None}
for p in sorted(glob.glob(root + "/**/*.jsonl", recursive=True)):
    lines = open(p).read().splitlines()
    summary[os.path.relpath(p, root)] = {"n": len(lines), "sample": trunc(json.loads(lines[0]))}
json.dump(summary, open(out + "/summary.json", "w"), indent=1, ensure_ascii=False)
PY
