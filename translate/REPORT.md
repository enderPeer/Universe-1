# Translation report: test corpus -> Universe-1 programs

Corpus: `translate/corpus.py` (30 unary, 25 binary functions, W=4). Search depth 3, basis extra 64.
Cell = stages/total max steps (`*` = some stage never halts; value exact at step 256), `✓` = emitted Rust compiled and its emulation test passed, `✗` = not synthesizable.

## unary functions

| function | w4_o2_add_jc<br>`SWAP,ADD,NAND,JC` | w4_o2_adc<br>`SWAP,ADC,NAND,SKZ` | w4_o2_add_jz<br>`SWAP,ADD,NAND,JZ` | w4_codex_shr_mul<br>`SWAP,ADD,NAND,XOR,SHR,MUL,SKZ,HALT` | w4_o2_xor_shr<br>`SWAP,ADD,XOR,SHR` | w4_o2_shr<br>`SWAP,ADD,SHR,SKZ` | w4_o2_rol<br>`SWAP,ADD,NAND,ROL` | w4_o2_nocond<br>`SWAP,ADD,NAND,SHR` | w4_prop_combined<br>`SWAP,ADD,NAND,SKZ,HALT,LD,ST,LDI` |
|---|---|---|---|---|---|---|---|---|---|
| `a_plus_5` | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | ✗ | ✗ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `not_b` | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | ✗ | ✗ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `a_minus_1` | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/4 ✓ | ✗ | ✗ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `rotl3` | 2st/512* ✓ | 1st/256* ✓ | ✗ | 2st/512* ✓ | 1st/256* ✓ | 2st/512* ✓ | 1st/256* ✓ | 2st/512* ✓ | ✗ |
| `times3` | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `gray` | ✗ | ✗ | ✗ | 1st/5 ✓ | 1st/256* ✓ | ✗ | ✗ | ✗ | ✗ |
| `ungray` | ✗ | ✗ | ✗ | 1st/256* ✓ | 1st/256* ✓ | ✗ | ✗ | ✗ | ✗ |
| `popcount` | 2st/512* ✓ | 1st/256* ✓ | ✗ | ✗ | ✗ | 2st/512* ✓ | ✗ | ✗ | ✗ |
| `parity` | 1st/256* ✓ | 1st/256* ✓ | 2st/512* ✓ | 1st/256* ✓ | 1st/256* ✓ | 2st/512* ✓ | 2st/512* ✓ | 2st/512* ✓ | 2st/512* ✓ |
| `abs_signed` | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 2st/512* ✓ | ✗ | 1st/256* ✓ | ✗ | ✗ | ✗ |
| `sign_bit` | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/4 ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 2st/512* ✓ |
| `nibble_swap` | 2st/512* ✓ | 1st/256* ✓ | 2st/512* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | ✗ |
| `sat_inc` | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | ✗ | ✗ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `sat_dec` | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | ✗ | ✗ | 2st/512* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `is_pow2` | 1st/256* ✓ | 1st/256* ✓ | 2st/512* ✓ | 1st/256* ✓ | ✗ | 2st/512* ✓ | 3st/768* ✓ | 1st/256* ✓ | 2st/512* ✓ |
| `mod3` | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | ✗ | ✗ | ✗ | 1st/256* ✓ | 2st/262* ✓ |
| `div3` | 2st/512* ✓ | 2st/512* ✓ | ✗ | 2st/512* ✓ | ✗ | ✗ | ✗ | 1st/256* ✓ | ✗ |
| `square` | 2st/512* ✓ | ✗ | 1st/256* ✓ | 1st/2 ✓ | 3st/768* ✓ | 3st/768* ✓ | 2st/512* ✓ | 2st/512* ✓ | ✗ |
| `cube` | ✗ | ✗ | 3st/768* ✓ | 1st/5 ✓ | ✗ | 1st/256* ✓ | ✗ | ✗ | ✗ |
| `bitrev` | ✗ | 2st/512* ✓ | ✗ | 1st/256* ✓ | 1st/256* ✓ | ✗ | 2st/512* ✓ | ✗ | ✗ |
| `clz` | 2st/512* ✓ | ✗ | ✗ | 2st/512* ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `ctz` | 3st/768* ✓ | 2st/512* ✓ | 2st/512* ✓ | ✗ | ✗ | ✗ | 3st/768* ✓ | ✗ | ✗ |
| `lowbit` | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 2st/512* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `clear_lowbit` | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | ✗ | ✗ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `fill_right` | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | ✗ | ✗ | ✗ | 1st/256* ✓ | ✗ |
| `bcd_inc` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `sign_extend2` | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ | 2st/512* ✓ | 1st/256* ✓ | 1st/256* ✓ | 1st/256* ✓ |
| `lerp_half` | ✗ | 1st/256* ✓ | ✗ | 1st/6 ✓ | ✗ | ✗ | ✗ | 1st/256* ✓ | ✗ |
| `triangular` | ✗ | ✗ | 1st/256* ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `collatz_step` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **translated** | **22/30** | **22/30** | **20/30** | **25/30** | **11/30** | **12/30** | **17/30** | **19/30** | **13/30** |

