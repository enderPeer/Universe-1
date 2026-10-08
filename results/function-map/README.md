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
| [w4_codex_shr_mul](w4_codex_shr_mul.json) | W=4 unary | 3,038,671 | 352 | 345 | 419 |
| [w4_i8_o3](w4_i8_o3.json) | W=4 unary | 1,157 | 352 | 109 | 181 |
| [w4_i8_o4](w4_i8_o4.json) | W=4 unary | 4,926 | 352 | 163 | 235 |
| [w4_o2_adc](w4_o2_adc.json) | W=4 unary | 7,873,949 | 352 | 275 | 350 |
| [w4_o2_add](w4_o2_add.json) | W=4 unary | 1,829,051 | 352 | 324 | 396 |
| [w4_o2_add_bin](w4_o2_add_bin.json) | W=4 binary | 24,684,247 | 740 | 646 | 824 |
| [w4_o2_add_jc](w4_o2_add_jc.json) | W=4 unary | 8,533,818 | 352 | 337 | 410 |
| [w4_o2_add_jz](w4_o2_add_jz.json) | W=4 unary | 5,181,022 | 352 | 330 | 403 |
| [w4_o2_add_sknz](w4_o2_add_sknz.json) | W=4 unary | 1,043,408 | 352 | 316 | 388 |
| [w4_o2_nand](w4_o2_nand.json) | W=4 unary | 16 | 352 | 4 | 22 |
| [w4_o2_nand_bin](w4_o2_nand_bin.json) | W=4 binary | 17,827 | 740 | 16 | 68 |
| [w4_o2_nocond](w4_o2_nocond.json) | W=4 unary | 1,055,395 | 352 | 337 | 411 |
| [w4_o2_rol](w4_o2_rol.json) | W=4 unary | 1,259,140 | 352 | 324 | 399 |
| [w4_o2_shr](w4_o2_shr.json) | W=4 unary | 331,839 | 352 | 55 | 90 |
| [w4_o2_sub](w4_o2_sub.json) | W=4 unary | 1,123,714 | 352 | 315 | 387 |
| [w4_o2_xor](w4_o2_xor.json) | W=4 unary | 547,533 | 352 | 17 | 49 |
| [w4_o2_xor_shr](w4_o2_xor_shr.json) | W=4 unary | 500,264 | 352 | 60 | 96 |
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
| [w4_prop_combined](w4_prop_combined.json) | W=4 unary | 228,409 | 352 | 313 | 385 |
| [w8_o4](w8_o4.json) | W=8 unary | 7,119 | 1805 | 485 | 552 |

## Distinct recognized functions across ISAs

These counts deduplicate identical truth tables within each width and arity; aliases and repeats across ISAs count once.

| Width | Mode | Distinct recognized functions |
|---|---|---:|
| 1 | unary | 4 |
| 1 | binary | 4 |
| 2 | unary | 3 |
| 2 | binary | 4 |
| 4 | unary | 350 |
| 4 | binary | 685 |
| 8 | unary | 485 |

## Affine arithmetic at W=4

There are 256 distinct functions `(a*x+b) mod 16` for a,b in 0..15.

| Unary run | Affine functions found / 256 |
|---|---:|
| w4_codex_shr_mul | 256 |
| w4_i8_o3 | 71 |
| w4_i8_o4 | 104 |
| w4_o2_adc | 190 |
| w4_o2_add | 256 |
| w4_o2_add_jc | 256 |
| w4_o2_add_jz | 256 |
| w4_o2_add_sknz | 256 |
| w4_o2_nand | 4 |
| w4_o2_nocond | 256 |
| w4_o2_rol | 256 |
| w4_o2_shr | 16 |
| w4_o2_sub | 256 |
| w4_o2_xor | 16 |
| w4_o2_xor_shr | 16 |
| w4_o3_arith | 16 |
| w4_o3_bool | 4 |
| w4_o3_core | 229 |
| w4_o3_swap | 256 |
| w4_o4_full | 134 |
| w4_prop_combined | 256 |

## W=4 unary highlights

