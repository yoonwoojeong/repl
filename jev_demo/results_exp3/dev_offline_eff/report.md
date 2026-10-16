# Jev proof demo — experiment 3 (core-library benchmark)

82 theorems; `claude-opus-5-5`, effort `medium` — **offline replay** (cache misses give no proposals).

| method | proved | rate | 95% CI | notional USD | USD per proved | Claude requests | requests per proved | Lean calls | audit-rejected proofs |
|---|---|---|---|---|---|---|---|---|---|
| claude_search | 59/82 | 0.72 | 0.61–0.81 | 3.8381 | 0.0651 | 407 | 6.90 | 1936 | 98 |
| menu_first | 55/82 | 0.67 | 0.56–0.76 | 1.6945 | 0.0308 | 169 | 3.07 | 2248 | 130 |
| jev_router | 59/82 | 0.72 | 0.61–0.81 | 2.1897 | 0.0371 | 221 | 3.75 | 1970 | 147 |

Paired comparisons (same theorems): difference in success rate a − b with a 95% bootstrap CI, discordant pairs, and the exact McNemar p-value.

| a | b | a only | b only | a − b | 95% CI | McNemar p |
|---|---|---|---|---|---|---|
| jev_router | claude_search | 0 | 0 | +0.000 | +0.000–+0.000 | 1.0000 |
| menu_first | claude_search | 0 | 4 | -0.049 | -0.098–-0.012 | 0.1250 |
| jev_router | menu_first | 4 | 0 | +0.049 | +0.012–+0.098 | 0.1250 |

Total Claude spend (actual): $0.0000 of $10.0.

## Per theorem

