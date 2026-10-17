#!/usr/bin/env bash
# Shared miniF2F setup (sourced): elan, yangky11/miniF2F-lean4 at a pinned commit with Mathlib's
# build cache, the leanprover-community REPL at v4.24.0; exports W, LEAN_PATH and MF_REPL.
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
export MF_REPL=$W/repl/.lake/build/bin/repl
pip install -q numpy networkx bm25s
