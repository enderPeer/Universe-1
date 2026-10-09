# exp11: Avida's length-8 replicator enumeration reproduced, and beyond (2026-10-09)

Machine: Avida's heads CPU with the default 26-instruction set and Avida's Analyze-Mode viability test, written from the Avida 2.14.0
source (every semantic decision and its source line: docs/14_exp11_avida.md). Reference `sim/avida.py`; engines `gpu/u1_avida.cu`
(CUDA / CPU emulation) and `gpu/u1_avida.comp` + `gpu/u1_avida_vk.c` (Vulkan); checker `fast/check_avida.py`; driver
`cluster/exp11_node.py`; analysis `fast/exp11_analyze.py`. Genome index g = sum op_i 26^i (letters a..z = instructions 0..25).

## Validation

1. The three engines agree with the reference on every per-genome field (viable, depth, first-divide cycle, intact, copy-true,
   fecundity, copy-true fecundity) for the 914 published genomes plus 65,536 random length-8 genomes (Vulkan, R9700), 4,096 random
   length-8 (CUDA, RTX 3060; CPU emulation) and 2,048 random length-7 genomes (all three).
2. **Avida 2.14.0 itself** (built on falke64 from the `2.14.0` tag, run in Analyze Mode with `LOAD_SEQUENCE` / `RECALC` / `DETAIL`
   on the default `avida.cfg`, `environment.cfg`, `instset-heads.cfg`; `results/exp11/avida214_analyze.cfg`, output
   `results/exp11/avida214_analyze_detail.dat`) agrees with `sim/avida.py` on viability for all 936 genomes tested (914 published,
   the 2 extra ones below, 20 random controls) and, for every viable one, on the gestation time of the first organism (Avida's
   `gest_time` = our first-divide cycle, 936 of 936).
3. The sweeps below reproduce the published facts: nothing at length 7, and every one of the 914 at length 8.

## Length 7: all 26^7 = 8,031,810,176 genomes

| viable | genomes that divide at all | time |
|---:|---:|---|
| **0** | 565 | 55 s on 2 x R9700 (145 M genomes/s) |

A length-7 genome can allocate and divide, but Avida's hard minimum genome length of 8 (docs/14, 4.1) forbids a child equal to the
parent; the 565 dividing genomes produce longer children, none of which replicates within the 3-generation test.

## Length 8: all 26^8 = 208,827,064,576 genomes (`results/exp11/len8.json`, `len8_viable.tsv`)

