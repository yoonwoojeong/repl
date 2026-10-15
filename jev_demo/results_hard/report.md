# Jev proof demo — phase 1 results

| method | proved | easy | hard | mean calls (proved) | mean seconds (proved) |
|---|---|---|---|---|---|
| model | 1/20 | 0/0 | 1/20 | 39.00 | 2.51 |
| model_no_premise | 1/20 | 0/0 | 1/20 | 19.00 | 0.99 |
| fixed | 0/20 | 0/0 | 0/20 | – | – |
| random | 0/20 | 0/0 | 0/20 | – | – |
| grind_only | 0/20 | 0/0 | 0/20 | – | – |
| try_only | 5/20 | 0/0 | 5/20 | 1.00 | 1.81 |

Success criterion (hard set: `model` proves strictly more than the best of fixed, grind_only, try_only): **not met** — model 1/20 vs try_only 5/20.

Supplementary, added after the first run and not part of the success criterion: the planned `fixed`/`random` rankers report confidence 1.0, so the search only tries their first 3 actions per state. With confidence = top score (1/n) the search escalates and expands the whole menu:

| method | proved | easy | hard | mean calls (proved) | mean seconds (proved) |
|---|---|---|---|---|---|
| fixed_expand_all | 1/20 | 0/0 | 1/20 | 36.00 | 1.91 |
| random_expand_all | 1/20 | 0/0 | 1/20 | 44.00 | 4.58 |

- ECE (10 bins) of `kind` on test gold steps: 0.15 (25 steps)
- Calibrated temperatures: `kind` = 2.3, `premise` = 4.0
- Premise shortlist recall@16 on test gold premise steps: 0.00
- Premise shortlist recall@16 on train gold premise steps: 0.25
- Train replay: 105 gold steps, 0 outside the `kind` options, 2/8 premise steps shortlisted
- Test replay: 62 gold steps, 37 outside the `kind` options, 0/7 premise steps shortlisted

## Per theorem

| theorem | difficulty | menu-reachable | model | model_no_premise | fixed | random | grind_only | try_only | fixed_expand_all | random_expand_all |
|---|---|---|---|---|---|---|---|---|---|---|
| h2_sum_cubes | hard | no | yes (39) | yes (19) | – | – | – | yes (1) | yes (36) | yes (44) |
| h2_sum_acc | hard | no | – | – | – | – | – | – | – | – |
| h2_compile_correct | hard | no | – | – | – | – | – | – | – | – |
| h2_isort_length | hard | no | – | – | – | – | – | – | – | – |
| h2_isort_sorted | hard | no | – | – | – | – | – | – | – | – |
| h2_fib_coprime | hard | no | – | – | – | – | – | – | – | – |
| h2_fib_add | hard | no | – | – | – | – | – | yes (1) | – | – |
| h2_six_dvd_consec | hard | no | – | – | – | – | – | – | – | – |
| h2_sq_le_two_pow | hard | no | – | – | – | – | – | – | – | – |
| h2_is_even | hard | no | – | – | – | – | – | yes (1) | – | – |
| h2_ack_gt | hard | no | – | – | – | – | – | yes (1) | – | – |
| h2_count_isort | hard | no | – | – | – | – | – | – | – | – |
| h2_rev_append_acc | hard | no | – | – | – | – | – | – | – | – |
| h2_take_drop_sum | hard | no | – | – | – | – | – | – | – | – |
| h2_ack_succ | hard | no | – | – | – | – | – | – | – | – |
| h2_isort_idem | hard | no | – | – | – | – | – | – | – | – |
| h2_rev2_append | hard | no | – | – | – | – | – | – | – | – |
| h2_fib_lt_two_pow | hard | no | – | – | – | – | – | yes (1) | – | – |
| h2_prod_acc | hard | no | – | – | – | – | – | – | – | – |
| h2_fast_fib | hard | no | – | – | – | – | – | – | – | – |

Cells: `yes (calls)` when proved, `–` otherwise.
