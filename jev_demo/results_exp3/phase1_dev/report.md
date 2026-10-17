# Jev proof demo — phase 1 results

| method | proved | easy | hard | mean calls (proved) | mean seconds (proved) |
|---|---|---|---|---|---|
| model | 7/82 | 0/0 | 7/82 | 34.43 | 3.45 |
| model_no_premise | 4/82 | 0/0 | 4/82 | 18.25 | 0.91 |
| fixed | 5/82 | 0/0 | 5/82 | 32.80 | 5.13 |
| random | 5/82 | 0/0 | 5/82 | 26.20 | 4.76 |
| grind_only | 0/82 | 0/0 | 0/82 | – | – |
| try_only | 0/82 | 0/0 | 0/82 | – | – |

Success criterion (hard set: `model` proves strictly more than the best of fixed, grind_only, try_only): **met** — model 7/82 vs fixed 5/82.

Supplementary, added after the first run and not part of the success criterion: the planned `fixed`/`random` rankers report confidence 1.0, so the search only tries their first 3 actions per state. With confidence = top score (1/n) the search escalates and expands the whole menu:

| method | proved | easy | hard | mean calls (proved) | mean seconds (proved) |
|---|---|---|---|---|---|
| fixed_expand_all | 0/82 | 0/0 | 0/82 | – | – |
| random_expand_all | 0/82 | 0/0 | 0/82 | – | – |

- ECE (10 bins) of `kind` on test gold steps: 0.00 (0 steps)
- Calibrated temperatures: `kind` = 2.3, `premise` = 4.0
- Premise shortlist recall@16 on test gold premise steps: 0.00
- Premise shortlist recall@16 on train gold premise steps: 0.25
- Train replay: 105 gold steps, 0 outside the `kind` options, 2/8 premise steps shortlisted
- Test replay: 0 gold steps, 0 outside the `kind` options, 0/0 premise steps shortlisted

## Per theorem

