# exp09 binary, champion ISA SWAP,ADD,NAND,SKZ: every step 1..256 of every program, binary functions (x in A, y in M[1])

All 256 per-step maps (hashed 128-bit keys, minimum program per key) on the workstation under results/exp09/w4_o2_add_bin/ (about 124 GB).
Analysed 2026-10-08 20:26: per-step counts in the T<nnn>.json files; named functions over the clock in named_over_T.json.

| T | binary functions |
|---:|---:|
| 1 | 8 |
| 2 | 42 |
| 4 | 1,973 |
| 8 | 604,702 |
| 16 | 6,078,091 |
| 32 | 18,946,132 |
| 64 | 23,495,553 |
| 96 | 24,453,210 |
| 128 | 23,944,331 |
| 160 | 25,120,075 |
| 192 | 24,829,154 |
| 220 | 28,058,604 |
| 224 | 24,997,242 |
| 240 | 24,687,991 |
| 255 | 25,672,722 |
| 256 | 24,684,247 |

Richest step: T = 220 with 28,058,604 (step 256: 24,684,247). Catalog tables (740) realised at some step: 678; at step 256: 646; only before 256: 32.

## Named binary functions that exist only before step 256

| function | minimal T | steps present |
|---|---:|---:|
| equal_11_of_y (`1 if y=11 else 0 (ignore x)`) | 11 | 239 |
| equal_3_of_y (`1 if y=3 else 0 (ignore x)`) | 12 | 243 |
| is_power_of_two_of_y (`1 if y is a positive power of two else 0 (ignore x)`) | 19 | 88 |
| less_than_13_of_y (`1 if y<13 else 0 (unsigned) (ignore x)`) | 23 | 85 |
| equal_10_of_y (`1 if y=10 else 0 (ignore x)`) | 23 | 189 |
| less_than_13_of_x (`1 if x<13 else 0 (unsigned) (ignore y)`) | 26 | 103 |
| is_power_of_two_of_x (`1 if x is a positive power of two else 0 (ignore y)`) | 27 | 87 |
| shift_right_3_of_y (`y >> 3 (unsigned) (ignore x)`) | 43 | 63 |
| shift_right_3_of_x (`x >> 3 (unsigned) (ignore y)`) | 44 | 42 |
| cube_of_x (`x^3 mod N (ignore y)`) | 62 | 4 |
| less_than_7_of_y (`1 if y<7 else 0 (unsigned) (ignore x)`) | 66 | 5 |
| less_than_4_of_x (`1 if x<4 else 0 (unsigned) (ignore y)`) | 66 | 11 |
| rotate_left_1_of_y (`rotate W-bit y left by 1 (ignore x)`) | 70 | 10 |
| less_than_5_of_x (`1 if x<5 else 0 (unsigned) (ignore y)`) | 117 | 7 |
| rotate_right_1_of_x (`rotate W-bit x right by 1 (ignore y)`) | 118 | 2 |
| cube_of_y (`y^3 mod N (ignore x)`) | 118 | 2 |
| signed_abs_of_x (`abs(signed_W(x)) mod N (ignore y)`) | 119 | 18 |
| saturating_add (`min(x+y,N-1)`) | 125 | 13 |
| unsigned_min (`min(x,y)`) | 127 | 18 |
| trailing_zeros_mod_N_of_x (`trailing-zero count; x=0 maps to W mod N (ignore y)`) | 135 | 2 |
| signed_signum_of_x (`sign(signed_W(x)) encoded mod N (ignore y)`) | 145 | 10 |
| less_than_9_of_x (`1 if x<9 else 0 (unsigned) (ignore y)`) | 155 | 7 |
| less_than_7_of_x (`1 if x<7 else 0 (unsigned) (ignore y)`) | 163 | 7 |
| less_than_11_of_y (`1 if y<11 else 0 (unsigned) (ignore x)`) | 178 | 1 |
| rotate_left_1_of_x (`rotate W-bit x left by 1 (ignore y)`) | 223 | 5 |
| greater_equal_unsigned_mask (`greater_equal: unsigned inputs, true=15, false=0`) | 227 | 9 |
| greater_than_unsigned_mask (`greater_than: unsigned inputs, true=15, false=0`) | 227 | 14 |
| less_than_unsigned_mask (`less_than: unsigned inputs, true=15, false=0`) | 234 | 10 |
| less_than_9_of_y (`1 if y<9 else 0 (unsigned) (ignore x)`) | 246 | 1 |
| signed_abs_of_y (`abs(signed_W(y)) mod N (ignore x)`) | 251 | 1 |
| shift_right_1_of_y (`y >> 1 (unsigned) (ignore x)`) | 251 | 1 |
| signed_signum_of_y (`sign(signed_W(y)) encoded mod N (ignore x)`) | 255 | 1 |

## The translator's open binary functions

| function | status over the clock |
|---|---|
| multiply | absent at every step |
| unsigned_min | minimal T 127, present at 18 steps |
| unsigned_max | absent at every step |
| gcd | absent at every step |
| lcm_mod_N | absent at every step |
| unsigned_divide_zero_returns_zero | absent at every step |
| unsigned_remainder_zero_returns_zero | absent at every step |
| less_than_unsigned_bool | absent at every step |
| less_than_unsigned_mask | minimal T 234, present at 10 steps |
| carry | absent at every step |
| saturating_add | minimal T 125, present at 13 steps |
| absolute_difference | absent at every step |
