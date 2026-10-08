# Experiment 05 (unary) validation, results and output locations

Run date: 2026-10-07, 17:09-17:22Z (UTC). Source: branch `claude/charming-rubin-pi8nzs`, commit `eed02f8`.
Command: `python -u cluster/run_4byte_gpu.py --no-sync --chunk-log2 26 --resume` with the 14 exp05 lines of
`cluster/isas_4byte.conf` (the exp03 lines were already complete). All nine GPUs completed chunks in every sweep;
no device was retired and no chunk was requeued (`exp05_run.log`). The binary sweeps (`--binary`) have not been run.

## Coverage, witnesses, archives

- Each of the 14 result files covers `[0, 2^32)` contiguously with no gaps or overlaps (checked again before publication).
- 2,680 sampled witnesses, up to three per shard, reproduced their truth-table keys on the Python reference
  (`python fast/check_witnesses.py --experiment exp05`, log `validation/exp05-witnesses.log`). `w4_o2_xor_shr`
  reports 184 instead of 192 because four of its shards (0032-0035) hold a single record each.
- Every shard is packaged in `results/witnesses/` (`cluster/package_witnesses.py`): 163 archives, 1.21 GiB,
  SHA-256 and shard lists in `manifest.json`, with `"experiment": "exp05"` on the new entries. Extraction as in
  `witnesses/README.md`.
- Named-function recognition ran on all 14 sweeps (`python fast/map_functions.py --experiment exp05`); every matched
  witness was replayed on all 16 inputs (`function-map/<run>.json`, summary in `function-map/README.md`).

## Results (distinct unary operators over 2^32 programs; exp03 champion SWAP,ADD,NAND,SKZ = 1,829,051)

| run | ISA | operand bits | operators | vs champion | catalog tables matched (of 352) | wall s |
|---|---|---:|---:|---:|---:|---:|
| w4_o2_add_jc | SWAP,ADD,NAND,JC | 2 | 8,533,818 | 4.67x | 337 | 56.2 |
| w4_o2_adc | SWAP,ADC,NAND,SKZ | 2 | 7,873,949 | 4.30x | 275 | 61.4 |
| w4_o2_add_jz | SWAP,ADD,NAND,JZ | 2 | 5,181,022 | 2.83x | 330 | 55.5 |
| w4_codex_shr_mul | SWAP,ADD,NAND,XOR,SHR,MUL,SKZ,HALT | 1 | 3,038,671 | 1.66x | 345 | 30.9 |
| w4_o2_rol | SWAP,ADD,NAND,ROL | 2 | 1,259,140 | 0.69x | 324 | 38.3 |
| w4_o2_sub | SWAP,SUB,NAND,SKZ | 2 | 1,123,714 | 0.61x | 315 | 58.1 |
| w4_o2_nocond | SWAP,ADD,NAND,SHR | 2 | 1,055,395 | 0.58x | 337 | 40.0 |
| w4_o2_add_sknz | SWAP,ADD,NAND,SKNZ | 2 | 1,043,408 | 0.57x | 316 | 62.4 |
| w4_o2_xor | SWAP,ADD,XOR,SKZ | 2 | 547,533 | 0.30x | 17 | 56.4 |
| w4_o2_xor_shr | SWAP,ADD,XOR,SHR | 2 | 500,264 | 0.27x | 60 | 39.6 |
| w4_o2_shr | SWAP,ADD,SHR,SKZ | 2 | 331,839 | 0.18x | 55 | 55.4 |
| w4_prop_combined | SWAP,ADD,NAND,SKZ,HALT,LD,ST,LDI | 1 | 228,409 | 0.12x | 313 | 31.5 |
| w4_i8_o4 | 16-primitive ISA, 4 instructions x 8 bits | 4 | 4,926 | 0.003x | 163 | 38.1 |
| w4_i8_o3 | SWAP,ADD,NAND,SKZ,HALT,LDI,SHR,ROL, 4 x 8 bits | 5 | 1,157 | 0.0006x | 109 | 28.1 |

## What the unary sweeps say

- **The carry flag is the lever.** The three variants that read the carry or jump on a flag (JC, ADC, JZ) are the
  only ones above the champion, by 2.8-4.7x. The champion's ADD sets C but nothing reads it; JC consumes it as
  control flow, ADC as data. A 2-bit jump target (JZ) beats a skip (SKZ) 2.8x; SKNZ is 0.57x.
- **Codex's proposal is the best for named functions**, matching 345 of 352 catalog tables and realising gray
  encode (`0x000e7831`, halts in 5 steps), square (`0x000000ea`, 2 steps), cube (5 steps), gray decode, bit
  reverse and parity (the last three at the 256-step ceiling), while still counting 1.66x the champion's operators
  with only one operand bit. The 2-operand-bit cousin `w4_o2_xor_shr` also realises gray/ungray/bitrev/parity but
  matches only 60 tables and counts 0.27x.
- **Predictions from the decision note, scored.** "SHR or ROL ablations unlock gray/bitrev": no; SHR alone and ROL
  alone realise neither. It takes XOR together with SHR (xor_shr, codex_shr_mul). "The control lands near 1.46 M":
  no; HALT plus LD/ST/LDI at one operand bit collapses the count to 228 k, although it still matches 313 tables.
  "JC unlocks max/sat_add/abs_diff" and "no candidate reaches mul_hi, gcd, mod" are binary questions and remain open.
- **Control flow is not what makes the count.** Without any conditional (SWAP,ADD,NAND,SHR; the PC wraps 32 times
  over the 8 instructions) the count is 1.06 M, 58 % of the champion, with the same 337 catalog matches as JC.
- **Four wide instructions are too few.** Both 4 x 8-bit geometries stay below 5,000 operators; operand width does
  not compensate for program length.
- **Replacing NAND by XOR hurts the vocabulary most** (17 catalog tables), replacing ADD by SUB or ADC keeps it.
- popcount appears for the first time in a W=4 unary sweep (ADC, `0x00410c61`); integer_sqrt is still absent everywhere.

The decision rule for the Life ISA (corpus functions translated at depth 3 including binary composition, then distinct
binary operators, then median step cost of named operators) cannot be applied yet: it needs the exp05 binary sweeps,
`u1map build` on the new maps, `mapper/usability.py` and `translate/translate.py`. Based on the unary data, the binary
sweeps worth running first are w4_o2_add_jc, w4_o2_adc, w4_o2_add_jz and w4_codex_shr_mul.

## Locations

Merged results `results/exp05_<run>.json`; summary `exp05_summary.md`; raw shards in `results/shards/` on the
coordinator and in `/home/ender/universe-1/results/shards/` on the producing nodes; verified archives in
`results/witnesses/`; dispatcher log `exp05_run.log`.
