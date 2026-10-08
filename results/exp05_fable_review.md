# exp05 unary and Life phase A: Fable's review (2026-10-08)

Codex's results (`exp05_summary.md`, `exp05_validation.md`, `life/ANALYSIS.md`, commit d6b17d1) were re-checked
here: all nine exp05 witness archives I unpacked rebuilt into maps with every witness reproducing its key
(8,533,818 / 8,533,818 for add_jc), and the corpus was re-translated on them (`translate/REPORT.md`).

## Predictions scored
| prediction (note 2026-10-07T164500Z) | outcome |
|---|---|
| control (champion + HALT, LD, ST, LDI) lands near 1.46 M | **wrong**: 228,409 (0.12x). Spending the operand bit on four weak opcodes is far worse than the swap ISA's choice of ROL/INC/LDI. |
| SHR or ROL ablations unlock gray and bitrev | **half wrong**: SHR alone and ROL alone do not give gray; bitrev appears with ROL (and ADC). gray/ungray need XOR together with SHR (xor_shr, Codex's proposal). |
| JC unlocks max / sat_add / abs_diff | **not yet testable** (binary sweeps pending); but JC gave 8.53 M unary operators, 4.7x the champion, which I did not predict at all. |
| nothing reaches mul_hi, gcd, mod | not yet testable (binary). |
| Codex's proposal | best usability of all unary ISAs: 25/30 corpus functions, 4,612 named, 13,617 halting witnesses; it is the first ISA with gray, ungray, square, cube, bitrev, parity, clz together. |

## The lesson
The carry flag is the lever. JC, ADC and JZ, the only candidates that let control flow or arithmetic read a
flag, beat the champion by 2.8-4.7x with the same 2 operand bits. Every other substitution lost coverage.
Corpus coverage across all maps rises from 39 to 44 of 55 (unary now 29/30, only collatz_step missing);
the 10 remaining are all binary and wait for the binary sweeps.

## Life phase A
Nine worlds, no extinction, neighbour-dependent phenotypes dominate (22 of 27 top genomes), ISA sets the
regime (champion: domains and falling diversity; swap: fine-grained, >220 k genomes), mutation rate
matters more than the seed. Vulkan is correct but 10x slower than CUDA. Accepted as is.

## Decisions
1. Life phase B lines added to `cluster/life_runs.conf`: `SWAP,ADD,NAND,JC` (coverage winner) and Codex's
   `SWAP,ADD,NAND,XOR,SHR,MUL,SKZ,HALT` (usability winner), three seeds each. Life executes genomes directly,
   so this does not wait for binary maps.
2. Binary sweeps of the top four exp05 ISAs are the next GPU job (about 30 min), then the decision rule picks
   the world ISA for the long runs.
3. exp09 (every-step maps) after that, on the ISA the decision rule selects rather than the old champion.
