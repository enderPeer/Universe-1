# Universe-1, Dimension42 (NANO) and Universe-7: what was done, what it found, what is open (2026-10-08)

Three projects on the same question, "what do all the programs of a tiny machine compute?", with three different machines
and three different methods. This note compares them from their repositories as of 2026-10-08 and lists the open experiments.

## 1. The three machines

| | Universe-1 | Dimension42 / NANO | Universe-7 |
|---|---|---|---|
| repository | enderPeer/Universe-1 (branch claude/charming-rubin-pi8nzs; shared/universe-1 for handoffs) | enderPeer/Dimension42 (last push 0204fcf, 2026-10-06) | enderPeer/universe7 (origin dc216e1, 2026-10-07) |
| word / cell | 4 bits (W is a parameter: 1, 2, 4, 8 swept; 5 for exp06c) | 8-bit bytes | 1-bit pixels |
| memory | 4 words (layout L3, address 0 is the accumulator) or 16 to 32 words shared with code (layout L2) | 16 cells, code and data shared (von Neumann), cells 8 to 15 double as an 8x8 display | an 8x8 screen (origin: 64x64) and a head position; no registers, no memory |
| instruction | 4 bits: 2 or 3 opcode bits + operand bits; ISA is a parameter (37 swept) | 1 byte: opcode nibble + operand nibble, fixed 16-instruction set | 2 bits, 4 fixed drawing moves (flip / set / clear and a stride) |
| program | 8 instructions = 32 bits (2^32), exp06c 40 bits | 1 to 6 bytes (2^8 to 2^48) | 1 to 22 bits swept; horizon 48 bits |
| inputs and output | x (and y) placed in registers; the function is the accumulator after T steps | a, b in cells; the output is the first OUT | none; the output is the final screen |
| budget | 256 steps (512 in exp10), fixed-point and HALT stop early | 64 instructions | 127 instructions, fixed |
| self-modification | not in L3; yes in L2 (exp06b/c) | yes, always | no |
| what is enumerated | distinct functions (truth tables) per ISA and per step, with a minimum-program witness | distinct behaviour classes and probe signatures per program | distinct final screens per program length |

## 2. What each project has done and found

### Universe-1 (this repository)
- **37 exhaustive step-256 sweeps** (exp03, exp05): unary and binary function counts per ISA, witnesses published (3.2 GB of
  archives), named-function recognition, loadable maps, usability matrix, corpus translation (44 of 55 corpus functions).
  Champion SWAP,ADD,NAND,SKZ: 1,829,051 unary, 24,684,247 binary functions. exp05: the carry flag is the lever, JC 8,533,818.
- **Every step of every program** (exp09, exp10): champion 142,263,973 functions over 256 steps and 267,132,154 over 512;
  JC 875,798,276 over 256. The time axis is a function axis; late functions are fleeting; the library keeps growing (about 400 M
  champion functions by extrapolation). Binary every step for the champion: richest step 220 (28,058,604); saturating add, unsigned
  min and less-than-mask exist at steps 125, 127 and 234 but not at 256.
- **Self-modifying layout** (exp06b/c): code as data multiplies the function count 43 to 184 times; 61 to 89 % of all programs
  rewrite themselves; self-copiers exist only in the crawler ISA LDIND,STIND,INCM,JNZ (141 at 4 bytes, 16 persisting, none with
  intact code; identical with 32 words of memory); the 5-byte crawler sweep (2^40) is running.
- **Life** (docs/05, 06): twelve 1024^2 worlds for 200,000 ticks on the mapped machines, no extinction, neighbour-dependent
  phenotypes dominate, the clock changes the phenotype pool (512-step world), videos with dashboards; a learned world model
  predicts the next tick at 97.6 % (81.5 % on an unseen seed) against a 49.6 % copy baseline.
- **Composition**: chains of champion or JC programs reach all 16^16 unary functions (generators present); exact 2-stage and
  3-stage membership tests are feasible per target, full depth-2 maps are not.
- Validation: every GPU result against a Python reference and a Rust reference; CUDA against Vulkan on identical ranges;
  per-chunk program accounting; every published witness re-executed.

### Dimension42 / NANO
- **Class maps**: 3-byte (16.8 M, identical on 13 devices), 4-byte (4.3 G, identical hash on 9 GPUs), 5-byte (1.1 T, 160 s,
  repeat run identical), **6-byte (2^48 = 281 T programs, 794 GB of class data, 54 GPU-hours)**. Classes at 6 bytes: DRAW 40.3 %,
  ACTIVE 16.5 %, OUTPUT 13.8 %, SELF-MOD 12.3 %, HALT 10.0 %, IDLE 7.1 %.
- **Search results**: 2+2=4 over all 1 to 5-byte programs in 45 s, 74,527 proven 5-byte adders (0.027 % of those answering 4),
  shortest adder `45 66 50 D0`; three-input adders 423 to 2,504 per layout; **no program up to 5 bytes multiplies**.
- **Behaviour catalog**: 219,846 probe signatures over 2^40 programs, 84,933 singletons, 98.7 % of them self-modifying; the
  memory-crawling XOR program `17 C5 91 50 71` (one of 136 in 1.1 T).
- **Alife toolkit** (482 s on 5 GPUs): 316 replicators (none with original intact), 52,261 mutating replicators, 12.8 G self-healers,
  114 G walkers; no program is both a replicator and a repairer.
- **Neural experiments**: an 800 k-parameter transformer writes valid adders for unseen input layouts at 87 to 91 % (transfer, not
  invention); programming-by-example stays weak (at most 3 of 5 prompts); Mandelbrot synthesis 0 exact solutions.
