# Translation report: test corpus -> Universe-1 programs

Corpus: `translate/corpus.py` (30 unary, 25 binary functions, W=4).
Cell = stages/total max steps (`*` = some stage never halts; value exact at step 256), `✓` = emitted Rust compiled and its emulation test passed, `✗` = not synthesizable.

## unary functions

| function | w4_o2_add<br>`SWAP,ADD,NAND,SKZ` | w4_o2_nand<br>`LD,ST,NAND,JZ` | w4_o3_arith<br>`LD,ST,ADD,SUB,SHL,SHR,JNZ,HALT` | w4_o3_bool<br>`LD,ST,NOT,AND,OR,XOR,SKZ,HALT` | w4_o3_core<br>`LD,ST,LDI,NAND,ADD,SHL,JZ,HALT` | w4_o3_swap<br>`SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT` | w4_o4_full<br>`LD,ST,NOT,AND,OR,XOR,ADD,SUB,INC,DEC,SHL,SHR,ROL,SKZ,SKNZ,HALT` |
|---|---|---|---|---|---|---|---|
| `a_plus_5` | 1st/256* | ✗ | ✗ | ✗ | 1st/256* | 1st/256* | 1st/256* |
| `not_b` | 1st/256* | 1st/256* | ✗ | 1st/2 | 1st/2 | 1st/256* | 1st/256* |
| `a_minus_1` | 1st/256* | ✗ | ✗ | ✗ | 1st/256* | 1st/256* | 1st/256* |
| `rotl3` | ✗ | ✗ | 2st/15 | ✗ | ✗ | 1st/256* | 1st/256* |
| `times3` | 1st/256* | ✗ | 1st/4 | ✗ | 1st/4 | 1st/256* | ✗ |
| `gray` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `ungray` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `popcount` | ✗ | ✗ | ✗ | ✗ | ✗ | 2st/512* | ✗ |
| `parity` | 2st/512* | ✗ | 2st/260* | ✗ | 2st/260* | 2st/260* | 2st/264* |
| `abs_signed` | 1st/256* | ✗ | 1st/256* | ✗ | ✗ | 2st/512* | 2st/512* |
| `sign_bit` | 2st/512* | ✗ | 1st/4 | ✗ | 2st/512* | 1st/256* | 1st/256* |
| `nibble_swap` | 3st/768* | ✗ | 1st/8 | ✗ | ✗ | 1st/256* | 1st/256* |
| `sat_inc` | 1st/256* | ✗ | ✗ | ✗ | 1st/256* | 1st/4 | 1st/256* |
| `sat_dec` | 1st/256* | ✗ | 2st/264* | ✗ | 1st/256* | 1st/256* | 1st/3 |
| `is_pow2` | 2st/512* | ✗ | ✗ | ✗ | 2st/512* | 2st/512* | 3st/517* |
| `mod3` | 2st/512* | ✗ | 3st/517* | ✗ | 2st/261* | 1st/256* | 2st/260* |
| `div3` | ✗ | ✗ | ✗ | ✗ | ✗ | 2st/512* | 2st/512* |
| `square` | 2st/512* | ✗ | ✗ | ✗ | ✗ | 2st/512* | 4st/269* |
| `cube` | 2st/512* | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `bitrev` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `clz` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `ctz` | ✗ | ✗ | ✗ | ✗ | ✗ | 1st/256* | 2st/260* |
| `lowbit` | 1st/256* | ✗ | 1st/256* | ✗ | 1st/256* | 1st/256* | 1st/256* |
| `clear_lowbit` | 1st/256* | ✗ | ✗ | ✗ | 1st/7 | 1st/256* | ✗ |
| `fill_right` | 1st/256* | ✗ | 1st/256* | ✗ | ✗ | 1st/256* | 1st/256* |
| `bcd_inc` | ✗ | ✗ | ✗ | ✗ | ✗ | 3st/266* | 3st/266* |
| `sign_extend2` | 1st/256* | ✗ | 1st/256* | ✗ | 1st/256* | 1st/256* | 1st/256* |
| `lerp_half` | ✗ | ✗ | ✗ | ✗ | ✗ | 3st/267* | 3st/516* |
| `triangular` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `collatz_step` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **translated** | **18/30** | **1/30** | **11/30** | **1/30** | **13/30** | **23/30** | **20/30** |

## binary functions

| function | w4_o3_arith_bin<br>`LD,ST,ADD,SUB,SHL,SHR,JNZ,HALT` | w4_o3_bool_bin<br>`LD,ST,NOT,AND,OR,XOR,SKZ,HALT` | w4_o3_core_bin<br>`LD,ST,LDI,NAND,ADD,SHL,JZ,HALT` |
|---|---|---|---|
| `a_plus_b` | 1st/2 | ✗ | 1st/2 |
| `a_xor_b` | ✗ | 1st/2 | ✗ |
| `2a_plus_b` | 1st/3 | ✗ | 1st/3 |
| `a_plus_b_plus1` | ✗ | ✗ | 1st/5 |
| `a_xor_b_xor7` | ✗ | ✗ | ✗ |
| `a_minus_b` | 1st/2 | ✗ | 1st/4 |
| `sat_add` | ✗ | ✗ | ✗ |
| `sat_sub` | ✗ | ✗ | ✗ |
| `carry_out` | ✗ | ✗ | ✗ |
| `half_adder_sum` | 1st/256* | ✗ | 1st/256* |
| `mul` | ✗ | ✗ | ✗ |
| `mul_hi` | ✗ | ✗ | ✗ |
| `min` | ✗ | ✗ | ✗ |
| `max` | ✗ | ✗ | ✗ |
| `abs_diff` | ✗ | ✗ | ✗ |
| `avg_floor` | ✗ | ✗ | ✗ |
| `eq` | ✗ | ✗ | 1st/256* |
| `lt` | ✗ | ✗ | ✗ |
| `and_not` | ✗ | 1st/256* | ✗ |
| `mux_lsb` | ✗ | ✗ | ✗ |
| `shl_var` | ✗ | ✗ | ✗ |
| `shr_var` | ✗ | ✗ | ✗ |
| `hamming` | ✗ | ✗ | ✗ |
| `gcd` | ✗ | ✗ | ✗ |
| `mod` | ✗ | ✗ | ✗ |
| **translated** | **4/25** | **2/25** | **6/25** |

## Not translatable by any map

`gray`, `ungray`, `bitrev`, `clz`, `triangular`, `collatz_step`, `a_xor_b_xor7`, `sat_add`, `sat_sub`, `carry_out`, `mul`, `mul_hi`, `min`, `max`, `abs_diff`, `avg_floor`, `lt`, `mux_lsb`, `shl_var`, `shr_var`, `hamming`, `gcd`, `mod`

