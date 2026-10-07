# Named mathematical functions found in Universe-1

Exact finite-domain recognition against a bounded, explicit catalog. All matched witnesses were replayed on every input using the Python reference simulator.

For a broader vocabulary including composed expressions, see the [Rust mapper usability matrix](../maps/usability.md) and [mapper documentation](../../docs/03_function_map.md). The catalogs differ, so their named-function counts are not directly comparable. This report retains every matching alias and explicitly states signedness, modular arithmetic, and zero-divisor conventions.

Arithmetic wraps modulo N=2^W unless the formula says otherwise. Signed values use two's complement. Comparisons explicitly distinguish 0/1 from 0/all-ones outputs.

A match describes the accumulator at HALT or step 256; it does not imply termination. Witness IDs are minimum numeric IDs across the source shards, not shortest or fastest programs.

Unmatched functions are unclassified by this catalog, not established as novel. A missing label means it was not found in that completed run, not that it is impossible with a different ISA, geometry, or budget.

| Run | Mode | Discovered functions | Catalog tables | Matched tables | Matched names (aliases included) |
|---|---|---:|---:|---:|---:|
| [w1_nand_jz](w1_nand_jz.json) | W=1 unary | 4 | 4 | 4 | 48 |
| [w1_nand_jz_bin](w1_nand_jz_bin.json) | W=1 binary | 4 | 16 | 4 | 67 |
| [w1_nand_skz](w1_nand_skz.json) | W=1 unary | 4 | 4 | 4 | 48 |
| [w1_nand_skz_bin](w1_nand_skz_bin.json) | W=1 binary | 4 | 16 | 4 | 67 |
| [w2_o1](w2_o1.json) | W=2 unary | 12 | 39 | 3 | 19 |
| [w2_o1_bin](w2_o1_bin.json) | W=2 binary | 2,131 | 125 | 3 | 13 |
| [w2_o1_swap](w2_o1_swap.json) | W=2 unary | 2 | 39 | 2 | 16 |
| [w2_o1_swap_bin](w2_o1_swap_bin.json) | W=2 binary | 8 | 125 | 2 | 20 |
| [w4_o2_add](w4_o2_add.json) | W=4 unary | 1,829,051 | 352 | 324 | 396 |
| [w4_o2_add_bin](w4_o2_add_bin.json) | W=4 binary | 24,684,247 | 740 | 646 | 824 |
| [w4_o2_nand](w4_o2_nand.json) | W=4 unary | 16 | 352 | 4 | 22 |
| [w4_o2_nand_bin](w4_o2_nand_bin.json) | W=4 binary | 17,827 | 740 | 16 | 68 |
| [w4_o3_arith](w4_o3_arith.json) | W=4 unary | 24,420 | 352 | 49 | 84 |
| [w4_o3_arith_bin](w4_o3_arith_bin.json) | W=4 binary | 339,877 | 740 | 97 | 173 |
| [w4_o3_bool](w4_o3_bool.json) | W=4 unary | 16 | 352 | 4 | 22 |
| [w4_o3_bool_bin](w4_o3_bool_bin.json) | W=4 binary | 11,946 | 740 | 18 | 72 |
| [w4_o3_core](w4_o3_core.json) | W=4 unary | 62,880 | 352 | 280 | 351 |
| [w4_o3_core_bin](w4_o3_core_bin.json) | W=4 binary | 1,020,901 | 740 | 568 | 739 |
| [w4_o3_swap](w4_o3_swap.json) | W=4 unary | 1,463,824 | 352 | 335 | 410 |
| [w4_o3_swap_bin](w4_o3_swap_bin.json) | W=4 binary | 7,690,892 | 740 | 638 | 820 |
| [w4_o4_full](w4_o4_full.json) | W=4 unary | 977,928 | 352 | 206 | 273 |
| [w4_o4_full_bin](w4_o4_full_bin.json) | W=4 binary | 977,928 | 740 | 206 | 315 |
| [w8_o4](w8_o4.json) | W=8 unary | 7,119 | 1805 | 485 | 552 |

## Distinct recognized functions across ISAs

These counts deduplicate identical truth tables within each width and arity; aliases and repeats across ISAs count once.

| Width | Mode | Distinct recognized functions |
|---|---|---:|
| 1 | unary | 4 |
| 1 | binary | 4 |
| 2 | unary | 3 |
| 2 | binary | 4 |
| 4 | unary | 341 |
| 4 | binary | 685 |
| 8 | unary | 485 |

## Affine arithmetic at W=4

There are 256 distinct functions `(a*x+b) mod 16` for a,b in 0..15.

| Unary run | Affine functions found / 256 |
|---|---:|
| w4_o2_add | 256 |
| w4_o2_nand | 4 |
| w4_o3_arith | 16 |
| w4_o3_bool | 4 |
| w4_o3_core | 229 |
| w4_o3_swap | 256 |
| w4_o4_full | 134 |

## W=4 unary highlights

