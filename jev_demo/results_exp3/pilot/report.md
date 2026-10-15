# Jev proof demo — experiment 3 (core-library benchmark)

8 theorems; `claude-opus-5-5`, effort `medium`.

| method | proved | rate | 95% CI | notional USD | USD per proved | audit-rejected proofs |
|---|---|---|---|---|---|---|
| claude_whole | 4/8 | 0.50 | 0.22–0.78 | 0.3588 | 0.0897 | 6 |
| claude_search | 4/8 | 0.50 | 0.22–0.78 | 0.3197 | 0.0799 | 18 |
| hybrid | 4/8 | 0.50 | 0.22–0.78 | 0.3316 | 0.0829 | 9 |

Paired comparisons (same theorems): difference in success rate a − b with a 95% bootstrap CI, discordant pairs, and the exact McNemar p-value.

| a | b | a only | b only | a − b | 95% CI | McNemar p |
|---|---|---|---|---|---|---|
| hybrid | claude_search | 0 | 0 | +0.000 | +0.000–+0.000 | 1.0000 |
| claude_whole | claude_search | 1 | 1 | +0.000 | -0.375–+0.375 | 1.0000 |
| hybrid | claude_whole | 1 | 1 | +0.000 | -0.375–+0.375 | 1.0000 |

Total Claude spend (actual): $0.8222 of $3.0.

## Per theorem

| theorem | claude_whole | claude_search | hybrid |
|---|---|---|---|
| core_List_Cursor_tail_at | – | – | – |
| core_List_IsInfix_count_le | yes (1) | yes (7) | yes (1) |
| core_List_IsSuffix_getLast | – | – | – |
| core_List_IsSuffix_le_count | yes (1) | yes (3) | yes (11) |
| core_List_MergeSort_Internal_splitInTwo_fst_le_splitInTwo_snd | yes (1) | yes (2) | yes (3) |
| core_List_Perm_append_left | – | yes (4) | yes (5) |
| core_List_Perm_flatten | yes (3) | – | – |
| core_List_apply_minOn_append_le_right | – | – | – |