| theorem | difficulty | menu-reachable | model | model_no_premise | fixed | random | grind_only | try_only | fixed_expand_all | random_expand_all |
|---|---|---|---|---|---|---|---|---|---|---|
| core_List_Cursor_tail_at | hard | – | – | – | – | – | – | – | – | – |
| core_List_IsInfix_count_le | hard | – | yes (16) | yes (16) | yes (50) | yes (38) | – | – | – | – |
| core_List_IsSuffix_getLast | hard | – | – | – | – | – | – | – | – | – |
| core_List_IsSuffix_le_count | hard | – | – | – | – | – | – | – | – | – |
| core_List_MergeSort_Internal_splitInTwo_fst_le_splitInTwo_snd | hard | – | yes (62) | – | yes (32) | yes (27) | – | – | – | – |
| core_List_Perm_append_left | hard | – | yes (8) | yes (8) | yes (31) | yes (24) | – | – | – | – |
| core_List_Perm_flatten | hard | – | – | – | – | – | – | – | – | – |
| core_List_apply_minOn_append_le_right | hard | – | – | – | – | – | – | – | – | – |
| core_List_attach_filterMap | hard | – | – | – | – | – | – | – | – | – |
| core_List_cons_merge_cons | hard | – | – | – | – | – | – | – | – | – |
| core_List_count_attachWith | hard | – | – | – | – | – | – | – | – | – |
| core_List_filter_append_perm | hard | – | – | – | – | – | – | – | – | – |
| core_List_findIdx_subtype | hard | – | – | – | – | – | – | – | – | – |
| core_List_foldlM_map | hard | – | – | – | – | – | – | – | – | – |
| core_List_foldl_flatMap | hard | – | – | – | – | – | – | – | – | – |
| core_List_foldrM_subtype | hard | – | – | – | – | – | – | – | – | – |
| core_List_foldrM_wfParam | hard | – | yes (42) | yes (22) | yes (32) | yes (27) | – | – | – | – |
| core_List_getElem_attach | hard | – | – | – | – | – | – | – | – | – |
| core_List_getElem_maxIdxOn | hard | – | – | – | – | – | – | – | – | – |
| core_List_getElem_set_ne | hard | – | – | – | – | – | – | – | – | – |
| core_List_getLast_append_right | hard | – | – | – | – | – | – | – | – | – |
| core_List_head_singleton | hard | – | – | – | – | – | – | – | – | – |
| core_List_head_takeWhile | hard | – | – | – | – | – | – | – | – | – |
| core_List_infix_filterMap_iff | hard | – | – | – | – | – | – | – | – | – |
| core_List_infix_map_iff | hard | – | – | – | – | – | – | – | – | – |
| core_List_isGE_compare_nil_right | hard | – | – | – | – | – | – | – | – | – |
| core_List_le_max?_getD_of_mem | hard | – | – | – | – | – | – | – | – | – |
| core_List_length_modifyTailIdx | hard | – | – | – | – | – | – | – | – | – |
| core_List_mapFinIdx_congr | hard | – | – | – | – | – | – | – | – | – |
| core_List_mergeSort_pair | hard | – | – | – | – | – | – | – | – | – |
| core_List_merge_right | hard | – | – | – | – | – | – | – | – | – |
| core_List_minOn?_append | hard | – | – | – | – | – | – | – | – | – |
| core_List_minOn_cons | hard | – | – | – | – | – | – | – | – | – |
| core_List_nodup_iff_count | hard | – | – | – | – | – | – | – | – | – |
| core_List_nodup_nil | hard | – | – | – | – | – | – | – | – | – |
| core_List_not_of_lt_findIdx | hard | – | – | – | – | – | – | – | – | – |
| core_List_range'_subset_right | hard | – | – | – | – | – | – | – | – | – |
| core_List_replace_append | hard | – | – | – | – | – | – | – | – | – |
| core_List_set_set | hard | – | – | – | – | – | – | – | – | – |
| core_List_splitOnP_append_cons | hard | – | – | – | – | – | – | – | – | – |
| core_List_step_iterM_cons | hard | – | – | – | – | – | – | – | – | – |
| core_List_suffix_append_self_iff | hard | – | – | – | – | – | – | – | – | – |
| core_List_utf8Decode?_utf8Encode | hard | – | – | – | – | – | – | – | – | – |
| core_List_zipIdxLE_trans | hard | – | – | – | – | – | – | – | – | – |
| core_List_zipWithMAux_toArray_succ' | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_Coprime_mul_right | hard | – | yes (48) | – | – | – | – | – | – | – |
| core_Nat_Internal_Linear_Expr_of_cancel_eq | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_and_div_two_pow | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_compare_ne_gt | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_coprime_div_gcd_div_gcd | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_dvd_div_of_mul_dvd | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_dvd_mod_iff | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_fold_congr | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_gcd_add_left_left_of_dvd | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_gcd_mul_lcm | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_gcd_self_add_left | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_gcd_self_add_right | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_gcd_sub_left_left_of_dvd | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_gcd_sub_self_left | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_getElem!_toList_ric | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_getElem?_toArray_rcc | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_getElem_toArray_rco | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_lcm_mul_left_right | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_left_le_or | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_lt_of_le_pred | hard | – | yes (47) | yes (27) | yes (19) | yes (15) | – | – | – | – |
| core_Nat_lt_of_pow_dvd_right | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_map_add_toArray_rco' | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_mod_mul | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_mul_div_le | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_mul_dvd_mul_right | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_mul_lt_mul'' | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_mul_lt_mul_of_le_of_lt' | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_or_and_distrib_right | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_or_lt_two_pow | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_pow_lcm_pow | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_right_le_or | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_shiftRight_succ_inside | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_size_rco | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_toArray_rco_append_toArray_rco | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_toArray_roo_succ_succ | hard | – | yes (18) | – | – | – | – | – | – | – |
| core_Nat_toList_repr | hard | – | – | – | – | – | – | – | – | – |
| core_Nat_toNat?_repr | hard | – | – | – | – | – | – | – | – | – |

Cells: `yes (calls)` when proved, `–` otherwise.
