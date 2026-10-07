# Universe-1 Life: building an artificial-life universe on the mapped functions

Status 2026-10-07: 23 exhaustive sweeps, 15 maps in the repo plus the 24.68 M-function
binary map of the champion ISA (`SWAP,ADD,NAND,SKZ`, W=4, 8 instructions x 4 bits = 32-bit
program). Every 32-bit program's behaviour is known, and a verified emulator exists in C,
CUDA, Vulkan, Rust and Python. This document answers: can we build an artificial-life (ALife)
universe on this now, what would it look like, and in what order.

## 1. What the maps give an ALife universe that no other ALife system has

A 32-bit program is a **genome**. Its truth table (what it does to a 4-bit state given a
4-bit neighbour value) is its **phenotype**. For the champion ISA we know, exhaustively:

| | unary (state only) | binary (state, neighbour) |
|---|---:|---:|
| genomes | 4,294,967,296 | 4,294,967,296 |
| distinct phenotypes | 1,829,051 | 24,684,247 |
| genomes per phenotype (mean) | 2,348 | 174 |
| phenotype universe | 16^16 = 1.8e19 | 16^256 |

So the **genotype-to-phenotype map is complete and tabulated**. In most ALife systems
(Tierra, Avida, Lenia, AlChemy) that map is implicit and can only be sampled. Here we can
compute mutational robustness, neutral-network structure and evolvability exactly, before
and during a run. The other quantities the maps already carry per phenotype: the cheapest
witness program, its step cost (1..256), and whether it halts. Step cost is a natural
**metabolic cost**.

What is *not* in hand: self-replicating code. The machine is Harvard (code is not in the
addressable memory) and a genome has 8 instructions and 3 data words. Replication therefore
has to be a rule of the world (section 3), not an act of the program, until section 5.

## 2. Three ways to build it, and the recommendation

| design | organisms | replication | what the maps contribute | ready? |
|---|---|---|---|---|
| A. **Grid world** (CA-like, Lenia/Avida hybrid) | cells with 4-bit state + 32-bit genome | world rule: a cell that reaches a trigger state copies its genome to a neighbour with mutation | phenotype = update rule; cost = metabolism; full G-P map for analysis | **yes, now** |
| B. **Chemistry** (AlChemy-like) | programs as molecules acting on other programs' nibbles | reactions f(g) -> h; autocatalytic sets | unary map = reaction table; closure under composition already measured (1.46 M -> 2.54 M at depth 2) | yes, analysis-first |
| C. **Soup** (Tierra/Avida) | programs in one shared memory, copying themselves | by the program itself | requires von Neumann layout L2 and a replicator search | after exp06 |

Recommendation: build **A** as the universe, run **B** as an analysis layer on the same maps,
and run the **C** feasibility sweep (exp06) on the cluster in parallel because it costs one
minute per ISA.

## 3. Design A in detail: Universe-1 Life

**World.** A torus of N x N cells (start 256 x 256, scale to 4096 x 4096 on one GPU).
```
cell = { state: u4, genome: u32, energy: u8, age: u16 }
```
**Tick** (synchronous, all cells):
1. Pick the neighbour `nb` for this tick (rotate N, E, S, W each tick, so the binary
   function sees one 4-bit neighbour value exactly as in the sweeps: x = own state in A,
   y = neighbour state in M[1]).
2. `state' = phenotype(genome)(state, nb.state)`; this is one run of the genome on the
   Universe-1 machine (<= 256 steps) or one lookup in the tabulated map (section 4).
3. `energy -= cost(genome)` where cost is the step count of that run (halting genomes are
   cheap; non-halting pay 256). Energy income: a fixed amount per tick, or state-dependent
   (e.g. cells in state 0 "photosynthesize"), which gives phenotypes a reason to exist.
4. **Reproduction rule.** If `state' == TRIGGER` (default 15) and `energy >= COST_REPRO`,
   write the genome into `nb`, each bit flipped with probability `mu` (default 1/32, one
   mutation per copy on average), set `nb.state = 0`, `nb.energy = energy/2`, halve own.
5. **Death.** `energy == 0` or `age > MAX_AGE` -> cell becomes empty (genome 0, which under
   `SWAP 0` x8 is the identity: an inert "rock").

Everything a cell does is therefore determined by its phenotype, and the phenotype is one
of the 24,684,247 functions we have mapped. No fitness function is defined: a genome
persists only if its phenotype makes its cell reach the trigger state often enough, from the
states its neighbours produce, while keeping cost below income. That is the open-ended
setting ALife wants.

**Why this can show real evolution.** Reaching state 15 from arbitrary (state, neighbour)
pairs is a non-trivial property of a phenotype; so is doing it cheaply (halting). The maps
let us list in advance which phenotypes are "always-15" (trivial replicators, like the
constant functions), which depend on the neighbour (cooperation/parasitism become
possible: a genome that reaches 15 only when its neighbour is in state k exploits
neighbours that produce k), and how many genomes encode each (the neutral network size).
Predictions to test: (i) constant-15 genomes win first; (ii) cost pressure then selects
halting variants; (iii) spatial structure lets neighbour-dependent phenotypes invade.

