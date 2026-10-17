# Jev proof demo — phase 2 results

| method | proved | easy | hard | mean calls (proved) | Claude requests | billed calls | USD (actual) | USD (notional) | refusals | errors |
|---|---|---|---|---|---|---|---|---|---|---|
| claude_whole | 17/20 | 0/0 | 17/20 | 1.41 | 80 | 80 | 2.3547 | 2.3547 | 0 | 0 |
| claude_search | 16/20 | 0/0 | 16/20 | 10.62 | 79 | 79 | 1.5316 | 1.5316 | 0 | 0 |
| hybrid | 11/20 | 0/0 | 11/20 | 7.64 | 81 | 27 | 0.5314 | 1.6740 | 0 | 0 |
| phase1_best (`try_only`, phase-1 reference) | 5/20 | 0/0 | 5/20 | 1.00 | – | – | – | – | – | – |

Reference, post hoc in phase 1 (the strongest phase-1 method, not pre-registered):

| method | proved | easy | hard | mean calls (proved) | Claude requests | billed calls | USD (actual) | USD (notional) | refusals | errors |
|---|---|---|---|---|---|---|---|---|---|---|
| phase1_fixed_expand_all (phase-1 reference) | 1/20 | 0/0 | 1/20 | 36.00 | – | – | – | – | – | – |

`phase1_*` rows are copied from the phase-1 `results.json`. `claude_whole` asks for 4 complete scripts and counts a theorem as proved if any passes `check_proof`; `claude_search` expands Claude's proposals first, then the fixed menu; `hybrid` ranks Claude's proposals together with the menu using the model refit on phase-1 replays plus Claude labels. USD (actual) is what was billed; USD (notional) prices every request at its original cost, cached or not (`+?`: some cache entries carry no price), and is what question 2 compares. At most 16 Claude requests are made per theorem and method.

Supplementary (ruling P11, not part of the pre-registered questions): `hybrid_expand_all` is `hybrid` with confidence fixed at 0.0, so the search expands every ranked action instead of the top 3 when confident. It separates Jev's ranking from confidence gating. Its Claude requests are mostly cache hits (USD actual near zero); USD (notional) counts them at their original price.

| method | proved | easy | hard | mean calls (proved) | Claude requests | billed calls | USD (actual) | USD (notional) | refusals | errors |
|---|---|---|---|---|---|---|---|---|---|---|
| hybrid_expand_all | 10/20 | 0/0 | 10/20 | 11.20 | 90 | 19 | 0.1968 | 1.5646 | 0 | 0 |

## Pre-registered questions

1. Does `hybrid` prove more hard theorems than `claude_search` (did Jev add value on top of Claude)? **no**: 11/20 vs 16/20.
2. At equal or lower USD? **no**: `hybrid` notional $1.6740 vs `claude_search` $1.5316.
3. Hard theorems with no gold proof inside the phase-1 menu (`menu_reachable = false`) that any Claude method proved: **19/20** (`h2_sum_cubes` by claude_whole, claude_search, hybrid; `h2_sum_acc` by claude_whole, claude_search; `h2_compile_correct` by claude_whole, claude_search, hybrid; `h2_isort_length` by claude_whole, claude_search; `h2_isort_sorted` by claude_whole; `h2_fib_coprime` by claude_whole, claude_search, hybrid; `h2_fib_add` by claude_whole, claude_search, hybrid; `h2_six_dvd_consec` by claude_whole, claude_search, hybrid; `h2_is_even` by claude_search, hybrid; `h2_ack_gt` by claude_search, hybrid; `h2_count_isort` by claude_whole, claude_search, hybrid; `h2_rev_append_acc` by claude_whole, claude_search, hybrid; `h2_take_drop_sum` by claude_whole, claude_search, hybrid; `h2_ack_succ` by claude_whole; `h2_isort_idem` by claude_whole; `h2_rev2_append` by claude_whole, claude_search; `h2_fib_lt_two_pow` by claude_whole, claude_search, hybrid; `h2_prod_acc` by claude_whole, claude_search; `h2_fast_fib` by claude_whole, claude_search).

Total Claude spend: $4.6144 of $20.0 (`claude-opus-5-5`, effort `medium`).

## Per theorem

| theorem | difficulty | menu-reachable | claude_whole | claude_search | hybrid | hybrid_expand_all | phase1_best | phase1_fixed_expand_all |
|---|---|---|---|---|---|---|---|---|
| h2_sum_cubes | hard | no | yes (1) | yes (1) | yes (2) | yes (2) | yes (1) | yes (36) |
| h2_sum_acc | hard | no | yes (1) | yes (16) | – | – | – | – |
| h2_compile_correct | hard | no | yes (1) | yes (16) | yes (41) | – | – | – |
| h2_isort_length | hard | no | yes (1) | yes (17) | – | yes (44) | – | – |
| h2_isort_sorted | hard | no | yes (1) | – | – | – | – | – |
| h2_fib_coprime | hard | no | yes (1) | yes (1) | yes (2) | yes (2) | – | – |
| h2_fib_add | hard | no | yes (4) | yes (38) | yes (12) | yes (44) | yes (1) | – |
| h2_six_dvd_consec | hard | no | yes (1) | yes (1) | yes (2) | yes (2) | – | – |
| h2_sq_le_two_pow | hard | no | – | – | – | – | – | – |
| h2_is_even | hard | no | – | yes (5) | yes (6) | yes (6) | yes (1) | – |
| h2_ack_gt | hard | no | – | yes (1) | yes (1) | yes (1) | yes (1) | – |
| h2_count_isort | hard | no | yes (1) | yes (3) | yes (3) | yes (3) | – | – |
| h2_rev_append_acc | hard | no | yes (1) | yes (17) | yes (7) | – | – | – |
| h2_take_drop_sum | hard | no | yes (1) | yes (5) | yes (6) | yes (6) | – | – |
| h2_ack_succ | hard | no | yes (1) | – | – | – | – | – |
| h2_isort_idem | hard | no | yes (3) | – | – | – | – | – |
| h2_rev2_append | hard | no | yes (1) | yes (16) | – | – | – | – |
| h2_fib_lt_two_pow | hard | no | yes (2) | yes (1) | yes (2) | yes (2) | yes (1) | – |
| h2_prod_acc | hard | no | yes (1) | yes (16) | – | – | – | – |
| h2_fast_fib | hard | no | yes (2) | yes (16) | – | – | – | – |

Cells: `yes (calls)` when proved, `–` otherwise.
