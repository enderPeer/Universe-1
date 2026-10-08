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
