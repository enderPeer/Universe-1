# exp09: map every step of every program (the time axis of the champion ISA)

**Status 2026-10-08: done for the champion ISA (unary)**, see `results/exp09_summary.md` and `results/exp09_validation.md`: 142,263,973 functions over T = 1..256, 77.8x the step-256 map. Kernel `gpu/u1_multi.cu`, driver `cluster/exp09_node.py`.

## Why
A program is a trajectory; the maps so far record only its state at step 256. On a 2 M-program sample,
reading 32 checkpoints gave 16.5x more distinct functions than step 256 alone (`docs/07`, section 3).
exp09 reads all 256 steps of all 2^32 programs and builds the (program, T) library: every function with its
minimal clock T, its abundance (how many (program, T) pairs compute it), and its catalog descriptors.

## What is computed
For each program p (2^32), each budget T = 1..256, the truth table f(p, T): A after T steps, for every input
(16 unary, 256 binary pairs). HALT freezes A: f(p, T) is constant for T past the halting step. Semantics are
exactly those of `u1map budgets --every 1` (CPU reference, verified against the sweep at T = 256).

## Data volume (champion ISA `SWAP,ADD,NAND,SKZ`)
| quantity | size | note |
|---|---:|---|
| raw (p, T) truth tables, unary | 2^32 x 256 x 8 B = 8.8 TB | never stored; hashed on the GPU |
| distinct functions per T, unary | ~1.8 M each for T >= 64, fewer below | per-T maps: 256 x 1.8 M x 12 B = **5.5 GB** |
| union over all T, unary | estimate 30-150 M functions | key 8 B + program 4 B + minT 1 B + abundance 4 B = 17 B -> **0.5-2.5 GB** |
| distinct per T, binary | ~24.7 M each | per-T maps: 256 x 24.7 M x 24 B = **150 GB** (keep only every 8th T: 19 GB) |
| union over all T, binary | estimate 0.3-2 G functions | 16 B hash + 4 + 1 + 4 = 25 B -> **8-50 GB**; needs the 1.5 TB disk on falke64 or sampling |
The unary numbers are safe on any node; the binary union is the only item that may need pruning (store
every 8th T, or the union only).

## GPU plan (kernel variant of `gpu/u1_cuda.cu` / `gpu/u1.comp`)
Per program, run the 256 steps once and hash the table at every checkpoint into one hash table per
checkpoint. Memory per GPU: unary 2^22 slots x 20 B = 84 MB per table; 32 tables per pass = 2.7 GB (fits
every card). So **8 passes of 32 checkpoints** cover all 256 steps: ~8 x 1 min = **10 minutes** for unary on the
9 GPUs. Binary: 2^26 slots x 20 B = 1.3 GB per table; 8 tables per pass fit the 12 GB cards (16 on the
24-32 GB cards); every 8th T = 32 checkpoints = 4 passes x 7 min = **30 minutes**; every step = 32 passes =
~4 hours. Record format: shard v2 = header + {key_lo u64, key_hi u64, program u32, T u16} per record
(the T field is the only change; `fast/merge.py` / `u1map build` get a `--multi` mode).
Dedup within a program first: consecutive steps of halting programs repeat the same table; skip hashing a
table equal to the previous checkpoint's (cheap, halves the hashing work on HALT ISAs; no effect on the
champion).

## Index design (what makes it usable)
1. **Union map** `results/maps/<isa>.T.u1prog2`: sorted by key; per function: minT, program at minT,
   abundance, and the T-histogram summary (first T, last T, count of distinct T at which it occurs).
   Loading recomputes tables from (program, minT), as today.
2. **Per-T maps** `results/maps/<isa>.T<nnn>.u1prog` (unary all 256; binary every 8th): the time series of
   the library. Enables "functions available at clock <= T" and the growth curve |F(T)|.
3. **Named index** `results/maps/<isa>.T.named.jsonl`: every vocabulary name realized anywhere, with
   (program, minT, abundance) and the cheapest halting alternative if one exists. This replaces the single
   `steps` column: cost of a named function = its minT.
4. **Usability matrix with time**: `mapper/usability.py` cell = minT instead of max steps; a second matrix
   "functions available by T" (T = 8, 16, 32, 64, 128, 256) per ISA.
5. **Catalog over the union** (`u1map catalog --deep`): the existing descriptors plus minT, abundance and
   number of distinct T; sorted by class, name, minT. Abundance is the neutral-network size over
   (program, T) pairs: the robustness measure the Life world needs.
6. **Orbit index** (optional, sampled): for 1 M random programs, the sequence of function keys over T,
   run-length encoded. Answers "which programs pass through f and when" and measures how many distinct
   functions one program visits (sample said: most champion programs change function nearly every step).

## Deliverables
- Shards v2 under the artifact locations; union and per-T maps committed (unary) or archived (binary).
- `results/exp09_summary.md`: |F(T)| for T = 1..256 (unary) and every 8th (binary), union size, minT
  histogram, abundance distribution, and the growth-curve plot data.
- Catalog of the union and the refreshed named index / usability matrices.
- A note with wall times per pass and per GPU model.

## Division of work
- Codex: kernel variants, the sweeps, shard v2 output, per-pass validation against `u1map budgets` on a
  2^20-program range at three checkpoints (T = 8, 100, 256), archive publication.
- Fable: shard v2 reader, `u1map build --multi` (union with minT/abundance), `catalog` and `usability`
  extensions, the catalog of the union, and the write-up. The CPU reference for any (p, T) is
  `u1map budgets --lo p --hi p+1 --every 1`.
