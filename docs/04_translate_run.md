# Experiment 04: translate the test corpus on the cluster (instructions for Codex)

Goal: translate real test code into Universe-1 programs with every operator map, on the
whole cluster, and publish the report. The pipeline is validated here on all W=4 maps with
a depth-3 search (`translate/REPORT.md`); the cluster run extends it to deeper searches and
to the maps of the remaining sweeps.

## What gets translated
`translate/corpus.py`: 30 unary and 25 binary 4-bit functions written as ordinary Python.
Ten come from Dimension42's `explorer/ai/pbe.py` TESTS (`a+b`, `a XOR b`, `2a+b`, `a+b+1`,
`3b`, `a+5`, `NOT b`, `a-1`, `rotate a left 3`, `a XOR b XOR 7`), scaled from 8 to 4 bits.
The rest are classic kernels (gray code, popcount, parity, abs, saturating arithmetic,
bit reverse, clz/ctz, BCD increment, Collatz step, carry out, mul/mul-high, min/max,
comparisons, variable shifts, Hamming distance, gcd, mod, ...). Each is one lambda; add more.

## How translation works
`u1map translate` loads a map, builds composition prefixes once (level 0 = all named
operators plus the `--extra` cheapest unnamed ones; each deeper level extends the previous
one by the elementary basis), then for each target finds a single witness program or a chain
of up to `--depth` programs whose composition equals the target table. For every translated
function it emits a Rust file with the program images, a verified lookup table, an embedded
reference machine and a `#[test]` proving emulation == table. `translate/translate.py`
drives the maps it is given, compiles and runs every emitted test with `rustc`, and writes
the per-map `translate/out/<map>.report.jsonl`. `translate/merge_reports.py` merges all
reports into `translate/REPORT.md` and `translate/report_merged.json`.

## Results so far (this container, depth 3, extra 64)
| map | translated |
|---|---|
| w4_o3_swap `SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT` | 22 / 30 unary |
| w4_o4_full (16 zero-address opcodes) | 20 / 30 unary |
| w4_o3_core `LD,ST,LDI,NAND,ADD,SHL,JZ,HALT` | 13 / 30 unary, 6 / 25 binary |
| w4_o3_arith | 10 / 30 unary, 4 / 25 binary |
| w4_o3_bool | 1 / 30 unary, 2 / 25 binary |
| w4_o2_add `SWAP,ADD,NAND,SKZ` | 19 / 30 unary |
All 99 emitted Rust files compile and pass their self-test. The exact grid and the list of
functions no map can translate are in `translate/REPORT.md`.

## Binary composition (added after the depth-4 run started)
For a binary map, `translate.py` now passes `--unary-map results/maps/<same ISA>.u1prog`
automatically when that file exists. `u1map translate` then also searches `u(b(x,y))`,
`b(u(x),y)`, `u2(b(u1(x),y))`, `b2(b1(x,y),y)` and `u(b2(b1(x,y),y))`, where b are binary
witnesses and u unary witnesses of the same ISA (y is re-supplied in M[1] to every binary
stage; emitted Rust carries `STAGE_BINARY`). Verified: `(x+y)*3+5` on the core ISA becomes
`x-(!y)` then `x*3+2`, and its emitted test passes. The three existing binary ISAs gained
nothing from it (their binary witnesses are too few); the four new W=4 binary maps should.
Also fixed: vocabulary names substituted the letter x inside identifiers (`max` became
`ma(x+y)`); regenerate `*.named.jsonl` / `*.stats.json` of any map built before this commit
with `u1map info --map <m> --named <m>.named.jsonl --stats <m>.stats.json`.

## Run it on the cluster (one node per group of maps; maps are independent)
```bash
# on every node, once
cd ~/universe-1 && git pull && (cd mapper && cargo build --release)
# unary maps, deeper search (depth 4, wider basis) on the 64 GB nodes:
# adler40:  python3 -u translate/translate.py --depth 4 --extra 256 --maps results/maps/w4_o3_swap.u1prog results/maps/w4_o4_full.u1prog
# knecht24: python3 -u translate/translate.py --depth 4 --extra 256 --maps results/maps/w4_o2_add.u1prog results/maps/w4_o3_core.u1prog
# specht32: python3 -u translate/translate.py --depth 4 --extra 256 --maps results/maps/w4_o3_arith.u1prog results/maps/w4_o2_nand.u1prog results/maps/w4_o3_bool.u1prog
# falke64:  python3 -u translate/translate.py --maps results/maps/w4_o3_core_bin.u1prog results/maps/w4_o3_arith_bin.u1prog results/maps/w4_o3_bool_bin.u1prog
```
Depth 4 multiplies the level-2 prefix set by the elementary basis; watch RSS (level 1 is a few
million 16-byte tables, 1 to 2 GB on the two largest maps; level 2 can be 100x that, so stop
at depth 3 for a map if RSS passes 40 GB). Binary maps support direct lookup only.

Then collect `translate/out/*.report.jsonl` from all nodes onto one node and run
`python3 translate/merge_reports.py`.

Timing reference here (4 threads): map load 2 s, prefix build for the core map 1 s
(1,393 level-0 and 43,937 level-1 prefixes), 30 unary targets in about 1 minute, each
`rustc --test` about 1 s.

## Also map the new sweeps
`snapshots/status.json` on `shared/universe-1` lists 23 completed sweeps; 15 are mapped in
`results/maps/`. For each unmapped one (the W=1/W=2 binary runs and any new ISA): extract its
witness archive, then
```bash
mapper/target/release/u1map build --shards results/shards/<run>_[0-9]*.bin \
  --out results/maps/<run>.u1prog --named results/maps/<run>.named.jsonl --stats results/maps/<run>.stats.json
python3 mapper/usability.py results/maps/*.named.jsonl --out results/maps/usability.md
```
and add W=1/W=2 corpora if wanted (`corpus.tables(w=2)`).

## Deliverables to commit (branch `claude/charming-rubin-pi8nzs`)
1. `translate/REPORT.md` and `translate/report_merged.json` from the depth-4 run.
2. `translate/examples/`: emitted Rust for the ten Dimension42 functions (already there from
   depth 3; replace with shorter chains if depth 4 finds them).
3. New maps under `results/maps/` and the refreshed usability matrix.
4. A handoff note on `shared/universe-1` under `agents/codex/` with: which functions remain
   untranslatable, the proposed next ISA sweep (e.g. HALT + SWAP + ADD + NAND + ROL together,
   and binary mode for the swap ISA), and per-node timings.
5. If any emitted `#[test]` fails: do not edit the emitted file; report function, map and
   program ids. That would be a machine-semantics mismatch in `mapper/src/synth.rs` worth
   stopping for.