- **Infrastructure firsts**: hand-written OS and the cluster bridge convention later reused by Universe-1; the amdgpu watchdog
  bug found by cross-device agreement; the per-chunk checksum discipline.
- Caveats listed in its own docs: the 6-byte phenotype and rarity results are sampled (8.4 M and 20 M programs, half the chunks),
  the catalog is probe-level, several artefacts (pbe3, catalog run time, the L6 CPU re-check) are missing; much of the 6-byte,
  alife and NANO-256 work is uncommitted.

### Universe-7
- A deliberately minimal line: the **law itself was chosen by search** to maximise output variety (125,580 three-op and 3,876
  four-op tables scored on all short programs; winner F4 F8 S3 C3 at 127 steps).
- **All 8,388,606 programs of 1 to 22 bits** run: 99.17 % distinct screens on 8x8, 100.00 % on 64x64 (origin). A one-byte
  catalog with full traces (242 distinct screens of 256 programs, max cycle 256).
- Tooling: a 316 to 352-byte hand-written x86-64 runner, Python reference, C/OpenMP sweeps; no GPU, no cluster.
- Caveats: the variety figure sums distinct counts per length rather than a union across lengths; the 64x64 head never wraps in
  127 steps, so 100 % reflects the canvas; the step and table sweeps beyond round 3 come from uncommitted tools; the local checkout
  is one commit behind origin and holds an uncommitted one-byte catalog for the old 8x8 law; no plan or status files exist.

## 3. Side by side

| axis | Universe-1 | NANO | Universe-7 |
|---|---|---|---|
| largest exhaustive space | 2^32 per ISA (37 ISAs); 2^32 x 256 steps (2 ISAs); 2^40 (running) | 2^48 (class map only); 2^40 with probes | 2^22 |
| objects counted | functions, exact per step; witnesses re-executed | behaviour classes and 16-probe signatures (fingerprints) | final screens (hashes) |
| strongest finding | the clock is a function axis (78 to 146x); code as data (43 to 184x); self-copiers exist at 4 bytes | self-modification makes the rare behaviours; replicators at 5 bytes, none intact; a small transformer transfers adders to new layouts | a law can be chosen so that almost every short program is a distinct picture |
| validation | reference interpreters (Python, Rust), CUDA vs Vulkan, program accounting, witness re-execution | reference interpreters, 13-device agreement, repeat runs, checksums, Python re-checks | binary vs Python on short programs; Python vs Python for the catalog |
| artificial life | grid worlds running on the mapped functions, world model | replicator / walker / healer census, no world | none |
| learning | learned world model (97.6 %) | adder-writing and PBE transformers | none |
| publication | witness archives and reports on GitHub; shared handoff branch | GitHub, Hugging Face dataset, two Reddit posts (2026-10-06) | GitHub only |
| open data debt | binary every-step union (needs an external merge); exp05 binary maps | 6-byte class data on the cluster only (794 GB); uncommitted L6 work | one-byte catalog for the old law; origin not pulled |

The three projects share the cluster (adler40, knecht24, specht32, falke64), the hex-build convention and the cross-device
validation discipline; they do not share hash formats or shard formats, and no result file of one is readable by another's tools.

## 4. Open experiments, ranked

Across the three projects, the experiments that would change what we know, in order of value per GPU-hour:

1. **Replicator with intact code** (Universe-1 exp06c, running; NANO found none at 5 bytes). If the 5-byte crawler also fails,
   the next lever is a world rule where the copy window is the child, not larger programs. Then design C of the ALife plan
   (a Tierra-style soup) becomes possible for the first time in any of the three projects.
2. **exp05 binary sweeps and the Life ISA decision** (Universe-1; Codex): the top four ISAs, about 30 GPU-minutes, unblock the
   decision rule and the long Life runs.
3. **Binary every step for JC and the external-memory union** (Universe-1): the nine binary functions still missing at every
   champion step (multiply, max, gcd, lcm, divide, remainder, less-than, carry, absolute difference) are the translator's open list.
4. **Exact 2-stage and 3-stage composition membership for the catalog and corpus** (Universe-1): which functions are chains of
   two or three programs, with the clock as a per-stage parameter.
5. **NANO 6-byte phenotypes, exhaustively** (Dimension42): the 6-byte map holds classes only; an I/O catalog over 2^48 is about
   256 times the 5-byte catalog's cost, feasible on the cluster in days; it would say whether multiply ever appears.
6. **Commit and publish Dimension42's 6-byte, alife and NANO-256 work**, and the L6 CPU re-check; these results exist only on
   disk and are not part of the 2026-10-06 publication.
7. **Universe-7 union across lengths and the 64x64 catalog**: redo the variety count as a union over all lengths (the current
   figure double-counts equal programs), regenerate the one-byte catalog for the 64x64 law, commit the search tools for rounds
   4 to 6, and pull origin.
8. **Neural experiments on Universe-1 data** (transfer of the NANO adder result): a transformer that writes 32-bit programs for a
   given truth table at a given step, trained on the every-step witnesses; the function-at-step library is the largest exact
   supervised set any of the projects has produced (267 M champion, 876 M JC).
9. **Universe-7 toward 48 bits**: beyond 2^22 the screen hash needs the same chunked GPU enumeration as NANO; the law-search
   method could also be applied to Universe-1 (choose the ISA to maximise distinct functions, which exp05 did by hand).

Status of the running jobs at the time of writing: Universe-1 champion binary every-step map 12 of 13 passes merged
(208 of 256 maps on the workstation); 5-byte crawler sweep on seven GPUs, about two hours to go.