| Function | Matching completed runs and verified witness IDs |
|---|---|
| identity | w4_o2_add `0x00000000`; w4_o2_nand `0x00000000`; w4_o3_arith `0x00000000`; w4_o3_bool `0x00000000`; w4_o3_core `0x00000000`; w4_o3_swap `0x00000000`; w4_o4_full `0x00000000` |
| negation | w4_o2_add `0x000055c1`; w4_o3_arith `0x00000377`; w4_o3_core `0x00003996`; w4_o3_swap `0x00000ac4`; w4_o4_full `0x00000e29` |
| bitwise_not | w4_o2_add `0x00000091`; w4_o2_nand `0x0010826e`; w4_o3_bool `0x000000e4`; w4_o3_core `0x000000e6`; w4_o3_swap `0x00000051`; w4_o4_full `0x000000e2` |
| increment | w4_o2_add `0x00001a15`; w4_o3_core `0x0000e953`; w4_o3_swap `0x000000ec`; w4_o4_full `0x000000d8` |
| decrement | w4_o2_add `0x000016a2`; w4_o3_core `0x000c9643`; w4_o3_swap `0x00001317`; w4_o4_full `0x000000d9` |
| square | Not found in the mapped completed runs |
| cube | Not found in the mapped completed runs |
| integer_sqrt | Not found in the mapped completed runs |
| popcount | Not found in the mapped completed runs |
| parity | Not found in the mapped completed runs |
| bit_reverse | Not found in the mapped completed runs |
| gray_encode | Not found in the mapped completed runs |
| signed_abs | w4_o2_add `0x9a3c1171`; w4_o3_arith `0x001d7a53` |
| is_zero | w4_o2_add `0x0005a13c`; w4_o3_core `0x00015d66`; w4_o3_swap `0x00013a1a`; w4_o4_full `0x00250e29` |
| shift_left_1 | w4_o2_add `0x00000051`; w4_o3_arith `0x000000d4`; w4_o3_core `0x000000e8`; w4_o3_swap `0x00000071`; w4_o4_full `0x000000f6` |
| shift_right_1 | w4_o3_arith `0x000000da`; w4_o3_swap `0x0060a888`; w4_o4_full `0x000000fb` |
| rotate_left_1 | w4_o3_arith `0x0e55aaa3`; w4_o3_swap `0x000000a8`; w4_o4_full `0x000000ec` |

## W=4 binary highlights

| Function | Matching completed runs and verified witness IDs |
|---|---|
| add | w4_o2_add_bin `0x00000162`; w4_o3_arith_bin `0x000000e5`; w4_o3_core_bin `0x000000e9`; w4_o3_swap_bin `0x000000e7` |
| subtract | w4_o2_add_bin `0x00001415`; w4_o3_arith_bin `0x000000e7`; w4_o3_core_bin `0x0000e696`; w4_o3_swap_bin `0x00001617` |
| multiply | Not found in the mapped completed runs |
| unsigned_divide_zero_returns_zero | Not found in the mapped completed runs |
| unsigned_remainder_zero_returns_zero | Not found in the mapped completed runs |
| unsigned_min | Not found in the mapped completed runs |
| unsigned_max | Not found in the mapped completed runs |
| gcd | Not found in the mapped completed runs |
| lcm_mod_N | Not found in the mapped completed runs |
| and | w4_o2_add_bin `0x00000089`; w4_o2_nand_bin `0x00000059`; w4_o3_bool_bin `0x00000007`; w4_o3_core_bin `0x00000037`; w4_o3_swap_bin `0x00000045` |
| or | w4_o2_add_bin `0x00009231`; w4_o2_nand_bin `0x00000a96`; w4_o3_bool_bin `0x00000009`; w4_o3_swap_bin `0x000e5414` |
| xor | w4_o2_add_bin `0x00002b93`; w4_o2_nand_bin `0x0a978ab6`; w4_o3_bool_bin `0x000000eb` |
| nand | w4_o2_add_bin `0x00000019`; w4_o2_nand_bin `0x00006a59`; w4_o3_bool_bin `0x00000e47`; w4_o3_core_bin `0x000000e7`; w4_o3_swap_bin `0x00000015` |
| xnor | w4_o2_add_bin `0x000a58a2`; w4_o2_nand_bin `0xab978ab6`; w4_o3_bool_bin `0x00000e4b` |
| equal_unsigned_bool | w4_o2_add_bin `0x5a1c8581`; w4_o3_core_bin `0x004d3696`; w4_o3_swap_bin `0x3a121474` |
| less_than_unsigned_bool | Not found in the mapped completed runs |
| less_than_unsigned_mask | Not found in the mapped completed runs |
| carry | Not found in the mapped completed runs |
| saturating_add | Not found in the mapped completed runs |
| absolute_difference | Not found in the mapped completed runs |

## Reproduce / extend

Run `python fast/map_functions.py` after extracting witness archives into `results/shards/`. `--only RUN` maps one completed sweep. The script snapshots completed result files at startup; rerun as new sweeps finish.

The catalog includes constants, affine arithmetic, bit masks, shifts, rotations, Gray transforms, population counts, comparisons, modular arithmetic, selected number-theoretic functions, and all 16 bitwise Boolean functions. Affine coefficients are exhaustive at W<=4 and explicitly sampled at W=8.

Per-run JSON includes formulas, aliases, full truth tables, decoded instructions, witness IDs, source shards, and termination statistics. All input values are enumerated in increasing order; binary tables use x outer / y inner. Hash matches are independently verified by complete execution.
