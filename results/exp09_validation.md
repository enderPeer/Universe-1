# exp09 (every step of every program): kernel validation and run setup

Spec: `docs/08_exp09_every_step.md`. Kernel: `gpu/u1_multi.cu` (CUDA; one shard per checkpoint T in v1 format,
up to 64 checkpoints per pass in unary mode). Merge: `fast/merge_np.py` (numpy; same JSON as `fast/merge.py`).
Driver on the node: `cluster/exp09_node.py` (chunk queue over the node's GPUs, per-T merge after each pass, raw
shards deleted, union with minimal T at the end).

## Validation (2026-10-08, knecht24, RTX 3060, programs [0, 2^20), champion ISA SWAP,ADD,NAND,SKZ)

1. **T = 256 against the production sweep kernel.** `u1_multi --T-lo 193 --T-hi 256` and `u1_cuda` on the same range:
   the T=256 shard holds the same 1,660 records (keys and minimum program ids) as `u1_cuda`'s shard. IDENTICAL.
2. **All 256 steps against the CPU reference.** `u1map budgets --every 1 --lo 0 --hi 1048576` (Rust, `run_snapshots`:
   A after exactly T steps, HALT freezes A) gives the number of distinct functions at every T. The four passes of
   `u1_multi` (T = 1..64, 65..128, 129..192, 193..256) give the same 256 numbers, 0 mismatches
   (T=1: 5, T=8: 230, T=100: 1,649, T=256: 1,660). On this sample the union over all T is 83,919 functions, 50.6x
   the T=256 set, which is the effect the spec was written to measure.
3. **merge_np against merge.py.** On the exp03 shards of w4_o2_nand (16 operators) and the first 8 chunks of w4_o2_add
   (1,829,051 records) the numpy merge returns the same key set and the same minimum program for every key.

Throughput with 64 checkpoints per pass: 14.0-14.7 M programs/s per RTX 3060, the same as the single-checkpoint
sweep (the hashing of 64 tables per program is hidden behind the 256-step simulation). One pass over 2^32 programs
on the three 3060s: about 2.5 minutes of GPU time plus the per-T merges.

## Semantics

Checkpoint T = the accumulator after exactly T steps, for each of the 16 inputs; identical to the sweeps at T = 256.
HALT and the fixed-point exit (state unchanged and PC back at the same instruction) freeze A for all later T. No cycle
fast-forward is used (none is needed: the trajectory is simulated step by step).

## Outputs (on the node, `results/exp09/<name>/`)

- `T<nnn>.npy`: the distinct functions at step T (key_lo, key_hi, minimum program), sorted by key; `T<nnn>.json`: count and coverage.
- `union.npy`: every function occurring at any T with its minimal T, the program at that T and the number of distinct T at which it occurs.
- `summary.json` / `summary.md`: |F(T)| for T = 1..256, union size, minimal-T and occurrence histograms, pass timings.
