# Translation report: test corpus -> Universe-1 programs

Corpus: `translate/corpus.py` (30 unary, 25 binary functions, W=4).
Cell = stages/sum of per-stage worst-case steps (`*` = not every input halts within the budget in every stage; value exact at step 256), `✓` = emitted Rust compiled and its emulation test passed, `✗` = not found in the configured search. This is a bounded basis search, not a proof of impossibility.

## Run settings and timings

| Map | Node | Actual depth | Extra basis | Wall seconds (including tests) |
|---|---|---:|---:|---:|
| w4_o2_add | knecht24 | 4 | 256 | 137.43 |
| w4_o2_add_bin | falke64 | binary forms <=3 | 256 | 1002.21 |
| w4_o2_nand | specht32 | 4 | 256 | 0.43 |
| w4_o2_nand_bin | falke64 | binary forms <=3 | 256 | 1.58 |
| w4_o3_arith | specht32 | 4 | 256 | 22.71 |
| w4_o3_arith_bin | falke64 | 1 | 256 | 3.31 |
| w4_o3_bool | specht32 | 4 | 256 | 0.40 |
| w4_o3_bool_bin | falke64 | 1 | 256 | 0.62 |
| w4_o3_core | knecht24 | 4 | 256 | 22.43 |
| w4_o3_core_bin | falke64 | 1 | 256 | 7.02 |
| w4_o3_swap | adler40 | 4 | 256 | 104.03 |
| w4_o3_swap_bin | falke64 | binary forms <=3 | 256 | 188.72 |
| w4_o4_full | adler40 | 4 | 256 | 46.98 |
| w4_o4_full_bin | falke64 | binary forms <=3 | 256 | 28.95 |

## unary functions

| function | w4_o2_add<br>`SWAP,ADD,NAND,SKZ` | w4_o2_nand<br>`LD,ST,NAND,JZ` | w4_o3_arith<br>`LD,ST,ADD,SUB,SHL,SHR,JNZ,HALT` | w4_o3_bool<br>`LD,ST,NOT,AND,OR,XOR,SKZ,HALT` | w4_o3_core<br>`LD,ST,LDI,NAND,ADD,SHL,JZ,HALT` | w4_o3_swap<br>`SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT` | w4_o4_full<br>`LD,ST,NOT,AND,OR,XOR,ADD,SUB,INC,DEC,SHL,SHR,ROL,SKZ,SKNZ,HALT` |
|---|---|---|---|---|---|---|---|
| `a_plus_5` | 1st/256* ✓ | ✗ | ✗ | ✗ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `not_b` | 1st/256* ✓ | 1st/256* ✓ | ✗ | 1st/2 ✓ | 1st/2 ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `a_minus_1` | 1st/256* ✓ | ✗ | ✗ | ✗ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `rotl3` | ✗ | ✗ | 2st/15 ✓ | ✗ | ✗ | 1st/256* ✓ | 1st/256* ✓ |
| `times3` | 1st/256* ✓ | ✗ | 1st/4 ✓ | ✗ | 1st/4 ✓ | 1st/256* ✓ | ✗ |
| `gray` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `ungray` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `popcount` | ✗ | ✗ | 4st/277* ✓ | ✗ | ✗ | 2st/512* ✓ | ✗ |
| `parity` | 2st/512* ✓ | ✗ | 2st/512* ✓ | ✗ | 2st/260* ✓ | 2st/512* ✓ | 2st/263* ✓ |
| `abs_signed` | 1st/256* ✓ | ✗ | 1st/256* ✓ | ✗ | ✗ | 2st/512* ✓ | 2st/512* ✓ |
| `sign_bit` | 2st/512* ✓ | ✗ | 1st/4 ✓ | ✗ | 2st/512* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `nibble_swap` | 3st/768* ✓ | ✗ | 1st/8 ✓ | ✗ | ✗ | 1st/256* ✓ | 1st/256* ✓ |
| `sat_inc` | 1st/256* ✓ | ✗ | ✗ | ✗ | 1st/256* ✓ | 1st/4 ✓ | 1st/256* ✓ |
| `sat_dec` | 1st/256* ✓ | ✗ | 2st/264* ✓ | ✗ | 1st/256* ✓ | 1st/256* ✓ | 1st/3 ✓ |
| `is_pow2` | 2st/512* ✓ | ✗ | 3st/20 ✓ | ✗ | 2st/512* ✓ | 2st/512* ✓ | 3st/274* ✓ |
| `mod3` | 2st/512* ✓ | ✗ | 2st/264* ✓ | ✗ | 2st/262* ✓ | 1st/256* ✓ | 2st/261* ✓ |
| `div3` | ✗ | ✗ | 3st/19 ✓ | ✗ | ✗ | 2st/512* ✓ | 2st/512* ✓ |
| `square` | 2st/512* ✓ | ✗ | 4st/26 ✓ | ✗ | 3st/19 ✓ | 2st/512* ✓ | 4st/270* ✓ |
| `cube` | 2st/512* ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `bitrev` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `clz` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `ctz` | 4st/1024* ✓ | ✗ | ✗ | ✗ | ✗ | 1st/256* ✓ | 2st/512* ✓ |
| `lowbit` | 1st/256* ✓ | ✗ | 1st/256* ✓ | ✗ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `clear_lowbit` | 1st/256* ✓ | ✗ | ✗ | ✗ | 1st/7 ✓ | 1st/256* ✓ | ✗ |
| `fill_right` | 1st/256* ✓ | ✗ | 1st/256* ✓ | ✗ | ✗ | 1st/256* ✓ | 1st/256* ✓ |
| `bcd_inc` | ✗ | ✗ | ✗ | ✗ | ✗ | 3st/266* ✓ | 3st/266* ✓ |
| `sign_extend2` | 1st/256* ✓ | ✗ | 1st/256* ✓ | ✗ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `lerp_half` | ✗ | ✗ | ✗ | ✗ | ✗ | 3st/267* ✓ | 3st/16 ✓ |
| `triangular` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `collatz_step` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **translated** | **19/30** | **1/30** | **15/30** | **1/30** | **14/30** | **23/30** | **20/30** |

