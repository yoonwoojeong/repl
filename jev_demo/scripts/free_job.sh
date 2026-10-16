#!/usr/bin/env bash
# Job 4: looped-transformer premise retriever vs. equal-parameter and equal-compute baselines,
# plus BM25, on LeanDojo Benchmark 4 (novel_premises), scored with ReProver's R@1/R@10/MRR.
# Runs here rather than in a cloud session so it survives the session going idle. CPU only;
# the four runs share the runner's cores (one thread each).
set -euo pipefail
pip install -q torch --index-url https://download.pytorch.org/whl/cpu
pip install -q numpy networkx rank_bm25
pip install -q -e jev_demo > /dev/null
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONWARNINGS=ignore
mkdir -p jev_demo/results_free/looped/logs
for v in same_params looped same_flops; do
  python3 -m jev_demo.looped variant=$v > jev_demo/results_free/looped/logs/$v.log 2>&1 &
done
python3 -m jev_demo.bm25_baseline > jev_demo/results_free/looped/logs/bm25.log 2>&1 &
wait
grep -h "R@1" jev_demo/results_free/looped/logs/*.log
