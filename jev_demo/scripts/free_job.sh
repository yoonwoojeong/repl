#!/usr/bin/env bash
# Job 3: miniF2F (Lean 4 port, Lean v4.24.0 + Mathlib) Lean-only baselines on the validation
# split: `single` (each menu tactic alone) and `menu_search` (best-first over the fixed menu, 64
# Lean calls). Sets up elan, the miniF2F project with Mathlib's build cache, and the
# leanprover-community REPL at v4.24.0.
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
pip install -q numpy
pip install -q -e jev_demo > /dev/null
python3 -m jev_demo.minif2f $W/miniF2F valid single $W/repl/.lake/build/bin/repl > /tmp/single.log 2>&1 &
python3 -m jev_demo.minif2f $W/miniF2F valid menu_search $W/repl/.lake/build/bin/repl > /tmp/menu.log 2>&1 &
wait
tail -n 3 /tmp/single.log /tmp/menu.log
