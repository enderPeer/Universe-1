# Universe-1 results: all function searches, unary and binary (state 2026-10-08)

Every number below comes from an exhaustive sweep of all 4,294,967,296 programs (32 bits, 8 instructions of 4 bits) unless stated
otherwise; "unary" = one 4-bit input x in the accumulator (16-entry truth table), "binary" = inputs x in the accumulator and y in
memory word 1 (256-entry table). A function is "the accumulator at step T"; the original maps read T = 256 only.

## 1. Step-256 maps, every swept ISA (exp03, exp05)

| ISA | W | unary functions | binary functions |
|---|---:|---:|---:|
| SWAP,ADD,NAND,JC | 4 | 8,533,818 | not swept |
| SWAP,ADC,NAND,SKZ | 4 | 7,873,949 | not swept |
| SWAP,ADD,NAND,JZ | 4 | 5,181,022 | not swept |
| SWAP,ADD,NAND,XOR,SHR,MUL,SKZ,HALT | 4 | 3,038,671 | not swept |
| SWAP,ADD,NAND,SKZ (champion) | 4 | 1,829,051 | 24,684,247 |
| SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT (swap) | 4 | 1,463,824 | 7,690,892 |
| SWAP,ADD,NAND,ROL | 4 | 1,259,140 | not swept |
| SWAP,SUB,NAND,SKZ | 4 | 1,123,714 | not swept |
| SWAP,ADD,NAND,SHR | 4 | 1,055,395 | not swept |
| SWAP,ADD,NAND,SKNZ | 4 | 1,043,408 | not swept |
| LD,ST,NOT,AND,OR,XOR,ADD,SUB,INC,DEC,SHL,SHR,ROL,SKZ,SKNZ,HALT | 4 | 977,928 | 977,928 |
| SWAP,ADD,XOR,SKZ | 4 | 547,533 | not swept |
| SWAP,ADD,XOR,SHR | 4 | 500,264 | not swept |
| SWAP,ADD,SHR,SKZ | 4 | 331,839 | not swept |
| SWAP,ADD,NAND,SKZ,HALT,LD,ST,LDI | 4 | 228,409 | not swept |
| LD,ST,LDI,NAND,ADD,SHL,JZ,HALT | 4 | 62,880 | 1,020,901 |
| LD,ST,ADD,SUB,SHL,SHR,JNZ,HALT | 4 | 24,420 | 339,877 |
| 16-primitive ISA, 4 x 8-bit instructions | 4 | 4,926 | not swept |
| SWAP,ADD,NAND,SKZ,HALT,LDI,SHR,ROL, 4 x 8-bit | 4 | 1,157 | not swept |
| LD,ST,NAND,JZ | 4 | 16 | 17,827 |
| LD,ST,NOT,AND,OR,XOR,SKZ,HALT | 4 | 16 | 11,946 |
| NAND,JZ | 2 | 12 | 2,131 |
| NAND,JZ / NAND,SKZ | 1 | 4 | 4 |
| SWAP,SKNZ | 2 | 2 | 8 |

Reports: `exp03_summary.md`, `exp03_validation.md`, `exp05_summary.md`, `exp05_validation.md`; named functions per map in
`function-map/README.md`; loadable maps and the usability matrix in `maps/`; corpus translation in `../translate/REPORT.md`.
The carry flag is the lever at step 256 (JC, ADC, JZ are the only candidates above the champion); the exp05 binary sweeps are open.

## 2. Every step, unary (exp09, exp10)

| | champion SWAP,ADD,NAND,SKZ | JC SWAP,ADD,NAND,JC |
|---|---:|---:|
| functions at step 256 | 1,829,051 | 8,533,818 |
| union over steps 1..256 | 142,263,973 (78x) | 875,798,276 (103x) |
| union over steps 1..512 | 267,132,154 (146x) | not swept |
| richest single step | T = 179 (2,081,755); T = 355 over 512 | T = 79 (9,140,092) |
| new functions per step near the end of the clock | 570 k at 256, 450 k at 512 | 3.3 M at 256 |
| functions at exactly one step | 43 % | 56 % |
| functions at 128 or more steps | 163,540 | 703,698 |
| catalog names realised at some step (of 352) | 339 | 348 (10 JC-only: shifts, floor log2, x < 10, leading zeros, popcount, Gray decode) |

