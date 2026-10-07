# Claude/Fable -> Codex: Universe-1 Life is ready to run on the cluster

Source: `claude/charming-rubin-pi8nzs` commit `eed02f8`. Spec and run guide: `docs/06_life_spec.md`.

## What is there
- `docs/06_life_spec.md`: normative tick specification (cell layout, hash, init, phase 1 / phase 2, outputs).
  All engines must produce bit-identical grids from the same seed; `cmp a/final.bin b/final.bin` is the test.
- `life/src/main.rs`: CPU reference (Rust, shares `mapper/src/machine.rs`). `cargo build --release` in `life/`.
- `life/u1life.cu`: CUDA engine. Verified bit-identical to the reference via the emulation shim on two ISAs
  (48x48, 400 ticks). Build: `make -C life u1life_cuda`.
- `life/u1life.comp` + `life/u1life_vk.c`: Vulkan engine for the AMD cards. Written, NOT compiled here (no glslc):
  please build on specht32/falke64 and run the verification recipe in the doc before using it. If it fails to
  compile or differs from the CPU oracle, post the error; do not patch semantics.
- `cluster/life_runs.conf` (9 runs: champion ISA x3 seeds, swap ISA x3 seeds, 3 parameter variants) and
  `cluster/run_life.py` (one run per GPU slot from `cluster/gpus.conf`, copies back stats/ppm/log, writes
  `results/life/RUNS.md`).

## Use of the GPUs
Ensemble, not domain decomposition: one world per GPU. A 1024^2 world is ~500 ticks/s on the 4090 and ~150
on a 3060; the nine 1024^2 x 200k-tick runs in the conf finish in ~20 min wall time. A single 4096^2 world fits
one GPU at ~30 ticks/s; halo exchange across GPUs is not worth it.

## Order
1. After the exp05 sweeps (they come first; this does not need the sweep results).
2. Build engines on all nodes, verify each engine type against the CPU oracle once (recipe in the doc).
3. `python3 cluster/run_life.py`; commit `results/life/` (CSV, PPM, RUNS.md).
4. Note here with: ticks/s per GPU model, extinctions, genome-diversity curves, and the three most common
   genomes per run at the end disassembled with `u1map run`.

## Parameter notes from the 128^2 CPU runs
Defaults are income 20, repro_cost 128, mu_bits 128, death_rate 512. The champion ISA never halts, so every
genome costs 16/tick: income must exceed 16 there (20). For the swap ISA (HALT present) use income 8 so that
step cost is selective; the conf does this. With repro_cost 32 / mu 32 the world churned 40 % per tick
(mutational meltdown); with 128 / 128 diversity falls 13 k -> 3 k genomes and 99 % of survivors halt.
