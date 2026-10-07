# Experiment 03 validation and output locations

Run date: 2026-10-07 (Europe/Berlin). Base source: branch
`claude/charming-rubin-pi8nzs`, commit `7132c01`.

All 12 unary sweeps completed with full, contiguous 2^32-program coverage
each (51,539,607,552 programs total). The supported binary sweeps are a
separate follow-on run; consult the summary for completed result rows.
After the unary run, 2,240 sampled witnesses across all 768 shards matched
the Python reference. W=8's floating-point fraction underflows to zero;
its `fraction_log10` field preserves the nonzero magnitude.

## Validation before the exhaustive sweep

Built the CPU engine from source on all four nodes, CUDA on Adler/Knecht,
and Vulkan on Specht/Falke. No dependencies needed installation.
Every GPU's shard matched its node's CPU shard, including exact truth-table
keys and minimum program IDs, for programs `[0, 16777216)` using W=4, a=2,
p=3, I=4 and `LD,ST,LDI,NAND,ADD,SHL,JZ,HALT`. Each found 2,606 operators.

| Node | GPU | Result | Measured M programs/s |
|---|---|---|---:|
| adler40 | RTX 4090, CUDA 0 | IDENTICAL | 39.5 |
| adler40 | RTX 4080, CUDA 1 | IDENTICAL | 33.6 |
| knecht24 | RTX 3060, CUDA 0 | IDENTICAL | 13.6 |
| knecht24 | RTX 3060, CUDA 1 | IDENTICAL | 13.7 |
| knecht24 | RTX 3060, CUDA 2 | IDENTICAL | 14.0 |
| specht32 | RX 9060 XT, discrete Vulkan 0 | IDENTICAL | 10.2 |
| specht32 | RX 9070 XT, discrete Vulkan 1 | IDENTICAL | 17.8 |
| falke64 | R9700, discrete Vulkan 0 | IDENTICAL | 20.7 |
| falke64 | R9700, discrete Vulkan 1 | IDENTICAL | 18.4 |

These are measured on this validation range, not guaranteed full-run speeds.
The branch's expected >1 G programs/s per card was not observed.
All 12 candidate ISAs additionally passed 100 seeded random CPU-vs-Python
checks each (1,200/1,200); see `validation/all_isa_reference.log`.

Binary mode also passed 100 seeded CPU-vs-Python checks for each of the 11
supported ISAs (1,100/1,100). All nine GPUs matched CPU keys and witnesses
for the W=4 core ISA in binary mode over `[123456789, 123522325)` (65,536
programs, 1,219 distinct operators). The corrected Vulkan dispatch was
rechecked against the original 2^24-program CPU shard and remained IDENTICAL.

Before full dispatch, the Vulkan sub-batch was reduced from 2^25 to 2^23
programs, keeping dispatch below Vulkan's guaranteed X-workgroup limit.
The dispatcher now records per-chunk commands/timings, checks merge failures,
and saves wall time and throughput in result JSON. The report validates
contiguous coverage of the entire program space.

During W=8 unary, all four AMD cards hit compute-scheduler timeouts. The
drivers reset the affected queues; the dispatcher retired those devices for
that ISA and requeued their chunks onto the five NVIDIA cards. No reboot
was requested or performed. For subsequent runs, Vulkan dispatches with
more than 16 truth-table entries were reduced further to 2^18 programs,
and an explicit shader/host memory barrier was added between dispatches.
All four AMD cards then matched the CPU reference on a W=8 range spanning
two new dispatches: `[335544320, 335806465)`, 262,145 programs, 88 operators.
This verifies the correction on that range; the original full W=8 run
continues using its surviving NVIDIA workers.

## Exact data locations

- Source/build directory on every worker: `/home/ender/universe-1/`.
- Raw worker shards: `/home/ender/universe-1/results/shards/<ISA>_<chunk>.bin`.
  Each worker retains only the chunks it produced; these contain keys and
  minimum program witnesses.
- Coordinator on the Windows workstation: `C:\Users\end\Desktop\u1`.
- Collected shards and per-chunk logs:
  `C:\Users\end\Desktop\u1\results\shards\`.
- Merged results: `C:\Users\end\Desktop\u1\results\exp03_<ISA>.json`.
- Human-readable report: `results/exp03_summary.md`.
- Dispatch log: `results/exp03_run.log`.
- Engine validation logs: `results/validation/` (Adler logs are at its root).

Large binary shards are ignored by Git and preserved on disk. JSON counts,
validation logs, and the summary are suitable for committing. JSON contains
coverage and counts; minimum-program witnesses remain in binary shards.

## Run command

```powershell
python -u cluster/run_4byte_gpu.py --no-sync --chunk-log2 26 --resume
python -u cluster/run_4byte_gpu.py --no-sync --chunk-log2 26 --resume --binary
```

All nine GPUs are configured; W=8 unary completed chunks use the surviving
five NVIDIA workers after the AMD timeouts described above. GPU hash capacity
is 2^22 slots (80 MiB per device) for unary and 2^26 slots (1.25 GiB per
device) for binary, with 64 chunks per ISA. Jobs run at `nice -n 19 ionice -c3` on the
workers. Adler's pre-existing `homunculi` workload was left running.

The second invocation is the binary sweep. W=8 binary is unsupported by the current
GPU kernels (65,536 inputs versus a 256-entry compiled limit); the dispatcher
explicitly skips that configuration in binary mode.

The binary dispatcher uses one tar transfer per node to avoid repeated SCP
connections. Its log is `results/exp03_binary_run.log`. Coordination requires
the workstation to remain running and connected to the LAN. Peer SSH was
not configured on the head node, and no credentials were changed.
