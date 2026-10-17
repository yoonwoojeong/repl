# Jev proof demo — phase 2 results

| method | proved | easy | hard | mean calls (proved) | Claude requests | billed calls | USD (actual) | USD (notional) | refusals | errors |
|---|---|---|---|---|---|---|---|---|---|---|
| claude_whole | 20/20 | 8/8 | 12/12 | 1.00 | 80 | 80 | 0.6792 | 0.6792 | 0 | 0 |
| claude_search | 20/20 | 8/8 | 12/12 | 2.05 | 27 | 27 | 0.3118 | 0.3118 | 0 | 0 |
| hybrid | 20/20 | 8/8 | 12/12 | 4.05 | 43 | 19 | 0.2448 | 0.5300 | 0 | 0 |
| phase1_best (`model`, phase-1 reference) | 16/20 | 8/8 | 8/12 | 14.25 | – | – | – | – | – | – |

Reference, post hoc in phase 1 (the strongest phase-1 method, not pre-registered):

| method | proved | easy | hard | mean calls (proved) | Claude requests | billed calls | USD (actual) | USD (notional) | refusals | errors |
|---|---|---|---|---|---|---|---|---|---|---|
| phase1_fixed_expand_all (phase-1 reference) | 18/20 | 8/8 | 10/12 | 15.72 | – | – | – | – | – | – |

`phase1_*` rows are copied from the phase-1 `results.json`. `claude_whole` asks for 4 complete scripts and counts a theorem as proved if any passes `check_proof`; `claude_search` expands Claude's proposals first, then the fixed menu; `hybrid` ranks Claude's proposals together with the menu using the model refit on phase-1 replays plus Claude labels. USD (actual) is what was billed; USD (notional) prices every request at its original cost, cached or not (`+?`: some cache entries carry no price), and is what question 2 compares. At most 16 Claude requests are made per theorem and method.

Supplementary (ruling P11, not part of the pre-registered questions): `hybrid_expand_all` is `hybrid` with confidence fixed at 0.0, so the search expands every ranked action instead of the top 3 when confident. It separates Jev's ranking from confidence gating. Its Claude requests are mostly cache hits (USD actual near zero); USD (notional) counts them at their original price.

| method | proved | easy | hard | mean calls (proved) | Claude requests | billed calls | USD (actual) | USD (notional) | refusals | errors |
|---|---|---|---|---|---|---|---|---|---|---|
| hybrid_expand_all | 19/20 | 8/8 | 11/12 | 1.90 | 44 | 0 | 0.0000 | 0.5388 | 0 | 0 |

## Pre-registered questions

1. Does `hybrid` prove more hard theorems than `claude_search` (did Jev add value on top of Claude)? **no**: 12/12 vs 12/12.
2. At equal or lower USD? **no**: `hybrid` notional $0.5300 vs `claude_search` $0.3118.
3. Hard theorems with no gold proof inside the phase-1 menu (`menu_reachable = false`) that any Claude method proved: **2/2** (`test_sq_mod_four` by claude_whole, claude_search, hybrid; `test_rev_eq_reverse` by claude_whole, claude_search, hybrid).

Total Claude spend: $1.2358 of $20.0 (`claude-opus-5-5`, effort `medium`).

## Per theorem

| theorem | difficulty | menu-reachable | claude_whole | claude_search | hybrid | hybrid_expand_all | phase1_best | phase1_fixed_expand_all |
|---|---|---|---|---|---|---|---|---|
| test_add_comm | easy | yes | yes (1) | yes (1) | yes (2) | yes (2) | yes (2) | yes (4) |
| test_append_length | easy | yes | yes (1) | yes (1) | yes (2) | yes (2) | yes (2) | yes (2) |
| test_reverse_reverse | easy | yes | yes (1) | yes (1) | yes (1) | yes (1) | yes (2) | yes (2) |
| test_mod_two_cases | easy | yes | yes (1) | yes (1) | yes (2) | yes (2) | yes (6) | yes (4) |
| test_or_comm | easy | yes | yes (1) | yes (2) | yes (2) | yes (2) | yes (14) | yes (10) |
| test_add_eq_zero_left | easy | yes | yes (1) | yes (2) | yes (3) | yes (3) | yes (2) | yes (2) |
| test_double | easy | yes | yes (1) | yes (1) | yes (2) | yes (2) | yes (38) | yes (27) |
| test_sum_to | easy | yes | yes (1) | yes (2) | yes (3) | yes (3) | yes (39) | yes (36) |
| test_sum_odd | hard | yes | yes (1) | yes (1) | yes (2) | yes (2) | yes (39) | yes (36) |
| test_sum_sq | hard | yes | yes (1) | yes (1) | yes (2) | yes (2) | yes (39) | yes (36) |
| test_succ_le_two_pow | hard | yes | yes (1) | yes (1) | yes (2) | yes (2) | – | yes (25) |
| test_sq_mod_four | hard | no | yes (1) | yes (1) | yes (2) | yes (2) | – | – |
| test_gcd_succ | hard | yes | yes (1) | yes (1) | yes (2) | yes (2) | yes (3) | yes (2) |
| test_dvd_mul_right | hard | yes | yes (1) | yes (2) | yes (2) | yes (2) | yes (11) | yes (10) |
| test_map_double_sum | hard | yes | yes (1) | yes (1) | yes (1) | yes (1) | yes (6) | yes (25) |
| test_rev_eq_reverse | hard | no | yes (1) | yes (17) | yes (45) | – | – | – |
| test_two_dvd_mul_succ | hard | yes | yes (1) | yes (1) | yes (2) | yes (2) | – | yes (25) |
| test_fib_mono | hard | yes | yes (1) | yes (1) | yes (2) | yes (2) | yes (5) | yes (24) |
| test_map_map | hard | yes | yes (1) | yes (1) | yes (1) | yes (1) | yes (2) | yes (2) |
| test_mul_self_le | hard | yes | yes (1) | yes (2) | yes (1) | yes (1) | yes (18) | yes (11) |

Cells: `yes (calls)` when proved, `–` otherwise.
