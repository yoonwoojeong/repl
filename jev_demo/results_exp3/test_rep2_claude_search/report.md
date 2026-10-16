# Jev proof demo — experiment 3 (core-library benchmark)

148 theorems; `claude-opus-5-5`, effort `medium`.

| method | proved | rate | 95% CI | notional USD | USD per proved | Claude requests | requests per proved | Lean calls | audit-rejected proofs |
|---|---|---|---|---|---|---|---|---|---|
| claude_search | 94/148 | 0.64 | 0.56–0.71 | 7.7702 | 0.0827 | 798 | 8.49 | 3991 | 126 |

Total Claude spend (actual): $7.7702 of $10.6059.

## Per theorem

| theorem | claude_search |
|---|---|
| core_List_IsPrefix_le_countP | yes (3) |
| core_List_IsSuffix_sublist | yes (2) |
| core_List_Mem_brecOn | – |
| core_List_MergeSort_Internal_splitInTwo_cons_cons_zipIdx_snd | – |
| core_List_Nodup_not_mem_erase | yes (1) |
| core_List_Pairwise_iff | yes (3) |
| core_List_Pairwise_imp_mem | yes (1) |
| core_List_Perm_append_right | yes (3) |
| core_List_Sublist_brecOn | – |
| core_List_all_bne' | yes (20) |
| core_List_all_takeWhile | – |
| core_List_append_of_mem | yes (2) |
| core_List_append_sublist_iff | – |
| core_List_apply_maxOn_lt_iff | – |
| core_List_contains_congr | yes (5) |
| core_List_count_cons | yes (1) |
| core_List_count_filter | yes (6) |
| core_List_count_filterMap | yes (4) |
| core_List_count_le_length | yes (4) |
| core_List_decide_mem_cons | yes (35) |
| core_List_dropWhile_suffix | yes (1) |
| core_List_drop_drop | yes (1) |
| core_List_drop_take | yes (1) |
| core_List_eraseIdx_modify_of_gt | yes (17) |
| core_List_erase_replicate_ne | yes (1) |
| core_List_filterMapM_loop_eq | – |
| core_List_finRange_succ | yes (1) |
| core_List_flatMapM_loop_induct_unfolding | – |
| core_List_flatMapM_wfParam | yes (3) |
| core_List_foldrM_filterMap | – |
| core_List_foldrRecOn_cons | – |
| core_List_foldr_assoc | yes (1) |
| core_List_getElem?_insert_zero | yes (2) |
| core_List_getElem_append | – |
| core_List_getElem_append_right | – |
| core_List_getElem_append_right' | – |
| core_List_getElem_cons_drop | yes (33) |
| core_List_getElem_drop | – |
| core_List_getElem_eraseIdx_of_ge | – |
| core_List_getElem_insert | – |
| core_List_getElem_replace_of_ne | – |
| core_List_getElem_zipIdx | – |
| core_List_getElem_zipWith | – |
| core_List_getLast_mapIdx | – |
| core_List_getLast_tail | – |
| core_List_head?_range | yes (1) |
| core_List_head_append_right | – |
| core_List_head_dropLast | – |
| core_List_idxOf_le_length | yes (2) |
| core_List_insert_of_not_mem | yes (1) |
| core_List_instTransOrd | – |
| core_List_isPrefixOf_replicate | yes (5) |
| core_List_isSome_minOn?_of_mem | yes (1) |
| core_List_le_min_iff | – |
| core_List_left_le_minIdxOn_append | – |
| core_List_lt_iff_exists | – |
| core_List_map_id'' | yes (2) |
| core_List_map_id_fun | – |
| core_List_map_unattach | – |
| core_List_maxIdxOn_append | – |
| core_List_maxIdxOn_singleton | – |
| core_List_maxOn_cons | – |
| core_List_max_congr_simp | – |
| core_List_max_cons_cons | – |
| core_List_mem_eraseIdx_iff_getElem | – |
| core_List_mergeSort_append | – |
| core_List_mergeSort_cons | – |
| core_List_minIdxOn?_cons | yes (3) |
| core_List_minIdxOn?_nil | yes (4) |
| core_List_minOn_replicate | yes (2) |
| core_List_min_le_of_mem | – |
| core_List_modifyTailIdx_modifyTailIdx | yes (62) |
| core_List_pair_sublist_mergeSort | yes (2) |
| core_List_pairwise_append_comm | yes (1) |
| core_List_pairwise_mergeSort | – |
| core_List_perm_iff_count | yes (5) |
| core_List_perm_iff_toArray_perm | yes (1) |
| core_List_pmap_reverse | – |
| core_List_range'_concat | yes (1) |
| core_List_range'_succ_left | yes (1) |
| core_List_range_succ | yes (1) |
| core_List_removeAll_cons | yes (3) |
| core_List_replace_cons_self | yes (2) |
| core_List_replace_take | yes (2) |
| core_List_reverse_attachWith | – |
| core_List_set_getElem_self | yes (2) |
| core_List_set_getElem_succ_eraseIdx_succ | – |
| core_List_sum_singleton | – |
| core_List_tail?_nil | – |
| core_List_tail_drop | yes (20) |
| core_List_tail_pmap | – |
| core_List_take_append_drop | yes (1) |
| core_List_take_append_getLast | yes (37) |
| core_List_take_set | yes (3) |
| core_List_unattach_append | yes (4) |
| core_List_unattach_filter | yes (58) |
| core_List_unattach_nil | – |
| core_List_unzip_zip | yes (3) |
| core_List_zipIdx_succ | – |
| core_List_zipWith_comm_of_comm | yes (2) |
| core_Nat_Coprime_gcd_left | yes (2) |
| core_Nat_Coprime_gcd_mul | – |
| core_Nat_Internal_Linear_ExprCnstr_toPoly_norm_eq | yes (1) |
| core_Nat_Internal_Linear_Expr_toPoly_go_induct | yes (1) |
| core_Nat_Internal_Linear_Poly_of_isNonZero | yes (35) |
| core_Nat_add_div_of_dvd_add_add_one | – |
| core_Nat_add_mul_div_right | yes (2) |
| core_Nat_all_congr | – |
| core_Nat_div_add_mod' | yes (1) |
| core_Nat_div_dvd_of_dvd | yes (1) |
| core_Nat_div_le_iff_le_mul_add_pred | yes (2) |
| core_Nat_div_le_self | yes (19) |
| core_Nat_div_lt_of_lt | yes (1) |
| core_Nat_dvd_gcd_mul_gcd_iff_dvd_mul | yes (1) |
| core_Nat_dvd_gcd_mul_iff_dvd_mul | yes (1) |
| core_Nat_dvd_lcm_left | yes (1) |
| core_Nat_fold_add | – |
| core_Nat_gcd_add_right_right_of_dvd | yes (19) |
| core_Nat_gcd_add_self_right | yes (1) |
| core_Nat_gcd_le_right | yes (1) |
| core_Nat_gcd_mul_left_add_left | yes (3) |
| core_Nat_ge_two_pow_of_testBit | yes (1) |
| core_Nat_getD_toArray_rcc | yes (2) |
| core_Nat_getD_toList_ric | yes (19) |
| core_Nat_getElem?_toArray_roc | yes (19) |
| core_Nat_getElem_toArray_rio | yes (2) |
| core_Nat_isSome_getElem?_toArray_ric_eq | yes (1) |
| core_Nat_lcm_zero_left | yes (1) |
| core_Nat_le_of_dvd | yes (4) |
| core_Nat_le_pow | yes (2) |
| core_Nat_lt_mul_div_succ | yes (2) |
| core_Nat_lt_pow_self | yes (17) |
| core_Nat_map_add_toArray_rco | yes (18) |
| core_Nat_map_add_toArray_rio | yes (17) |
| core_Nat_mul_add_mul_div_of_dvd | yes (17) |
| core_Nat_one_le_div_iff | yes (2) |
| core_Nat_or_exists_add_one | yes (2) |
| core_Nat_pow_lt_pow_right | yes (2) |
| core_Nat_pow_right_comm | yes (1) |
| core_Nat_pow_sub_mul_pow | yes (2) |
| core_Nat_pred_lt_pred | yes (2) |
| core_Nat_repr_injective | – |
| core_Nat_self_add_pred | yes (1) |
| core_Nat_shiftLeft_shiftRight | yes (1) |
| core_Nat_testBit_two_pow_mul_add | – |
| core_Nat_toArray_roc_succ_succ | yes (1) |
| core_Nat_toList_rco_succ_succ | – |
| core_Nat_zero_lt_getElem!_toList_rio_iff | yes (4) |
