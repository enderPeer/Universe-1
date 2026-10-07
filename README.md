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
- `translate/` — test-code corpus (Dimension42 TESTS + classic kernels) and the pipeline that translates it into Universe-1 programs and verified Rust (`docs/04_translate_run.md`).

## Cluster experiment results

- [Exhaustive sweep results](results/exp03_summary.md)
- [Validation, run details, and exact data locations](results/exp03_validation.md)
- [Downloadable witness shards and Rust-compatible binary format](results/witnesses/README.md)
- [Named mathematical functions with verified witness programs](results/function-map/README.md)

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
