# exp06b: self-modifying code and self-copiers under the von Neumann layout (L2), all 2^32 programs per ISA

Layout L2: 16 words of 4 bits, the 8 instructions live at M[0..7], fetch reads memory, the copy window M[8..15] starts as code+1 at every word.
Engines `gpu/u1_l2.cu` (CUDA) and `gpu/u1_l2.comp` + `gpu/u1_l2_vk.c` (Vulkan, used here on falke64 and specht32); reference `sim/machine_l2.py`;
driver `cluster/exp06b_node.py`; figures `fast/l2_viz.py`. Statistics are from the x = 0 run of every program; the copier rule follows the
Dimension42 NANO sweeps (full 8-word copy at any step, at least two nonzero code words). Run 2026-10-08.

| ISA | o | unary functions at step 256 | Harvard (L3) map | code ever changed | code differs at end | walkers | best copy 7/8 | full copy ever | persists | original intact |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SWAP,ADD,NAND,SKZ,LDIND,STIND,INCM,HALT | 3 | 336,500,469 | 1,829,051 (champion) | 66 % | 64 % | 11 % | 1 | 0 | 0 | 0 |
| SWAP,ADD,NAND,JC,LDIND,STIND,INCM,HALT | 3 | 367,521,120 | 8,533,818 (JC) | 65 % | 64 % | 9 % | 1 | 0 | 0 | 0 |
| LDI,LDIND,STIND,INCM,DECM,NAND,SKNZ,HALT | 3 | 20,286,084 | - | 70 % | 67 % | 17 % | 8 | 0 | 0 | 0 |
| LD,ST,LDIND,STIND,INCM,ADD,JNZ,HALT | 3 | 129,910,772 | - | 64 % | 63 % | 9 % | 0 | 0 | 0 | 0 |
| LD,ST,LDIND,STIND,INCM,NAND,SKZ,JMP | 3 | 148,818,617 | - | 74 % | 73 % | 21 % | 3 | 0 | 0 | 0 |
| LDIND,STIND,INCM,JNZ | 2 | 200,738,959 | - | 89 % | 88 % | 53 % | 3,081 | 141 | 16 | 0 |
| SWAP,LDIND,STIND,INCM,ADD,NAND,JZ,HALT | 3 | 326,400,260 | - | 61 % | 59 % | 9 % | 1 | 0 | 0 | 0 |

## Findings

- **Self-modification multiplies expressiveness.** The same primitives under L2 give 20 M to 368 M unary functions at step 256; with pointers added, the champion
  goes from 1.83 M (Harvard) to 336.5 M and JC from 8.53 M to 367.5 M. 61 to 89 % of all programs change their own code; 9 to 53 % are walkers (operand-only edits).
- **The first Universe-1 self-copiers exist, and only in the pure crawler ISA** `LDIND,STIND,INCM,JNZ` (2-bit operands): 141 programs out of 2^32 write all 8 of their
  code words into the window; the first copies appear at steps 41..198 (most at 41-51); 16 copies survive to step 256; **none keeps its original code intact** at the moment
  of copying, exactly the pattern of the 316 five-byte NANO copiers: the copy loop uses code words as pointers and wears them away.
- Every ISA with one operand bit (o = 3) stops at 7 of 8 words (1 to 8 programs each): a single operand bit leaves too little addressing to run a copy loop within
  8 instructions; the 2-operand-bit crawler has pointers in M[0..3] and gets there.
- The crawler is also the most self-modifying universe (89 % ever change their code, 53 % walkers) and the second most expressive (200.7 M functions) with only four primitives.
- The 141 copiers were re-executed on the Python reference (best score 8 at the reported step, window equal to the initial code). The space-time diagram of the first
  one, `0x1e891417`, is in `results/exp06b/copier_0x1e891417.png`; per-ISA figures are `results/exp06b/<name>.png`.

## What this means for design C (a Tierra-style soup)

- A 32-bit genome can copy itself, but not without destroying itself: the 4-byte space has copiers and no replicators. Either a 5th byte (NANO found 316 copiers
  at 5 bytes, also none intact) or a world rule that reads the copy rather than the original (the child is the window, the parent is consumed) is needed.
- The persistent copies (16) are the candidates for a soup where the window becomes the child; the first-copy step (41 to 51) sets the minimal generation time.
- Next sweeps: the crawler ISA with 16-word code and 32-word memory (p = 4, a = 5), and 5-byte crawlers, to find an intact replicator; both are one GPU-minute each per ISA on the AMD cards.

## exp06c: the crawler with more room (2026-10-08, evening)

| configuration | programs | code ever changed | walkers | full copy ever | persists | original intact at the copy |
|---|---:|---:|---:|---:|---:|---:|
| crawler, 4-bit words, 16 words (exp06b) | 2^32 | 89 % | 53 % | 141 | 16 | 0 |
| crawler, 4-bit words, 32 words | 2^32 | 89 % | 53 % | 141 | 16 | 0 |
| crawler, 5-bit words, 32 words (8 x 5-bit instructions = 5 bytes) | 2^40 = 1,099,511,627,776 | 87 % | 58 % | 21,818 | 7,482 | **3** |

Copy test: all 8 code words written by the program into any non-overlapping window (offsets 8..24), checked after every write; the
intact flag means the code region equals the original program at the moment the copy completes. 32 words of memory alone change
nothing at 4 bits (same 141 copiers, all at offset 8). The 5-bit word (three operand bits, pointers over all eight code words) is
what opens the space: copies appear at every offset from 8 to 24 (most at 9, 8 and 10), the first copies at step 33, most between
40 and 55, a second wave around step 190.

**The first Universe-1 replicators.** Three programs of the 1.1 trillion copy themselves completely while their own code is intact,
all three confirmed on the Python reference, space-time diagrams in `exp06b/replicator_<program>.png`:

| program | disassembly | first full copy | offset | copy persists to 256 | code intact to 256 |
|---|---|---:|---:|---|---|
| 0xa2c841f269 | STIND 1; INCM 3; JNZ 4; LDIND 3; LDIND 4; LDIND 4; STIND 3; INCM 4 | step 220 | 16 | no | no |
| 0xa9344f2e8d | STIND 5; INCM 4; STIND 3; JNZ 6; LDIND 4; JNZ 2; LDIND 4; INCM 5 | step 197 | 22 | yes | no |
| 0xd9b17359e8 | STIND 0; STIND 7; INCM 6; LDIND 6; INCM 7; JNZ 0; LDIND 6; JNZ 3 | step 196 | 21 | yes | no |

They are self-healers in the NANO sense: the copy loop increments pointer words that are also instructions, and the pointers wrap
back to their original values exactly when the eighth word lands. The code is not intact at step 256 (the loop continues and
disturbs it again), so in a world rule that reads the parent at the moment of division these three reproduce with a faithful
parent and child; in a rule that reads it at a fixed budget they do not. That is the same situation Avida resolves with h-divide
(docs/10_avida_comparison.md). The 500 listed copiers all re-executed identically on the Python reference.

Cost: 2^40 programs at one run each, copy-only, in 6,045 s per share on falke64 (2 x R9700) and specht32, and about the same on
knecht24 (3 x RTX 3060), about 35 M programs/s per card. Data: `exp06b/l2c_crawl_w5_a5.json` (combined from three node shares).
