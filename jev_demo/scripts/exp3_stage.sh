#!/usr/bin/env bash
# Paid stages of experiment 3, run by .github/workflows/jev-exp3-live.yml (one label per stage).
# Every stage has a hard USD cap (--max-usd per command); the caps are the budget approved for it.
set -euo pipefail
stage="${1:?usage: exp3_stage.sh pilot|stage1|dev2|final|replicate}"
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
              # cache (no shared Claude responses), two replicates; README "Independent replication"
    for rep in 1 2; do
      for m in claude_search jev_router; do
        run --test $D/core_test.json --train none --methods $m \
            --labels $D/claude_labels_core.json,$D/jev_closes_labels.json \
            --cache-dir jev_demo/cache/rep${rep}_$m --out $R/test_rep${rep}_$m --max-usd 9 \
            2>&1 | tee $R/test_rep${rep}_$m.log
      done
    done ;;
  *) echo "unknown stage $stage" >&2; exit 2 ;;
esac
