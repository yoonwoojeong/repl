#!/usr/bin/env bash
# Paid stages of experiment 3, run by .github/workflows/jev-exp3-live.yml (one label per stage).
# Every stage has a hard USD cap (--max-usd per command); the caps are the budget approved for it.
set -euo pipefail
stage="${1:?usage: exp3_stage.sh pilot|stage1|final}"
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
        --labels $D/claude_labels.json,$D/claude_labels_core.json --out $R/dev_v1 --max-usd 15 \
        2>&1 | tee $R/dev_v1.log ;;
  final)  # the pre-registered test run, once
    run --test $D/core_test.json --methods claude_whole,claude_search,hybrid \
        --labels $D/claude_labels.json,$D/claude_labels_core.json --out $R/test --max-usd 40 \
        2>&1 | tee $R/test.log ;;
  *) echo "unknown stage $stage" >&2; exit 2 ;;
esac
