#!/usr/bin/env bash
# Paid stages of experiment 3, run by .github/workflows/jev-exp3-live.yml (one label per stage).
# Every stage has a hard USD cap (--max-usd per command); the caps are the budget approved for it.
set -euo pipefail
stage="${1:?usage: exp3_stage.sh pilot|stage1|dev2|final|replicate|g-haiku|g-sonnet|g-opus-low|g-tight|g-ext|mf-pilot|mf-test}"
D=jev_demo/data
R=jev_demo/results_exp3
mkdir -p "$R"
run() { python -m jev_demo exp3 "$@"; }
case "$stage" in
  pilot)  # 8 dev theorems, all three methods: checks the live path, audit and caching end to end
    run --test $D/core_dev.json --limit 8 --methods claude_whole,claude_search,hybrid \
        --labels $D/claude_labels.json --out $R/pilot --max-usd 3 2>&1 | tee $R/pilot.log ;;
  stage1) # labels from claude_search on train, then all methods on dev (hybrid with the new labels)
    run --test $D/core_train.json --methods claude_search --labels-out $D/claude_labels_core.json \
        --labels $D/claude_labels.json --out $R/train --max-usd 15 2>&1 | tee $R/train.log
    run --test $D/core_dev.json --methods claude_whole,claude_search,hybrid \
        --labels $D/claude_labels.json,$D/claude_labels_core.json --out $R/dev_v1 --max-usd 20 \
        2>&1 | tee $R/dev_v1.log ;;
  dev2)   # iteration 2 on dev: claude_search first (fills the response cache), then hybrid_filter,
          # which reuses Claude's responses at shared states, so the two are paired
    run --test $D/core_dev.json --methods claude_search,hybrid_filter \
        --labels $D/claude_labels.json,$D/claude_labels_core.json --out $R/dev_v2 --max-usd 8 \
        2>&1 | tee $R/dev_v2.log ;;
  final)  # the pre-registered test run (README: "Pre-registered test run"), once
    run --test $D/core_test.json --train none --methods claude_search,menu_first,jev_router \
        --labels $D/claude_labels_core.json,$D/jev_closes_labels.json --out $R/test --max-usd 15 \
        2>&1 | tee $R/test.log ;;
  replicate)  # independent replication of the test run: each method has its own empty response
              # cache (no shared Claude responses), two replicates; README "Independent replication".
              # Total budget $26 (approved): each run's cap = what is left minus a reserve for the
              # runs still to come, so the stage can never spend more than $26 in total.
    total=26; spent=0
    order="1:claude_search 1:jev_router 2:claude_search 2:jev_router"
    reserve() {  # reserve for the runs after position $1 (claude_search 7.0, jev_router 3.8)
      python3 -c "import sys; r={'claude_search':7.0,'jev_router':3.8}; print(sum(r[x.split(':')[1]] for x in sys.argv[2:][int(sys.argv[1]):]))" "$1" $order
    }
    k=0
    for item in $order; do
      k=$((k+1)); rep=${item%%:*}; m=${item##*:}
      cap=$(python3 -c "print(round($total - $spent - $(reserve $k), 4))")
      echo "replicate $rep $m: cap \$$cap (spent so far \$$spent of \$$total)"
      run --test $D/core_test.json --train none --methods $m \
          --labels $D/claude_labels_core.json,$D/jev_closes_labels.json \
          --cache-dir jev_demo/cache/rep${rep}_$m --out $R/test_rep${rep}_$m --max-usd "$cap" \
          2>&1 | tee $R/test_rep${rep}_$m.log
      spent=$(python3 -c "import json; print(round($spent + json.load(open('$R/test_rep${rep}_$m/results.json'))['total_usd'], 4))")
    done
    echo "replicate stage spent \$$spent of \$$total" ;;
  g-haiku|g-sonnet|g-opus-low|g-tight|g-ext)
    # Generality (README "Experiment 4", pre-registered): one setting changed from the test run,
    # claude_search then jev_router, each with its own empty response cache (independent samples).
    # The stage total is the approved cap; claude_search's run is capped so that the router's
    # reserve is always left.
    test=$D/core_test.json; extra=""
    case "$stage" in
      g-haiku)    total=3;  reserve=1.0; extra="--claude-model claude-haiku-5-5" ;;
      g-sonnet)   total=9;  reserve=3.5; extra="--claude-model claude-sonnet-5-5" ;;
      g-opus-low) total=12; reserve=4.5; extra="--effort low" ;;
      g-tight)    total=10; reserve=3.5; extra="--claude-cap 8 --lean-budget 32" ;;
      g-ext)      total=14; reserve=5.0; test=$D/ext_test148.json; extra="--library $D/library_ext.json" ;;
    esac
    spent=0
    for m in claude_search jev_router; do
      if [ "$m" = claude_search ]; then cap=$(python3 -c "print(round($total - $reserve, 4))")
      else cap=$(python3 -c "print(round($total - $spent, 4))"); fi
      echo "$stage $m: cap \$$cap (spent so far \$$spent of \$$total)"
      run --test $test --train none --methods $m $extra \
          --labels $D/claude_labels_core.json,$D/jev_closes_labels.json \
          --cache-dir jev_demo/cache/${stage}_$m --out $R/${stage}_$m --max-usd "$cap" \
          2>&1 | tee $R/${stage}_$m.log
      spent=$(python3 -c "import json; print(round($spent + json.load(open('$R/${stage}_$m/results.json'))['total_usd'], 4))")
    done
    echo "$stage spent \$$spent of \$$total" ;;
  mf-pilot|mf-test)
    # miniF2F efficiency run (README "miniF2F efficiency run", pre-registered). claude_search then
    # jev_router, each with its own empty response cache; router trained only on Lean-only
    # `closes` labels from the validation split. mf-pilot: 20 validation problems (plumbing only,
    # not scored); mf-test: the 244 test problems, once.
    source jev_demo/scripts/minif2f_setup.sh
    O=jev_demo/results_free/minif2f
    if [ "$stage" = mf-pilot ]; then split=valid; extra="--limit 20"; total=4; reserve=1.5
    else split=test; extra=""; total=40; reserve=15; fi
    spent=0
    for m in claude_search jev_router; do
      if [ "$m" = claude_search ]; then cap=$(python3 -c "print(round($total - $reserve, 4))")
      else cap=$(python3 -c "print(round($total - $spent, 4))"); fi
      echo "$stage $m: cap \$$cap (spent so far \$$spent of \$$total)"
      python3 -m jev_demo.minif2f claude $W/miniF2F $split $MF_REPL $extra --methods $m \
          --labels $O/valid_closes_labels.json \
          --cache-dir jev_demo/cache/${stage}_$m --out $R/${stage}_$m --max-usd "$cap" \
          2>&1 | tee $R/${stage}_$m.log
      spent=$(python3 -c "import json; print(round($spent + json.load(open('$R/${stage}_$m/results.json'))['total_usd'], 4))")
    done
    echo "$stage spent \$$spent of \$$total" ;;
  *) echo "unknown stage $stage" >&2; exit 2 ;;
esac