| | count |
|---|---:|
| viable (Avida's `is_viable`) | **916** |
| of which copy-true at depth 0 (the first child equals the genome) | 865 |
| of which viable only at depth 1 (the first child differs and is itself a true replicator) | 51 |
| parent intact after the first divide (memory[0..8) unchanged, cut exactly at 8) | 906 |
| genomes that divide at all within 160 cycles | 87,418 |
| fecundity within the 160-cycle lifetime: 1 / 2 | 909 / 7 |
| copy-true fecundity 0 / 1 / 2 | 51 / 858 / 7 |
| first divide: min / median / max cycle | 57 / 111 / 156 |
| distinct up to rotation | 900 |
| one-substitution clusters (largest) | 41 (213, 200, 165, 96), 20 singletons |
| instructions in every viable genome | h-copy, h-alloc, h-divide |
| time | 1,793 GPU-seconds on the four AMD cards (15 min wall), 66-100 M genomes/s per node |

**Against the published set (figshare 4551559, 914 genomes): all 914 are found, and 2 more are found that are not in the file:**
`vwsfgxgb` and `vwsxfggb`. Both are plain replicators: copy-true at depth 0, parent intact, first divide at cycles 97 and 110, and
Avida 2.14.0's own Analyze Mode reports them viable with gestation times 97 and 110 (validation point 2). They are the two
`add`-placements of the seven-instruction core `b f g g v w x` + one free slot: the published file has that core with `sub` and with
`nand` in all 40 placements each and with `add` in only 38; the two missing placements are exactly these (`add` right after
`h-copy h-alloc`, where `sub` and `nand` are published: `vwtfgxgb`, `vwufgxgb`, `vwtxfggb`, `vwuxfggb`). In the heads CPU `add`,
`sub` and `nand` are indistinguishable there (BX = CX = 0 and the result is never read), and nothing in the Avida source
distinguishes `add` from `sub` (both are `Inst_Add`/`Inst_Sub` with the same flags), so no semantic decision in docs/14 can separate
them; the gap is on the published file's side. **So the exact count of viable length-8 Avida genomes is 916, not 914**, and the
information content is 8 - log26(916) = 5.907 mers (the paper's 5.9 is unchanged at that precision); the 41-cluster structure is
unchanged except that the two largest clusters grow by one each (213, 200).

The 51 depth-1 genomes are counted as "self-replicators" by the paper's criterion but do not copy themselves: 41 of them produce a
length-8 child whose first instruction has become nop-A (e.g. `bxrchcvw` -> `axrchcvw`: the first instruction is a nop-B modifier
that the loop never copies), 10 produce a length-9 child; in every case the child is a true replicator. The 7 genomes with fecundity 2
(e.g. `vvxwfggb`, first divide at 61) divide twice within their 160-cycle lifetime; both children are true copies. The 10 genomes
whose parent is not intact (e.g. `wvfgvxgb` -> parent part `wvfgvxgba`, 9 long) are all among the depth-1 cases.

## Against the Universe-1 copiers (results/exp06b_summary.md)

| | Avida heads CPU, length 8 (exp11) | Universe-1 crawler, 4 bytes (exp06b) | crawler, 5 bytes (exp06c) |
|---|---:|---:|---:|
| space | 26^8 = 2.09e11 | 2^32 = 4.29e9 | 2^40 = 1.10e12 |
| self-copiers | 916 viable (865 copy themselves, 51 via a different replicating child) | 141 full copies | 21,818 full copies |
| density | 4.4e-9 | 3.3e-8 | 2.0e-8 |
| parent intact at the copy | 906 of 916 (99 %) | 0 of 141 | 3 of 21,818 |
| fecundity | 1 for 99 %, 2 for 7 genomes (160-cycle lifetime) | one by construction (the copy wears the code) | one |
| first copy | cycles 57..156, median 111 | steps 41..198, most 41..51 | step 33.., most 40..55 |
| mandatory core | h-alloc, h-copy, h-divide in all (3 of 8 slots), one free slot | all four primitives (every slot a pointer or loop word) | same |
| one-substitution clusters | 41, largest 213/200/165/96, 20 singletons | 27, two of 27, 15 singletons | not computed |

The two machines are built differently and the numbers say how: Avida's copy primitive plus separate heads give an intact parent for
free (99 % intact against 0 and 3), at a density ten times lower per genome (4.4e-9 against 2-3e-8) because a replicator must spend
three of eight slots on alloc/copy/divide and must close a loop with templates; the crawler copiers have no free slot and destroy
themselves. Both spaces show the same sharp length threshold (nothing at 7, hundreds at 8 / nothing with one operand bit, 141 with
two) and the same cluster structure (a few large Hamming-1 clusters plus singletons).

## Length 9: all 26^9 = 5,429,503,678,976 genomes (running)

Started 2026-10-09 10:37 (falke64, 2 x R9700, chunks 0..11699) and 10:46 (specht32, RX 9070 XT + 9060 XT, chunks 11700..20217) with
2^28 genomes per chunk and a 180-cycle budget; about 7 hours. Results will be appended here (viable count, depth split, intact
fraction, fecundity and first-divide distributions, clusters) with the comparison to length 8 and to the information-content
prediction (a constant 5.9 mers would predict 26^9 x 26^-5.907 = 23,800 viable genomes).