**Measurements** (all from the maps, per tick): phenotype count and Shannon diversity,
abundance-weighted mean step cost, fraction of neighbour-dependent phenotypes, genome
robustness (fraction of the 32 single-bit mutants with the same phenotype; exact from the
G-P table), and the phenotype succession graph.

## 4. Making it fast: the tabulated genotype-to-phenotype map on one GPU

The sweeps stored one witness per phenotype. For the world we want the inverse direction:
`phenotype_id[genome]` for all 2^32 genomes, plus `table[phenotype_id]` (256 bytes).
- `phenotype_id` array: 4,294,967,296 x u32 = 17.2 GB.
- `table` array: 24,684,247 x 256 B = 6.3 GB; `cost`/`halts`: 24.7 M x 2 B.
- Both fit the RTX 4090 (24 GB) or one R9700 (32 GB); the 24.7 M-entry key -> id hash table
  used to build it fits alongside.
Then a tick is two dependent loads per cell: ~1e9 cells/s per GPU, so a 4096 x 4096 world
runs at ~60 ticks/s; the 256 x 256 development world runs millions of ticks per hour.
Without the table, running the genome directly costs <= 256 steps per cell: still ~4e6
cells/s on one GPU, enough for 256 x 256 at 60 ticks/s. Phase 1 can start without the table.

**exp06a (cluster, ~2 min per ISA):** a kernel variant of `gpu/u1_cuda.cu` that, for each
program, computes the table key, looks it up in the (loaded) key -> id table and writes
`phenotype_id[program]`. Output 17.2 GB per ISA on adler40's disk; also emit the
`mutational robustness` histogram directly (32 neighbours per genome, 1.4e11 lookups, a few
minutes).

## 5. exp06b: can a Universe-1 genome copy itself? (feasibility for design C)

Layout L2 (von Neumann): a = 4 (16 words of 4 bits), the 8 instructions live at M[0..7],
M[8..15] free; fetch reads M[PC]. Replication criterion after 256 steps: M[8..15] ==
initial M[0..7] (or any 8-word window equals the initial code). Sweep all 2^32 programs for
each candidate ISA that has indirect addressing: e.g. `LDIND,STIND,INCM,JNZ,HALT,...` with
o=3 (operand bit selects pointer M[1] or A). Cost: one 2^32 sweep per ISA, one minute on the
9 GPUs, plus an L2 fetch path in the C/CUDA engines (small change: fetch = M[PC&15]).
Outcome either way is a result: the smallest self-copier, or a proof that none exists at 8
instructions, which sets the genome size for a Tierra-style soup.

## 6. Design B as an analysis layer: reaction networks over the unary map

Treat each unary phenotype as a molecule and composition as the reaction f o g. The depth-2
closure is already measured (1,463,824 -> 2,543,086 for the swap ISA). Next: for the
champion ISA compute the composition graph restricted to the named operators (2,703 nodes)
and search for autocatalytic sets (sets closed under composition that contain their own
generators). This is a CPU job on the maps and needs no new sweeps.

## 7. Plan and order of work

| phase | what | where | effort | output |
|---|---|---|---|---|
| 1 | `life/` Rust crate: world struct, tick, reproduction, death, direct genome execution (reuses `mapper/src/machine.rs`), PNG/CSV output; 256 x 256 runs on CPU | Claude, this branch | 1 day | first evolutionary runs; phenotype succession curves |
| 2 | exp06a: `phenotype_id` table + robustness histogram for the champion ISA | Codex, adler40 (4090) | kernel variant + 1 run | 17 GB table, robustness stats |
| 3 | GPU world (CUDA/Vulkan compute shader, same pattern as `gpu/u1.comp`) using the table; 4096 x 4096 | Codex | 1-2 days | 60 ticks/s worlds, long runs |
| 4 | exp06b: L2 fetch path + self-replicator sweeps for 4-6 ISAs | both | engine change + 6 sweeps | smallest self-copier or non-existence |
| 5 | analysis: diversity, robustness, parasitism detection; design B autocatalytic sets | Claude | ongoing | report |

Phase 1 needs nothing from the cluster and starts now. Phases 2 and 3 are the cluster's
work after the exp05 sweeps. Phase 4 is the only one that changes machine semantics (adding
layout L2 as an option; L3 results are untouched).

## 8. Decisions to take (defaults in bold)
- Trigger state for reproduction: **15**, or "state unchanged for k ticks".
- Neighbour sampling: **one rotating neighbour** (exact binary-function semantics) vs an
  aggregate (XOR / majority of four; would need a 3rd stage).
- Energy income: **constant per tick**, or state-dependent.
- Mutation: **bit flips at 1/32 per bit** vs instruction-level (nibble) mutation.
- Initial population: **random genomes at 1% density**, or seeded with the 2,703 named
  phenotypes' witnesses to watch which math operators survive.
