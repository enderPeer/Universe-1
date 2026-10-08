# Universe-1
Math

Machine-level bits-and-bytes simulation. Goal: the maximum number of
mathematical operators on the smallest bitmap (word width 1..8 bits).

## Codex / Claude shared workspace

Use the [shared coordination branch](https://github.com/enderPeer/Universe-1/tree/shared/universe-1)
for handoffs, current status, decisions, and artifact locations. It synchronizes
with `/home/ender/universe-1-share` on `adler40`.
See [access and synchronization details](docs/04_shared_workspace.md).

- `docs/00_machine_model.md` — everything allocatable at machine level and the candidate memory layouts.
- `docs/01_bruteforce_plan.md` — ISA search (per width) and program search (256-step runtime), with search-space sizes and pruning.
- `sim/machine.py` — parametric W-bit machine with a primitive catalogue.
- `experiments/` — runnable experiments; see `experiments/README.md`. Codex runs these and commits `results/`.
- `fast/` — C/OpenMP brute-force core (`u1`), `crosscheck.py` vs the Python reference, `merge.py`, `compare_shards.py`.
- `gpu/` — CUDA (`u1_cuda.cu`) and Vulkan (`u1.comp` + `u1_vk.c`) ports, same shard format.
- `cluster/` — node/GPU/ISA configs and dispatchers for the 2^32-program sweeps (`docs/02_4byte_run.md`).
- `mapper/` — Rust function mapper `u1map`: builds operator maps from sweep witnesses, names operators, synthesizes programs and Rust code (`docs/03_function_map.md`).
- `results/maps/` — operator maps, named-operator listings and the cross-ISA usability matrix.
- `docs/05_alife_plan.md` — plan for an artificial-life universe on the mapped functions (grid world, tabulated genotype-to-phenotype map, self-replicator sweep).
- `life/` — Universe-1 Life: artificial-life world on the mapped functions, CPU reference + CUDA + Vulkan engines (`docs/06_life_spec.md`); ensemble dispatcher `cluster/run_life.py`.
- `results/catalog/` — sorted index of every champion-ISA function with structural descriptors; `docs/07_catalog_and_composition.md` also shows composition reaches all 16^16 functions.
- `docs/08_exp09_every_step.md` — exp09: map every step of every program; data volumes, GPU plan, index design.
- `docs/09_three_projects.md` � Universe-1, Dimension42/NANO and Universe-7 compared: machines, experiments, findings, validation, and the ranked list of open experiments.
- `translate/` — test-code corpus (Dimension42 TESTS + classic kernels) and the pipeline that translates it into Universe-1 programs and verified Rust (`docs/04_translate_run.md`).

## Cluster experiment results

- [Exhaustive sweep results](results/exp03_summary.md)
- [Validation, run details, and exact data locations](results/exp03_validation.md)
- [exp05: 14 candidate ISAs, unary sweeps](results/exp05_summary.md) and [their validation and what they say](results/exp05_validation.md)
- [Life ensemble: nine 1024^2 worlds for 200,000 ticks, analysis](results/life/ANALYSIS.md)
- [exp09: every step of every champion program, 142 M functions = 78x the step-256 map](results/exp09_summary.md) and [its validation](results/exp09_validation.md)
- [exp09 for the JC ISA and the comparison with the champion: 876 M vs 142 M functions over 256 steps](results/exp09_jc_vs_champion.md)
- [exp10: the clock extended to 512 steps, 267 M functions, what is new and how to use it](results/exp10_w4_o2_add_summary.md)
- [exp06b: the von Neumann layout, 20 M to 368 M functions per ISA, and the first self-copiers (141 in the crawler ISA, none with intact code)](results/exp06b_summary.md)
- [Learned world model: a conv net predicting the JC world one tick ahead (97.6 % next-state accuracy in-world, 81.5 % on an unseen seed)](results/life/worldmodel/REPORT.md)
- [Downloadable witness shards and Rust-compatible binary format](results/witnesses/README.md)
- [Named mathematical functions with verified witness programs](results/function-map/README.md)
- [Completed depth-4 cluster translation run, timings and next-ISA proposal](translate/CLUSTER_RUN.md)

Raw shards are produced in `/home/ender/universe-1/results/shards/` on the
cluster workers and collected in `results/shards/` on the coordinator.
Merged JSON files and the summary live in `results/`. Original binary shards
stay on disk; verified compressed copies are committed in `results/witnesses/`
for consumers without cluster access.

First smoke results (this session): W=1 with ISA {NOT, JZ} or {NAND, JZ}
reaches all 4 unary 1-bit operators. W=2 with 4 opcodes in a 2-bit
instruction leaves 0 operand bits, so LD/ST can only address A and only
4/256 unary operators are reachable: the operand field is the bottleneck,
not the opcode count.

## Compute resources for Fable

See [the verified SSH cluster inventory](docs/cluster-inventory.md) for all
GPUs, CPUs, RAM, access details, and a live availability snapshot.
