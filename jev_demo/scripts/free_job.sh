#!/usr/bin/env bash
# Job 6: Lean-only baselines (`single`, `menu_search`) on the miniF2F **test** split, free, as the
# reference for the pre-registered efficiency run (README "miniF2F efficiency run"). No Claude.
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
pip install -q numpy networkx
pip install -q -e jev_demo > /dev/null
O=jev_demo/results_free/minif2f
mkdir -p $O/logs
M="python3 -m jev_demo.minif2f"
R="$W/miniF2F test $W/repl/.lake/build/bin/repl"
$M single $R > $O/logs/test_single.log 2>&1 &
$M menu_search $R > $O/logs/test_menu_search.log 2>&1 &
wait
tail -n 2 $O/logs/test_*.log
