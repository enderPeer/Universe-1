# Experiment 03: exhaustive 4-byte run (all 2^32 programs per ISA)

Hardware: the 4-node LAN cluster in `docs/cluster-inventory.md` (72 logical CPUs, 9 GPUs).
Pattern and Vulkan host borrowed from `enderPeer/Dimension42` (`explorer/nano_search3*`),
which swept 2^40 five-byte programs at 12 G programs/s on the same 9 GPUs.

## What one run computes
For a fixed ISA and geometry with `2^p * I = 32` program bits, every program id 0..2^32-1 is
decoded, run for every input (unary: x in A; binary: x in A, y in M[1]) for <= 256 steps, and
the vector of final A values is its truth table. Output: the set of distinct truth tables with
the smallest program id that realizes each. That set size is the ISA's operator count.

## Geometries with exactly 32 program bits
| W | I | p | instructions | opcode bits o | operand bits I-o |
|---|---|---|---|---|---|
| 1 | 1 | 5 | 32 | 1 | 0 |
| 2 | 2 | 4 | 16 | 1 or 2 | 1 or 0 |
| 4 | 4 | 3 | 8 | 2, 3 or 4 | 2, 1 or 0 |
| 8 | 8 | 2 | 4 | 1..8 | 7..0 |
The ISA list for the sweep is `cluster/isas_4byte.conf`; edit it to add more.

## Three engines, one shard format
| engine | file | devices | measured / expected speed |
|---|---|---|---|
| CPU, OpenMP | `fast/u1.c` | all 72 cores | 0.8 M programs/s per thread (cycle detection), ~75 s per 2^32 sweep on 72 threads |
| CUDA | `gpu/u1_cuda.cu` | RTX 4090, 4080, 3x 3060 | expected > 1 G programs/s per card |
| Vulkan | `gpu/u1.comp` + `gpu/u1_vk.c` | RX 9070 XT, 9060 XT, 2x R9700 | same kernel in GLSL |
All three write the same shard file (header + records of key lo, key hi, program id), merged by
`fast/merge.py`. The key is the exact packed table when it fits 128 bits (all unary W <= 4
cases, binary W = 2), otherwise a 2x64-bit hash (W = 8 unary, W >= 3 binary): with 2^32
programs the expected number of hash collisions is below 1e-9.

Validation done in this session (no GPU here): `fast/crosscheck.py` agrees with the Python
reference `sim/machine.py` on random programs for W = 1, 2, 4, 8 and binary mode;
`gpu/u1_cuda.cu` compiled through `gpu/cuda_shim.h` (single-threaded emulation) produces
byte-identical shards to `fast/u1` on five configurations. The Vulkan shader has not been
compiled yet: first thing on specht32/falke64 is `make -C gpu u1_vk` and a range comparison
(below) against `fast/u1`.

## Commands for Codex
```bash
# 1. on every node: clone to ~/universe-1, then
make -C fast                      # all nodes
make -C gpu u1_cuda               # adler40, knecht24 (nvcc)
sudo apt-get install -y glslc libvulkan-dev && make -C gpu u1_vk   # specht32, falke64

# 2. engine agreement on a range of 2^24 programs (every node, every GPU)
fast/u1      --W 4 --a 2 --p 3 --isa LD,ST,LDI,NAND,ADD,SHL,JZ,HALT --lo 0 --hi 16777216 --out /tmp/c.bin
gpu/u1_cuda  --gpu 0 --W 4 --a 2 --p 3 --isa LD,ST,LDI,NAND,ADD,SHL,JZ,HALT --lo 0 --hi 16777216 --out /tmp/g.bin   # or gpu/u1_vk
python3 fast/compare_shards.py /tmp/c.bin /tmp/g.bin     # must print IDENTICAL

# 3. full 2^32 sweep of every ISA in cluster/isas_4byte.conf on all 9 GPUs
python3 cluster/run_4byte_gpu.py              # unary operators
python3 cluster/run_4byte_gpu.py --binary     # binary operators (16x the work for W=4)
# CPU-only fallback: cluster/run_4byte.sh

# 4. commit results/exp03_*.json and results/exp03_summary.md
```

## Deliverables
1. `results/exp03_summary.md`: per ISA, distinct operators vs universe `(2^W)^(2^W)`, wall time, G programs/s.
2. The winning ISA per width and its operand-bit split (o vs I-o): this is the answer to
   "operand field vs opcode count" raised by the W=2 smoke result.
3. Engine agreement report (step 2) for each GPU, and the measured per-card speed.
4. If a hash table overflows (`ERROR hash table overflow`), rerun that chunk with `--cap-log2 27`
   or a smaller `--chunk-log2`; the dispatcher requeues failed chunks but retires the device.

## Known limits
- Kernels are compiled for a <= 4 (16 data words), tables <= 256 entries, <= 256 instructions.
- Hash table per GPU: 2^26 slots = 1.25 GB; raise `--cap-log2` on the 24 GB and 32 GB cards if a
  single chunk has more than ~45 M distinct tables.
- Vulkan path needs `shaderInt64` and `shaderBufferInt64Atomics` (RADV on RDNA 3/4 has both).
