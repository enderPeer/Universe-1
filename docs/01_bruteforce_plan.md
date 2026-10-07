# Brute-force plan

Two nested searches. The outer search picks an ISA; the inner search runs
every program (or a sampled subset) for up to 256 steps and counts distinct
operators realized.

## Search A — ISA enumeration (per word width W = 1..8)

An ISA for width W with instruction width I = W has exactly 2^W opcodes.
An ISA *is* an assignment of a primitive semantic to each opcode:

    ISA = (prim[0], prim[1], ..., prim[2^W - 1]),   prim[k] in P

where P is the primitive catalogue (docs/00_machine_model.md §2, finite
list, |P| ≈ 40 with operands fixed by the layout). Search-space sizes:

| W | opcodes 2^W | ISAs = |P|^(2^W) with |P|=40 | feasible? |
|---|-------------|-----------------------------|-----------|
| 1 | 2 | 1,600 | yes, exhaustive |
| 2 | 4 | 2.56e6 | yes, exhaustive |
| 3 | 8 | 6.6e12 | no: prune to unordered sets -> C(40+8-1, 8) ≈ 3.1e8, still heavy; use canonical ordering + symmetry |
| 4 | 16 | 4.3e25 | sample / hill-climb / genetic |
| 5..8 | 32..256 | astronomically large | sample only; or greedy "add the primitive that unlocks most new operators" |

Pruning rules (all sound):
1. Opcode order does not matter -> enumerate multisets, not tuples.
2. Duplicate primitives never help -> enumerate sets.
3. Without at least one of {LD, ST} and one non-trivial ALU op the realizable
   operator set is the trivial one -> skip.
4. Boolean completeness check first: an ISA whose bitwise ops are not
   functionally complete (no NAND/NOR, and no {AND,NOT}/{OR,NOT}/{XOR,AND,1})
   cannot realize all unary functions; score it lower immediately.

## Search B — program enumeration (fixed ISA, 256-step runtime)

A program is the code image: 2^p instructions of I bits = 2^p·I bits.

| p | I | program bits | programs 2^(2^p·I) |
|---|---|--------------|---------------------|
| 2 | 1 | 4 | 16 |
| 3 | 2 | 16 | 65,536 |
| 4 | 3 | 48 | 2.8e14 (sample) |
| 4 | 4 | 64 | 1.8e19 (sample) |

Procedure for one (ISA, program):
1. For every input x in 0..2^W-1 (unary) or every pair (x, y) (binary):
   set the input slot, zero the rest, run ≤ 256 steps or until HALT.
2. Record the observation (final A). The vector of observations over all
   inputs is the *truth table* of the operator this program computes.
3. Insert the truth table into a set. |set| at the end = operators realized.

Score of an ISA = number of distinct truth tables realizable by any program
within the step budget. Maximize score, then minimize state bits.

## Early termination inside the 256 steps
- Detect a repeated full state -> infinite loop -> abort as "no result".
- Detect HALT -> stop.
- 256 steps with W=1..4 and small memory means the full state space
  (2^|S|) is often smaller than 256, so a cycle detector is both cheap and
  exact.

## Deliverables Codex should produce per experiment
- `results/expNN_W<w>.json`: per ISA, score and the list of truth tables found.
- `results/expNN_summary.md`: best ISA per W, its memory layout, state bits.
