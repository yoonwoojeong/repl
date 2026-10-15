# Jev proof demo — phase 1 results

| method | proved | easy | hard | mean calls (proved) | mean seconds (proved) |
|---|---|---|---|---|---|
| model | 16/20 | 8/8 | 8/12 | 14.25 | 0.49 |
| model_no_premise | 15/20 | 8/8 | 7/12 | 8.67 | 0.37 |
| fixed | 5/20 | 3/8 | 2/12 | 2.00 | 0.15 |
| random | 9/20 | 6/8 | 3/12 | 1.44 | 0.15 |
| grind_only | 8/20 | 6/8 | 2/12 | 1.00 | 0.18 |
| try_only | 15/20 | 8/8 | 7/12 | 1.00 | 0.90 |

Success criterion (hard set: `model` proves strictly more than the best of fixed, grind_only, try_only): met nominally (8 vs 7) — model 8/12 vs try_only 7/12.
However, the model does not beat exhaustive search over the same menu (8 vs 10 hard for post-hoc `fixed_expand_all`), so this experiment does not show that the model helps.

Supplementary, added after the first run and not part of the success criterion: the planned `fixed`/`random` rankers report confidence 1.0, so the search only tries their first 3 actions per state. With confidence = top score (1/n) the search escalates and expands the whole menu:

| method | proved | easy | hard | mean calls (proved) | mean seconds (proved) |
|---|---|---|---|---|---|
| fixed_expand_all | 18/20 | 8/8 | 10/12 | 15.72 | 0.54 |
| random_expand_all | 18/20 | 8/8 | 10/12 | 15.56 | 0.93 |

- ECE (10 bins) of `kind` on test gold steps: 0.06 (52 steps)
- Calibrated temperatures: `kind` = 2.3, `premise` = 4.0
- Premise shortlist recall@16 on test gold premise steps: 0.25
- Premise shortlist recall@16 on train gold premise steps: 0.25
- Train replay: 105 gold steps, 0 outside the `kind` options, 2/8 premise steps shortlisted
- Test replay: 54 gold steps, 2 outside the `kind` options, 1/4 premise steps shortlisted

## Per theorem

| theorem | difficulty | menu-reachable | model | model_no_premise | fixed | random | grind_only | try_only | fixed_expand_all | random_expand_all |
|---|---|---|---|---|---|---|---|---|---|---|
| test_add_comm | easy | True | yes (2) | yes (2) | – | yes (2) | yes (1) | yes (1) | yes (4) | yes (2) |
| test_append_length | easy | True | yes (2) | yes (2) | yes (2) | yes (1) | yes (1) | yes (1) | yes (2) | yes (1) |
| test_reverse_reverse | easy | True | yes (2) | yes (2) | yes (2) | yes (1) | yes (1) | yes (1) | yes (2) | yes (1) |
| test_mod_two_cases | easy | True | yes (6) | yes (6) | – | yes (2) | yes (1) | yes (1) | yes (4) | yes (2) |
| test_or_comm | easy | True | yes (14) | yes (14) | – | yes (2) | yes (1) | yes (1) | yes (10) | yes (2) |
| test_add_eq_zero_left | easy | True | yes (2) | yes (2) | yes (2) | yes (1) | yes (1) | yes (1) | yes (2) | yes (1) |
| test_double | easy | True | yes (38) | yes (18) | – | – | – | yes (1) | yes (27) | yes (40) |
| test_sum_to | easy | True | yes (39) | yes (19) | – | – | – | yes (1) | yes (36) | yes (44) |
| test_sum_odd | hard | True | yes (39) | yes (19) | – | – | – | yes (1) | yes (36) | yes (44) |
| test_sum_sq | hard | True | yes (39) | yes (19) | – | – | – | yes (1) | yes (36) | yes (44) |
| test_succ_le_two_pow | hard | True | – | – | – | – | – | – | yes (25) | yes (23) |
| test_sq_mod_four | hard | False | – | – | – | – | – | – | – | – |
| test_gcd_succ | hard | True | yes (3) | yes (3) | yes (2) | yes (1) | – | yes (1) | yes (2) | yes (1) |
| test_dvd_mul_right | hard | True | yes (11) | yes (11) | – | yes (2) | yes (1) | yes (1) | yes (10) | yes (2) |
| test_map_double_sum | hard | True | yes (6) | yes (6) | – | – | – | – | yes (25) | yes (23) |
| test_rev_eq_reverse | hard | False | – | – | – | – | – | – | – | – |
| test_two_dvd_mul_succ | hard | True | – | – | – | – | – | – | yes (25) | yes (23) |
| test_fib_mono | hard | True | yes (5) | yes (5) | – | – | – | yes (1) | yes (24) | yes (21) |
| test_map_map | hard | True | yes (2) | yes (2) | yes (2) | yes (1) | yes (1) | yes (1) | yes (2) | yes (1) |
| test_mul_self_le | hard | True | yes (18) | – | – | – | – | yes (1) | yes (11) | yes (5) |

Cells: `yes (calls)` when proved, `–` otherwise.