| Function | Matching completed runs and verified witness IDs |
|---|---|
| identity | w4_codex_shr_mul `0x00000000`; w4_i8_o3 `0x00000000`; w4_i8_o4 `0x00000000`; w4_o2_adc `0x00000000`; w4_o2_add `0x00000000`; w4_o2_add_jc `0x00000000`; w4_o2_add_jz `0x00000000`; w4_o2_add_sknz `0x00000000`; w4_o2_nand `0x00000000`; w4_o2_nocond `0x00000000`; w4_o2_rol `0x00000000`; w4_o2_shr `0x00000000`; w4_o2_sub `0x00000000`; w4_o2_xor `0x00000000`; w4_o2_xor_shr `0x00000000`; w4_o3_arith `0x00000000`; w4_o3_bool `0x00000000`; w4_o3_core `0x00000000`; w4_o3_swap `0x00000000`; w4_o4_full `0x00000000`; w4_prop_combined `0x00000000` |
| negation | w4_codex_shr_mul `0x000033c1`; w4_i8_o3 `0x21216001`; w4_i8_o4 `0x00118161`; w4_o2_adc `0x00015181`; w4_o2_add `0x000055c1`; w4_o2_add_jc `0x00012868`; w4_o2_add_jz `0x00001d15`; w4_o2_add_sknz `0x00012868`; w4_o2_nocond `0x00012868`; w4_o2_rol `0x00012868`; w4_o2_shr `0x000055c1`; w4_o2_sub `0x00000126`; w4_o2_xor `0x000055c1`; w4_o2_xor_shr `0x000155a2`; w4_o3_arith `0x00000377`; w4_o3_core `0x00003996`; w4_o3_swap `0x00000ac4`; w4_o4_full `0x00000e29`; w4_prop_combined `0x00003361` |
| bitwise_not | w4_codex_shr_mul `0x00000051`; w4_i8_o3 `0x00008040`; w4_i8_o4 `0x0000b130`; w4_o2_adc `0x00000091`; w4_o2_add `0x00000091`; w4_o2_add_jc `0x00000091`; w4_o2_add_jz `0x00000091`; w4_o2_add_sknz `0x00000091`; w4_o2_nand `0x0010826e`; w4_o2_nocond `0x00000091`; w4_o2_rol `0x00000091`; w4_o2_sub `0x00000091`; w4_o3_bool `0x000000e4`; w4_o3_core `0x000000e6`; w4_o3_swap `0x00000051`; w4_o4_full `0x000000e2`; w4_prop_combined `0x00000051` |
| increment | w4_codex_shr_mul `0x00014613`; w4_i8_o3 `0x01420121`; w4_i8_o4 `0x71e22f11`; w4_o2_adc `0x00016b28`; w4_o2_add `0x00001a15`; w4_o2_add_jc `0x00001a15`; w4_o2_add_jz `0x00001a15`; w4_o2_add_sknz `0x00001a15`; w4_o2_nocond `0x00001a15`; w4_o2_rol `0x00001a15`; w4_o2_sub `0x00016828`; w4_o3_core `0x0000e953`; w4_o3_swap `0x000000ec`; w4_o4_full `0x000000d8`; w4_prop_combined `0x000083f1` |
| decrement | w4_codex_shr_mul `0x0000e341`; w4_i8_o3 `0x01a10121`; w4_i8_o4 `0x3081e1d2`; w4_o2_adc `0x00005a13`; w4_o2_add `0x000016a2`; w4_o2_add_jc `0x000016a2`; w4_o2_add_jz `0x000016a2`; w4_o2_add_sknz `0x000016a2`; w4_o2_nocond `0x000016a2`; w4_o2_rol `0x000016a2`; w4_o2_sub `0x00001a15`; w4_o3_core `0x000c9643`; w4_o3_swap `0x00001317`; w4_o4_full `0x000000d9`; w4_prop_combined `0x00001f13` |
| square | w4_codex_shr_mul `0x000000ea`; w4_o2_add_jz `0x5812753f`; w4_o2_sub `0x186437c2` |
| cube | w4_codex_shr_mul `0x000eba31`; w4_o2_shr `0x8151c426`; w4_o2_xor `0x14a1ac52` |
| integer_sqrt | Not found in the mapped completed runs |
| popcount | w4_o2_adc `0x00410c61` |
| parity | w4_codex_shr_mul `0x00813ac1`; w4_o2_adc `0x14268c62`; w4_o2_add_jc `0x4f959418`; w4_o2_xor_shr `0x0962a2c1` |
| bit_reverse | w4_codex_shr_mul `0x00721781`; w4_o2_xor_shr `0x009419c1` |
| gray_encode | w4_codex_shr_mul `0x000e7831`; w4_i8_o4 `0xb261a011`; w4_o2_xor_shr `0x0012abc3` |
| signed_abs | w4_o2_adc `0x05827873`; w4_o2_add `0x9a3c1171`; w4_o2_add_jc `0x001d2541`; w4_o2_add_jz `0x191e9185`; w4_o2_shr `0x01c52841`; w4_o2_sub `0x91c91581`; w4_o3_arith `0x001d7a53` |
| is_zero | w4_codex_shr_mul `0x000a415c`; w4_i8_o3 `0x60a0a160`; w4_i8_o4 `0x21d0e1a0`; w4_o2_adc `0x00012793`; w4_o2_add `0x0005a13c`; w4_o2_add_jc `0x000e5812`; w4_o2_add_jz `0x0001d59f`; w4_o2_add_sknz `0x0012955c`; w4_o2_nocond `0x85c52515`; w4_o2_rol `0x186a28cc`; w4_o2_sub `0x000189c5`; w4_o3_core `0x00015d66`; w4_o3_swap `0x00013a1a`; w4_o4_full `0x00250e29`; w4_prop_combined `0x00013f46` |
| shift_left_1 | w4_codex_shr_mul `0x00000031`; w4_i8_o3 `0x00000121`; w4_i8_o4 `0x0000b170`; w4_o2_adc `0x00000444`; w4_o2_add `0x00000051`; w4_o2_add_jc `0x00000051`; w4_o2_add_jz `0x00000051`; w4_o2_add_sknz `0x00000051`; w4_o2_nocond `0x00000051`; w4_o2_rol `0x00000051`; w4_o2_shr `0x00000051`; w4_o2_sub `0x00000051`; w4_o2_xor `0x00000051`; w4_o2_xor_shr `0x00000051`; w4_o3_arith `0x000000d4`; w4_o3_core `0x000000e8`; w4_o3_swap `0x00000071`; w4_o4_full `0x000000f6`; w4_prop_combined `0x00000031` |
| shift_right_1 | w4_codex_shr_mul `0x000000e8`; w4_i8_o3 `0x000080c0`; w4_i8_o4 `0x0000b1a0`; w4_o2_adc `0x00000044`; w4_o2_add_jc `0x162823f6`; w4_o2_add_jz `0x5e021912`; w4_o2_nocond `0x001541c5`; w4_o2_rol `0x1451ccc5`; w4_o2_shr `0x000014c8`; w4_o2_xor_shr `0x00012aca`; w4_o3_arith `0x000000da`; w4_o3_swap `0x0060a888`; w4_o4_full `0x000000fb` |
| rotate_left_1 | w4_codex_shr_mul `0x00388813`; w4_i8_o3 `0x000080e0`; w4_o2_adc `0x0000164c`; w4_o2_add_jc `0x095e8541`; w4_o2_add_jz `0x51f81518`; w4_o2_nocond `0x005ccc15`; w4_o2_rol `0x0019a28c`; w4_o2_shr `0x00588815`; w4_o2_xor_shr `0x005ccc15`; w4_o3_arith `0x0e55aaa3`; w4_o3_swap `0x000000a8`; w4_o4_full `0x000000ec` |

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

Run `python fast/map_functions.py` (exp03) or `python fast/map_functions.py --experiment exp05` after extracting witness archives into `results/shards/`. `--only RUN` maps one completed sweep. The script snapshots completed result files at startup; rerun as new sweeps finish.

The catalog includes constants, affine arithmetic, bit masks, shifts, rotations, Gray transforms, population counts, comparisons, modular arithmetic, selected number-theoretic functions, and all 16 bitwise Boolean functions. Affine coefficients are exhaustive at W<=4 and explicitly sampled at W=8.

Per-run JSON includes formulas, aliases, full truth tables, decoded instructions, witness IDs, source shards, and termination statistics. All input values are enumerated in increasing order; binary tables use x outer / y inner. Hash matches are independently verified by complete execution.
