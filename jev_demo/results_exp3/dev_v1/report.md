# Jev proof demo — experiment 3 (core-library benchmark)

82 theorems; `claude-opus-5-5`, effort `medium`.

| method | proved | rate | 95% CI | notional USD | USD per proved | audit-rejected proofs |
|---|---|---|---|---|---|---|
| claude_whole | 57/82 | 0.70 | 0.59–0.78 | 5.2293 | 0.0917 | 2 |
| claude_search | 59/82 | 0.72 | 0.61–0.81 | 4.3349 | 0.0735 | 96 |
| hybrid | 52/82 | 0.63 | 0.53–0.73 | 3.5745 | 0.0687 | 128 |

Paired comparisons (same theorems): difference in success rate a − b with a 95% bootstrap CI, discordant pairs, and the exact McNemar p-value.

| a | b | a only | b only | a − b | 95% CI | McNemar p |
|---|---|---|---|---|---|---|
| hybrid | claude_search | 1 | 8 | -0.085 | -0.159–-0.024 | 0.0391 |
| claude_whole | claude_search | 3 | 5 | -0.024 | -0.098–+0.037 | 0.7266 |
| hybrid | claude_whole | 3 | 8 | -0.061 | -0.146–+0.012 | 0.2266 |

Total Claude spend (actual): $10.2643 of $20.0.

## Per theorem

