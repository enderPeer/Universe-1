# Universe-1
Math

Machine-level bits-and-bytes simulation. Goal: the maximum number of
mathematical operators on the smallest bitmap (word width 1..8 bits).

- `docs/00_machine_model.md` — everything allocatable at machine level and the candidate memory layouts.
- `docs/01_bruteforce_plan.md` — ISA search (per width) and program search (256-step runtime), with search-space sizes and pruning.
- `sim/machine.py` — parametric W-bit machine with a primitive catalogue.
- `experiments/` — runnable experiments; see `experiments/README.md`. Codex runs these and commits `results/`.

First smoke results (this session): W=1 with ISA {NOT, JZ} or {NAND, JZ}
reaches all 4 unary 1-bit operators. W=2 with 4 opcodes in a 2-bit
instruction leaves 0 operand bits, so LD/ST can only address A and only
4/256 unary operators are reachable: the operand field is the bottleneck,
not the opcode count.