| theorem | claude_search | menu_first | jev_router |
|---|---|---|---|
| core_List_Cursor_tail_at | – | – | – |
| core_List_IsInfix_count_le | yes (1) | yes (1) | yes (1) |
| core_List_IsSuffix_getLast | – | – | – |
| core_List_IsSuffix_le_count | yes (5) | yes (5) | yes (5) |
| core_List_MergeSort_Internal_splitInTwo_fst_le_splitInTwo_snd | yes (2) | yes (2) | yes (2) |
| core_List_Perm_append_left | yes (1) | yes (1) | yes (1) |
| core_List_Perm_flatten | yes (2) | yes (2) | yes (2) |
| core_List_apply_minOn_append_le_right | – | – | – |
| core_List_attach_filterMap | – | – | – |
| core_List_cons_merge_cons | yes (3) | yes (3) | yes (4) |
| core_List_count_attachWith | yes (32) | yes (26) | yes (34) |
| core_List_filter_append_perm | yes (15) | yes (29) | yes (16) |
| core_List_findIdx_subtype | yes (17) | yes (57) | yes (26) |
| core_List_foldlM_map | yes (4) | yes (4) | yes (4) |
| core_List_foldl_flatMap | yes (2) | yes (2) | yes (2) |
| core_List_foldrM_subtype | – | – | – |
| core_List_foldrM_wfParam | yes (1) | yes (1) | yes (1) |
| core_List_getElem_attach | – | – | – |
| core_List_getElem_maxIdxOn | – | – | – |
| core_List_getElem_set_ne | – | – | – |
| core_List_getLast_append_right | – | – | – |
| core_List_head_singleton | – | – | – |
| core_List_head_takeWhile | – | – | – |
| core_List_infix_filterMap_iff | – | – | – |
| core_List_infix_map_iff | – | – | – |
| core_List_isGE_compare_nil_right | yes (2) | yes (2) | yes (2) |
| core_List_le_max?_getD_of_mem | yes (5) | yes (5) | yes (5) |
| core_List_length_modifyTailIdx | yes (2) | yes (2) | yes (2) |
| core_List_mapFinIdx_congr | – | – | – |
| core_List_mergeSort_pair | yes (38) | yes (60) | yes (42) |
| core_List_merge_right | yes (3) | yes (3) | yes (3) |
| core_List_minOn?_append | yes (61) | – | yes (63) |
| core_List_minOn_cons | – | – | – |
| core_List_nodup_iff_count | yes (33) | yes (29) | yes (40) |
| core_List_nodup_nil | – | – | – |
| core_List_not_of_lt_findIdx | – | – | – |
| core_List_range'_subset_right | – | – | – |
| core_List_replace_append | yes (31) | yes (30) | yes (35) |
| core_List_set_set | yes (18) | yes (35) | yes (19) |
| core_List_splitOnP_append_cons | yes (20) | – | yes (27) |
| core_List_step_iterM_cons | – | – | – |
| core_List_suffix_append_self_iff | yes (1) | yes (1) | yes (1) |
| core_List_utf8Decode?_utf8Encode | – | – | – |
| core_List_zipIdxLE_trans | yes (2) | yes (2) | yes (2) |
| core_List_zipWithMAux_toArray_succ' | yes (2) | yes (2) | yes (2) |
| core_Nat_Coprime_mul_right | yes (3) | yes (3) | yes (3) |
| core_Nat_Internal_Linear_Expr_of_cancel_eq | – | – | – |
| core_Nat_and_div_two_pow | yes (1) | yes (1) | yes (1) |
| core_Nat_compare_ne_gt | yes (20) | yes (49) | yes (22) |
| core_Nat_coprime_div_gcd_div_gcd | yes (1) | yes (1) | yes (1) |
| core_Nat_dvd_div_of_mul_dvd | yes (21) | – | yes (25) |
| core_Nat_dvd_mod_iff | yes (17) | – | yes (19) |
| core_Nat_fold_congr | – | – | – |
| core_Nat_gcd_add_left_left_of_dvd | yes (1) | yes (1) | yes (1) |
| core_Nat_gcd_mul_lcm | yes (1) | yes (1) | yes (1) |
| core_Nat_gcd_self_add_left | yes (3) | yes (3) | yes (3) |
| core_Nat_gcd_self_add_right | yes (1) | yes (1) | yes (1) |
| core_Nat_gcd_sub_left_left_of_dvd | yes (20) | yes (60) | yes (21) |
| core_Nat_gcd_sub_self_left | yes (2) | yes (2) | yes (2) |
| core_Nat_getElem!_toList_ric | yes (3) | yes (3) | yes (3) |
| core_Nat_getElem?_toArray_rcc | yes (1) | yes (1) | yes (1) |
| core_Nat_getElem_toArray_rco | yes (2) | yes (2) | yes (2) |
| core_Nat_lcm_mul_left_right | yes (1) | yes (1) | yes (1) |
| core_Nat_left_le_or | yes (1) | yes (1) | yes (1) |
| core_Nat_lt_of_le_pred | yes (3) | yes (3) | yes (3) |
| core_Nat_lt_of_pow_dvd_right | yes (2) | yes (2) | yes (2) |
| core_Nat_map_add_toArray_rco' | yes (2) | yes (2) | yes (2) |
| core_Nat_mod_mul | yes (1) | yes (1) | yes (1) |
| core_Nat_mul_div_le | yes (2) | yes (2) | yes (3) |
| core_Nat_mul_dvd_mul_right | yes (3) | yes (3) | yes (4) |
| core_Nat_mul_lt_mul'' | yes (2) | yes (2) | yes (2) |
| core_Nat_mul_lt_mul_of_le_of_lt' | yes (2) | yes (2) | yes (2) |
| core_Nat_or_and_distrib_right | yes (1) | yes (1) | yes (1) |
| core_Nat_or_lt_two_pow | yes (2) | yes (2) | yes (2) |
| core_Nat_pow_lcm_pow | yes (1) | yes (1) | yes (1) |
| core_Nat_right_le_or | yes (20) | yes (37) | yes (21) |
| core_Nat_shiftRight_succ_inside | yes (1) | yes (1) | yes (2) |
| core_Nat_size_rco | yes (38) | yes (45) | yes (21) |
| core_Nat_toArray_rco_append_toArray_rco | yes (2) | yes (2) | yes (2) |
| core_Nat_toArray_roo_succ_succ | yes (1) | yes (1) | yes (1) |
| core_Nat_toList_repr | yes (1) | yes (1) | yes (1) |
| core_Nat_toNat?_repr | – | – | – |
