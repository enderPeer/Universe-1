# Completed cluster translation run

The initial unary depth-4 run used 96b8687 with extra=256. The four new binary checks used the 87185a8 composition/naming update plus the name-refresh hook (deployed source 1a83882). Source revisions and modes are recorded per target.

131 map/function translations compiled and passed; 39/55 distinct corpus functions were translated. All seven unary maps completed depth 4 without fallback. All eight missing maps were built and their counts match the exhaustive sweep results.

## Per-node timings

Wall times below are sums of monitored commands on each node. They include load/verification/search/test work, but exclude source deployment, data transfers, and the pause for the upstream update. Nodes ran concurrently; these totals are not whole-job elapsed time. RSS is sampled every 250 ms.

| Node | Translation seconds | Peak translation RAM (GB) | Map-build seconds | Peak map-build RAM (GB) |
|---|---:|---:|---:|---:|
| adler40 | 151.4 | 3.93 | 0.0 | 0.00 |
| knecht24 | 160.2 | 3.87 | 0.0 | 0.00 |
| specht32 | 23.9 | 0.96 | 0.0 | 0.00 |
| falke64 | 1233.7 | 17.28 | 1677.6 | 17.92 |

## Comparison with the original report

The original report had 99 passing map/function translations. Existing maps gained these six successes with the wider/deeper unary search; no baseline success was lost:

- w4_o2_add/ctz
- w4_o3_arith/popcount
- w4_o3_arith/is_pow2
- w4_o3_arith/div3
- w4_o3_arith/square
- w4_o3_core/square

## Remaining targets

**Unary:** gray, ungray, bitrev, clz, triangular, collatz_step.

**Binary:** sat_add, mul_hi, max, abs_diff, avg_floor, shl_var, shr_var, hamming, gcd, mod.

These were not found in the configured search. Unary prefixes use restricted bases, and the new binary search uses the listed pre/post/two-binary-stage forms, not arbitrary composition of all functions.

## Artifacts and validation

- [Full matrix](REPORT.md) and [machine-readable rows](report_merged.json).
- [All emitted sources and logs](emitted_sources.zip): extract from the repository root with `python -m zipfile -e translate/emitted_sources.zip .`.
- [Selected examples](examples/manifest.json) and [12 passing example tests](examples/test-results.json). All ten Dimension42 corpus examples are represented.
- [Map extraction and checksums](../results/maps/README.md). The largest two maps are ordinary ZIP archives in Git, preserving the U1PROG01 format.
- [Raw node timings and logs](cluster-logs/) and [summary with archive checksum](run_summary.json). No emitted test failed and no interpreter or emitted-file repair was made.
- The RSS guard was separately tested with a disposable allocation at a lower threshold; it stopped only that test process group.

## Proposed next ISA

`SWAP,ADD,NAND,XOR,SHR,MUL,SKZ,HALT` with W=4, a=2, p=3, I=4 (3 opcode bits, 1 operand bit). This retains the winning four operations, adds high-to-low bit flow and XOR, and permits halting multiplication.

Reference-verified constructive witnesses in [next_isa_proposal.json](next_isa_proposal.json) implement Gray code in 5 steps, multiplication and square in 2, and a XOR b XOR 7 in 7. Three Gray-code stages implement ungray in 15 steps. Gray/ungray are still missing from the current search; multiplication and XOR-7 now translate in two non-halting-budget stages with a 512-step bound, so the proposal also targets latency.

This is a proposal, not an exhaustive new sweep. Its operand field shrinks from two bits to one compared with the champion. Evaluate coverage and halting cost together. The HALT/SWAP/ADD/NAND/ROL combination and its binary sweep already exist.

The exp05 branch-free SWAP/ADD/NAND/SHR candidate still wraps the PC under current semantics; it does not automatically halt after eight instructions. A one-pass comparison needs an explicitly different termination rule.
