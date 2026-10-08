# Universe-1 Life: tick specification (normative for life/, life/u1life.cu, life/u1life.comp)

All engines must produce bit-identical worlds from the same parameters and seed.

## Cell
```
genome : u32   the 32-bit Universe-1 program (8 instructions x 4 bits, champion ISA by default)
state  : u4    0..15
alive  : bit
age    : u11   ticks since birth (saturates at 2047)
energy : u16
```
Packed: `meta = state | alive << 4 | age << 5 | energy << 16` (u32). Empty cell: meta = 0, genome = 0.

## Parameters (defaults)
| name | default | meaning |
|---|---|---|
| N | 256 | torus side; cell index c = y*N + x |
| isa, a, p, I | SWAP,ADD,NAND,SKZ; 2; 3; 4 | the machine (W=4 fixed) |
| seed | 1 | u64 |
| density | 0.05 | initial fraction of live cells |
| start_energy | 64 | energy of initial cells and of newborn children |
| max_energy | 255 | energy is capped here (bounded state, so the GPU can use 8 bits) |
| income | 20 | energy added to every live cell each tick |
| trigger | 15 | new state that triggers reproduction |
| repro_cost | 128 | parent needs this much energy after paying its step cost, and pays it when its child cell is colonised |
| mu_bits | 128 | each genome bit flips with probability 1/mu_bits on copy |
| max_age | 1024 | death by age |
| death_rate | 512 | each live cell dies with probability 1/death_rate per tick (random turnover keeps the mutation supply) |
| ticks | 10000 | run length |
| max_steps | 256 | step budget of one organism run (exp10: 512 draws phenotypes from the 512-step library; cost = ceil(steps/16) then reaches 32). CUDA and CPU reference only; Vulkan still fixed at 256 |

## Hash (shared with the sweep engines' `mix`)
```
mix(x): x ^= x>>33; x *= 0xff51afd7ed558ccd; x ^= x>>33; x *= 0xc4ceb9fe1a85ec53; x ^= x>>33
h(seed, tick, cell, k) = mix(seed ^ mix(tick*0x9E3779B97F4A7C15 + cell) ^ (k * 0xD1B54A32D192ED03))   (u64)
```
## Initialisation (tick 0)
For every cell c: r = h(seed, 0, c, 0). Live iff (r >> 32) < density * 2^32. If live:
genome = low 32 bits of h(seed, 0, c, 1); state = h(seed,0,c,2) & 15; age = 0; energy = start_energy.

## Tick t (synchronous; two phases read only the previous grid and phase-1 results)
dir = t % 4 -> offset (dx,dy): 0:(0,-1) N, 1:(1,0) E, 2:(0,1) S, 3:(-1,0) W. nb(c) = cell at (x+dx, y+dy) mod N.

**Phase 1** (per live cell c): run genome(c) on the Universe-1 machine with A = state(c), M[1] = state(nb(c))
(empty neighbour counts as state 0) for <= 256 steps (HALT / cycle fast-forward exactly as in the sweeps).
Record new_state(c) = final A, cost(c) = ceil(steps / 16) in 1..16 (steps = 256 for non-halting).
energy_after(c) = min(max_energy, energy(c) + income) saturating-minus cost(c).
Dead cells: new_state = 0, cost = 0, energy_after = 0.

**Phase 2** (per cell c, writing the new grid):
parent p = cell at (x-dx, y-dy) mod N (the one whose nb is c).
p qualifies iff alive(p) && new_state(p) == trigger && energy_after(p) >= repro_cost.
c resists iff alive(c) && new_state(c) == trigger && energy_after(c) >= energy_after(p) (a reproducing cell is
overwritten only by a parent with strictly more energy; ties protect the occupant).
c is colonised iff p qualifies && !resists(c).
- if colonised: genome(c)' = mutate(genome(p)); state' = 0; age' = 0; energy' = start_energy; alive.
  mutate: for k in 0..32: if (h(seed, t, c, 16 + k) % mu_bits) == 0 flip bit k.
- else if alive(c): energy' = energy_after(c) minus repro_cost if c qualified and nb(c) did not resist (c can
  recompute nb(c)'s decision from nb(c)'s own phase-1 values); if energy' == 0 || age(c) + 1 > max_age ||
  h(seed, t, c, 8) % death_rate == 0 -> empty;
  else state' = new_state(c); age' = min(2047, age(c)+1); genome unchanged.
- else: stays empty.
Rationale: reaching the trigger state often is the only way to persist (non-reproducers are overwritten by
neighbours that reproduce); step cost converts into reproduction rate through the energy budget; energy is bounded.

## Outputs
Every `report_every` ticks: CSV line `tick, alive, distinct_genomes, mean_energy, mean_steps, halting_fraction,
births, deaths` (births/deaths accumulated since the previous report) and (optionally) a PPM image: hue from mix(genome) low 24 bits, dark = empty, brightness by state.
Final grid dump: `genome[]` then `meta[]` as little-endian u32 (for cross-engine comparison and restart).

