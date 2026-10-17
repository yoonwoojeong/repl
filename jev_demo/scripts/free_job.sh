#!/usr/bin/env bash
# Job 5: miniF2F valid (Lean v4.24.0 + Mathlib), free. (1) dump Mathlib theorem names (filters the
# LeanDojo corpus for BM25 premises); (2) re-run the Lean-only baselines after the loader fix;
# (3) Jev alone with BM25-premise steps; (4) Lean-only `closes` labels for the router.
set -euo pipefail
MF_COMMIT=5746b7d6c47855ce1294bed87329618ff7f1bc31
W=$HOME/mf
curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y --default-toolchain none
export PATH=$HOME/.elan/bin:$PATH
git clone -q https://github.com/yangky11/miniF2F-lean4 $W/miniF2F && git -C $W/miniF2F checkout -q $MF_COMMIT
(cd $W/miniF2F && lake exe cache get > /dev/null && lake build Mathlib > /dev/null)
git clone -q --depth 1 --branch v4.24.0 https://github.com/leanprover-community/repl $W/repl
cp $W/miniF2F/lean-toolchain $W/repl/lean-toolchain
(cd $W/repl && lake build > /dev/null)
export LEAN_PATH=$(cd $W/miniF2F && lake env printenv LEAN_PATH)
pip install -q numpy networkx bm25s
pip install -q -e jev_demo > /dev/null
O=jev_demo/results_free/minif2f
mkdir -p $O/logs
M="python3 -m jev_demo.minif2f"
R="$W/miniF2F valid $W/repl/.lake/build/bin/repl"
NC="--names-cache $O/mathlib_theorem_names.txt.gz"
$M labels $R $NC --out $O/valid_closes_labels.json --limit 1 > $O/logs/names.log 2>&1  # warms the name cache
$M single $R > $O/logs/single.log 2>&1 &
$M menu_search $R > $O/logs/menu_search.log 2>&1 &
wait
$M jev_search $R $NC > $O/logs/jev_search.log 2>&1 &
$M labels $R $NC --out $O/valid_closes_labels.json > $O/logs/labels.log 2>&1 &
wait
tail -n 2 $O/logs/*.log