## binary functions

| function | w4_o2_add_bin<br>`SWAP,ADD,NAND,SKZ` | w4_o2_nand_bin<br>`LD,ST,NAND,JZ` | w4_o3_arith_bin<br>`LD,ST,ADD,SUB,SHL,SHR,JNZ,HALT` | w4_o3_bool_bin<br>`LD,ST,NOT,AND,OR,XOR,SKZ,HALT` | w4_o3_core_bin<br>`LD,ST,LDI,NAND,ADD,SHL,JZ,HALT` | w4_o3_swap_bin<br>`SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT` | w4_o4_full_bin<br>`LD,ST,NOT,AND,OR,XOR,ADD,SUB,INC,DEC,SHL,SHR,ROL,SKZ,SKNZ,HALT` |
|---|---|---|---|---|---|---|---|
| `a_plus_b` | 1st/256* ✓ | ✗ | 1st/2 ✓ | ✗ | 1st/2 ✓ | 1st/2 ✓ | ✗ |
| `a_xor_b` | 1st/256* ✓ | 1st/256* ✓ | ✗ | 1st/2 ✓ | ✗ | ✗ | ✗ |
| `2a_plus_b` | 1st/256* ✓ | ✗ | 1st/3 ✓ | ✗ | 1st/3 ✓ | 1st/3 ✓ | ✗ |
| `a_plus_b_plus1` | 1st/256* ✓ | ✗ | ✗ | ✗ | 1st/5 ✓ | 1st/3 ✓ | ✗ |
| `a_xor_b_xor7` | 2st/512* ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `a_minus_b` | 1st/256* ✓ | ✗ | 1st/2 ✓ | ✗ | 1st/4 ✓ | 1st/256* ✓ | ✗ |
| `sat_add` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `sat_sub` | 1st/256* ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `carry_out` | 2st/512* ✓ | ✗ | ✗ | ✗ | ✗ | 3st/514* ✓ | ✗ |
| `half_adder_sum` | 1st/256* ✓ | ✗ | 1st/256* ✓ | ✗ | 1st/256* ✓ | 1st/256* ✓ | ✗ |
| `mul` | 2st/512* ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `mul_hi` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `min` | ✗ | ✗ | ✗ | ✗ | ✗ | 2st/512* ✓ | ✗ |
| `max` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `abs_diff` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `avg_floor` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `eq` | 1st/256* ✓ | ✗ | ✗ | ✗ | 1st/256* ✓ | 1st/256* ✓ | ✗ |
| `lt` | 3st/768* ✓ | ✗ | ✗ | ✗ | ✗ | 2st/258* ✓ | ✗ |
| `and_not` | 1st/256* ✓ | 1st/256* ✓ | ✗ | 1st/256* ✓ | ✗ | 1st/256* ✓ | ✗ |
| `mux_lsb` | 1st/256* ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `shl_var` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `shr_var` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `hamming` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `gcd` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `mod` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **translated** | **14/25** | **2/25** | **4/25** | **2/25** | **6/25** | **10/25** | **0/25** |

## Not translated within this search

`gray`, `ungray`, `bitrev`, `clz`, `triangular`, `collatz_step`, `sat_add`, `mul_hi`, `max`, `abs_diff`, `avg_floor`, `shl_var`, `shr_var`, `hamming`, `gcd`, `mod`

Binary maps marked 'binary forms <=3' use the matching unary map and the composition forms introduced in 87185a8; other binary rows are direct lookup. Unary depth and any memory fallback are listed above; all searches use bounded bases. Source revision and mode are stored per row in report_merged.json.

[Cluster timings, validation and next-ISA proposal](CLUSTER_RUN.md) | [All emitted sources and test logs](emitted_sources.zip)