| theorem | claude_whole | claude_search | hybrid |
|---|---|---|---|
| core_List_Cursor_tail_at | – | – | – |
| core_List_IsInfix_count_le | yes (1) | yes (1) | yes (1) |
| core_List_IsSuffix_getLast | – | – | – |
| core_List_IsSuffix_le_count | yes (1) | yes (4) | yes (2) |
| core_List_MergeSort_Internal_splitInTwo_fst_le_splitInTwo_snd | yes (1) | yes (5) | yes (5) |
| core_List_Perm_append_left | yes (1) | yes (1) | yes (1) |
| core_List_Perm_flatten | yes (1) | yes (17) | yes (41) |
| core_List_apply_minOn_append_le_right | – | – | – |
| core_List_attach_filterMap | – | – | – |
| core_List_cons_merge_cons | yes (1) | yes (2) | yes (2) |
| core_List_count_attachWith | yes (1) | yes (6) | yes (6) |
| core_List_filter_append_perm | yes (1) | yes (18) | – |
| core_List_findIdx_subtype | yes (1) | yes (19) | yes (39) |
| core_List_foldlM_map | yes (1) | yes (4) | yes (14) |
| core_List_foldl_flatMap | yes (1) | yes (4) | – |
| core_List_foldrM_subtype | yes (2) | yes (54) | – |
| core_List_foldrM_wfParam | yes (1) | yes (14) | yes (36) |
| core_List_getElem_attach | – | – | – |
| core_List_getElem_maxIdxOn | – | – | – |
| core_List_getElem_set_ne | – | – | – |
| core_List_getLast_append_right | – | – | – |
| core_List_head_singleton | – | – | – |
| core_List_head_takeWhile | – | – | – |
| core_List_infix_filterMap_iff | yes (1) | – | – |
| core_List_infix_map_iff | yes (1) | – | yes (43) |
| core_List_isGE_compare_nil_right | yes (1) | yes (1) | yes (1) |
| core_List_le_max?_getD_of_mem | yes (1) | yes (3) | yes (5) |
| core_List_length_modifyTailIdx | yes (1) | yes (40) | yes (41) |
| core_List_mapFinIdx_congr | – | – | – |
| core_List_mergeSort_pair | – | yes (36) | – |
| core_List_merge_right | yes (2) | yes (5) | yes (38) |
| core_List_minOn?_append | – | yes (60) | – |
| core_List_minOn_cons | – | – | – |
| core_List_nodup_iff_count | yes (4) | yes (35) | – |
| core_List_nodup_nil | – | – | – |
| core_List_not_of_lt_findIdx | – | – | – |
| core_List_range'_subset_right | yes (2) | yes (3) | – |
| core_List_replace_append | – | yes (4) | yes (12) |
| core_List_set_set | yes (1) | yes (17) | – |
| core_List_splitOnP_append_cons | – | – | – |
| core_List_step_iterM_cons | – | – | – |
| core_List_suffix_append_self_iff | yes (1) | yes (2) | yes (2) |
| core_List_utf8Decode?_utf8Encode | – | – | – |
| core_List_zipIdxLE_trans | yes (1) | yes (4) | yes (4) |
| core_List_zipWithMAux_toArray_succ' | yes (1) | yes (4) | yes (39) |
| core_Nat_Coprime_mul_right | – | yes (2) | yes (2) |
| core_Nat_Internal_Linear_Expr_of_cancel_eq | – | – | – |
| core_Nat_and_div_two_pow | yes (1) | yes (1) | yes (5) |
| core_Nat_compare_ne_gt | yes (1) | yes (2) | yes (3) |
| core_Nat_coprime_div_gcd_div_gcd | yes (1) | yes (1) | yes (1) |
| core_Nat_dvd_div_of_mul_dvd | yes (1) | yes (19) | yes (39) |
| core_Nat_dvd_mod_iff | yes (2) | yes (16) | yes (36) |
| core_Nat_fold_congr | – | – | – |
| core_Nat_gcd_add_left_left_of_dvd | yes (1) | yes (1) | yes (1) |
| core_Nat_gcd_mul_lcm | yes (1) | yes (1) | yes (2) |
| core_Nat_gcd_self_add_left | yes (1) | yes (1) | yes (2) |
| core_Nat_gcd_self_add_right | yes (1) | yes (1) | yes (1) |
| core_Nat_gcd_sub_left_left_of_dvd | yes (1) | – | – |
| core_Nat_gcd_sub_self_left | yes (1) | yes (2) | yes (2) |
| core_Nat_getElem!_toList_ric | yes (1) | yes (1) | yes (1) |
| core_Nat_getElem?_toArray_rcc | yes (2) | yes (1) | yes (14) |
| core_Nat_getElem_toArray_rco | yes (4) | yes (4) | yes (3) |
| core_Nat_lcm_mul_left_right | yes (1) | yes (1) | yes (1) |
| core_Nat_left_le_or | yes (1) | yes (3) | yes (4) |
| core_Nat_lt_of_le_pred | yes (1) | yes (2) | yes (3) |
| core_Nat_lt_of_pow_dvd_right | yes (1) | yes (2) | yes (2) |
| core_Nat_map_add_toArray_rco' | yes (1) | yes (1) | yes (1) |
| core_Nat_mod_mul | yes (1) | yes (1) | yes (1) |
| core_Nat_mul_div_le | yes (1) | yes (1) | yes (2) |
| core_Nat_mul_dvd_mul_right | yes (1) | yes (3) | yes (3) |
| core_Nat_mul_lt_mul'' | yes (1) | yes (2) | yes (1) |
| core_Nat_mul_lt_mul_of_le_of_lt' | yes (1) | yes (2) | yes (1) |
| core_Nat_or_and_distrib_right | yes (1) | yes (1) | yes (1) |
| core_Nat_or_lt_two_pow | yes (1) | yes (2) | yes (3) |
| core_Nat_pow_lcm_pow | yes (1) | yes (1) | yes (1) |
| core_Nat_right_le_or | yes (1) | yes (2) | yes (2) |
| core_Nat_shiftRight_succ_inside | yes (1) | yes (1) | yes (2) |
| core_Nat_size_rco | – | yes (6) | yes (5) |
| core_Nat_toArray_rco_append_toArray_rco | yes (1) | yes (2) | yes (2) |
| core_Nat_toArray_roo_succ_succ | yes (1) | yes (1) | yes (1) |
| core_Nat_toList_repr | yes (1) | yes (1) | yes (2) |
| core_Nat_toNat?_repr | – | – | – |
