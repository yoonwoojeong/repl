# Jev proof demo — experiment 3 (core-library benchmark)

161 theorems; `claude-opus-5-5`, effort `medium`.

| method | proved | rate | 95% CI | notional USD | USD per proved | audit-rejected proofs |
|---|---|---|---|---|---|---|
| claude_search | 115/161 | 0.71 | 0.64–0.78 | 7.7041 | 0.0670 | 104 |

Total Claude spend (actual): $7.7041 of $15.0.

## Per theorem

| theorem | claude_search |
|---|---|
| core_List_Cursor_pos_le_length | – |
| core_List_IsInfix_filter | yes (3) |
| core_List_IsInfix_le_count | yes (3) |
| core_List_MergeSort_Internal_splitRevAt_eq | – |
| core_List_Nodup_count | yes (17) |
| core_List_Pairwise_and_mem | yes (1) |
| core_List_Pairwise_perm | yes (2) |
| core_List_Perm_flatMap_right | yes (2) |
| core_List_Sublist_erase | yes (2) |
| core_List_Sublist_of_sublist_append_left | yes (43) |
| core_List_all_subtype | yes (18) |
| core_List_apply_maxOn_le_iff | – |
| core_List_apply_maxOn_lt_apply_getElem_of_lt_maxIdxOn | – |
| core_List_attachWith_congr | – |
| core_List_attachWith_congr_simp | – |
| core_List_compareLex_nil_cons | yes (1) |
| core_List_count_erase | yes (3) |
| core_List_count_replicate_self | yes (2) |
| core_List_dropLast_take | yes (3) |
| core_List_dropWhile_cons | yes (1) |
| core_List_drop_modifyHead_of_pos | yes (1) |
| core_List_drop_reverse | yes (19) |
| core_List_drop_set | yes (13) |
| core_List_drop_set_of_lt | yes (3) |
| core_List_erase_cons_head | yes (3) |
| core_List_erase_subset | yes (2) |
| core_List_exists_of_set | yes (1) |
| core_List_filterTR_loop_eq | yes (2) |
| core_List_filter_eq | yes (2) |
| core_List_findFinIdx?_append | – |
| core_List_findIdx?_flatten | – |
| core_List_findIdx_singleton | yes (1) |
| core_List_flatten_nil | – |
| core_List_foldlM_attachWith | – |
| core_List_foldrM_attachWith | – |
| core_List_getElem?_attach | – |
| core_List_getElem?_unattach | yes (22) |
| core_List_getElem_get_minIdxOn? | – |
| core_List_getElem_idxOf | yes (2) |
| core_List_getElem_intersperse_two_mul | – |
| core_List_getElem_mapFinIdx | – |
| core_List_getLast?_nil | – |
| core_List_getLast_congr_simp | – |
| core_List_getLast_erase_mem | yes (2) |
| core_List_getLast_filter | – |
| core_List_getLast_filter_of_pos | – |
| core_List_get_maxOn? | – |
| core_List_get_min? | – |
| core_List_head_congr_simp | – |
| core_List_head_filter_of_pos | – |
| core_List_head_ofFn | – |
| core_List_infix_filter_iff | yes (34) |
| core_List_infix_iff_getElem? | – |
| core_List_infix_iff_prefix_suffix | yes (1) |
| core_List_instLawfulBEqCmpCompareLex | yes (20) |
| core_List_instReflOrd | yes (20) |
| core_List_intercalate_splitOn | – |
| core_List_isLE_compareLex_nil_left | yes (1) |
| core_List_isPrefixOf_cons_cons_self | yes (2) |
| core_List_isSome_minIdxOn?_of_mem | yes (2) |
| core_List_le_count_tail | yes (4) |
| core_List_le_trans | yes (6) |
| core_List_left_le_left_of_cons_le_cons | yes (2) |
| core_List_left_le_maxIdxOn_append | – |
| core_List_length_insert_pos | yes (3) |
| core_List_lookup_nil | – |
| core_List_lt_of_le_of_lt | yes (2) |
| core_List_mapFinIdx_append | – |
| core_List_mapFinIdx_mapFinIdx | – |
| core_List_mapFinIdx_reverse | – |
| core_List_map_inj | yes (1) |
| core_List_map_set | yes (18) |
| core_List_maxIdxOn?_cons | yes (41) |
| core_List_max_singleton | – |
| core_List_mergeSort_fun_cases_unfolding | – |
| core_List_min?_singleton | yes (1) |
| core_List_minOn?_fun_cases_unfolding | yes (1) |
| core_List_minOn?_singleton | yes (1) |
| core_List_ofFn_succ_last | yes (55) |
| core_List_pairwise_iff_getElem | – |
| core_List_pairwise_lt_finRange | yes (2) |
| core_List_perm_append_comm_assoc | yes (1) |
| core_List_perm_comm | yes (1) |
| core_List_perm_ext_iff_of_nodup | – |
| core_List_perm_insertIdx | yes (3) |
| core_List_pmap_append | – |
| core_List_pmap_attachWith | – |
| core_List_range'_succ | yes (1) |
| core_List_size_toByteArray | yes (18) |
| core_List_step_iterM | – |
| core_List_step_iter_nil | – |
| core_List_suffix_of_suffix_length_le | yes (2) |
| core_List_sum_div_length_le_max_nat | – |
| core_List_sum_le_max_mul_length_int | yes (2) |
| core_List_sum_pos_iff_exists_pos_nat | yes (1) |
| core_List_tail_attachWith | – |
| core_List_tail_scanl | – |
| core_List_takeWhile_append_of_pos | yes (19) |
| core_List_takeWhile_cons_of_neg | yes (2) |
| core_List_take_reverse | – |
| core_List_take_takeWhile | yes (1) |
| core_List_toByteArray_append | yes (21) |
| core_List_unattach_replicate | yes (1) |
| core_List_unzip_nil | – |
| core_List_utf8DecodeChar_utf8Encode_cons | yes (1) |
| core_Nat_Coprime_mul_dvd_of_dvd_of_dvd | yes (2) |
| core_Nat_Coprime_mul_gcd | yes (2) |
| core_Nat_Coprime_mul_left | yes (1) |
| core_Nat_Internal_Linear_Poly_denote_le_cancel_eq | yes (1) |
| core_Nat_Internal_SOM_Poly_denote_insertSorted | yes (1) |
| core_Nat_add_mod_left | yes (1) |
| core_Nat_and_div_two | yes (1) |
| core_Nat_any_zero | yes (1) |
| core_Nat_base_induction | yes (61) |
| core_Nat_div_gcd_pos_of_pos_left | yes (1) |
| core_Nat_dvd_add_iff_right | yes (1) |
| core_Nat_dvd_gcd | yes (1) |
| core_Nat_dvd_of_mul_dvd_mul_right | yes (2) |
| core_Nat_exists_testBit_ne_of_ne | yes (1) |
| core_Nat_forall_lt_succ_left' | – |
| core_Nat_gcd_add_one | yes (1) |
| core_Nat_gcd_div_gcd_div_gcd_of_pos_left | yes (4) |
| core_Nat_gcd_div_gcd_div_gcd_of_pos_right | yes (18) |
| core_Nat_gcd_dvd_gcd_mul_left_right | yes (2) |
| core_Nat_gcd_mul_left_add_right | yes (1) |
| core_Nat_gcd_mul_right_sub_right | yes (18) |
| core_Nat_gcd_sub_mul_right_left | yes (2) |
| core_Nat_getD_toArray_ric | yes (2) |
| core_Nat_getD_toArray_roc | yes (2) |
| core_Nat_getD_toList_rcc | yes (2) |
| core_Nat_getElem!_toList_roc | yes (4) |
| core_Nat_getElem_toArray_rcc | yes (3) |
| core_Nat_getElem_toList_ric | yes (3) |
| core_Nat_induct_rcc_right | yes (2) |
| core_Nat_induct_roo_left | yes (53) |
| core_Nat_instNeZeroHPow | yes (2) |
| core_Nat_isNone_getElem?_toList_roo_eq | yes (2) |
| core_Nat_lcm_dvd_lcm_of_dvd_right | yes (3) |
| core_Nat_lcm_mul_right_left | yes (1) |
| core_Nat_le_of_testBit | yes (2) |
| core_Nat_lt_log2_self | yes (1) |
| core_Nat_map_add_toArray_roc' | yes (4) |
| core_Nat_map_add_toList_rio' | yes (4) |
| core_Nat_mul_add_mod | yes (1) |
| core_Nat_mul_div_assoc | yes (3) |
| core_Nat_mul_div_le_mul_div_assoc | yes (1) |
| core_Nat_mul_lt_mul_of_le_of_lt | yes (2) |
| core_Nat_mul_lt_mul_of_lt_of_lt | yes (2) |
| core_Nat_mul_right_inj | yes (2) |
| core_Nat_mul_sub_mod | – |
| core_Nat_or_and_distrib_left | yes (1) |
| core_Nat_powMod_induct_unfolding | yes (61) |
| core_Nat_pow_lt_pow_of_lt | yes (3) |
| core_Nat_shiftLeft_and_distrib | yes (2) |
| core_Nat_sub_mod_add_mod_cancel | yes (1) |
| core_Nat_toArray_rco_succ_succ | yes (1) |
| core_Nat_toList_ric_succ | yes (41) |
| core_Nat_toList_roc_append_toList_roc | yes (20) |
| core_Nat_toList_roc_succ_succ | yes (17) |
| core_Nat_xor_lt_two_pow | yes (20) |
| core_Nat_zero_lt_getElem!_toList_ric_iff | yes (16) |