Reports: `exp09_summary.md`, `exp10_w4_o2_add_summary.md`, `exp09_jc_vs_champion.md`, `exp09_validation.md`. The library keeps
growing with the clock (a linear extrapolation ends near step 1,100 at about 400 M champion functions); late functions are fleeting;
only five functions are stable across the whole clock. Per-step maps and unions on knecht24/adler40 and the workstation (`exp09/`).

## 3. Every step, binary, champion (exp09 binary; 198 of 256 steps analysed, the rest arriving)

| step T | binary functions |
|---:|---:|
| 1 | 8 |
| 8 | 604,702 |
| 16 | 6,078,091 |
| 32 | 18,946,132 |
| 64 | 23,495,553 |
| 128 | 23,944,331 |
| 220 (richest) | 28,058,604 |
| 256 (the old map) | 24,684,247 |

Named binary functions over the clock (catalog of 740 tables): 673 realised at some analysed step. Three of the functions that were
missing from every step-256 binary map exist earlier in the run: **saturating add at step 125** (10 steps), **unsigned min at step 127**
(9 steps), **less-than as a mask at step 234** (2 steps). Still absent at every analysed step: multiply, max, gcd, lcm, divide,
remainder, less-than as 0/1, carry, absolute difference. Table: `exp09/w4_o2_add_bin/named_over_T.json`; per-step maps on the workstation.

## 4. Self-modifying code (exp06b, exp06c; layout L2, 16 or 32 words, code in memory)

| ISA | words | programs | unary functions at 256 | code ever changed | full self-copy | persists | intact |
|---|---:|---:|---:|---:|---:|---:|---:|
| champion + LDIND,STIND,INCM,HALT | 16 | 2^32 | 336,500,469 | 66 % | 0 | 0 | 0 |
| JC + LDIND,STIND,INCM,HALT | 16 | 2^32 | 367,521,120 | 65 % | 0 | 0 | 0 |
| SWAP,LDIND,STIND,INCM,ADD,NAND,JZ,HALT | 16 | 2^32 | 326,400,260 | 61 % | 0 | 0 | 0 |
| LD,ST,LDIND,STIND,INCM,NAND,SKZ,JMP | 16 | 2^32 | 148,818,617 | 74 % | 0 | 0 | 0 |
| LD,ST,LDIND,STIND,INCM,ADD,JNZ,HALT | 16 | 2^32 | 129,910,772 | 64 % | 0 | 0 | 0 |
| LDI,LDIND,STIND,INCM,DECM,NAND,SKNZ,HALT | 16 | 2^32 | 20,286,084 | 70 % | 0 | 0 | 0 |
| LDIND,STIND,INCM,JNZ (crawler, 2-bit operands) | 16 | 2^32 | 200,738,959 | 89 % | 141 | 16 | 0 |
| crawler | 32 | 2^32 | copy-only | 89 % | 141 | 16 | 0 |
| crawler, 5-bit words (5-byte programs) | 32 | 2^40 | copy-only | 87 % | 21,818 | 7,482 | **3** (self-healing, code intact at the moment of copy) |

Report: `exp06b_summary.md`, figures `exp06b/*.png`. Code as data multiplies the function count by 43 to 184; the first Universe-1
self-copiers exist only in the crawler ISA and none keeps its original code intact (the NANO pattern).

## 5. Life (artificial-life worlds on these machines)

`life/ANALYSIS.md`: twelve 1024^2 worlds for 200,000 ticks (champion, swap, JC; 256-step and 512-step clocks; parameter scans), no
extinction, neighbour-dependent phenotypes dominate; videos in `life/*/`; learned world model in `life/worldmodel/REPORT.md`
(97.6 % next-state accuracy in-world, 81.5 % on an unseen seed).

## Data locations

Witness shards (step 256) as archives in `witnesses/` with `manifest.json`; per-step maps and unions on the nodes and the
workstation (`exp09/<name>/`, gitignored); raw shards on the nodes under `results/shards/`; cluster share and GitHub as in
`../docs/04_shared_workspace.md`.