## Engines and verification
| engine | file | status |
|---|---|---|
| CPU reference (Rust) | `life/src/main.rs` (shares `mapper/src/machine.rs`) | reference |
| CUDA | `life/u1life.cu` | bit-identical to the reference via `gpu/cuda_shim.h` emulation (48x48, 400 ticks, two ISAs); on the cluster: all five NVIDIA GPUs byte-identical to the CPU reference for both ISAs (Codex, 2026-10-07) |
| Vulkan | `life/u1life.comp` + `life/u1life_vk.c` | on the cluster: all four AMD GPUs byte-identical to the CPU reference for both ISAs (Codex, 2026-10-07; logs to follow in `results/life/validation/`) |
Verification recipe (any engine): same options, `--dump-final`, then `cmp a/final.bin b/final.bin`.

## Measured speed and what one run costs
CPU reference, 4 threads, 128 x 128 cells: 6000 ticks in 10 s (swap ISA, mostly halting genomes) to 23 s
(champion ISA, every genome runs 256 steps). That is 10-20 M cell-updates/s.
GPU estimate from the sweep kernels (40 M programs/s x 16 runs each on the RTX 4090 = 6e8 machine runs/s;
RTX 3060 about one third of that): one tick of a 1024 x 1024 world is 1 M runs, so about 500 ticks/s on the
4090, 150 on a 3060; 4096 x 4096 runs at about 30 ticks/s on the 4090. Reports every 1000 ticks cost one host
copy of 8 MB (1024^2) and a sort, negligible.

| world | ticks | one RTX 4090 | one RTX 3060 / RX 9060 XT |
|---|---:|---:|---:|
| 256 x 256 | 1,000,000 | ~2 min | ~6 min |
| 1024 x 1024 | 200,000 | ~7 min | ~20 min |
| 1024 x 1024 | 1,000,000 | ~35 min | ~2 h |
| 4096 x 4096 | 100,000 | ~1 h | ~3 h |

Combined use of the nine GPUs: an ensemble (`cluster/life_runs.conf`, `cluster/run_life.py`), one world per GPU
slot: nine 1024^2 x 200k-tick worlds finish in about 20 minutes wall time. A single world does not need more
than one GPU: 4096^2 already fits, and halo exchange between GPUs would cost more than it gains.

## How long a run should go
Dynamics seen so far at 128^2: filling takes ~300 ticks; selection (genome diversity 13 k -> 3 k, 99 % halting
genomes) is visible by tick 1000-3000; the age cap (1024) imposes turnover waves. Rule of thumb: run at least
100 x max_age ticks (100 k) so many generations pass; 1 M ticks for long-term questions (phenotype succession,
whether neighbour-dependent strategies appear). Run length is a parameter; the world has no end state.

## Expected capabilities (honest)
- Organisms are single 4-bit functions of (own state, neighbour state) with a cost. Expect: selection for
  trigger-reaching phenotypes, then for cheap (halting) ones; competition between genome families; spatial
  domains and fronts; parasitic phenotypes that reach the trigger only when the neighbour emits a specific
  state; drift along neutral networks (174 genomes per binary phenotype on average).
- Do not expect: self-replicating code, growing program complexity, or computation beyond a 4-bit function
  per organism. The phenotype space is large (24.68 M functions for the champion ISA) but finite; the
  interesting question is how much of it evolution explores and which phenotypes dominate, which the complete
  genotype-to-phenotype map lets us answer exactly.
- Open-endedness beyond this needs exp06b (self-copying programs, von Neumann layout) per docs/05_alife_plan.md.

## Running on the cluster (Codex)
```bash
# every node: git pull; cargo build --release in life/ (optional, CPU oracle); make -C life u1life_cuda | u1life_vk
# verify an engine against the CPU oracle once per node type:
life/target/release/u1life --N 64 --ticks 300 --seed 7 --out-dir /tmp/r --dump-final --report-every 300
life/u1life_cuda --gpu 0 --N 64 --ticks 300 --seed 7 --out-dir /tmp/g --dump-final --report-every 300    # or u1life_vk
cmp /tmp/r/final.bin /tmp/g/final.bin && echo IDENTICAL
# ensemble (9 runs in cluster/life_runs.conf):
python3 cluster/run_life.py
# results: results/life/<run>/stats.csv, final.ppm, run.log; summary results/life/RUNS.md
```
Deliverables: commit `results/life/` (CSV, PPMs, RUNS.md); post a note with ticks/s per GPU model, whether
any run went extinct, the genome-diversity curve, and the three most common genomes per run at the end
(disassemble with `mapper/target/release/u1map run --W 4 --a 2 --p 3 --isa <isa> --program 0x...`).
